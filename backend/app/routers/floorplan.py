"""Floor plan GeoJSON API router."""

import json
import math
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/floorplan", tags=["floorplan"])

# Path to extracted IMDF GeoJSON files - check both possible folder names
_base_dir = Path(__file__).parent.parent.parent / "floorplan_geojson"
if (_base_dir / "imdf_package").exists():
    GEOJSON_DIR = _base_dir / "imdf_package"
else:
    GEOJSON_DIR = _base_dir / "imdf_output"

# Reference point for coordinate transformation (Dallas area)
# This is the center point from level.geojson
REF_LAT = 32.7766
REF_LON = -96.7969
# Scale factor: meters per degree (approximate at this latitude)
METERS_PER_DEG_LAT = 111320  # ~111.32 km per degree latitude
METERS_PER_DEG_LON = METERS_PER_DEG_LAT * math.cos(math.radians(REF_LAT))  # ~94.5 km at this lat
# Assume CAD units are in feet, convert to degrees
FEET_TO_METERS = 0.3048
SCALE_X = FEET_TO_METERS / METERS_PER_DEG_LON
SCALE_Y = FEET_TO_METERS / METERS_PER_DEG_LAT


def load_geojson(filename: str) -> dict[str, Any]:
    """Load a GeoJSON file from the floorplan directory."""
    filepath = GEOJSON_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"GeoJSON file not found: {filename}")
    
    with open(filepath) as f:
        return json.load(f)


def transform_coords(x: float, y: float) -> tuple[float, float]:
    """Transform local CAD coordinates to geographic coordinates."""
    # Offset to center the floor plan (assuming CAD origin needs adjustment)
    # These offsets center the floor plan at the reference point
    lon = REF_LON + (x * SCALE_X)
    lat = REF_LAT + (y * SCALE_Y)
    return (lon, lat)


def transform_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    """Transform a GeoJSON geometry from CAD to geographic coordinates."""
    geom_type = geometry.get("type")
    
    if geom_type == "Point":
        coords = geometry["coordinates"]
        new_coords = list(transform_coords(coords[0], coords[1]))
        return {"type": "Point", "coordinates": new_coords}
    
    elif geom_type == "Polygon":
        new_rings = []
        for ring in geometry["coordinates"]:
            new_ring = [list(transform_coords(pt[0], pt[1])) for pt in ring]
            new_rings.append(new_ring)
        return {"type": "Polygon", "coordinates": new_rings}
    
    elif geom_type == "LineString":
        new_coords = [list(transform_coords(pt[0], pt[1])) for pt in geometry["coordinates"]]
        return {"type": "LineString", "coordinates": new_coords}
    
    elif geom_type == "MultiPolygon":
        new_polys = []
        for poly in geometry["coordinates"]:
            new_rings = []
            for ring in poly:
                new_ring = [list(transform_coords(pt[0], pt[1])) for pt in ring]
                new_rings.append(new_ring)
            new_polys.append(new_rings)
        return {"type": "MultiPolygon", "coordinates": new_polys}
    
    return geometry


def is_cad_coordinates(geometry: dict[str, Any]) -> bool:
    """Check if geometry uses CAD coordinates (not geographic)."""
    coords = geometry.get("coordinates", [])
    if not coords:
        return False
    
    # Get first coordinate point
    if geometry.get("type") == "Point":
        pt = coords
    elif geometry.get("type") in ("Polygon", "MultiPolygon", "LineString"):
        # Navigate to first actual point
        pt = coords
        while isinstance(pt, list) and len(pt) > 0 and isinstance(pt[0], list):
            pt = pt[0]
    else:
        return False
    
    if len(pt) >= 2:
        # Geographic coords: lon typically -180 to 180, lat -90 to 90
        # CAD coords in this dataset: x ~0-200, y ~-20 to 100
        x, y = pt[0], pt[1]
        # If x is positive and not in typical lon range for US, it's likely CAD
        if x > 0 and x < 1000 and y > -1000 and y < 1000:
            return True
    return False


def transform_feature(feature: dict[str, Any]) -> dict[str, Any]:
    """Transform a feature's geometry if it uses CAD coordinates."""
    if "geometry" not in feature:
        return feature
    
    if is_cad_coordinates(feature["geometry"]):
        new_feature = {
            "type": feature.get("type", "Feature"),
            "id": feature.get("id"),  # Explicitly preserve ID
            "geometry": transform_geometry(feature["geometry"]),
            "properties": feature.get("properties", {}),
        }
        
        # Also add feature_type if present
        if "feature_type" in feature:
            new_feature["feature_type"] = feature["feature_type"]
        
        # Store ID in properties too (for MapLibre compatibility)
        # MapLibre's queryRenderedFeatures may not preserve string IDs
        if "id" in feature and feature["id"]:
            new_props = new_feature["properties"].copy() if new_feature["properties"] else {}
            new_props["feature_id"] = feature["id"]
            new_feature["properties"] = new_props
        
        # Also transform display_point in properties if present
        props = new_feature.get("properties", {})
        if props and "display_point" in props:
            dp = props["display_point"]
            if isinstance(dp, dict) and is_cad_coordinates(dp):
                new_props = props.copy()
                new_props["display_point"] = transform_geometry(dp)
                new_feature["properties"] = new_props
        
        return new_feature
    
    # Even if not CAD coordinates, ensure ID is in properties
    if "id" in feature and feature["id"]:
        new_feature = feature.copy()
        new_props = new_feature.get("properties", {}).copy() if new_feature.get("properties") else {}
        new_props["feature_id"] = feature["id"]
        new_feature["properties"] = new_props
        return new_feature
    
    return feature


@router.get("/levels")
async def get_levels() -> JSONResponse:
    """Get all floor levels."""
    data = load_geojson("level.geojson")
    
    # Extract level info for floor selector
    levels = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        name = props.get("name", f"Floor {props.get('ordinal', 0)}")
        # Handle both string and dict name formats
        if isinstance(name, dict):
            name = name.get("en", f"Floor {props.get('ordinal', 0)}")
        short_name = props.get("short_name", str(props.get("ordinal", 0)))
        if isinstance(short_name, dict):
            short_name = short_name.get("en", str(props.get("ordinal", 0)))
        
        levels.append({
            "id": feature.get("id"),
            "ordinal": props.get("ordinal", 0),
            "name": name,
            "short_name": short_name,
        })
    
    # Sort by ordinal
    levels.sort(key=lambda x: x["ordinal"])
    
    return JSONResponse(content={"levels": levels})


@router.get("/units")
async def get_all_units() -> JSONResponse:
    """Get all units (rooms) GeoJSON with transformed coordinates."""
    data = load_geojson("unit.geojson")
    
    # Transform each feature's coordinates
    transformed_features = [transform_feature(f) for f in data.get("features", [])]
    
    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": transformed_features,
    })


@router.get("/units/{level_id}")
async def get_units_by_level(level_id: str) -> JSONResponse:
    """Get units (rooms) for a specific level/floor with transformed coordinates."""
    data = load_geojson("unit.geojson")
    
    # Filter features by level_id and transform coordinates
    filtered_features = [
        transform_feature(feature) 
        for feature in data.get("features", [])
        if feature.get("properties", {}).get("level_id") == level_id
    ]
    
    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": filtered_features,
    })


@router.get("/units/floor/{floor_number}")
async def get_units_by_floor_number(floor_number: int) -> JSONResponse:
    """Get units (rooms) for a specific floor number (1-based)."""
    # First get the level_id for this floor number
    levels_data = load_geojson("level.geojson")
    
    level_id = None
    for feature in levels_data.get("features", []):
        props = feature.get("properties", {})
        # ordinal matches floor_number directly (both 1-based in this dataset)
        if props.get("ordinal") == floor_number:
            level_id = feature.get("id")
            break
    
    if not level_id:
        # Return empty if floor not found
        return JSONResponse(content={
            "type": "FeatureCollection",
            "features": [],
        })
    
    # Get units for this level and transform coordinates
    units_data = load_geojson("unit.geojson")
    
    filtered_features = [
        transform_feature(feature)
        for feature in units_data.get("features", [])
        if feature.get("properties", {}).get("level_id") == level_id
    ]
    
    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": filtered_features,
    })


@router.get("/openings")
async def get_openings() -> JSONResponse:
    """Get all openings (doors) GeoJSON with transformed coordinates."""
    data = load_geojson("opening.geojson")
    
    transformed_features = [transform_feature(f) for f in data.get("features", [])]
    
    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": transformed_features,
    })


@router.get("/openings/floor/{floor_number}")
async def get_openings_by_floor(floor_number: int) -> JSONResponse:
    """Get openings (doors) for a specific floor number."""
    # First get the level_id for this floor number
    levels_data = load_geojson("level.geojson")
    
    level_id = None
    for feature in levels_data.get("features", []):
        props = feature.get("properties", {})
        if props.get("ordinal") == floor_number:
            level_id = feature.get("id")
            break
    
    if not level_id:
        return JSONResponse(content={
            "type": "FeatureCollection",
            "features": [],
        })
    
    # Get openings for this level and transform coordinates
    openings_data = load_geojson("opening.geojson")
    
    filtered_features = [
        transform_feature(feature)
        for feature in openings_data.get("features", [])
        if feature.get("properties", {}).get("level_id") == level_id
    ]
    
    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": filtered_features,
    })


@router.get("/building")
async def get_building() -> JSONResponse:
    """Get building footprint GeoJSON."""
    data = load_geojson("building.geojson")
    return JSONResponse(content=data)


@router.get("/venue")
async def get_venue() -> JSONResponse:
    """Get venue GeoJSON."""
    data = load_geojson("venue.geojson")
    return JSONResponse(content=data)


@router.get("/amenities/floor/{floor_number}")
async def get_amenities_by_floor(floor_number: int) -> JSONResponse:
    """Get amenities (workstations, desks) for a specific floor number."""
    # First get the level_id for this floor number
    levels_data = load_geojson("level.geojson")
    
    level_id = None
    for feature in levels_data.get("features", []):
        props = feature.get("properties", {})
        if props.get("ordinal") == floor_number:
            level_id = feature.get("id")
            break
    
    if not level_id:
        return JSONResponse(content={
            "type": "FeatureCollection",
            "features": [],
        })
    
    # Get amenities for this level and transform coordinates
    amenities_data = load_geojson("amenity.geojson")
    
    filtered_features = [
        transform_feature(feature)
        for feature in amenities_data.get("features", [])
        if feature.get("properties", {}).get("level_id") == level_id
    ]
    
    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": filtered_features,
    })


@router.get("/all/floor/{floor_number}")
async def get_all_for_floor(floor_number: int) -> JSONResponse:
    """Get all GeoJSON data for a specific floor (units + openings + amenities combined)."""
    # Get units
    units_response = await get_units_by_floor_number(floor_number)
    units_data = json.loads(units_response.body)
    
    # Get openings
    openings_response = await get_openings_by_floor(floor_number)
    openings_data = json.loads(openings_response.body)
    
    # Get amenities
    amenities_response = await get_amenities_by_floor(floor_number)
    amenities_data = json.loads(amenities_response.body)
    
    # Combine features
    all_features = (units_data.get("features", []) + 
                   openings_data.get("features", []) + 
                   amenities_data.get("features", []))
    
    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": all_features,
    })


# ============================================================================
# Navigation endpoints
# ============================================================================

from app.services.navigation_service import get_navigation_graph, reload_navigation_graph
from pydantic import BaseModel


@router.post("/navigation/reload")
async def reload_navigation() -> JSONResponse:
    """Reload the navigation graph from IMDF data."""
    graph = reload_navigation_graph()
    return JSONResponse(content={
        "success": True,
        "message": "Navigation graph reloaded",
        "nodes": len(graph.nodes),
        "edges": sum(len(e) for e in graph.edges.values()),
    })


class NavigationRequest(BaseModel):
    """Request body for navigation."""
    from_unit_id: str | None = None
    from_lon: float | None = None
    from_lat: float | None = None
    to_unit_id: str
    level_id: str | None = None


class NavigationResponse(BaseModel):
    """Response for navigation request."""
    success: bool
    path: list[str]
    geometry: dict
    total_distance_meters: float
    estimated_time_seconds: int
    destination_name: str | None = None
    steps: list[dict]
    error: str | None = None


@router.post("/navigate")
async def get_navigation_path(request: NavigationRequest) -> JSONResponse:
    """
    Calculate navigation path between two points.
    
    You can specify either:
    - from_unit_id: Start from a specific room/unit
    - from_lon/from_lat: Start from a geographic point (e.g., current location)
    
    The to_unit_id is required and specifies the destination room.
    """
    graph = get_navigation_graph()
    
    # Validate destination exists
    if request.to_unit_id not in graph.nodes:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": f"Destination unit not found: {request.to_unit_id}",
                "path": [],
                "geometry": {"type": "LineString", "coordinates": []},
                "total_distance_meters": 0,
                "estimated_time_seconds": 0,
                "steps": [],
            }
        )
    
    # Find path
    if request.from_unit_id:
        # Path from unit to unit
        if request.from_unit_id not in graph.nodes:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": f"Starting unit not found: {request.from_unit_id}",
                    "path": [],
                    "geometry": {"type": "LineString", "coordinates": []},
                    "total_distance_meters": 0,
                    "estimated_time_seconds": 0,
                    "steps": [],
                }
            )
        path = graph.find_path(request.from_unit_id, request.to_unit_id)
    elif request.from_lon is not None and request.from_lat is not None:
        # Path from geographic point
        path = graph.find_path_from_point(
            request.from_lon,
            request.from_lat,
            request.to_unit_id,
            request.level_id,
        )
    else:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Must provide either from_unit_id or from_lon/from_lat",
                "path": [],
                "geometry": {"type": "LineString", "coordinates": []},
                "total_distance_meters": 0,
                "estimated_time_seconds": 0,
                "steps": [],
            }
        )
    
    if not path:
        return JSONResponse(
            content={
                "success": False,
                "error": "No path found between the specified locations",
                "path": [],
                "geometry": {"type": "LineString", "coordinates": []},
                "total_distance_meters": 0,
                "estimated_time_seconds": 0,
                "steps": [],
            }
        )
    
    # Get detailed path info
    details = graph.get_path_details(path)
    return JSONResponse(content=details)


@router.get("/navigate/from/{from_unit_id}/to/{to_unit_id}")
async def get_navigation_simple(from_unit_id: str, to_unit_id: str) -> JSONResponse:
    """Simple GET endpoint for navigation between two units."""
    graph = get_navigation_graph()
    
    path = graph.find_path(from_unit_id, to_unit_id)
    if not path:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "No path found",
                "path": [],
                "geometry": {"type": "LineString", "coordinates": []},
                "total_distance_meters": 0,
                "estimated_time_seconds": 0,
                "steps": [],
            }
        )
    
    details = graph.get_path_details(path)
    return JSONResponse(content=details)


@router.get("/units/list")
async def list_all_units() -> JSONResponse:
    """List all units with their IDs and names for navigation reference."""
    graph = get_navigation_graph()
    
    units = []
    for unit_id, node in graph.nodes.items():
        name = node.get("name", "")
        if isinstance(name, dict):
            name = name.get("en", unit_id)
        
        units.append({
            "id": unit_id,
            "name": name,
            "category": node.get("category"),
            "level_id": node.get("level_id"),
            "centroid": node.get("centroid"),
        })
    
    # Sort by level_id, then by name
    units.sort(key=lambda x: (x["level_id"] or "", x["name"]))
    
    return JSONResponse(content={"units": units, "count": len(units)})


@router.post("/navigate/reload")
async def reload_navigation() -> JSONResponse:
    """Reload the navigation graph (useful after floor plan updates)."""
    graph = reload_navigation_graph()
    return JSONResponse(content={
        "success": True,
        "message": "Navigation graph reloaded",
        "node_count": len(graph.nodes),
        "edge_count": sum(len(edges) for edges in graph.edges.values()) // 2,
    })


@router.get("/navigate/debug")
async def debug_navigation_graph() -> JSONResponse:
    """Debug endpoint to inspect the navigation graph structure."""
    graph = get_navigation_graph()
    
    # Count nodes by category
    category_counts = {}
    level_counts = {}
    for unit_id, node in graph.nodes.items():
        category = node.get("category", "unknown")
        level_id = node.get("level_id", "unknown")
        category_counts[category] = category_counts.get(category, 0) + 1
        level_counts[level_id] = level_counts.get(level_id, 0) + 1
    
    # Find stairs and elevators
    stairs = []
    elevators = []
    for unit_id, node in graph.nodes.items():
        category = node.get("category", "")
        if category == "stairs":
            stairs.append({
                "id": unit_id,
                "level_id": node.get("level_id"),
                "name": node.get("name"),
                "connections": len(graph.edges.get(unit_id, [])),
            })
        elif category == "elevator":
            elevators.append({
                "id": unit_id,
                "level_id": node.get("level_id"),
                "name": node.get("name"),
                "connections": len(graph.edges.get(unit_id, [])),
            })
    
    return JSONResponse(content={
        "total_nodes": len(graph.nodes),
        "total_edges": sum(len(edges) for edges in graph.edges.values()) // 2,
        "category_counts": category_counts,
        "level_counts": level_counts,
        "stairs": stairs,
        "elevators": elevators,
        "stairs_count": len(stairs),
        "elevators_count": len(elevators),
    })


@router.post("/navigate/force-connect-floors")
async def force_connect_floors() -> JSONResponse:
    """Force connection of stairs and elevators across floors."""
    graph = get_navigation_graph()
    
    # Find all stairs by floor
    stairs_by_floor = {}
    elevators_by_floor = {}
    
    for unit_id, node in graph.nodes.items():
        category = node.get("category", "")
        level_id = node.get("level_id", "")
        
        if category == "stairs":
            stairs_by_floor.setdefault(level_id, []).append(unit_id)
        elif category == "elevator":
            elevators_by_floor.setdefault(level_id, []).append(unit_id)
    
    connections_made = []
    
    # Get sorted list of floor levels
    floor_levels = sorted(stairs_by_floor.keys() | elevators_by_floor.keys())
    
    # Connect all stairs across floors
    for i, level1 in enumerate(floor_levels):
        for level2 in floor_levels[i+1:]:  # Only connect to higher floors
            stairs1 = stairs_by_floor.get(level1, [])
            stairs2 = stairs_by_floor.get(level2, [])
            
            for s1 in stairs1:
                for s2 in stairs2:
                    # Add bidirectional edge (always add, don't check if exists)
                    if s2 not in graph.edges.get(s1, []):
                        graph.edges.setdefault(s1, []).append(s2)
                    if s1 not in graph.edges.get(s2, []):
                        graph.edges.setdefault(s2, []).append(s1)
                    
                    graph.edge_weights[(s1, s2)] = 20
                    graph.edge_weights[(s2, s1)] = 20
                    connections_made.append(f"Stairs: {s1} ({level1}) ↔ {s2} ({level2})")
    
    # Connect all elevators across floors
    for i, level1 in enumerate(floor_levels):
        for level2 in floor_levels[i+1:]:
            elevs1 = elevators_by_floor.get(level1, [])
            elevs2 = elevators_by_floor.get(level2, [])
            
            for e1 in elevs1:
                for e2 in elevs2:
                    if e2 not in graph.edges.get(e1, []):
                        graph.edges.setdefault(e1, []).append(e2)
                    if e1 not in graph.edges.get(e2, []):
                        graph.edges.setdefault(e2, []).append(e1)
                    
                    graph.edge_weights[(e1, e2)] = 15
                    graph.edge_weights[(e2, e1)] = 15
                    connections_made.append(f"Elevator: {e1} ({level1}) ↔ {e2} ({level2})")
    
    return JSONResponse(content={
        "success": True,
        "connections_made": connections_made,
        "total_connections": len(connections_made),
        "stairs_by_floor": {k: len(v) for k, v in stairs_by_floor.items()},
        "elevators_by_floor": {k: len(v) for k, v in elevators_by_floor.items()},
    })


@router.post("/navigate/smart")
async def smart_navigate(request: NavigationRequest) -> JSONResponse:
    """
    Smart navigation that auto-selects a good starting point if not specified.
    This provides a simpler, one-click navigation experience.
    For multi-floor navigation, always starts from Main Entrance on Floor 1.
    """
    graph = get_navigation_graph()
    
    # Validate destination exists
    if request.to_unit_id not in graph.nodes:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": f"Destination not found: {request.to_unit_id}",
                "path": [],
                "geometry": {"type": "LineString", "coordinates": []},
                "total_distance_meters": 0,
                "estimated_time_seconds": 0,
                "steps": [],
            }
        )
    
    # Auto-select starting point if not provided
    from_unit = request.from_unit_id
    if not from_unit:
        # Priority order for starting points (across ALL floors for multi-floor support):
        # 1. Main Entrance on Floor 1 (ground level)
        # 2. Any entrance on Floor 1
        # 3. Reception on Floor 1
        # 4. Main entrance on any floor
        # 5. Any entrance on any floor
        # 6. Elevator/Stairs on same floor as destination
        # 7. Any walkway on same floor as destination
        
        dest_level = graph.nodes[request.to_unit_id].get("level_id")
        candidates = []
        
        for unit_id, node in graph.nodes.items():
            category = node.get("category", "")
            level_id = node.get("level_id", "")
            name = node.get("name", "")
            if isinstance(name, dict):
                name = name.get("en", "").lower()
            else:
                name = str(name).lower()
            
            # Check if this is floor 1 (ground level)
            is_ground_floor = level_id in ("level-1", "level_1", "level-01", "1")
            
            # Prioritize based on category, name, and floor
            if is_ground_floor and "main" in name and "entrance" in name:
                candidates.append((1, unit_id))  # Highest: Main Entrance on Floor 1
            elif is_ground_floor and category == "entrance":
                candidates.append((2, unit_id))  # Entrance on Floor 1
            elif is_ground_floor and category == "reception":
                candidates.append((3, unit_id))  # Reception on Floor 1
            elif "main" in name and "entrance" in name:
                candidates.append((4, unit_id))  # Main entrance on any floor
            elif category == "entrance":
                candidates.append((5, unit_id))  # Any entrance
            elif node.get("level_id") == dest_level and category in ("elevator", "stairs"):
                candidates.append((6, unit_id))  # Elevator/stairs on destination floor
            elif node.get("level_id") == dest_level and category == "walkway":
                candidates.append((7, unit_id))  # Walkway on destination floor
            elif node.get("level_id") == dest_level:
                candidates.append((8, unit_id))  # Any room on destination floor
        
        # Sort by priority and pick the first
        if candidates:
            candidates.sort(key=lambda x: x[0])
            from_unit = candidates[0][1]
        else:
            # Last resort: use any node on any level
            from_unit = list(graph.nodes.keys())[0] if graph.nodes else None
    
    # Validate starting point exists
    if not from_unit or from_unit not in graph.nodes:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": f"Could not determine a starting point",
                "path": [],
                "geometry": {"type": "LineString", "coordinates": []},
                "total_distance_meters": 0,
                "estimated_time_seconds": 0,
                "steps": [],
            }
        )
    
    # Find path
    path = graph.find_path(from_unit, request.to_unit_id)
    
    if not path:
        return JSONResponse(
            content={
                "success": False,
                "error": "No path found to destination",
                "path": [],
                "geometry": {"type": "LineString", "coordinates": []},
                "total_distance_meters": 0,
                "estimated_time_seconds": 0,
                "steps": [],
            }
        )
    
    # Get detailed path info
    details = graph.get_path_details(path)
    details["from_unit_id"] = from_unit
    
    from_name = graph.nodes[from_unit].get("name", "Start")
    if isinstance(from_name, dict):
        from_name = from_name.get("en", "Start")
    details["from_unit_name"] = from_name
    
    return JSONResponse(content=details)
