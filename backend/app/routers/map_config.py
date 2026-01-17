"""Map configuration API router - Azure Maps credentials."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/api/map", tags=["map"])

settings = get_settings()


class MapConfig(BaseModel):
    """Azure Maps configuration for frontend."""

    client_id: str
    subscription_key: str  # Needed for SDK auth
    tileset_id: str
    stateset_id: str
    routeset_id: str
    dataset_id: str


@router.get("/config", response_model=MapConfig)
async def get_map_config() -> MapConfig:
    """
    Get Azure Maps configuration for the frontend.

    For production, consider using Azure AD authentication instead
    of exposing the subscription key directly.
    """
    return MapConfig(
        client_id=settings.azure_maps_client_id,
        subscription_key=settings.azure_maps_subscription_key,
        tileset_id=settings.azure_maps_tileset_id,
        stateset_id=settings.azure_maps_stateset_id,
        routeset_id=settings.azure_maps_routeset_id,
        dataset_id=settings.azure_maps_dataset_id,
    )


class FloorInfo(BaseModel):
    """Floor information."""

    floor_number: int
    name: str
    ordinal: int


class BuildingInfo(BaseModel):
    """Building information for indoor maps."""

    building_id: str
    name: str
    floors: list[FloorInfo]


@router.get("/building", response_model=BuildingInfo)
async def get_building_info() -> BuildingInfo:
    """Get building information for floor selector."""
    # TODO: Load from database or Azure Maps Creator API
    return BuildingInfo(
        building_id="hq-main",
        name="Headquarters",
        floors=[
            FloorInfo(floor_number=1, name="Ground Floor", ordinal=0),
            FloorInfo(floor_number=2, name="Floor 2", ordinal=1),
            FloorInfo(floor_number=3, name="Floor 3", ordinal=2),
            FloorInfo(floor_number=4, name="Floor 4", ordinal=3),
            FloorInfo(floor_number=5, name="Floor 5", ordinal=4),
            FloorInfo(floor_number=6, name="Floor 6", ordinal=5),
        ],
    )


# --- Wayfinding Endpoints ---

class WayfindingRequest(BaseModel):
    """Request for indoor wayfinding."""
    
    from_lat: float
    from_lon: float
    to_feature_id: str
    facility_id: str | None = None


class WayfindingLeg(BaseModel):
    """A leg of the wayfinding path."""
    
    floor_ordinal: int
    points: list[dict]
    distance_meters: float
    instruction: str | None = None


class WayfindingResponse(BaseModel):
    """Response from wayfinding API."""
    
    success: bool
    legs: list[WayfindingLeg]
    total_distance_meters: float
    estimated_time_seconds: float


@router.post("/wayfinding", response_model=WayfindingResponse)
async def get_wayfinding_path(request: WayfindingRequest) -> WayfindingResponse:
    """
    Get indoor wayfinding path between two points.
    
    This proxies the request to Azure Maps Wayfinding API
    to avoid exposing subscription key in frontend.
    """
    from app.services.indoor_navigation_service import indoor_navigation_service
    
    result = await indoor_navigation_service.get_wayfinding_path(
        from_lat=request.from_lat,
        from_lon=request.from_lon,
        to_feature_id=request.to_feature_id,
        facility_id=request.facility_id,
    )
    
    if not result:
        return WayfindingResponse(
            success=False,
            legs=[],
            total_distance_meters=0,
            estimated_time_seconds=0,
        )
    
    # Parse Azure Maps response into our format
    legs = []
    total_distance = 0
    
    paths = result.get("paths", [])
    if paths:
        for leg in paths[0].get("legs", []):
            leg_distance = leg.get("distanceInMeters", 0)
            total_distance += leg_distance
            
            legs.append(WayfindingLeg(
                floor_ordinal=leg.get("floorOrdinal", 0),
                points=leg.get("points", []),
                distance_meters=leg_distance,
                instruction=leg.get("instruction"),
            ))
    
    # Estimate walking time (average 1.4 m/s walking speed)
    estimated_time = total_distance / 1.4
    
    return WayfindingResponse(
        success=True,
        legs=legs,
        total_distance_meters=total_distance,
        estimated_time_seconds=estimated_time,
    )


# --- Feature State Endpoints ---

class FeatureStateUpdate(BaseModel):
    """Request to update feature state."""
    
    feature_id: str
    states: dict


@router.post("/feature-state")
async def update_feature_state(request: FeatureStateUpdate) -> dict:
    """
    Update the state of an indoor map feature.
    
    Common states:
    - available: bool (room availability)
    - occupied: bool (desk/room occupied)
    - temperature: float (room temperature)
    """
    from app.services.indoor_navigation_service import indoor_navigation_service
    
    success = await indoor_navigation_service.update_feature_state(
        feature_id=request.feature_id,
        states=request.states,
    )
    
    return {"success": success}


@router.get("/feature-state/{feature_id}")
async def get_feature_state(feature_id: str) -> dict:
    """Get current state of a feature."""
    from app.services.indoor_navigation_service import indoor_navigation_service
    
    states = await indoor_navigation_service.get_feature_state(feature_id)
    return {"feature_id": feature_id, "states": states or {}}


# --- Floor Plan GeoJSON Endpoints ---

@router.get("/floor/{floor_number}")
async def get_floor_plan(floor_number: int) -> dict:
    """
    Get floor plan GeoJSON for a specific floor.
    
    Returns GeoJSON FeatureCollection with rooms (units) and doors (openings)
    from the converted IMDF data.
    """
    import json
    from pathlib import Path
    
    # Look for IMDF output directory
    imdf_dir = Path(__file__).parent.parent.parent / "imdf_output"
    
    features = []
    
    # Load units (rooms)
    unit_file = imdf_dir / "unit.geojson"
    if unit_file.exists():
        with open(unit_file) as f:
            unit_data = json.load(f)
            for feature in unit_data.get("features", []):
                # Filter by floor (level_id contains floor ordinal)
                level_id = feature.get("properties", {}).get("level_id", "")
                # Level IDs are like "level_0" for floor 1, "level_1" for floor 2
                feature_floor = int(level_id.split("_")[-1]) + 1 if level_id else 1
                
                if feature_floor == floor_number:
                    features.append(feature)
    
    # Load openings (doors)
    opening_file = imdf_dir / "opening.geojson"
    if opening_file.exists():
        with open(opening_file) as f:
            opening_data = json.load(f)
            for feature in opening_data.get("features", []):
                level_id = feature.get("properties", {}).get("level_id", "")
                feature_floor = int(level_id.split("_")[-1]) + 1 if level_id else 1
                
                if feature_floor == floor_number:
                    features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/floors")
async def get_available_floors() -> dict:
    """Get list of floors that have floor plan data."""
    import json
    from pathlib import Path
    
    imdf_dir = Path(__file__).parent.parent.parent / "imdf_output"
    level_file = imdf_dir / "level.geojson"
    
    floors = []
    
    if level_file.exists():
        with open(level_file) as f:
            level_data = json.load(f)
            for feature in level_data.get("features", []):
                props = feature.get("properties", {})
                ordinal = props.get("ordinal", 0)
                name = props.get("name", {}).get("en", f"Floor {ordinal + 1}")
                floors.append({
                    "floor_number": ordinal + 1,
                    "name": name,
                    "ordinal": ordinal,
                })
    
    # Sort by floor number
    floors.sort(key=lambda x: x["floor_number"])
    
    # If no IMDF data, return default floors
    if not floors:
        floors = [
            {"floor_number": 1, "name": "Floor 1", "ordinal": 0},
            {"floor_number": 2, "name": "Floor 2", "ordinal": 1},
        ]
    
    return {"floors": floors}

