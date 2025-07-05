import re
from datetime import datetime, date
from typing import Dict, Any, List
from App.services.amadeus_service import AmadeusService
import json
import groq
import os
from typing import Optional


class ChatbotService:
    def __init__(self, amadeus_service: AmadeusService):
        self.amadeus_service = amadeus_service
        # Initialize Groq client
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        self.groq_client = groq.Client(api_key=self.groq_api_key)
        # Default to a powerful model
        self.model = "llama3-70b-8192"
    
    async def process_natural_language(self, user_input: str) -> Dict[str, Any]:
        """
        Process natural language input using Groq LLM to extract travel intent
        
        Args:
            user_input: Natural language input from user
            
        Returns:
            Structured travel information extracted from the input
        """
        prompt = f"""
        Extract travel information from the following user input. 
        Return a JSON object with the following structure:
        {{
            "flight": {{
                "origin": "3-letter IATA code",
                "destination": "3-letter IATA code",
                "departure_date": "YYYY-MM-DD",
                "return_date": "YYYY-MM-DD" (optional),
                "adults": number
            }},
            "hotel": {{
                "city_code": "3-letter IATA city code",
                "check_in_date": "YYYY-MM-DD",
                "check_out_date": "YYYY-MM-DD",
                "rooms": number
            }},
            "activities": {{
                "location": "city name",
                "interests": ["interest1", "interest2", ...]
            }}
        }}
        
        Only include the sections (flight, hotel, activities) that can be clearly identified from the input.
        
        User input: {user_input}
        """
        
        response = self.groq_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a travel planning assistant that extracts structured travel information from user queries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Low temperature for more deterministic outputs
            max_tokens=1000
        )
        
        try:
            # Extract the JSON from the response
            extracted_json = response.choices[0].message.content.strip()
            # Clean up the response to ensure it's valid JSON
            if "" in extracted_json:
                extracted_json = extracted_json.split("json")[1].split("")[0].strip()
            elif "" in extracted_json:
                extracted_json = extracted_json.split("")[1].split("")[0].strip()
            
            return json.loads(extracted_json)
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            raise Exception(f"Failed to parse LLM response: {str(e)}")
    
    async def enhance_tour_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance the tour plan with LLM-generated recommendations and descriptions
        
        Args:
            plan: Basic tour plan data
            
        Returns:
            Enhanced tour plan with better descriptions and recommendations
        """
        flight_info = plan.get("flight", {})
        hotel_info = plan.get("hotel", {})
        activities_info = plan.get("activities", {})
        
        prompt = f"""
        Create an enhanced travel itinerary based on the following information:
        
        Flight: From {flight_info.get('origin', 'N/A')} to {flight_info.get('destination', 'N/A')} 
        on {flight_info.get('departure_date', 'N/A')}
        
        Hotel: In {hotel_info.get('city_code', 'N/A')} from {hotel_info.get('check_in_date', 'N/A')} 
        to {hotel_info.get('check_out_date', 'N/A')}
        
        Activities interests: {', '.join(activities_info.get('interests', ['general sightseeing']))}
        
        Provide a detailed day-by-day itinerary with:
        1. A compelling overall trip summary
        2. For each day, include:
           - Day number and title
           - Morning, afternoon, and evening activities with times
           - Recommended local restaurants for meals
           - Cultural insights about the destination
        
        Return the response as a JSON object with the following structure:
        {{
            "summary": "overall trip summary",
            "itinerary": [
                {{
                    "day": 1,
                    "date": "YYYY-MM-DD",
                    "title": "day title",
                    "description": "day overview",
                    "activities": [
                        {{
                            "time": "time of activity",
                            "description": "short description",
                            "details": "longer details"
                        }}
                    ]
                }}
            ]
        }}
        """
        
        response = self.groq_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a travel expert that creates detailed and engaging travel itineraries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,  # Higher temperature for more creative outputs
            max_tokens=2000
        )
        
        try:
            # Extract the JSON from the response
            enhanced_plan = response.choices[0].message.content.strip()
            # Clean up the response to ensure it's valid JSON
            if "" in enhanced_plan:
                enhanced_plan = enhanced_plan.split("json")[1].split("")[0].strip()
            elif "" in enhanced_plan:
                enhanced_plan = enhanced_plan.split("")[1].split("")[0].strip()
            
            enhanced_data = json.loads(enhanced_plan)
            # Merge the enhanced data with the original plan
            plan["summary"] = enhanced_data.get("summary", "")
            plan["itinerary"] = enhanced_data.get("itinerary", [])
            return plan
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            raise Exception(f"Failed to parse LLM response for enhanced plan: {str(e)}")
    
    async def process_message(self, user_id: str, message: str) -> str:
        """Process user message and generate a response"""
        # Store user message
        self.memory.add_message(user_id, "user", message)
        
        # Process the message
        response = await self._generate_response(user_id, message)
        
        # Store bot response
        self.memory.add_message(user_id, "assistant", response)
        
        return response
    
    async def _generate_response(self, user_id: str, message: str) -> str:
        """Generate a response based on user message and context"""
        message = message.lower().strip()
        context = self.memory.get_user_context(user_id)
        
        # Check for greetings
        if self._is_greeting(message):
            return self._get_greeting_response(context)
        
        # Check for flight search intent
        flight_info = self._extract_flight_info(message)
        if flight_info:
            return await self._handle_flight_search(user_id, flight_info)
        
        # Check for hotel search intent
        hotel_info = self._extract_hotel_info(message)
        if hotel_info:
            return await self._handle_hotel_search(user_id, hotel_info)
        
        # Check for city search intent
        city_info = self._extract_city_info(message)
        if city_info:
            return await self._handle_city_search(user_id, city_info)
        
        # Check for activity search intent
        activity_info = self._extract_activity_info(message)
        if activity_info:
            return await self._handle_activity_search(user_id, activity_info)
        
        # Check for tour plan request
        if "plan" in message and ("tour" in message or "trip" in message or "vacation" in message):
            return self._generate_tour_plan(user_id)
        
        # Default response
        return "I can help you search for flights, hotels, cities, and activities to plan your tour. What would you like to know?"
    
    def _is_greeting(self, message: str) -> bool:
        """Check if the message is a greeting"""
        greetings = ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening"]
        return any(greeting in message for greeting in greetings)
    
    def _get_greeting_response(self, context: Any) -> str:
        """Generate a greeting response based on context"""
        if not context.messages or len(context.messages) <= 2:
            return (
                "Hello! I'm your travel planning assistant. I can help you search for flights, "
                "hotels, cities, and activities to create a perfect tour plan. What destination are you interested in?"
            )
        else:
            return "Hello again! How can I continue helping with your travel plans?"
    
    def _extract_flight_info(self, message: str) -> Optional[Dict[str, Any]]:
        """Extract flight search parameters from message"""
        if "flight" not in message and "fly" not in message:
            return None
        
        # Extract origin and destination
        origin_match = re.search(r"from\s+([a-zA-Z\s]+)(?:\s+to|\s+and)", message)
        dest_match = re.search(r"to\s+([a-zA-Z\s]+)", message)
        
        if not origin_match or not dest_match:
            return None
        
        origin = origin_match.group(1).strip()
        destination = dest_match.group(1).strip()
        
        # Extract dates
        departure_match = re.search(r"(?:on|departing|leaving)(?:\s+on)?\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+(?:\s+\d{4})?)", message)
        return_match = re.search(r"(?:return|returning|coming back)(?:\s+on)?\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+(?:\s+\d{4})?)", message)
        
        # Extract number of adults
        adults_match = re.search(r"(\d+)\s+(?:adult|adults|people|passengers)", message)
        adults = int(adults_match.group(1)) if adults_match else 1
        
        return {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_match.group(1) if departure_match else None,
            "return_date": return_match.group(1) if return_match else None,
            "adults": adults
        }
    
    def _extract_hotel_info(self, message: str) -> Optional[Dict[str, Any]]:
        """Extract hotel search parameters from message"""
        if "hotel" not in message and "accommodation" not in message and "stay" not in message:
            return None
        
        # Extract city
        city_match = re.search(r"(?:in|at)\s+([a-zA-Z\s]+)(?:$|\.|\?|,|\s+for)", message)
        if not city_match:
            return None
        
        city = city_match.group(1).strip()
        
        # Try to extract city code if it's in the format "New York (NYC)"
        city_code_match = re.search(r"\(([A-Z]{3})\)", city)
        city_code = city_code_match.group(1) if city_code_match else None
        
        return {
            "city": city,
            "city_code": city_code
        }
    
    def _extract_city_info(self, message: str) -> Optional[Dict[str, Any]]:
        """Extract city search parameters from message"""
        if "city" not in message and "cities" not in message and "places" not in message:
            return None
        
        # Extract country
        country_match = re.search(r"(?:in|within)\s+([a-zA-Z\s]+)(?:$|\.|\?|,)", message)
        if not country_match:
            return None
        
        country = country_match.group(1).strip()
        
        # Extract keyword
        keyword_match = re.search(r"(?:like|named|called)\s+([a-zA-Z\s]+)(?:$|\.|\?|,|\s+in)", message)
        keyword = keyword_match.group(1).strip() if keyword_match else None
        
        return {
            "country": country,
            "keyword": keyword
        }
    
    def _extract_activity_info(self, message: str) -> Optional[Dict[str, Any]]:
        """Extract activity search parameters from message"""
        if "activity" not in message and "activities" not in message and "things to do" not in message and "attractions" not in message:
            return None
        
        # Extract location
        location_match = re.search(r"(?:in|at|near|around)\s+([a-zA-Z\s]+)(?:$|\.|\?|,)", message)
        if not location_match:
            return None
        
        location = location_match.group(1).strip()
        
        return {
            "location": location
        }
    
    async def _handle_flight_search(self, user_id: str, flight_info: Dict[str, Any]) -> str:
        """Handle flight search request"""
        # This would connect to the actual flight search API
        # For now, we'll just store the search parameters and return a placeholder
        self.memory.update_preferences(user_id, {"flight_preferences": flight_info})
        
        origin = flight_info["origin"]
        destination = flight_info["destination"]
        
        # Store in current plan
        plan = self.memory.get_current_plan(user_id)
        plan["flight"] = {
            "origin": origin,
            "destination": destination,
            "departure_date": flight_info["departure_date"],
            "return_date": flight_info["return_date"],
            "adults": flight_info["adults"]
        }
        self.memory.update_current_plan(user_id, plan)
        
        return (
            f"I've noted your flight search from {origin} to {destination}. "
            f"When I have more details about your trip, I'll help you find the best flights. "
            f"Would you like to search for hotels in {destination} as well?"
        )
    
    async def _handle_hotel_search(self, user_id: str, hotel_info: Dict[str, Any]) -> str:
        """Handle hotel search request"""
        city = hotel_info["city"]
        city_code = hotel_info["city_code"]
        
        if not city_code:
            return (
                f"I need a city code to search for hotels in {city}. "
                f"Could you provide the 3-letter IATA code for {city}? For example, NYC for New York City."
            )
        
        # Store in current plan
        plan = self.memory.get_current_plan(user_id)
        plan["hotel"] = {
            "city": city,
            "city_code": city_code
        }
        self.memory.update_current_plan(user_id, plan)
        
        return (
            f"I've noted your interest in hotels in {city} ({city_code}). "
            f"Would you like to know about activities in {city} as well?"
        )
    
    async def _handle_city_search(self, user_id: str, city_info: Dict[str, Any]) -> str:
        """Handle city search request"""
        country = city_info["country"]
        keyword = city_info["keyword"]
        
        # Convert country name to country code (simplified)
        country_code = self._get_country_code(country)
        
        if not country_code:
            return (
                f"I need a country code to search for cities in {country}. "
                f"Could you provide the 2-letter ISO code for {country}? For example, US for United States."
            )
        
        if not keyword:
            return f"What kind of cities are you looking for in {country}?"
        
        # Store in current plan
        plan = self.memory.get_current_plan(user_id)
        plan["city_search"] = {
            "country": country,
            "country_code": country_code,
            "keyword": keyword
        }
        self.memory.update_current_plan(user_id, plan)
        
        return (
            f"I've noted your interest in cities like '{keyword}' in {country}. "
            f"This will help me suggest destinations for your tour plan."
        )
    
    async def _handle_activity_search(self, user_id: str, activity_info: Dict[str, Any]) -> str:
        """Handle activity search request"""
        location = activity_info["location"]
        
        # Store in current plan
        plan = self.memory.get_current_plan(user_id)
        plan["activities"] = {
            "location": location
        }
        self.memory.update_current_plan(user_id, plan)
        
        return (
            f"I've noted your interest in activities in {location}. "
            f"When we finalize your destination, I'll help you find exciting things to do there."
        )
    
    def _generate_tour_plan(self, user_id: str) -> str:
        """Generate a tour plan based on collected information"""
        plan = self.memory.get_current_plan(user_id)
        
        if not plan:
            return "I don't have enough information to create a tour plan yet. Let's start by discussing your destination preferences."
        
        response_parts = ["Here's a summary of your tour plan based on our conversation:"]
        
        if "flight" in plan:
            flight = plan["flight"]
            response_parts.append(
                f"✈️ Flight: From {flight['origin']} to {flight['destination']}\n"
                f"   Departure: {flight['departure_date']}"
            )
            if flight.get('return_date'):
                response_parts.append(f"   Return: {flight['return_date']}")
            response_parts.append(f"   Passengers: {flight.get('adults', 1)} adult(s)")
        
        if "hotel" in plan:
            hotel = plan["hotel"]
            response_parts.append(f"🏨 Accommodation: Hotels in {hotel['city']} ({hotel['city_code']})")
        
        if "activities" in plan:
            activities = plan["activities"]
            response_parts.append(f"🎭 Activities: Exploring attractions in {activities['location']}")
        
        response_parts.append(
            "\nWould you like me to help you search for specific flights, hotels, or activities based on this plan?"
        )
        
        return "\n".join(response_parts)
    
    def _get_country_code(self, country_name: str) -> Optional[str]:
        """Convert country name to country code (simplified version)"""
        country_mapping = {
            "united states": "US",
            "usa": "US",
            "america": "US",
            "united kingdom": "GB",
            "uk": "GB",
            "france": "FR",
            "germany": "DE",
            "italy": "IT",
            "spain": "ES",
            "japan": "JP",
            "china": "CN",
            "india": "IN",
            "australia": "AU",
            "canada": "CA",
            "brazil": "BR",
            "mexico": "MX",
            "russia": "RU",
            "south korea": "KR",
            "korea": "KR",
            "netherlands": "NL",
            "sweden": "SE",
            "norway": "NO",
            "denmark": "DK",
            "finland": "FI",
            "singapore": "SG",
            "thailand": "TH",
            "indonesia": "ID",
            "malaysia": "MY",
            "vietnam": "VN",
            "turkey": "TR",
            "egypt": "EG",
            "south africa": "ZA",
            "nigeria": "NG",
            "kenya": "KE",
            "morocco": "MA",
            "united arab emirates": "AE",
            "uae": "AE",
            "dubai": "AE",
            "saudi arabia": "SA",
            "qatar": "QA",
            "new zealand": "NZ",
            "argentina": "AR",
            "chile": "CL",
            "colombia": "CO",
            "peru": "PE",
            "portugal": "PT",
            "greece": "GR",
            "switzerland": "CH",
            "austria": "AT",
            "belgium": "BE",
            "ireland": "IE",
            "poland": "PL",
            "czech republic": "CZ",
            "czechia": "CZ",
            "hungary": "HU",
        }
        
        return country_mapping.get(country_name.lower())