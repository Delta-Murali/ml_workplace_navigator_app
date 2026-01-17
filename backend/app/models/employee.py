"""Employee model with PostGIS geometry support."""

from datetime import datetime
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import Column
from sqlmodel import Field, SQLModel

if TYPE_CHECKING:
    from shapely.geometry import Point


class EmployeeBase(SQLModel):
    """Base employee attributes."""

    employee_id: str = Field(index=True, unique=True, description="Unique employee identifier")
    name: str = Field(index=True, description="Employee full name")
    email: str = Field(index=True, description="Employee email address")
    department: str = Field(index=True, description="Department name")
    title: str | None = Field(default=None, description="Job title")
    desk_id: str | None = Field(default=None, index=True, description="Assigned desk identifier")
    floor: int = Field(default=1, index=True, description="Floor number")
    building: str = Field(default="HQ", description="Building name")


class Employee(EmployeeBase, table=True):
    """Employee database model with spatial desk location."""

    __tablename__ = "employees"

    id: int | None = Field(default=None, primary_key=True)

    # PostGIS geometry column for desk location (POINT)
    desk_location: "Point | None" = Field(
        default=None,
        sa_column=Column(
            Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
    )

    # Azure Maps FeatureID for indoor mapping
    feature_id: str | None = Field(default=None, description="Azure Maps Indoor Feature ID")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EmployeeRead(EmployeeBase):
    """Employee response schema."""

    id: int
    feature_id: str | None = None
    desk_coordinates: tuple[float, float] | None = None


class EmployeeCreate(EmployeeBase):
    """Employee creation schema."""

    desk_x: float | None = None
    desk_y: float | None = None
    feature_id: str | None = None
