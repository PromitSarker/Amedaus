from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import date, datetime

class FlightSearchParams(BaseModel):
    origin: str
    destination: str
    departure_date: date
    return_date: Optional[date] = None
    adults: int = 1
    max_results: int = 10

class FlightSegment(BaseModel):
    departure_airport: str
    departure_terminal: Optional[str] = None
    departure_time: datetime
    arrival_airport: str
    arrival_terminal: Optional[str] = None
    arrival_time: datetime
    carrier_code: str
    flight_number: str
    aircraft: Optional[str] = None
    duration: str

class Itinerary(BaseModel):
    segments: List[FlightSegment]
    duration: str

class PriceDetail(BaseModel):
    currency: str
    total: float
    base: float
    fees: float
    taxes: float
    grand_total: float

class FlightOffer(BaseModel):
    id: str
    source: str = "AMADEUS"
    one_way: bool
    last_ticketing_date: Optional[date] = None
    number_of_bookable_seats: int
    itineraries: List[Itinerary]
    price: PriceDetail
    validating_airline_codes: List[str]
    traveler_pricings: Optional[List[Any]] = None