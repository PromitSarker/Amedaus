import httpx
from fastapi import HTTPException
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from App.core.config import settings
from App.model.schemas import FlightOffer, FlightSearchParams

class AmadeusService:
    def __init__(self):
        self.client_id = settings.amadeus_api_key
        self.client_secret = settings.amadeus_api_secret
        self.base_url = settings.amadeus_api_url
        self.token = None
        self.token_expiry = None

    async def get_access_token(self) -> str:
        """Get or refresh Amadeus API access token"""
        # Check if token exists and is still valid
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token

        # Get new token
        url = f"{self.base_url}/v1/security/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, headers=headers)
            if response.status_code != 200:
                raise Exception(f"Failed to get access token: {response.text}")
            
            token_data = response.json()
            self.token = token_data["access_token"]
            # Set token expiry time (subtract 5 minutes to be safe)
            self.token_expiry = datetime.now() + timedelta(seconds=token_data["expires_in"] - 300)
            return self.token

    async def search_flights(self, params: FlightSearchParams) -> List[FlightOffer]:
        """Search for flights using Amadeus API"""
        access_token = await self.get_access_token()
        
        url = f"{self.base_url}/v2/shopping/flight-offers"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Build request parameters
        request_params = {
            "originLocationCode": params.origin,
            "destinationLocationCode": params.destination,
            "departureDate": params.departure_date.strftime("%Y-%m-%d"),
            "adults": params.adults,
            "max": params.max_results
        }
        
        if params.return_date:
            request_params["returnDate"] = params.return_date.strftime("%Y-%m-%d")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=request_params)
            
            if response.status_code != 200:
                error_message = f"Flight search failed: {response.text}"
                raise Exception(error_message)
            
            data = response.json()
            return [FlightOffer.parse_obj(offer) for offer in data.get("data", [])]

    async def search_hotels_by_city(self, city_code: str):
        """
        Search for hotels by city code using Amadeus API
        
        Args:
            city_code: 3-letter IATA city code
            
        Returns:
            List of hotels in the specified city
        """
        try:
            # Get access token
            access_token = await self.get_access_token()
            
            # Prepare the API endpoint
            url = f"{self.base_url}/v1/reference-data/locations/hotels/by-city"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "cityCode": city_code
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                elif response.status_code == 400:
                    raise HTTPException(status_code=400, detail="Invalid city code provided")
                elif response.status_code == 404:
                    return []  # Return empty list if no hotels found
                else:
                    response.raise_for_status()
                    
        except httpx.HTTPStatusError as e:
            raise Exception(f"Amadeus API error: {str(e)}")
        except HTTPException as e:
            raise e  # Re-raise FastAPI HTTPExceptions
        except Exception as e:
            raise Exception(f"Hotel search failed: {str(e)}")

    async def search_cities(self, country_code: str, keyword: str, max_results: int = 10):
        """
        Search for cities in a specific country using a keyword
        
        Args:
            country_code: 2-letter country code (ISO 3166-1 alpha-2)
            keyword: City name or part of city name to search for
            max_results: Maximum number of results to return
            
        Returns:
            List of cities matching the search criteria
        """
        try:
            # Get access token
            access_token = await self.get_access_token()
            
            # Prepare the API endpoint
            url = f"{self.base_url}/v1/reference-data/locations/cities"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "countryCode": country_code,
                "keyword": keyword,
                "max": max_results
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                elif response.status_code == 400:
                    raise Exception("Invalid parameters provided for city search")
                else:
                    response.raise_for_status()
                    
        except httpx.HTTPStatusError as e:
            raise Exception(f"Amadeus API error: {str(e)}")
        except Exception as e:
            raise Exception(f"City search failed: {str(e)}")

    async def search_activities(self, latitude: float, longitude: float):
        """
        Search for tourist activities near a specific location
        
        Args:
            latitude: Latitude coordinate of the location
            longitude: Longitude coordinate of the location
            
        Returns:
            List of activities available near the specified location
        """
        try:
            # Get access token
            access_token = await self.get_access_token()
            
            # Prepare the API endpoint
            url = f"{self.base_url}/v1/shopping/activities"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "latitude": latitude,
                "longitude": longitude
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                elif response.status_code == 400:
                    raise Exception("Invalid coordinates provided for activity search")
                elif response.status_code == 404:
                    return []  # Return empty list if no activities found
                else:
                    response.raise_for_status()
                    
        except httpx.HTTPStatusError as e:
            raise Exception(f"Amadeus API error: {str(e)}")
        except Exception as e:
            raise Exception(f"Activity search failed: {str(e)}")