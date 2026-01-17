"""OpenRouter AI service for intent parsing."""

import json
import logging
from enum import Enum
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import get_settings
from app.models.room import RoomCategory

logger = logging.getLogger(__name__)
settings = get_settings()


class IntentType(str, Enum):
    """Types of user intents."""

    FIND_PERSON = "find_person"
    FIND_ROOM = "find_room"
    FIND_SERVICE = "find_service"
    GET_DIRECTIONS = "get_directions"
    GENERAL_QUERY = "general_query"


class ParsedIntent(BaseModel):
    """Structured intent from AI parsing."""

    intent_type: IntentType
    target_name: str | None = None
    target_category: RoomCategory | None = None
    floor: int | None = None
    additional_context: str | None = None
    confidence: float = 0.0


class AIService:
    """OpenRouter-based AI service for natural language understanding."""

    SYSTEM_PROMPT = """You are an AI assistant for a corporate workplace navigation system.
Your job is to parse user queries and extract structured intent for wayfinding.

VALID ROOM CATEGORIES (use exactly these values):
- Meeting Room, Focus Room, Conference Room, Huddle Space, Phone Booth
- Library, Cafeteria, Cafe, Kitchen, Restroom
- Elevator, Stairs, Reception, Lobby
- Gym, Wellness Room, Prayer Room, Mothers Room
- IT Helpdesk, HR Office, Finance, Tech Hub
- Training Room, Auditorium, Storage, Mail Room, Print Station
- Locker Room, Parking, Other

INTENT TYPES:
- find_person: User wants to find a specific person BY NAME or TITLE (CEO, Manager, etc.)
- find_room: User wants to find a specific room by name
- find_service: User wants to find a type of service/amenity (map to category)
- get_directions: User wants directions/navigation to a person or place
- general_query: Other queries

RESPONSE FORMAT (JSON only, no markdown):
{
    "intent_type": "find_person",
    "target_name": "CEO",
    "target_category": null,
    "floor": null,
    "additional_context": "user wants to meet the CEO",
    "confidence": 0.95
}

RULES:
1. Map natural language to the closest valid category
2. "quiet place" → Focus Room or Library
3. "coffee" or "snacks" → Cafe or Cafeteria
4. "bathroom" → Restroom
5. "help desk" or "IT support" → IT Helpdesk
6. IMPORTANT: If user says "need to meet X", "find X", "where is X", "looking for X" and X is a job title or person's name, use find_person intent with target_name set to the title/name
7. Common job titles to recognize: CEO, CTO, CFO, Manager, Director, Lead, Engineer, Designer, HR, Finance, VP, President, Executive
8. If query contains "navigate to", "directions to", "how to get to", "take me to" - use get_directions intent
9. Always include confidence score (0.0-1.0)
10. If floor is mentioned, extract it; otherwise leave null
11. For "need to meet [title]" queries, set intent_type to find_person and target_name to the title (e.g., "CEO", "HR Manager")
12. Search names AND titles, so "find CEO" should search for employees with CEO in their title"""

    def __init__(self):
        """Initialize OpenRouter client."""
        self.client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
        self.model = settings.openrouter_model

    async def parse_intent(self, user_query: str) -> ParsedIntent:
        """Parse user query into structured intent using OpenRouter."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_query},
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                return self._fallback_intent(user_query)

            parsed = json.loads(content)

            # Validate and convert category
            category = parsed.get("target_category")
            if category:
                try:
                    parsed["target_category"] = RoomCategory(category)
                except ValueError:
                    parsed["target_category"] = None

            return ParsedIntent(**parsed)

        except Exception as e:
            logger.error(f"AI intent parsing failed: {e}")
            return self._fallback_intent(user_query)

    def _fallback_intent(self, query: str) -> ParsedIntent:
        """Fallback intent when AI fails."""
        return ParsedIntent(
            intent_type=IntentType.GENERAL_QUERY,
            additional_context=query,
            confidence=0.0,
        )


# Singleton instance
_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    """Get or create AI service singleton."""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
