"""Floor Plan Import Script.

Imports DWG/DXF floor plan files into PostGIS database.

DWG files must first be converted to DXF format (using AutoCAD, LibreCAD, 
or online converters) as DWG is a proprietary format.

Usage:
    python -m app.scripts.import_floorplan data/floorplans/floor1.dxf --floor 1
    python -m app.scripts.import_floorplan data/floorplans/ --batch

Supported layer naming conventions:
    - ROOMS or ROOM_* : Room polygons
    - WALLS or WALL_* : Wall geometry
    - DOORS or DOOR_* : Door locations
    - POI or POI_* : Points of interest
    - PATH or NAV_* : Navigation paths/walkways
    - DESK or DESK_* : Desk locations
    - TEXT or LABEL_* : Room labels/names
"""

import argparse
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf.entities import LWPolyline, Circle, Line, Text, MText, Insert
from shapely.geometry import Point, Polygon, LineString, MultiLineString, box
from shapely.ops import unary_union
from geoalchemy2.shape import from_shape
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, engine
from app.models.room import Room, RoomCategory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Layer name patterns for auto-detection
LAYER_PATTERNS = {
    "rooms": re.compile(r"^(ROOM|ROOMS|SPACE|AREA|A-AREA|A-ROOM)", re.IGNORECASE),
    "walls": re.compile(r"^(WALL|WALLS|A-WALL|STRUCT)", re.IGNORECASE),
    "doors": re.compile(r"^(DOOR|DOORS|A-DOOR|OPENING)", re.IGNORECASE),
    "paths": re.compile(r"^(PATH|NAV|WALK|CORRIDOR|HALLWAY)", re.IGNORECASE),
    "desks": re.compile(r"^(DESK|DESKS|FURNITURE|WORKSTATION)", re.IGNORECASE),
    "labels": re.compile(r"^(TEXT|LABEL|NAME|ANNOTATION|A-ANNO)", re.IGNORECASE),
    "pois": re.compile(r"^(POI|POINT|MARKER|SYMBOL)", re.IGNORECASE),
}

# Room category detection from names
CATEGORY_KEYWORDS = {
    RoomCategory.MEETING_ROOM: ["meeting", "conference", "board"],
    RoomCategory.FOCUS_ROOM: ["focus", "quiet", "private"],
    RoomCategory.HUDDLE_SPACE: ["huddle", "collab"],
    RoomCategory.PHONE_BOOTH: ["phone", "booth", "call"],
    RoomCategory.CAFETERIA: ["cafe", "cafeteria", "canteen", "dining"],
    RoomCategory.KITCHEN: ["kitchen", "pantry", "break"],
    RoomCategory.RESTROOM: ["restroom", "toilet", "wc", "bathroom", "lavatory"],
    RoomCategory.ELEVATOR: ["elevator", "lift"],
    RoomCategory.STAIRS: ["stair", "stairs", "stairwell"],
    RoomCategory.RECEPTION: ["reception", "lobby", "entrance"],
    RoomCategory.GYM: ["gym", "fitness", "exercise"],
    RoomCategory.IT_HELPDESK: ["it", "helpdesk", "tech support"],
    RoomCategory.HR_OFFICE: ["hr", "human resource"],
    RoomCategory.TRAINING_ROOM: ["training", "learn", "classroom"],
    RoomCategory.STORAGE: ["storage", "store", "closet"],
    RoomCategory.PRINT_STATION: ["print", "copy", "mail"],
    RoomCategory.LIBRARY: ["library", "reading"],
    RoomCategory.WELLNESS_ROOM: ["wellness", "meditation", "rest"],
    RoomCategory.MOTHERS_ROOM: ["mother", "nursing", "lactation"],
    RoomCategory.PRAYER_ROOM: ["prayer", "worship", "meditation"],
}


class FloorPlanImporter:
    """Import DXF floor plans into PostGIS."""

    def __init__(
        self,
        floor: int,
        building: str = "HQ",
        scale_factor: float = 1.0,
        origin_offset: tuple[float, float] = (0.0, 0.0),
    ):
        """
        Initialize importer.
        
        Args:
            floor: Floor number
            building: Building identifier
            scale_factor: Scale CAD units to meters (e.g., 0.001 for mm to m)
            origin_offset: (x, y) offset to align with geo-coordinates
        """
        self.floor = floor
        self.building = building
        self.scale_factor = scale_factor
        self.origin_offset = origin_offset
        
        self.rooms: list[dict[str, Any]] = []
        self.walls: list[LineString] = []
        self.paths: list[LineString] = []
        self.pois: list[dict[str, Any]] = []
        self.labels: dict[tuple[float, float], str] = {}

    def transform_point(self, x: float, y: float) -> tuple[float, float]:
        """Transform CAD coordinates to database coordinates."""
        return (
            (x * self.scale_factor) + self.origin_offset[0],
            (y * self.scale_factor) + self.origin_offset[1],
        )

    def transform_coords(self, coords: list[tuple]) -> list[tuple[float, float]]:
        """Transform a list of coordinates."""
        return [self.transform_point(x, y) for x, y, *_ in coords]

    def detect_layer_type(self, layer_name: str) -> str | None:
        """Detect the type of geometry based on layer name."""
        for layer_type, pattern in LAYER_PATTERNS.items():
            if pattern.match(layer_name):
                return layer_type
        return None

    def detect_room_category(self, name: str) -> RoomCategory:
        """Detect room category from its name."""
        name_lower = name.lower()
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in name_lower for kw in keywords):
                return category
        return RoomCategory.OTHER

    def parse_dxf(self, filepath: Path) -> None:
        """Parse a DXF file and extract geometry."""
        logger.info(f"Parsing DXF file: {filepath}")
        
        doc = ezdxf.readfile(str(filepath))
        msp = doc.modelspace()
        
        # First pass: collect all text labels for room naming
        for entity in msp:
            layer_type = self.detect_layer_type(entity.dxf.layer)
            
            if isinstance(entity, (Text, MText)):
                try:
                    if isinstance(entity, MText):
                        text_content = entity.plain_text()
                    else:
                        text_content = entity.dxf.text
                    
                    insert = entity.dxf.insert
                    pos = self.transform_point(insert.x, insert.y)
                    self.labels[pos] = text_content.strip()
                except Exception as e:
                    logger.warning(f"Error parsing text entity: {e}")
        
        # Second pass: collect geometry
        for entity in msp:
            layer_name = entity.dxf.layer
            layer_type = self.detect_layer_type(layer_name)
            
            try:
                if isinstance(entity, LWPolyline):
                    coords = self.transform_coords(list(entity.get_points()))
                    
                    if entity.closed and len(coords) >= 3:
                        # Closed polyline = room or area
                        if layer_type == "rooms" or layer_type is None:
                            self._add_room_from_polygon(coords, layer_name)
                    else:
                        # Open polyline = wall or path
                        if len(coords) >= 2:
                            line = LineString(coords)
                            if layer_type == "paths":
                                self.paths.append(line)
                            else:
                                self.walls.append(line)
                
                elif isinstance(entity, Line):
                    start = self.transform_point(entity.dxf.start.x, entity.dxf.start.y)
                    end = self.transform_point(entity.dxf.end.x, entity.dxf.end.y)
                    line = LineString([start, end])
                    
                    if layer_type == "paths":
                        self.paths.append(line)
                    else:
                        self.walls.append(line)
                
                elif isinstance(entity, Circle):
                    center = self.transform_point(entity.dxf.center.x, entity.dxf.center.y)
                    radius = entity.dxf.radius * self.scale_factor
                    
                    if layer_type == "pois" or layer_type == "desks":
                        self.pois.append({
                            "point": Point(center),
                            "radius": radius,
                            "layer": layer_name,
                            "type": layer_type or "poi",
                        })
                    else:
                        # Create circular room approximation
                        circle_poly = Point(center).buffer(radius, resolution=16)
                        self._add_room_from_shapely(circle_poly, layer_name)
                
            except Exception as e:
                logger.warning(f"Error processing entity on layer {layer_name}: {e}")
        
        logger.info(
            f"Parsed: {len(self.rooms)} rooms, {len(self.walls)} walls, "
            f"{len(self.paths)} paths, {len(self.pois)} POIs"
        )

    def _add_room_from_polygon(self, coords: list[tuple], layer_name: str) -> None:
        """Create a room from polygon coordinates."""
        try:
            # Ensure polygon is closed
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            
            polygon = Polygon(coords)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)  # Fix invalid geometry
            
            if polygon.area < 0.1:  # Skip tiny polygons
                return
            
            self._add_room_from_shapely(polygon, layer_name)
        except Exception as e:
            logger.warning(f"Invalid polygon on layer {layer_name}: {e}")

    def _add_room_from_shapely(self, polygon: Polygon, layer_name: str) -> None:
        """Add a room from a Shapely polygon."""
        centroid = polygon.centroid
        
        # Try to find a label near the centroid
        room_name = self._find_nearest_label(centroid.x, centroid.y, polygon)
        
        if not room_name:
            room_name = f"Room_{len(self.rooms) + 1}"
        
        category = self.detect_room_category(room_name)
        
        self.rooms.append({
            "polygon": polygon,
            "centroid": centroid,
            "name": room_name,
            "layer": layer_name,
            "category": category,
            "area": polygon.area,
        })

    def _find_nearest_label(
        self, x: float, y: float, polygon: Polygon, max_distance: float = 50.0
    ) -> str | None:
        """Find the nearest text label to a point, preferring labels inside the polygon."""
        best_label = None
        best_distance = max_distance
        
        for (lx, ly), label_text in self.labels.items():
            point = Point(lx, ly)
            
            # Prefer labels inside the polygon
            if polygon.contains(point):
                return label_text
            
            # Otherwise find nearest
            distance = point.distance(Point(x, y))
            if distance < best_distance:
                best_distance = distance
                best_label = label_text
        
        return best_label

    async def import_to_database(self) -> dict[str, int]:
        """Import parsed data to PostgreSQL/PostGIS."""
        stats = {"rooms": 0, "navigation_nodes": 0, "navigation_edges": 0}
        
        async with async_session_maker() as session:
            # Import rooms
            for room_data in self.rooms:
                try:
                    room = Room(
                        name=self._generate_room_id(room_data["name"]),
                        display_name=room_data["name"],
                        category=room_data["category"],
                        floor=self.floor,
                        building=self.building,
                        capacity=self._estimate_capacity(room_data["area"]),
                        amenities="",
                        is_bookable=room_data["category"] in [
                            RoomCategory.MEETING_ROOM,
                            RoomCategory.FOCUS_ROOM,
                            RoomCategory.HUDDLE_SPACE,
                            RoomCategory.TRAINING_ROOM,
                        ],
                        is_accessible=True,
                        boundary=from_shape(room_data["polygon"], srid=4326),
                        centroid=from_shape(room_data["centroid"], srid=4326),
                        feature_id=f"FEAT_{self.building}_F{self.floor}_{stats['rooms'] + 1:03d}",
                    )
                    session.add(room)
                    stats["rooms"] += 1
                except Exception as e:
                    logger.warning(f"Failed to import room {room_data['name']}: {e}")
            
            # Import navigation paths as edges
            if self.paths:
                await self._import_navigation_graph(session, stats)
            
            await session.commit()
        
        logger.info(f"Import complete: {stats}")
        return stats

    def _generate_room_id(self, name: str) -> str:
        """Generate a URL-safe room ID from name."""
        safe_name = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
        return f"{safe_name}-f{self.floor}"

    def _estimate_capacity(self, area: float) -> int:
        """Estimate room capacity from area (assuming ~5 sq meters per person)."""
        return max(1, int(area / 5))

    async def _import_navigation_graph(
        self, session: AsyncSession, stats: dict[str, int]
    ) -> None:
        """Import navigation paths as a graph for wayfinding."""
        # Create navigation tables if they don't exist
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS navigation_nodes (
                id SERIAL PRIMARY KEY,
                floor INTEGER NOT NULL,
                building VARCHAR(50) NOT NULL,
                geom GEOMETRY(POINT, 4326),
                node_type VARCHAR(50),
                room_id INTEGER REFERENCES rooms(id),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS navigation_edges (
                id SERIAL PRIMARY KEY,
                floor INTEGER NOT NULL,
                building VARCHAR(50) NOT NULL,
                from_node_id INTEGER REFERENCES navigation_nodes(id),
                to_node_id INTEGER REFERENCES navigation_nodes(id),
                geom GEOMETRY(LINESTRING, 4326),
                distance FLOAT,
                edge_type VARCHAR(50),
                is_accessible BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        # Merge all paths and extract unique nodes
        node_coords: dict[tuple[float, float], int] = {}
        
        for path in self.paths:
            coords = list(path.coords)
            for coord in coords:
                rounded = (round(coord[0], 6), round(coord[1], 6))
                if rounded not in node_coords:
                    # Insert node
                    result = await session.execute(
                        text("""
                            INSERT INTO navigation_nodes (floor, building, geom, node_type)
                            VALUES (:floor, :building, ST_SetSRID(ST_MakePoint(:x, :y), 4326), 'path')
                            RETURNING id
                        """),
                        {"floor": self.floor, "building": self.building, "x": rounded[0], "y": rounded[1]}
                    )
                    node_id = result.scalar()
                    node_coords[rounded] = node_id
                    stats["navigation_nodes"] += 1
        
        # Create edges between consecutive nodes in each path
        for path in self.paths:
            coords = list(path.coords)
            for i in range(len(coords) - 1):
                start = (round(coords[i][0], 6), round(coords[i][1], 6))
                end = (round(coords[i + 1][0], 6), round(coords[i + 1][1], 6))
                
                if start in node_coords and end in node_coords:
                    edge_geom = LineString([coords[i], coords[i + 1]])
                    distance = edge_geom.length
                    
                    await session.execute(
                        text("""
                            INSERT INTO navigation_edges 
                            (floor, building, from_node_id, to_node_id, geom, distance, edge_type)
                            VALUES (:floor, :building, :from_id, :to_id, 
                                    ST_SetSRID(ST_MakeLine(
                                        ST_MakePoint(:x1, :y1), 
                                        ST_MakePoint(:x2, :y2)
                                    ), 4326), 
                                    :distance, 'walkway')
                        """),
                        {
                            "floor": self.floor,
                            "building": self.building,
                            "from_id": node_coords[start],
                            "to_id": node_coords[end],
                            "x1": start[0], "y1": start[1],
                            "x2": end[0], "y2": end[1],
                            "distance": distance,
                        }
                    )
                    stats["navigation_edges"] += 1


async def import_single_file(
    filepath: Path,
    floor: int,
    building: str = "HQ",
    scale: float = 1.0,
) -> dict[str, int]:
    """Import a single DXF file."""
    importer = FloorPlanImporter(
        floor=floor,
        building=building,
        scale_factor=scale,
    )
    importer.parse_dxf(filepath)
    return await importer.import_to_database()


async def import_batch(
    directory: Path,
    building: str = "HQ",
    scale: float = 1.0,
) -> dict[str, int]:
    """Import all DXF files in a directory."""
    total_stats = {"rooms": 0, "navigation_nodes": 0, "navigation_edges": 0}
    
    dxf_files = sorted(directory.glob("*.dxf"))
    
    for i, filepath in enumerate(dxf_files, start=1):
        # Try to extract floor number from filename
        match = re.search(r"(\d+)", filepath.stem)
        floor = int(match.group(1)) if match else i
        
        logger.info(f"Importing {filepath.name} as floor {floor}")
        stats = await import_single_file(filepath, floor, building, scale)
        
        for key in total_stats:
            total_stats[key] += stats[key]
    
    return total_stats


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Import DXF floor plans into PostGIS database"
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to DXF file or directory containing DXF files",
    )
    parser.add_argument(
        "--floor", "-f",
        type=int,
        default=1,
        help="Floor number (for single file import)",
    )
    parser.add_argument(
        "--building", "-b",
        type=str,
        default="HQ",
        help="Building identifier",
    )
    parser.add_argument(
        "--scale", "-s",
        type=float,
        default=1.0,
        help="Scale factor (e.g., 0.001 to convert mm to m)",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Import all DXF files in directory",
    )
    
    args = parser.parse_args()
    
    if not args.path.exists():
        print(f"Error: Path not found: {args.path}")
        return
    
    if args.batch or args.path.is_dir():
        if not args.path.is_dir():
            print("Error: --batch requires a directory path")
            return
        stats = asyncio.run(import_batch(args.path, args.building, args.scale))
    else:
        if args.path.suffix.lower() not in [".dxf"]:
            print("Error: File must be a .dxf file")
            print("Convert your .dwg file to .dxf using AutoCAD, LibreCAD, or an online converter")
            return
        stats = asyncio.run(import_single_file(args.path, args.floor, args.building, args.scale))
    
    print(f"\nImport complete!")
    print(f"  Rooms imported: {stats['rooms']}")
    print(f"  Navigation nodes: {stats['navigation_nodes']}")
    print(f"  Navigation edges: {stats['navigation_edges']}")


if __name__ == "__main__":
    main()
