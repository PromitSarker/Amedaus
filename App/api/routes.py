from fastapi import FastAPI, APIRouter, HTTPException, Query, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from datetime import date
import httpx
from pydantic import BaseModel
from typing import Dict, Any
import json
import groq

from App.services.amadeus_service import AmadeusService
from App.model.schemas import FlightOffer, FlightSearchParams, TripInput
from App.core.config import settings

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()
amadeus_service = AmadeusService()

@router.get("/")
def read_root():
    return {"message": "Welcome to the Flight Search API"}


def validate_dates(departure_date: date, return_date: Optional[date] = None):
    today = date.today()
    if departure_date < today:
        raise HTTPException(status_code=400, detail="Departure date cannot be in the past")
    if return_date and return_date < today:
        raise HTTPException(status_code=400, detail="Return date cannot be in the past")
    if return_date and return_date < departure_date:
        raise HTTPException(status_code=400, detail="Return date cannot be earlier than departure date")
    return {"departure_date": departure_date, "return_date": return_date}


@router.get("/flights/search", response_model=List[FlightOffer])
async def search_flights(
    origin: str = Query(..., description="Origin airport code (IATA)"),
    destination: str = Query(..., description="Destination airport code (IATA)"),
    departure_date: date = Query(..., description="Departure date (YYYY-MM-DD)"),
    return_date: Optional[date] = Query(None, description="Return date for round trips (YYYY-MM-DD)"),
    adults: int = Query(1, description="Number of adults"),
    max_results: int = Query(10, description="Maximum number of results to return"),
    validated_dates: dict = Depends(validate_dates)
):
    try:
        departure_date = validated_dates["departure_date"]
        return_date = validated_dates["return_date"]
        search_params = FlightSearchParams(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            adults=adults,
            max_results=max_results
        )
        flight_offers = await amadeus_service.search_flights(search_params)
        return flight_offers
    except Exception as e:
        if "Date/Time is in the past" in str(e):
            raise HTTPException(status_code=400, detail="Please provide a future date for your flight search")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hotels/search")
async def search_hotels(
    city_code: str = Query(..., description="City code (IATA) to search hotels in", min_length=3, max_length=3)
):
    """
    Search for hotels in a specific city using the city code.
    
    Args:
        city_code: 3-letter IATA city code (e.g., BLR for Bangalore, NYC for New York)
    
    Returns:
        List of hotels available in the specified city
    """
    try:
        # Validate city code format
        if not city_code.isalpha():
            raise HTTPException(status_code=400, detail="City code must contain only letters")
        
        city_code = city_code.upper()
        
        # Call the amadeus service to search hotels
        hotels = await amadeus_service.search_hotels_by_city(city_code)
        
        return {
            "city_code": city_code,
            "hotels_count": len(hotels),
            "hotels": hotels
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching hotels: {str(e)}")


@router.get("/cities/search")
async def search_cities(
    country_code: str = Query(..., description="Country code (ISO 3166-1 alpha-2)", min_length=2, max_length=2),
    keyword: str = Query(..., description="City name keyword to search for", min_length=2),
    max_results: int = Query(10, description="Maximum number of results to return", ge=1, le=100)
):
    """
    Search for cities in a specific country using a keyword.
    
    Args:
        country_code: 2-letter country code (e.g., FR for France, US for United States)
        keyword: City name or part of city name to search for
        max_results: Maximum number of results to return
    
    Returns:
        List of cities matching the search criteria with their details
    """
    try:
        # Validate country code format
        if not country_code.isalpha():
            raise HTTPException(status_code=400, detail="Country code must contain only letters")
        
        country_code = country_code.upper()
        
        # Call the amadeus service to search cities
        cities = await amadeus_service.search_cities(country_code, keyword, max_results)
        
        return {
            "country_code": country_code,
            "keyword": keyword,
            "cities_count": len(cities),
            "cities": cities
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching cities: {str(e)}")


@router.get("/activities/search")
async def search_activities(
    latitude: float = Query(..., description="Latitude coordinate"),
    longitude: float = Query(..., description="Longitude coordinate")
):
    """
    Search for tourist activities near a specific location.
    
    Args:
        latitude: Latitude coordinate of the location
        longitude: Longitude coordinate of the location
    
    Returns:
        List of activities available near the specified location
    """
    try:
        # Validate coordinates
        if latitude < -90 or latitude > 90:
            raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
        if longitude < -180 or longitude > 180:
            raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")
        
        # Call the amadeus service to search activities
        activities = await amadeus_service.search_activities(latitude, longitude)
        
        return {
            "location": {
                "latitude": latitude,
                "longitude": longitude
            },
            "activities_count": len(activities),
            "activities": activities
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching activities: {str(e)}")


from typing import List, Dict, Any
from datetime import datetime

def transform_segment(raw_segment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a raw segment dict from Amadeus API to the expected segment format.
    """
    return {
        "departure_airport": raw_segment.get("departure", {}).get("iataCode"),
        "departure_time": raw_segment.get("departure", {}).get("at"),
        "arrival_airport": raw_segment.get("arrival", {}).get("iataCode"),
        "arrival_time": raw_segment.get("arrival", {}).get("at"),
        "carrier_code": raw_segment.get("carrierCode"),
        "flight_number": raw_segment.get("number"),
        "aircraft": raw_segment.get("aircraft", {}).get("code") if isinstance(raw_segment.get("aircraft"), dict) else raw_segment.get("aircraft")
    }

def transform_itinerary(raw_itinerary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a raw itinerary dict to the expected format.
    """
    raw_segments = raw_itinerary.get("segments", [])
    segments = [transform_segment(seg) for seg in raw_segments]
    return {"segments": segments}

def transform_price(raw_price: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform raw price dict to expected format.
    Assumes raw_price['fees'] is a list of dicts with 'amount' as string.
    """
    fees_list = raw_price.get("fees", [])
    total_fees = 0.0
    if isinstance(fees_list, list):
        for fee in fees_list:
            try:
                total_fees += float(fee.get("amount", 0))
            except Exception:
                pass
    else:
        # If fees is a single number or string, try to convert directly
        try:
            total_fees = float(fees_list)
        except Exception:
            total_fees = 0.0

    return {
        "fees": total_fees,
        "taxes": float(raw_price.get("taxes", 0)),
        "grand_total": float(raw_price.get("grandTotal", 0)),
        "currency": raw_price.get("currency", "USD")
    }

def transform_flight_offer(raw_offer: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform raw flight offer dict to the expected FlightOffer model format.
    """
    return {
        "id": raw_offer.get("id"),
        "source": raw_offer.get("source", "AMADEUS"),
        "one_way": raw_offer.get("oneWay", False),  # Adjust key if needed
        "last_ticketing_date": raw_offer.get("lastTicketingDate"),
        "number_of_bookable_seats": raw_offer.get("numberOfBookableSeats", 0),
        "itineraries": [transform_itinerary(itin) for itin in raw_offer.get("itineraries", [])],
        "price": transform_price(raw_offer.get("price", {})),
        "validating_airline_codes": raw_offer.get("validatingAirlineCodes", []),
        "traveler_pricings": raw_offer.get("travelerPricings", [])
    }

# Add this import at the top
from groq import Groq

# Initialize Groq client after your settings import
groq_client = Groq(api_key=settings.groq_api_key)

# ... your other code ...

@router.post("/plan-trip")
async def plan_trip(trip_input: TripInput):
    try:
        # Construct the prompt
        prompt = f"""
        Create a detailed trip plan based on the following inputs:
        - Duration: {trip_input.duration_days} days
        - Budget: {trip_input.budget}
        - Destination Preference: {trip_input.vacation_place}
        - Transportation: {trip_input.transportation}
        - Comfort Level: {trip_input.comfort_level}
        
        Additional data from sources:
        {json.dumps(trip_input.source_data, indent=2)}
        
        Provide a day-by-day itinerary including activities, transportation details, 
        accommodation suggestions, and cost estimates. Make sure it fits the budget 
        and comfort level specified.
        - At the end, say something like the price may vary 
        - PRIORITISE the tourism places from the given data.
        - If there's more place to discover, ALSO INCLUDE THOSE. BUT ADD HOW TO GET THERE FROM THE DESTINATION.
        """
        
        # Get AI response using Groq client
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama3-70b-8192",  # Updated model name
            temperature=0.3
        )
        
        return {"trip_plan": chat_completion.choices[0].message.content}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(router)