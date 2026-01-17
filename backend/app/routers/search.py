"""Search API router - AI-powered wayfinding search."""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.ai_service import ParsedIntent, get_ai_service
from app.services.spatial_service import SpatialService

router = APIRouter(prefix="/api/search", tags=["search"])
logger = logging.getLogger(__name__)

# Path to IMDF GeoJSON files
_base_dir = Path(__file__).parent.parent.parent / "floorplan_geojson"
if (_base_dir / "imdf_package").exists():
    IMDF_DIR = _base_dir / "imdf_package"
else:
    IMDF_DIR = _base_dir / "imdf_output"


def search_imdf_units(
    query: str | None = None,
    category: str | None = None,
    floor: int | None = None,
    limit: int = 10,
    search_occupants: bool = True,
) -> list[dict[str, Any]]:
    """Search IMDF unit.geojson for matching rooms, employees, and occupants."""
    results = []
    
    try:
        unit_file = IMDF_DIR / "unit.geojson"
        level_file = IMDF_DIR / "level.geojson"
        
        if not unit_file.exists():
            return results
        
        with open(unit_file) as f:
            units_data = json.load(f)
        
        # Load levels to map level_id to floor number
        level_map = {}  # level_id -> ordinal
        if level_file.exists():
            with open(level_file) as f:
                levels_data = json.load(f)
                for feature in levels_data.get("features", []):
                    level_id = feature.get("id")
                    ordinal = feature.get("properties", {}).get("ordinal", 1)
                    level_map[level_id] = ordinal
        
        # Normalize search terms
        query_lower = query.lower() if query else None
        category_lower = category.lower() if category else None
        
        # Split query into words for better matching
        query_words = query_lower.split() if query_lower else []
        
        # Map category names to IMDF categories (updated for new schema)
        category_mappings = {
            "huddle": ["huddleroom"],
            "conference": ["conferenceroom"],
            "meeting": ["conferenceroom", "huddleroom"],
            "office": ["office", "privateoffice"],
            "private office": ["privateoffice"],
            "workspace": ["workspace"],
            "open workspace": ["workspace"],
            "restroom": ["restroom"],
            "bathroom": ["restroom"],
            "kitchen": ["breakroom"],
            "break": ["breakroom"],
            "cafe": ["breakroom"],
            "reception": ["reception"],
            "lobby": ["reception"],
            "entrance": ["entrance"],
            "storage": ["storage"],
            "server": ["serverroom"],
            "elevator": ["elevator"],
            "stairs": ["stairs"],
            "lounge": ["lounge"],
            "wellness": ["wellness"],
            "phone": ["phonebooth"],
            "mail": ["mailroom"],
            "copy": ["copyroom"],
            "print": ["copyroom"],
            "hallway": ["walkway"],
            "corridor": ["walkway"],
        }
        
        # Job titles to recognize for person searches
        job_titles = {
            "ceo": "Chief Executive Officer",
            "cto": "Chief Technology Officer", 
            "cfo": "Chief Financial Officer",
            "coo": "Chief Operating Officer",
            "vp": "Vice President",
            "president": "President",
            "director": "Director",
            "manager": "Manager",
            "lead": "Lead",
            "senior": "Senior",
            "engineer": "Engineer",
            "developer": "Developer",
            "designer": "Designer",
            "analyst": "Analyst",
            "hr": "Human Resources",
            "finance": "Finance",
            "marketing": "Marketing",
            "sales": "Sales",
            "executive": "Executive",
        }
        
        # Find matching IMDF categories
        target_categories = []
        if category_lower:
            for key, cats in category_mappings.items():
                if key in category_lower.lower().replace(" ", "").replace("_", ""):
                    target_categories.extend(cats)
        
        # Score-based matching for better results
        scored_results = []
        
        for feature in units_data.get("features", []):
            props = feature.get("properties", {})
            unit_category = props.get("category", "")
            
            # Get name (handle both string and dict formats)
            name = props.get("name", "")
            if isinstance(name, dict):
                name = name.get("en", "")
            name_lower = name.lower() if name else ""
            
            # Get alt_name if available
            alt_name = props.get("alt_name", "")
            alt_name_lower = alt_name.lower() if alt_name else ""
            
            # Get floor number from level_id
            level_id = props.get("level_id")
            unit_floor = level_map.get(level_id, 1)
            
            # Filter by floor if specified
            if floor is not None and unit_floor != floor:
                continue
            
            score = 0
            matched_context = ""
            result_type = "room"
            
            # Match by exact name
            if query_lower and query_lower == name_lower:
                score += 100
                matched_context = f"Exact match: {name}"
            # Match by partial name
            elif query_lower and query_lower in name_lower:
                score += 50
                matched_context = f"Name contains: {query}"
            # Match by alt_name
            elif query_lower and alt_name_lower and query_lower in alt_name_lower:
                score += 40
                matched_context = f"Also known as: {alt_name}"
            
            # Match by individual words in query
            if query_words:
                for word in query_words:
                    if len(word) > 2:  # Skip short words
                        if word in name_lower:
                            score += 20
                        if word in alt_name_lower:
                            score += 15
            
            # Match by category
            if target_categories and unit_category in target_categories:
                score += 30
                matched_context = matched_context or f"Category: {unit_category}"
            
            # Match by category in query
            if query_lower:
                for key in category_mappings:
                    if key in query_lower and unit_category in category_mappings[key]:
                        score += 25
                        matched_context = matched_context or f"Matched category: {key}"
                        break
            
            # Search for employees/seats within workspace
            if query_lower and search_occupants:
                seats = props.get("seats", [])
                for seat in seats:
                    employee_name = seat.get("employee", "").lower()
                    employee_title = seat.get("title", "").lower()
                    seat_id = seat.get("id", "").lower()
                    
                    # Check for job title match
                    for title_key, title_full in job_titles.items():
                        if title_key in query_lower:
                            if title_key in employee_title or title_full.lower() in employee_title:
                                score += 80
                                result_type = "employee"
                                matched_context = f"Found {seat.get('employee', '')} ({seat.get('title', '')})"
                                name = f"{seat.get('employee', '')} - {seat.get('title', '')}"
                                break
                    
                    # Check for name match
                    for word in query_words:
                        if len(word) > 2 and word in employee_name:
                            score += 60
                            result_type = "employee"
                            matched_context = f"Employee: {seat.get('employee', '')}"
                            name = f"{seat.get('employee', '')} ({name})"
                            break
                    
                    if query_lower in seat_id:
                        score += 20
            
            # Also search by occupant field (for private offices)
            # Handle format: "Name - Title" or separate fields
            if query_lower and search_occupants:
                occupant_raw = props.get("occupant", "")
                occupant_title = props.get("occupant_title", "")
                
                # Parse "Name - Title" format
                occupant_name = ""
                if " - " in occupant_raw:
                    parts = occupant_raw.split(" - ", 1)
                    occupant_name = parts[0].strip()
                    if not occupant_title and len(parts) > 1:
                        occupant_title = parts[1].strip()
                else:
                    occupant_name = occupant_raw
                
                occupant_lower = occupant_raw.lower()
                occupant_name_lower = occupant_name.lower()
                occupant_title_lower = occupant_title.lower()
                
                # Check for job title match in occupant
                for title_key, title_full in job_titles.items():
                    if title_key in query_lower:
                        # Check both in combined string and separate title
                        if (title_key in occupant_lower or 
                            title_key in occupant_title_lower or 
                            title_full.lower() in occupant_lower or
                            title_full.lower() in occupant_title_lower):
                            score += 90  # High score for title match
                            result_type = "employee"
                            display_title = occupant_title or (occupant_raw.split(" - ")[1] if " - " in occupant_raw else "")
                            matched_context = f"Found {occupant_name} ({display_title})"
                            name = f"{occupant_name} - {display_title}" if display_title else occupant_name
                            break
                
                # Check for name match in occupant
                if score == 0 or result_type != "employee":  # Only if not already matched
                    for word in query_words:
                        if len(word) > 2 and word in occupant_name_lower:
                            score += 70
                            result_type = "employee"
                            display_title = occupant_title or (occupant_raw.split(" - ")[1] if " - " in occupant_raw else "")
                            matched_context = f"Found: {occupant_name}"
                            name = f"{occupant_name} - {display_title}" if display_title else occupant_name
                            break
            
            # Only include if there's a match
            if score > 0:
                # Get display point or compute from geometry centroid
                display_point = props.get("display_point", {})
                if display_point:
                    coords = display_point.get("coordinates", [0, 0])
                else:
                    # Use first coordinate as fallback
                    geom = feature.get("geometry", {})
                    coords_list = geom.get("coordinates", [[]])
                    if coords_list and coords_list[0]:
                        coords = coords_list[0][0] if coords_list[0] else [0, 0]
                    else:
                        coords = [0, 0]
                
                scored_results.append({
                    "score": score,
                    "result": {
                        "type": result_type,
                        "id": feature.get("id"),
                        "name": name,
                        "display_name": name,
                        "floor": unit_floor,
                        "building": "Main Building",
                        "feature_id": feature.get("id"),
                        "category": unit_category,
                        "x": coords[0],
                        "y": coords[1],
                        "matched_context": matched_context,
                        "capacity": props.get("capacity"),
                        "amenities": props.get("amenities", []),
                    }
                })
        
        # Sort by score descending and return top results
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        results = [r["result"] for r in scored_results[:limit]]
    
    except Exception as e:
        logger.error(f"Error searching IMDF units: {e}")
    
    return results


class SearchRequest(BaseModel):
    """Search request body."""

    query: str
    current_x: float | None = None
    current_y: float | None = None
    floor: int | None = None


class SearchResponse(BaseModel):
    """Search response with intent and results."""

    query: str
    intent: ParsedIntent
    results: list[dict[str, Any]]
    result_count: int


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    """
    AI-powered search endpoint.

    1. Parses natural language query using OpenRouter
    2. Queries PostGIS for matching locations
    3. Falls back to IMDF GeoJSON search if no DB results
    4. Also performs direct text search for comprehensive results
    5. Returns results with FeatureIDs for map highlighting
    """
    # Parse intent using AI
    ai_service = get_ai_service()
    intent = await ai_service.parse_intent(request.query)

    # Override floor if explicitly provided in request
    if request.floor is not None:
        intent.floor = request.floor

    # Build current location tuple if provided
    current_location = None
    if request.current_x is not None and request.current_y is not None:
        current_location = (request.current_x, request.current_y)

    results = []
    
    # Try database first
    try:
        spatial_service = SpatialService(session)
        results = await spatial_service.find_by_intent(
            intent=intent,
            current_location=current_location,
            limit=10,
        )
    except Exception as e:
        logger.warning(f"Database search failed: {e}")
    
    # Search IMDF data with AI-parsed intent
    imdf_results = []
    if intent.target_name or intent.target_category:
        logger.info(f"Searching IMDF with intent: name={intent.target_name}, category={intent.target_category}")
        imdf_results = search_imdf_units(
            query=intent.target_name,
            category=str(intent.target_category) if intent.target_category else None,
            floor=intent.floor,
            limit=10,
        )
    
    # Also do a direct text search on the original query for comprehensive results
    direct_results = search_imdf_units(
        query=request.query,
        category=None,
        floor=intent.floor,
        limit=10,
        search_occupants=True,
    )
    
    # Combine results, avoiding duplicates
    seen_ids = {r.get("id") or r.get("feature_id") for r in results}
    
    for r in imdf_results:
        rid = r.get("id") or r.get("feature_id")
        if rid not in seen_ids:
            results.append(r)
            seen_ids.add(rid)
    
    for r in direct_results:
        rid = r.get("id") or r.get("feature_id")
        if rid not in seen_ids:
            results.append(r)
            seen_ids.add(rid)
    
    # Limit final results
    results = results[:15]

    return SearchResponse(
        query=request.query,
        intent=intent,
        results=results,
        result_count=len(results),
    )


@router.get("/quick", response_model=SearchResponse)
async def quick_search(
    q: str = Query(..., min_length=1, description="Search query"),
    floor: int | None = Query(None, description="Filter by floor"),
    x: float | None = Query(None, description="Current X coordinate"),
    y: float | None = Query(None, description="Current Y coordinate"),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    """Quick GET-based search endpoint."""
    request = SearchRequest(
        query=q,
        current_x=x,
        current_y=y,
        floor=floor,
    )
    return await search(request, session)
