import httpx
from datetime import datetime
import logging
from typing import List, Dict, Any

from App.model.schemas import FlightOffer, FlightSearchParams, Itinerary, PriceDetail, FlightSegment
from App.core.config import settings

class AmadeusService:
    def __init__(self):
        self.api_key = settings.amadeus_api_key
        self.api_secret = settings.amadeus_api_secret
        self.api_url = settings.amadeus_api_url
        self.token = None
        self.token_expiry = None
        self.logger = logging.getLogger("amadeus_service")

    async def get_token(self) -> str:
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.api_key,
                    "client_secret": self.api_secret
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if response.status_code != 200:
                error_msg = f"Failed to get token: {response.text}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            token_data = response.json()
            self.token = token_data["access_token"]
            expiry_seconds = int(token_data.get("expires_in", 1800))
            self.token_expiry = datetime.now().fromtimestamp(
                datetime.now().timestamp() + expiry_seconds
            )
            return self.token

    async def search_flights(self, params: FlightSearchParams) -> List[FlightOffer]:
        token = await self.get_token()
        search_params = {
            "originLocationCode": params.origin,
            "destinationLocationCode": params.destination,
            "departureDate": params.departure_date.isoformat(),
            "adults": params.adults,
            "max": params.max_results
        }
        if params.return_date:
            search_params["returnDate"] = params.return_date.isoformat()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/v2/shopping/flight-offers",
                params=search_params,
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code != 200:
                error_msg = f"Failed to search flights: {response.text}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            flight_data = response.json()
            return self._parse_flight_offers(flight_data)

    def _parse_flight_offers(self, flight_data: Dict[str, Any]) -> List[FlightOffer]:
        flight_offers = []
        for offer in flight_data.get("data", []):
            itineraries = []
            for itinerary_data in offer.get("itineraries", []):
                segments = []
                duration = itinerary_data.get("duration", "")
                for segment in itinerary_data.get("segments", []):
                    segments.append(FlightSegment(
                        departure_airport=segment["departure"]["iataCode"],
                        departure_terminal=segment["departure"].get("terminal"),
                        departure_time=datetime.fromisoformat(segment["departure"]["at"].replace('Z', '+00:00')),
                        arrival_airport=segment["arrival"]["iataCode"],
                        arrival_terminal=segment["arrival"].get("terminal"),
                        arrival_time=datetime.fromisoformat(segment["arrival"]["at"].replace('Z', '+00:00')),
                        carrier_code=segment["carrierCode"],
                        flight_number=segment["number"],
                        aircraft=segment.get("aircraft", {}).get("code"),
                        duration=segment.get("duration", "")
                    ))
                itineraries.append(Itinerary(
                    segments=segments,
                    duration=duration
                ))
            price_data = offer.get("price", {})
            fees = sum(float(fee.get("amount", 0)) for fee in price_data.get("fees", []))
            taxes = sum(float(tax.get("amount", 0)) for tax in price_data.get("taxes", []))
            price = PriceDetail(
                currency=price_data.get("currency", "EUR"),
                total=float(price_data.get("total", 0)),
                base=float(price_data.get("base", 0)),
                fees=fees,
                taxes=taxes,
                grand_total=float(price_data.get("grandTotal", price_data.get("total", 0)))
            )
            flight_offers.append(FlightOffer(
                id=offer.get("id", ""),
                one_way=len(offer.get("itineraries", [])) == 1,
                last_ticketing_date=datetime.strptime(offer.get("lastTicketingDate", "2099-12-31"), "%Y-%m-%d").date() if "lastTicketingDate" in offer else None,
                number_of_bookable_seats=int(offer.get("numberOfBookableSeats", 1)),
                itineraries=itineraries,
                price=price,
                validating_airline_codes=[offer.get("validatingAirlineCodes", [""])[0]],
                traveler_pricings=offer.get("travelerPricings")
            ))
        return flight_offers