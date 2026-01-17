"""Room/POI model with PostGIS geometry support."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import Column
from sqlmodel import Field, SQLModel

if TYPE_CHECKING:
    from shapely.geometry import Polygon


class RoomCategory(str, Enum):
    """Valid room categories for AI intent matching."""

    MEETING_ROOM = "Meeting Room"
    FOCUS_ROOM = "Focus Room"
    CONFERENCE_ROOM = "Conference Room"
    HUDDLE_SPACE = "Huddle Space"
    PHONE_BOOTH = "Phone Booth"
    LIBRARY = "Library"
    CAFETERIA = "Cafeteria"
    CAFE = "Cafe"
    KITCHEN = "Kitchen"
    RESTROOM = "Restroom"
    ELEVATOR = "Elevator"
    STAIRS = "Stairs"
    RECEPTION = "Reception"
    LOBBY = "Lobby"
    GYM = "Gym"
    WELLNESS_ROOM = "Wellness Room"
    PRAYER_ROOM = "Prayer Room"
    MOTHERS_ROOM = "Mothers Room"
    IT_HELPDESK = "IT Helpdesk"
    HR_OFFICE = "HR Office"
    FINANCE = "Finance"
    TECH_HUB = "Tech Hub"
    TRAINING_ROOM = "Training Room"
    AUDITORIUM = "Auditorium"
    STORAGE = "Storage"
    MAIL_ROOM = "Mail Room"
    PRINT_STATION = "Print Station"
    LOCKER_ROOM = "Locker Room"
    PARKING = "Parking"
    OTHER = "Other"


class RoomBase(SQLModel):
    """Base room attributes."""

    name: str = Field(index=True, description="Room name/identifier")
    display_name: str = Field(description="Human-readable room name")
    category: RoomCategory = Field(index=True, description="Room category for search")
    floor: int = Field(index=True, description="Floor number")
    building: str = Field(default="HQ", description="Building name")
    capacity: int | None = Field(default=None, description="Room capacity")
    amenities: str = Field(default="", description="Comma-separated room amenities")
    description: str | None = Field(default=None, description="Room description")
    is_bookable: bool = Field(default=False, description="Can be booked via calendar")
    is_accessible: bool = Field(default=True, description="Wheelchair accessible")


class Room(RoomBase, table=True):
    """Room database model with spatial polygon geometry."""

    __tablename__ = "rooms"

    id: int | None = Field(default=None, primary_key=True)

    # PostGIS geometry column for room boundary (POLYGON)
    boundary: "Polygon | None" = Field(
        default=None,
        sa_column=Column(
            Geometry(geometry_type="POLYGON", srid=4326),
            nullable=True,
        ),
    )

    # PostGIS geometry column for room centroid (POINT) - for routing
    centroid: "Polygon | None" = Field(
        default=None,
        sa_column=Column(
            Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
    )

    # Azure Maps Indoor Feature ID for linking to IMDF data
    feature_id: str | None = Field(default=None, index=True, description="Azure Maps Indoor Feature ID")
    
    # Additional Azure Maps identifiers
    azure_maps_feature_id: str | None = Field(default=None, description="Azure Maps unit feature ID from IMDF")
    room_number: str | None = Field(default=None, description="Room number for matching")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RoomRead(RoomBase):
    """Room response schema."""

    id: int
    feature_id: str
    centroid_coordinates: tuple[float, float] | None = None


class RoomCreate(RoomBase):
    """Room creation schema."""

    feature_id: str
    centroid_x: float | None = None
    centroid_y: float | None = None
