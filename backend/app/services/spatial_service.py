"""Spatial query service using PostGIS."""

import logging
from typing import Any

from geoalchemy2.functions import ST_AsGeoJSON, ST_Distance, ST_MakePoint, ST_SetSRID
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.room import Room, RoomCategory
from app.services.ai_service import IntentType, ParsedIntent

logger = logging.getLogger(__name__)


class SpatialService:
    """Service for PostGIS spatial queries."""

    def __init__(self, session: AsyncSession):
        """Initialize with database session."""
        self.session = session

    async def find_by_intent(
        self,
        intent: ParsedIntent,
        current_location: tuple[float, float] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find locations based on parsed intent."""
        match intent.intent_type:
            case IntentType.FIND_PERSON:
                return await self._find_employee(intent.target_name, limit)
            case IntentType.FIND_ROOM:
                return await self._find_room_by_name(intent.target_name, intent.floor, limit)
            case IntentType.FIND_SERVICE:
                return await self._find_by_category(
                    intent.target_category,
                    intent.floor,
                    current_location,
                    limit,
                )
            case _:
                return []

    async def _find_employee(
        self,
        name: str | None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find employee by name, title, or department (fuzzy match)."""
        if not name:
            return []

        # Case-insensitive partial match on name, email, employee_id, title, and department
        query = select(Employee).where(
            or_(
                Employee.name.ilike(f"%{name}%"),
                Employee.email.ilike(f"%{name}%"),
                Employee.employee_id.ilike(f"%{name}%"),
                Employee.title.ilike(f"%{name}%"),
                Employee.department.ilike(f"%{name}%"),
            )
        ).limit(limit)

        result = await self.session.execute(query)
        employees = result.scalars().all()

        return [
            {
                "type": "employee",
                "id": emp.id,
                "name": emp.name,
                "email": emp.email,
                "department": emp.department,
                "title": emp.title,
                "desk_id": emp.desk_id,
                "floor": emp.floor,
                "building": emp.building,
                "feature_id": emp.feature_id,
            }
            for emp in employees
        ]

    async def _find_room_by_name(
        self,
        name: str | None,
        floor: int | None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find room by name."""
        if not name:
            return []

        query = select(Room).where(
            or_(
                Room.name.ilike(f"%{name}%"),
                Room.display_name.ilike(f"%{name}%"),
            )
        )

        if floor is not None:
            query = query.where(Room.floor == floor)

        query = query.limit(limit)
        result = await self.session.execute(query)
        rooms = result.scalars().all()

        return self._format_room_results(rooms)

    async def _find_by_category(
        self,
        category: RoomCategory | None,
        floor: int | None,
        current_location: tuple[float, float] | None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find rooms by category, optionally sorted by distance."""
        if not category:
            return []

        query = select(Room).where(Room.category == category)

        if floor is not None:
            query = query.where(Room.floor == floor)

        # Sort by distance if current location provided
        if current_location:
            user_point = ST_SetSRID(
                ST_MakePoint(current_location[0], current_location[1]),
                4326,
            )
            query = query.order_by(ST_Distance(Room.centroid, user_point))
        else:
            query = query.order_by(Room.floor, Room.name)

        query = query.limit(limit)
        result = await self.session.execute(query)
        rooms = result.scalars().all()

        return self._format_room_results(rooms)

    async def find_nearest(
        self,
        category: RoomCategory,
        current_location: tuple[float, float],
        floor: int | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find nearest rooms of a category using PostGIS ST_Distance."""
        user_point = ST_SetSRID(
            ST_MakePoint(current_location[0], current_location[1]),
            4326,
        )

        query = (
            select(
                Room,
                ST_Distance(Room.centroid, user_point).label("distance"),
            )
            .where(Room.category == category)
            .order_by("distance")
            .limit(limit)
        )

        if floor is not None:
            query = query.where(Room.floor == floor)

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                **self._format_single_room(room),
                "distance_meters": distance,
            }
            for room, distance in rows
        ]

    def _format_room_results(self, rooms: list[Room]) -> list[dict[str, Any]]:
        """Format room results for API response."""
        return [self._format_single_room(room) for room in rooms]

    def _format_single_room(self, room: Room) -> dict[str, Any]:
        """Format single room for API response."""
        # Convert comma-separated amenities string to list
        amenities_list = [a.strip() for a in room.amenities.split(",") if a.strip()] if room.amenities else []
        
        return {
            "type": "room",
            "id": room.id,
            "name": room.name,
            "display_name": room.display_name,
            "category": room.category.value,
            "floor": room.floor,
            "building": room.building,
            "capacity": room.capacity,
            "amenities": amenities_list,
            "is_bookable": room.is_bookable,
            "is_accessible": room.is_accessible,
            "feature_id": room.feature_id,
        }
