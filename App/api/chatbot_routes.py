from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
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

# New model for single string input containing all info, without user_id
class PlanInputRequest(BaseModel):
    plan_data: str  # JSON string or structured string containing flight, hotel, activities info

# New model for natural language input
class NaturalLanguageRequest(BaseModel):
    user_input: str  # Natural language query from the user

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
        if "flight" not in plan:
            raise HTTPException(status_code=400, detail="Flight information is required for generating a tour plan")
        
        # Use the LLM to enhance the tour plan
        enhanced_plan = await chatbot_service.enhance_tour_plan(plan)
        
        return TourPlanResponse(
            plan=enhanced_plan,
            summary=enhanced_plan.get("summary", ""),
            itinerary=enhanced_plan.get("itinerary", [])
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
    Process natural language input and extract structured travel information.
    
    Args:
        request: Contains user's natural language input
    
    Returns:
        Structured travel information extracted from the input
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
    Complete end-to-end process: from natural language to enhanced travel plan.
    
    Args:
        request: Contains user's natural language input
    
    Returns:
        A complete tour plan with itinerary
    """
    try:
        # Step 1: Process natural language to extract structured info
        extracted_info = await chatbot_service.process_natural_language(request.user_input)
        
        # Step 2: Validate the extracted information
        if not extracted_info or "flight" not in extracted_info:
            raise HTTPException(status_code=400, detail="Could not extract sufficient travel information from your request. Please provide more details about your flight.")
        
        # Step 3: Enhance the plan with LLM
        enhanced_plan = await chatbot_service.enhance_tour_plan(extracted_info)
        
        return TourPlanResponse(
            plan=enhanced_plan,
            summary=enhanced_plan.get("summary", ""),
            itinerary=enhanced_plan.get("itinerary", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating travel plan: {str(e)}")
