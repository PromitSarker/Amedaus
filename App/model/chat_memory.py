from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = datetime.now()


class UserContext(BaseModel):
    user_id: str
    messages: List[Message] = []
    preferences: Dict[str, Any] = {}
    search_history: Dict[str, Any] = {
        "flights": [],
        "hotels": [],
        "cities": [],
        "activities": []
    }
    current_plan: Dict[str, Any] = {}
    last_interaction: datetime = datetime.now()


class ChatMemoryCache:
    def __init__(self):
        self.user_contexts: Dict[str, UserContext] = {}
        self.expiry_time = 3600 * 24  # 24 hours in seconds

    def get_user_context(self, user_id: str) -> UserContext:
        """Get or create user context"""
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = UserContext(user_id=user_id)
        return self.user_contexts[user_id]

    def add_message(self, user_id: str, role: str, content: str) -> None:
        """Add a message to the user's conversation history"""
        context = self.get_user_context(user_id)
        context.messages.append(Message(role=role, content=content))
        context.last_interaction = datetime.now()

    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Message]:
        """Get the recent conversation history"""
        context = self.get_user_context(user_id)
        return context.messages[-limit:] if context.messages else []

    def store_search_result(self, user_id: str, search_type: str, result: Any) -> None:
        """Store search results in user context"""
        context = self.get_user_context(user_id)
        if search_type in context.search_history:
            context.search_history[search_type].append(result)
        context.last_interaction = datetime.now()

    def update_preferences(self, user_id: str, preferences: Dict[str, Any]) -> None:
        """Update user preferences"""
        context = self.get_user_context(user_id)
        context.preferences.update(preferences)
        context.last_interaction = datetime.now()

    def update_current_plan(self, user_id: str, plan_data: Dict[str, Any]) -> None:
        """Update the current tour plan"""
        context = self.get_user_context(user_id)
        context.current_plan.update(plan_data)
        context.last_interaction = datetime.now()

    def get_current_plan(self, user_id: str) -> Dict[str, Any]:
        """Get the current tour plan"""
        context = self.get_user_context(user_id)
        return context.current_plan

    def clear_expired_contexts(self) -> None:
        """Remove expired user contexts"""
        current_time = datetime.now()
        expired_users = []
        
        for user_id, context in self.user_contexts.items():
            time_diff = (current_time - context.last_interaction).total_seconds()
            if time_diff > self.expiry_time:
                expired_users.append(user_id)
                
        for user_id in expired_users:
            del self.user_contexts[user_id]