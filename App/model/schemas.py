from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date

class FlightSearchParams(BaseModel):
    origin: str
    destination: str
    departure_date: date
    return_date: Optional[date] = None
    adults: int = 1
    max_results: int = 10

class FlightEndpoint(BaseModel):
    iataCode: str
    terminal: Optional[str] = None
    at: str  # ISO datetime string (e.g., "2023-07-01T10:45")

class Aircraft(BaseModel):
    code: str

class FlightSegment(BaseModel):
    departure: FlightEndpoint
    arrival: FlightEndpoint
    carrierCode: str
    # Make flightNumber optional or provide a default value
    flightNumber: Optional[str] = None
    # Alternative: use number instead of flightNumber if that's what the API returns
    number: Optional[str] = None
    aircraft: Aircraft
    duration: str
    # Add any other fields that might be in the API response
    operating: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    blacklistedInEU: Optional[bool] = None
    model_config = {
        "extra": "ignore"  # Ignore extra fields in the API response
    }

class Itinerary(BaseModel):
    duration: str
    segments: List[FlightSegment]

class PriceDetail(BaseModel):
    currency: str
    total: str
    base: Optional[str] = None
    fees: Optional[List[Dict[str, Any]]] = None
    taxes: Optional[float] = None
    grandTotal: Optional[str] = None

class FlightOffer(BaseModel):
    id: str
    source: Optional[str] = "AMADEUS"
    oneWay: Optional[bool] = None
    lastTicketingDate: Optional[str] = None
    numberOfBookableSeats: Optional[int] = None
    itineraries: List[Itinerary]
    price: PriceDetail
    validatingAirlineCodes: List[str]
    travelerPricings: Optional[List[Any]] = None
    # Add any other fields that might be in the API response
    type: Optional[str] = None
