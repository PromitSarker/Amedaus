import httpx
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, date


class ChatbotService:
    def __init__(self, amadeus_service=None):
        self.amadeus_service = amadeus_service
        # Initialize Groq API settings
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_enabled = bool(self.groq_api_key)
        
        if not self.groq_enabled:
            print("Warning: GROQ_API_KEY environment variable is not set. Chatbot features will be limited.")
        
        self.groq_api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"
    
    def _check_groq_availability(self):
        """Check if Groq API is available and raise appropriate error"""
        if not self.groq_enabled:
            raise ValueError("Groq API is not configured. Please set GROQ_API_KEY environment variable.")
    
    async def _call_groq_api(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """
        Call Groq API using HTTP requests instead of SDK
        
        Args:
            messages: List of message objects with role and content
            temperature: Creativity level (0-1)
            max_tokens: Maximum tokens in response
            
        Returns:
            Response content from Groq API
        """
        self._check_groq_availability()
        
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.groq_api_url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise Exception(f"Groq API error: {response.status_code} - {response.text}")
            
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def process_natural_language(self, user_input: str) -> Dict[str, Any]:
        """
        Process natural language input using Groq API to extract travel intent
        
        Args:
            user_input: Natural language input from user
            
        Returns:
            Structured travel information extracted from the input
        """
        if not self.groq_enabled:
            # Return a basic fallback response when Groq is not available
            return {
                "error": "Natural language processing is not available. Please set GROQ_API_KEY.",
                "fallback": True,
                "message": "Please provide structured travel information instead."
            }
        
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
            }},
            "budget": {{
                "total_budget": number,
                "currency": "USD/EUR/etc",
                "budget_breakdown": {{
                    "flights": number,
                    "hotels": number,
                    "activities": number,
                    "food": number
                }}
            }}
        }}
        
        Only include the sections (flight, hotel, activities, budget) that can be clearly identified from the input.
        
        User input: {user_input}
        """
        
        messages = [
            {"role": "system", "content": "You are a travel planning assistant that extracts structured travel information from user queries. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        
        response_content = await self._call_groq_api(messages, temperature=0.1, max_tokens=1000)
        
        try:
            # Clean up the response to ensure it's valid JSON
            cleaned_response = response_content.strip()
            if "" in cleaned_response:
                cleaned_response = cleaned_response.split("json")[1].split("")[0].strip()
            elif "" in cleaned_response:
                cleaned_response = cleaned_response.split("")[1].split("")[0].strip()
            
            return json.loads(cleaned_response)
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            raise Exception(f"Failed to parse LLM response: {str(e)}")
    
    async def generate_tour_plan_with_data(
        self, 
        flights_data: List[Dict[str, Any]], 
        hotels_data: List[Dict[str, Any]], 
        activities_data: List[Dict[str, Any]], 
        user_budget: Dict[str, Any],
        user_preferences: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive tour plan using actual data from Amadeus APIs
        
        Args:
            flights_data: List of flight offers from Amadeus API
            hotels_data: List of hotels from Amadeus API
            activities_data: List of activities from Amadeus API
            user_budget: Budget information including total budget and breakdown
            user_preferences: User preferences for the trip
            
        Returns:
            Enhanced tour plan with recommendations based on budget
        """
        
        # Prepare data summary for the LLM
        flight_summary = self._summarize_flights(flights_data, user_budget.get('budget_breakdown', {}).get('flights', 0))
        hotel_summary = self._summarize_hotels(hotels_data, user_budget.get('budget_breakdown', {}).get('hotels', 0))
        activity_summary = self._summarize_activities(activities_data, user_budget.get('budget_breakdown', {}).get('activities', 0))
        
        total_budget = user_budget.get('total_budget', 0)
        currency = user_budget.get('currency', 'USD')
        
        prompt = f"""
        Create a comprehensive travel itinerary based on the following real data and budget constraints:

        BUDGET INFORMATION:
        - Total Budget: {total_budget} {currency}
        - Flight Budget: {user_budget.get('budget_breakdown', {}).get('flights', 0)} {currency}
        - Hotel Budget: {user_budget.get('budget_breakdown', {}).get('hotels', 0)} {currency}
        - Activities Budget: {user_budget.get('budget_breakdown', {}).get('activities', 0)} {currency}
        - Food Budget: {user_budget.get('budget_breakdown', {}).get('food', 0)} {currency}

        AVAILABLE FLIGHTS:
        {flight_summary}

        AVAILABLE HOTELS:
        {hotel_summary}

        AVAILABLE ACTIVITIES:
        {activity_summary}

        USER PREFERENCES:
        {json.dumps(user_preferences or {}, indent=2)}

        Based on this information, create a detailed travel plan that:
        1. Stays within the specified budget
        2. Recommends the best value options from the available data
        3. Provides a day-by-day itinerary
        4. Includes cost breakdown and budget optimization tips
        5. Suggests alternatives if budget is tight

        Return the response as a JSON object with the following structure:
        {{
            "summary": "overall trip summary with budget highlights",
            "total_estimated_cost": {{
                "flights": number,
                "hotels": number,
                "activities": number,
                "food": number,
                "total": number,
                "currency": "currency_code"
            }},
            "budget_status": "within_budget/over_budget/tight_budget",
            "recommended_selections": {{
                "flight": {{"id": "flight_id", "reason": "why this flight", "cost": number}},
                "hotel": {{"id": "hotel_id", "reason": "why this hotel", "cost_per_night": number}},
                "top_activities": [
                    {{"id": "activity_id", "name": "activity_name", "cost": number, "reason": "why recommended"}}
                ]
            }},
            "itinerary": [
                {{
                    "day": 1,
                    "date": "YYYY-MM-DD",
                    "title": "day title",
                    "description": "day overview",
                    "estimated_daily_cost": number,
                    "activities": [
                        {{
                            "time": "time of activity",
                            "activity": "activity name",
                            "description": "detailed description",
                            "cost": number,
                            "tips": "budget tips or alternatives"
                        }}
                    ]
                }}
            ],
            "budget_optimization_tips": [
                "tip 1: how to save money",
                "tip 2: alternative options"
            ],
            "alternative_options": {{
                "if_budget_increased": "what could be improved with more budget",
                "if_budget_decreased": "how to make it work with less budget"
            }}
        }}
        """
        
        messages = [
            {"role": "system", "content": "You are an expert travel planner who creates detailed, budget-conscious itineraries using real travel data. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        
        response_content = await self._call_groq_api(messages, temperature=0.7, max_tokens=3000)
        
        try:
            # Clean up the response to ensure it's valid JSON
            cleaned_response = response_content.strip()
            if "" in cleaned_response:
                cleaned_response = cleaned_response.split("json")[1].split("")[0].strip()
            elif "" in cleaned_response:
                cleaned_response = cleaned_response.split("")[1].split("")[0].strip()
            
            enhanced_plan = json.loads(cleaned_response)
            
            # Add the original data for reference
            enhanced_plan["source_data"] = {
                "flights": flights_data,
                "hotels": hotels_data,
                "activities": activities_data
            }
            
            return enhanced_plan
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            raise Exception(f"Failed to parse LLM response for enhanced plan: {str(e)}")
    
    def _summarize_flights(self, flights_data: List[Dict[str, Any]], flight_budget: float) -> str:
        """Summarize flight data for the LLM"""
        if not flights_data:
            return "No flights available"
        
        summary_parts = [f"Available Flights (Budget: {flight_budget}):"]
        
        for i, flight in enumerate(flights_data[:5]):  # Limit to top 5 flights
            price = flight.get('price', {})
            total_price = float(price.get('grandTotal', price.get('total', 0)))
            currency = price.get('currency', 'USD')
            
            itineraries = flight.get('itineraries', [])
            route_info = ""
            if itineraries:
                segments = itineraries[0].get('segments', [])
                if segments:
                    first_segment = segments[0]
                    last_segment = segments[-1]
                    departure = first_segment.get('departure', {})
                    arrival = last_segment.get('arrival', {})
                    route_info = f"{departure.get('iataCode', 'N/A')} to {arrival.get('iataCode', 'N/A')}"
            
            within_budget = "✓" if total_price <= flight_budget else "✗"
            summary_parts.append(
                f"  {i+1}. {route_info} - {total_price} {currency} {within_budget} (ID: {flight.get('id', 'N/A')})"
            )
        
        return "\n".join(summary_parts)
    
    def _summarize_hotels(self, hotels_data: List[Dict[str, Any]], hotel_budget: float) -> str:
        """Summarize hotel data for the LLM"""
        if not hotels_data:
            return "No hotels available"
        
        summary_parts = [f"Available Hotels (Budget per night: {hotel_budget}):"]
        
        for i, hotel in enumerate(hotels_data[:10]):  # Limit to top 10 hotels
            name = hotel.get('name', 'Unknown Hotel')
            hotel_id = hotel.get('hotelId', hotel.get('id', 'N/A'))
            
            # Extract location info
            address = hotel.get('address', {})
            city = address.get('cityName', 'Unknown City')
            
            # Note: Hotel pricing would come from a separate API call in Amadeus
            # For now, we'll indicate that pricing needs to be checked
            summary_parts.append(
                f"  {i+1}. {name} in {city} (ID: {hotel_id}) - Pricing to be checked"
            )
        
        return "\n".join(summary_parts)
    
    def _summarize_activities(self, activities_data: List[Dict[str, Any]], activities_budget: float) -> str:
        """Summarize activities data for the LLM"""
        if not activities_data:
            return "No activities available"
        
        summary_parts = [f"Available Activities (Budget: {activities_budget}):"]
        
        for i, activity in enumerate(activities_data[:15]):  # Limit to top 15 activities
            name = activity.get('name', 'Unknown Activity')
            activity_id = activity.get('id', 'N/A')
            
            # Extract price if available
            price_info = activity.get('price', {})
            price_amount = price_info.get('amount', 'Price varies')
            currency = price_info.get('currency', '')
            
            # Extract category/type
            category = activity.get('category', 'General')
            
            price_display = f"{price_amount} {currency}" if currency else str(price_amount)
            within_budget = ""
            
            if isinstance(price_amount, (int, float)) and price_amount <= activities_budget:
                within_budget = "✓"
            elif isinstance(price_amount, (int, float)):
                within_budget = "✗"
            
            summary_parts.append(
                f"  {i+1}. {name} ({category}) - {price_display} {within_budget} (ID: {activity_id})"
            )
        
        return "\n".join(summary_parts)
    
    async def enhance_tour_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy method for backward compatibility
        Enhanced version that works with basic plan data
        """
        flight_info = plan.get("flight", {})
        hotel_info = plan.get("hotel", {})
        activities_info = plan.get("activities", {})
        budget_info = plan.get("budget", {"total_budget": 1000, "currency": "USD"})
        
        prompt = f"""
        Create an enhanced travel itinerary based on the following information:
        
        Flight: From {flight_info.get('origin', 'N/A')} to {flight_info.get('destination', 'N/A')} 
        on {flight_info.get('departure_date', 'N/A')}
        
        Hotel: In {hotel_info.get('city_code', 'N/A')} from {hotel_info.get('check_in_date', 'N/A')} 
        to {hotel_info.get('check_out_date', 'N/A')}
        
        Activities interests: {', '.join(activities_info.get('interests', ['general sightseeing']))}
        
        Budget: {budget_info.get('total_budget', 'Not specified')} {budget_info.get('currency', 'USD')}
        
        Provide a detailed day-by-day itinerary with budget considerations:
        1. A compelling overall trip summary
        2. For each day, include:
           - Day number and title
           - Morning, afternoon, and evening activities with estimated costs
           - Recommended local restaurants for meals with price ranges
           - Cultural insights about the destination
           - Budget tips for each activity
        
        Return the response as a JSON object with the following structure:
        {{
            "summary": "overall trip summary",
            "estimated_total_cost": number,
            "itinerary": [
                {{
                    "day": 1,
                    "date": "YYYY-MM-DD",
                    "title": "day title",
                    "description": "day overview",
                    "estimated_cost": number,
                    "activities": [
                        {{
                            "time": "time of activity",
                            "description": "short description",
                            "details": "longer details",
                            "estimated_cost": number
                        }}
                    ]
                }}
            ]
        }}
        """
        
        messages = [
            {"role": "system", "content": "You are a travel expert that creates detailed and budget-conscious travel itineraries. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        
        response_content = await self._call_groq_api(messages, temperature=0.7, max_tokens=2000)
        
        try:
            # Clean up the response to ensure it's valid JSON
            cleaned_response = response_content.strip()
            if "" in cleaned_response:
                cleaned_response = cleaned_response.split("json")[1].split("")[0].strip()
            elif "" in cleaned_response:
                cleaned_response = cleaned_response.split("")[1].split("")[0].strip()
            
            enhanced_data = json.loads(cleaned_response)
            # Merge the enhanced data with the original plan
            plan["summary"] = enhanced_data.get("summary", "")
            plan["itinerary"] = enhanced_data.get("itinerary", [])
            plan["estimated_total_cost"] = enhanced_data.get("estimated_total_cost", 0)
            return plan
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            raise Exception(f"Failed to parse LLM response for enhanced plan: {str(e)}")