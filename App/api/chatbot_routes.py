from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from App.services.chatbot_service import ChatbotService
from App.services.amadeus_service import AmadeusService
import json

routes = APIRouter(prefix="/chatbot", tags=["chatbot"])

# Dependency to get the chatbot service
def get_chatbot_service():
    amadeus_service = AmadeusService()  # Adjust initialization as needed
    return ChatbotService(amadeus_service)

class TourPlanResponse(BaseModel):
    plan: Dict[str, Any]
    summary: str
    itinerary: List[Dict[str, Any]]
    estimated_total_cost: Optional[float] = None
    budget_status: Optional[str] = None

# New model for comprehensive tour planning with real data
class ComprehensiveTourPlanRequest(BaseModel):
    flights_data: List[Dict[str, Any]] = Field(..., description="Flight offers data from Amadeus API")
    hotels_data: List[Dict[str, Any]] = Field(..., description="Hotels data from Amadeus API")
    activities_data: List[Dict[str, Any]] = Field(..., description="Activities data from Amadeus API")
    user_budget: Dict[str, Any] = Field(..., description="User budget information including total and breakdown")
    user_preferences: Optional[Dict[str, Any]] = Field(None, description="User preferences for the trip")

# Budget information model
class BudgetInfo(BaseModel):
    total_budget: float = Field(..., description="Total budget for the trip")
    currency: str = Field(default="USD", description="Currency code (USD, EUR, etc.)")
    budget_breakdown: Optional[Dict[str, float]] = Field(None, description="Budget breakdown by category")

# Model for budget-aware planning
class BudgetAwarePlanRequest(BaseModel):
    travel_data: Dict[str, Any] = Field(..., description="Basic travel information (origin, destination, dates)")
    budget: BudgetInfo = Field(..., description="Budget information")
    preferences: Optional[Dict[str, Any]] = Field(None, description="User preferences")

# New model for single string input containing all info, without user_id
class PlanInputRequest(BaseModel):
    plan_data: str  # JSON string or structured string containing flight, hotel, activities info

# New model for natural language input
class NaturalLanguageRequest(BaseModel):
    user_input: str  # Natural language query from the user

# Model for flight search
class FlightSearchRequest(BaseModel):
    origin: str = Field(..., description="Origin airport code (e.g., NYC, LAX)")
    destination: str = Field(..., description="Destination airport code (e.g., PAR, LON)")
    departure_date: str = Field(..., description="Departure date in YYYY-MM-DD format")
    return_date: Optional[str] = Field(None, description="Return date in YYYY-MM-DD format for round trip")
    adults: int = Field(default=1, description="Number of adult passengers")
    travel_class: Optional[str] = Field(default="ECONOMY", description="Travel class (ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST)")
    max_price: Optional[float] = Field(None, description="Maximum price filter")
    currency: str = Field(default="USD", description="Currency code")

@routes.post("/generate-comprehensive-plan", response_model=TourPlanResponse)
async def generate_comprehensive_tour_plan(
    request: ComprehensiveTourPlanRequest,
    chatbot_service: ChatbotService = Depends(get_chatbot_service)
):
    """
    Generate a comprehensive tour plan using real data from Amadeus APIs with budget considerations.
    
    Args:
        request: Contains flights, hotels, activities data and budget information
    
    Returns:
        A detailed tour plan with budget optimization and recommendations
    """
    try:
        # Validate that we have minimum required data
        if not request.flights_data and not request.hotels_data and not request.activities_data:
            raise HTTPException(
                status_code=400, 
                detail="At least one type of travel data (flights, hotels, or activities) is required"
            )
        
        # Validate budget information
        if not request.user_budget or "total_budget" not in request.user_budget:
            raise HTTPException(
                status_code=400, 
                detail="Budget information with total_budget is required"
            )
        
        # Generate comprehensive tour plan using real data
        enhanced_plan = await chatbot_service.generate_tour_plan_with_data(
            flights_data=request.flights_data,
            hotels_data=request.hotels_data,
            activities_data=request.activities_data,
            user_budget=request.user_budget,
            user_preferences=request.user_preferences
        )
        
        return TourPlanResponse(
            plan=enhanced_plan,
            summary=enhanced_plan.get("summary", ""),
            itinerary=enhanced_plan.get("itinerary", []),
            estimated_total_cost=enhanced_plan.get("total_estimated_cost", {}).get("total"),
            budget_status=enhanced_plan.get("budget_status", "unknown")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating comprehensive tour plan: {str(e)}")

@routes.post("/generate-budget-aware-plan", response_model=TourPlanResponse)
async def generate_budget_aware_plan(
    request: BudgetAwarePlanRequest,
    chatbot_service: ChatbotService = Depends(get_chatbot_service)
):
    """
    Generate a budget-aware tour plan based on travel data and budget constraints.
    
    Args:
        request: Contains travel data, budget, and preferences
    
    Returns:
        A tour plan optimized for the specified budget
    """
    try:
        # Prepare the plan data with budget information
        plan_data = {
            **request.travel_data,
            "budget": {
                "total_budget": request.budget.total_budget,
                "currency": request.budget.currency,
                "budget_breakdown": request.budget.budget_breakdown or {}
            }
        }
        
        if request.preferences:
            plan_data["preferences"] = request.preferences
        
        # Use the enhanced tour plan method with budget considerations
        enhanced_plan = await chatbot_service.enhance_tour_plan(plan_data)
        
        return TourPlanResponse(
            plan=enhanced_plan,
            summary=enhanced_plan.get("summary", ""),
            itinerary=enhanced_plan.get("itinerary", []),
            estimated_total_cost=enhanced_plan.get("estimated_total_cost")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating budget-aware plan: {str(e)}")

@routes.post("/analyze-travel-data", response_model=Dict[str, Any])
async def analyze_travel_data(
    request: ComprehensiveTourPlanRequest,
    chatbot_service: ChatbotService = Depends(get_chatbot_service)
):
    """
    Analyze travel data and provide insights without generating a full itinerary.
    
    Args:
        request: Contains flights, hotels, activities data and budget information
    
    Returns:
        Analysis of the travel data including best options and budget insights
    """
    try:
        # Get a summary analysis of the data
        flight_summary = chatbot_service._summarize_flights(
            request.flights_data, 
            request.user_budget.get('budget_breakdown', {}).get('flights', 0)
        )
        hotel_summary = chatbot_service._summarize_hotels(
            request.hotels_data, 
            request.user_budget.get('budget_breakdown', {}).get('hotels', 0)
        )
        activity_summary = chatbot_service._summarize_activities(
            request.activities_data, 
            request.user_budget.get('budget_breakdown', {}).get('activities', 0)
        )
        
        return {
            "analysis": {
                "flights": flight_summary,
                "hotels": hotel_summary,
                "activities": activity_summary
            },
            "budget_info": request.user_budget,
            "data_counts": {
                "flights_available": len(request.flights_data),
                "hotels_available": len(request.hotels_data),
                "activities_available": len(request.activities_data)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing travel data: {str(e)}")

# Keep existing endpoints for backward compatibility
@routes.post("/generate-plan-from-string", response_model=TourPlanResponse)
async def generate_tour_plan_from_string(
    request: PlanInputRequest,
    chatbot_service: ChatbotService = Depends(get_chatbot_service)
):
    """
    Generate a complete tour plan based on a single string input containing all information.
    
    Args:
        request: Contains plan_data string
    
    Returns:
        A complete tour plan with itinerary
    """
    try:
        # Parse the plan_data string into a dict
        try:
            plan = json.loads(request.plan_data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid plan_data format. Must be a valid JSON string.")
        
        if not plan:
            raise HTTPException(status_code=404, detail="No tour plan information found in the input data")
        
        # Check if we have the minimum required information
        if "flight" not in plan and "budget" not in plan:
            raise HTTPException(status_code=400, detail="Either flight information or budget information is required for generating a tour plan")
        
        # Use the LLM to enhance the tour plan
        enhanced_plan = await chatbot_service.enhance_tour_plan(plan)
        
        return TourPlanResponse(
            plan=enhanced_plan,
            summary=enhanced_plan.get("summary", ""),
            itinerary=enhanced_plan.get("itinerary", []),
            estimated_total_cost=enhanced_plan.get("estimated_total_cost")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating tour plan: {str(e)}")

@routes.post("/process-natural-language", response_model=Dict[str, Any])
async def process_natural_language(
    request: NaturalLanguageRequest,
    chatbot_service: ChatbotService = Depends(get_chatbot_service)
):
    """
    Process natural language input and extract structured travel information including budget.
    
    Args:
        request: Contains user's natural language input
    
    Returns:
        Structured travel information extracted from the input including budget details
    """
    try:
        # Process the natural language input
        extracted_info = await chatbot_service.process_natural_language(request.user_input)
        
        return extracted_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing natural language input: {str(e)}")

@routes.post("/complete-travel-plan", response_model=TourPlanResponse)
async def complete_travel_plan(
    request: NaturalLanguageRequest,
    chatbot_service: ChatbotService = Depends(get_chatbot_service)
):
    """
    Complete end-to-end process: from natural language to enhanced travel plan with budget considerations.
    
    Args:
        request: Contains user's natural language input
    
    Returns:
        A complete tour plan with itinerary and budget information
    """
    try:
        # Step 1: Process natural language to extract structured info
        extracted_info = await chatbot_service.process_natural_language(request.user_input)
        
        # Step 2: Validate the extracted information
        if not extracted_info or (not extracted_info.get("flight") and not extracted_info.get("budget")):
            raise HTTPException(
                status_code=400, 
                detail="Could not extract sufficient travel information from your request. Please provide more details about your travel plans or budget."
            )
        
        # Step 3: Enhance the plan with LLM
        enhanced_plan = await chatbot_service.enhance_tour_plan(extracted_info)
        
        return TourPlanResponse(
            plan=enhanced_plan,
            summary=enhanced_plan.get("summary", ""),
            itinerary=enhanced_plan.get("itinerary", []),
            estimated_total_cost=enhanced_plan.get("estimated_total_cost")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating travel plan: {str(e)}")

# New endpoint for getting recommendations based on data
@routes.post("/get-recommendations", response_model=Dict[str, Any])
async def get_travel_recommendations(
    request: ComprehensiveTourPlanRequest,
    chatbot_service: ChatbotService = Depends(get_chatbot_service)
):
    """
    Get specific recommendations for flights, hotels, and activities based on budget.
    
    Args:
        request: Contains travel data and budget information
    
    Returns:
        Specific recommendations with reasons and alternatives
    """
    try:
        # Generate the comprehensive plan to get recommendations
        enhanced_plan = await chatbot_service.generate_tour_plan_with_data(
            flights_data=request.flights_data,
            hotels_data=request.hotels_data,
            activities_data=request.activities_data,
            user_budget=request.user_budget,
            user_preferences=request.user_preferences
        )
        
        # Extract recommendations from the plan
        recommendations = {
            "flight_recommendations": enhanced_plan.get("recommended_flights", []),
            "hotel_recommendations": enhanced_plan.get("recommended_hotels", []),
            "activity_recommendations": enhanced_plan.get("recommended_activities", []),
            "budget_analysis": enhanced_plan.get("budget_analysis", {}),
            "alternatives": enhanced_plan.get("alternatives", {}),
            "savings_tips": enhanced_plan.get("savings_tips", [])
        }
        
        return recommendations
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting travel recommendations: {str(e)}")

# Flight search endpoint
@routes.post("/search-flights", response_model=Dict[str, Any])
async def search_flights(
    request: FlightSearchRequest,
    chatbot_service: ChatbotService = Depends(get_chatbot_service)
):
    """
    Search for flights using Amadeus API.
    
    Args:
        request: Contains flight search parameters
    
    Returns:
        Flight search results from Amadeus API
    """
    try:
        # Get the Amadeus service from the chatbot service
        amadeus_service = chatbot_service.amadeus_service
        
        # Prepare search parameters
        search_params = {
            "originLocationCode": request.origin,
            "destinationLocationCode": request.destination,
            "departureDate": request.departure_date,
            "adults": request.adults,
            "travelClass": request.travel_class,
            "currencyCode": request.currency
        }
        
        # Add return date if provided (round trip)
        if request.return_date:
            search_params["returnDate"] = request.return_date
        
        # Perform the flight search
        flight_search_results = await amadeus_service.search_flights(search_params)
        
        return flight_search_results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching for flights: {str(e)}")