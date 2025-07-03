from fastapi import FastAPI, APIRouter, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import date

from App.services.amadeus_service import AmadeusService
from App.model.schemas import FlightOffer, FlightSearchParams
from App.core.config import settings

app = FastAPI(
    title="Flight Search API",
    description="API for searching flights using Amadeus API",
    version="1.0.0")

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


app.include_router(router)