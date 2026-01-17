"""DWG/DXF to IMDF Converter for Azure Maps Creator.

Converts floor plan CAD files to Indoor Mapping Data Format (IMDF)
for upload to Azure Maps Creator.

Workflow:
    1. DWG → DXF (external tool)
    2. DXF → GeoJSON (this script)
    3. GeoJSON → IMDF (this script)
    4. IMDF → Azure Maps Creator (Azure CLI or API)

Usage:
    # Convert single floor
    python -m app.scripts.convert_to_imdf floor1.dxf --floor 1 --output ./imdf_output

    # Convert multiple floors
    python -m app.scripts.convert_to_imdf ./floors/ --batch --output ./imdf_output

    # Then upload to Azure Maps:
    az maps creator dataset create --resource-group <rg> --account-name <account> \\
        --input-path ./imdf_output.zip
"""

import argparse
import json
import logging
import re
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf.entities import LWPolyline, Circle, Line, Text, MText
from shapely.geometry import Point, Polygon, LineString, mapping
from shapely.ops import unary_union

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# IMDF category mappings
IMDF_CATEGORIES = {
    "meeting": "conferenceroom",
    "conference": "conferenceroom",
    "huddle": "huddle",
    "focus": "privateroom",
    "office": "office",
    "desk": "workspace",
    "restroom": "restroom",
    "toilet": "restroom",
    "bathroom": "restroom",
    "elevator": "elevator",
    "lift": "elevator",
    "stairs": "stairs",
    "stairwell": "stairs",
    "lobby": "lobby",
    "reception": "reception",
    "cafeteria": "cafeteria",
    "cafe": "cafe",
    "kitchen": "kitchen",
    "gym": "fitnessroom",
    "fitness": "fitnessroom",
    "storage": "storage",
    "server": "serverroom",
    "it": "serverroom",
    "parking": "parking",
    "garage": "parking",
    "library": "library",
    "lounge": "lounge",
    "break": "lounge",
    "mail": "mailroom",
    "print": "copyroom",
    "copy": "copyroom",
    "training": "classroom",
    "classroom": "classroom",
    "auditorium": "auditorium",
    "mother": "mothersroom",
    "nursing": "mothersroom",
    "prayer": "prayerroom",
    "meditation": "meditationroom",
    "wellness": "wellnessroom",
}

# Layer patterns for CAD parsing
LAYER_PATTERNS = {
    "rooms": re.compile(r"^(ROOM|ROOMS|SPACE|AREA|A-AREA|A-ROOM|UNIT)", re.IGNORECASE),
    "walls": re.compile(r"^(WALL|WALLS|A-WALL|STRUCT)", re.IGNORECASE),
    "doors": re.compile(r"^(DOOR|DOORS|A-DOOR|OPENING)", re.IGNORECASE),
    "labels": re.compile(r"^(TEXT|LABEL|NAME|ANNOTATION|A-ANNO)", re.IGNORECASE),
}


class IMDFConverter:
    """Convert DXF floor plans to IMDF format."""

    def __init__(
        self,
        building_name: str = "Headquarters",
        building_id: str = None,
        address: dict = None,
        anchor_coordinate: tuple[float, float] = None,
        scale_factor: float = 1.0,
    ):
        """
        Initialize converter.
        
        Args:
            building_name: Human-readable building name
            building_id: Unique building identifier (auto-generated if None)
            address: Building address dict with street, city, etc.
            anchor_coordinate: (longitude, latitude) for geo-referencing
            scale_factor: Scale CAD units (e.g., 0.001 for mm to m)
        """
        self.building_name = building_name
        self.building_id = building_id or str(uuid.uuid4())
        self.address = address or {
            "address": "123 Main Street",
            "locality": "Seattle",
            "province": "WA",
            "country": "US",
            "postal_code": "98101",
        }
        self.anchor = anchor_coordinate or (-122.3321, 47.6062)  # Default: Seattle
        self.scale_factor = scale_factor
        
        # Collected data per level
        self.levels: dict[int, dict] = {}
        self.units: list[dict] = []
        self.openings: list[dict] = []
        self.amenities: list[dict] = []
        self.labels: dict[int, dict[tuple, str]] = {}  # floor -> {(x,y): "label"}

    def transform_point(self, x: float, y: float) -> tuple[float, float]:
        """Transform CAD coordinates to approximate geo coordinates."""
        # Simple linear transform - in production, use proper geo-referencing
        return (
            self.anchor[0] + (x * self.scale_factor * 0.00001),
            self.anchor[1] + (y * self.scale_factor * 0.00001),
        )

    def transform_coords(self, coords: list) -> list[list[float]]:
        """Transform coordinate list to GeoJSON format [lon, lat]."""
        return [list(self.transform_point(x, y)) for x, y, *_ in coords]

    def parse_dxf(self, filepath: Path, floor: int) -> None:
        """Parse a DXF file for a specific floor."""
        logger.info(f"Parsing {filepath} as floor {floor}")
        
        doc = ezdxf.readfile(str(filepath))
        msp = doc.modelspace()
        
        if floor not in self.labels:
            self.labels[floor] = {}
        
        # First pass: collect labels
        for entity in msp:
            if isinstance(entity, (Text, MText)):
                try:
                    text_content = entity.plain_text() if isinstance(entity, MText) else entity.dxf.text
                    insert = entity.dxf.insert
                    pos = (insert.x, insert.y)
                    self.labels[floor][pos] = text_content.strip()
                except Exception:
                    pass
        
        # Second pass: collect geometry
        rooms_on_floor = []
        doors_on_floor = []
        
        for entity in msp:
            layer_name = entity.dxf.layer
            
            # Detect rooms (closed polylines)
            if isinstance(entity, LWPolyline) and entity.closed:
                if LAYER_PATTERNS["rooms"].match(layer_name) or not any(
                    p.match(layer_name) for p in LAYER_PATTERNS.values()
                ):
                    coords = list(entity.get_points())
                    if len(coords) >= 3:
                        rooms_on_floor.append({
                            "coords": coords,
                            "layer": layer_name,
                        })
            
            # Detect doors
            if LAYER_PATTERNS["doors"].match(layer_name):
                if isinstance(entity, LWPolyline):
                    coords = list(entity.get_points())
                    if len(coords) >= 2:
                        doors_on_floor.append({
                            "coords": coords,
                            "layer": layer_name,
                        })
                elif isinstance(entity, Line):
                    doors_on_floor.append({
                        "coords": [
                            (entity.dxf.start.x, entity.dxf.start.y),
                            (entity.dxf.end.x, entity.dxf.end.y),
                        ],
                        "layer": layer_name,
                    })
        
        # Process rooms into units
        for room_data in rooms_on_floor:
            self._add_unit(room_data, floor)
        
        # Process doors into openings
        for door_data in doors_on_floor:
            self._add_opening(door_data, floor)
        
        # Store level info
        self.levels[floor] = {
            "ordinal": floor - 1,  # IMDF uses 0-indexed ordinals
            "short_name": f"L{floor}",
            "outdoor": False,
        }
        
        logger.info(f"Floor {floor}: {len(rooms_on_floor)} rooms, {len(doors_on_floor)} doors")

    def _add_unit(self, room_data: dict, floor: int) -> None:
        """Add a room as an IMDF unit."""
        coords = room_data["coords"]
        
        try:
            # Create polygon
            poly_coords = [(x, y) for x, y, *_ in coords]
            if poly_coords[0] != poly_coords[-1]:
                poly_coords.append(poly_coords[0])
            
            polygon = Polygon(poly_coords)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            
            if polygon.area < 1.0:  # Skip tiny areas
                return
            
            # Find label
            centroid = polygon.centroid
            name = self._find_label(centroid.x, centroid.y, polygon, floor)
            
            # Determine category
            category = self._detect_category(name, room_data["layer"])
            
            # Transform to geo coordinates
            geo_coords = self.transform_coords(poly_coords)
            
            unit_id = str(uuid.uuid4())
            
            self.units.append({
                "id": unit_id,
                "type": "Feature",
                "feature_type": "unit",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [geo_coords],
                },
                "properties": {
                    "category": category,
                    "name": {"en": name} if name else None,
                    "level_id": f"level_{floor}",
                    "display_point": {
                        "type": "Point",
                        "coordinates": list(self.transform_point(centroid.x, centroid.y)),
                    },
                },
            })
            
            # Add amenity for special categories
            if category in ["restroom", "elevator", "stairs", "cafeteria"]:
                self.amenities.append({
                    "id": str(uuid.uuid4()),
                    "type": "Feature",
                    "feature_type": "amenity",
                    "geometry": {
                        "type": "Point",
                        "coordinates": list(self.transform_point(centroid.x, centroid.y)),
                    },
                    "properties": {
                        "category": category,
                        "unit_ids": [unit_id],
                    },
                })
                
        except Exception as e:
            logger.warning(f"Failed to process room: {e}")

    def _add_opening(self, door_data: dict, floor: int) -> None:
        """Add a door as an IMDF opening."""
        coords = door_data["coords"]
        
        try:
            geo_coords = self.transform_coords(coords)
            
            self.openings.append({
                "id": str(uuid.uuid4()),
                "type": "Feature",
                "feature_type": "opening",
                "geometry": {
                    "type": "LineString",
                    "coordinates": geo_coords,
                },
                "properties": {
                    "category": "door",
                    "level_id": f"level_{floor}",
                },
            })
        except Exception as e:
            logger.warning(f"Failed to process door: {e}")

    def _find_label(
        self, x: float, y: float, polygon: Polygon, floor: int
    ) -> str | None:
        """Find text label for a room."""
        if floor not in self.labels:
            return None
        
        # Check labels inside polygon first
        for (lx, ly), label in self.labels[floor].items():
            if polygon.contains(Point(lx, ly)):
                return label
        
        # Find nearest label
        best_label = None
        best_dist = 100.0  # max distance
        
        for (lx, ly), label in self.labels[floor].items():
            dist = Point(x, y).distance(Point(lx, ly))
            if dist < best_dist:
                best_dist = dist
                best_label = label
        
        return best_label

    def _detect_category(self, name: str | None, layer: str) -> str:
        """Detect IMDF category from name or layer."""
        search_text = f"{name or ''} {layer}".lower()
        
        for keyword, category in IMDF_CATEGORIES.items():
            if keyword in search_text:
                return category
        
        return "room"  # default

    def generate_imdf(self, output_dir: str | Path) -> Path:
        """Generate IMDF package."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Manifest
        manifest = {
            "version": "1.0.0",
            "created": datetime.utcnow().isoformat() + "Z",
            "language": "en",
            "generated_by": "Workplace Navigator IMDF Converter",
        }
        self._write_json(output_dir / "manifest.json", manifest)
        
        # 2. Building
        # Create building footprint from all units, handling invalid geometries
        all_polygons = []
        for unit in self.units:
            if unit["geometry"]["type"] == "Polygon":
                coords = unit["geometry"]["coordinates"][0]
                try:
                    poly = Polygon(coords)
                    # Fix invalid polygons with buffer(0)
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    if poly.is_valid and not poly.is_empty:
                        all_polygons.append(poly)
                except Exception as e:
                    logger.warning(f"Skipping invalid polygon: {e}")
                    continue
        
        if all_polygons:
            try:
                # Use buffer(0) to fix any remaining topology issues
                valid_polygons = [p.buffer(0) if not p.is_valid else p for p in all_polygons]
                valid_polygons = [p for p in valid_polygons if p.is_valid and not p.is_empty]
                
                if valid_polygons:
                    building_footprint = unary_union(valid_polygons).convex_hull
                    building_coords = [list(c) for c in building_footprint.exterior.coords]
                else:
                    raise ValueError("No valid polygons")
            except Exception as e:
                logger.warning(f"Could not create building footprint: {e}, using default")
                building_coords = [
                    [self.anchor[0] - 0.001, self.anchor[1] - 0.001],
                    [self.anchor[0] + 0.001, self.anchor[1] - 0.001],
                    [self.anchor[0] + 0.001, self.anchor[1] + 0.001],
                    [self.anchor[0] - 0.001, self.anchor[1] + 0.001],
                    [self.anchor[0] - 0.001, self.anchor[1] - 0.001],
                ]
        else:
            # Default small footprint
            building_coords = [
                [self.anchor[0] - 0.001, self.anchor[1] - 0.001],
                [self.anchor[0] + 0.001, self.anchor[1] - 0.001],
                [self.anchor[0] + 0.001, self.anchor[1] + 0.001],
                [self.anchor[0] - 0.001, self.anchor[1] + 0.001],
                [self.anchor[0] - 0.001, self.anchor[1] - 0.001],
            ]
        
        building = {
            "type": "FeatureCollection",
            "features": [{
                "id": self.building_id,
                "type": "Feature",
                "feature_type": "building",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [building_coords],
                },
                "properties": {
                    "name": {"en": self.building_name},
                    "category": "office",
                    "address_id": "addr_1",
                },
            }],
        }
        self._write_json(output_dir / "building.geojson", building)
        
        # 3. Address
        address = {
            "type": "FeatureCollection",
            "features": [{
                "id": "addr_1",
                "type": "Feature",
                "feature_type": "address",
                "geometry": {
                    "type": "Point",
                    "coordinates": list(self.anchor),
                },
                "properties": self.address,
            }],
        }
        self._write_json(output_dir / "address.geojson", address)
        
        # 4. Levels
        level_features = []
        for floor_num, level_data in self.levels.items():
            level_features.append({
                "id": f"level_{floor_num}",
                "type": "Feature",
                "feature_type": "level",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [building_coords],
                },
                "properties": {
                    "ordinal": level_data["ordinal"],
                    "name": {"en": f"Floor {floor_num}"},
                    "short_name": {"en": level_data["short_name"]},
                    "outdoor": level_data["outdoor"],
                    "building_ids": [self.building_id],
                },
            })
        
        levels = {"type": "FeatureCollection", "features": level_features}
        self._write_json(output_dir / "level.geojson", levels)
        
        # 5. Units (rooms)
        units = {"type": "FeatureCollection", "features": self.units}
        self._write_json(output_dir / "unit.geojson", units)
        
        # 6. Openings (doors)
        openings = {"type": "FeatureCollection", "features": self.openings}
        self._write_json(output_dir / "opening.geojson", openings)
        
        # 7. Amenities
        amenities = {"type": "FeatureCollection", "features": self.amenities}
        self._write_json(output_dir / "amenity.geojson", amenities)
        
        # 8. Anchor (geo-reference point)
        anchor = {
            "type": "FeatureCollection",
            "features": [{
                "id": "anchor_1",
                "type": "Feature",
                "feature_type": "anchor",
                "geometry": {
                    "type": "Point",
                    "coordinates": list(self.anchor),
                },
                "properties": {
                    "unit_id": self.units[0]["id"] if self.units else None,
                },
            }],
        }
        self._write_json(output_dir / "anchor.geojson", anchor)
        
        # Create ZIP package
        zip_path = output_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in output_dir.glob("*.geojson"):
                zf.write(file, file.name)
            zf.write(output_dir / "manifest.json", "manifest.json")
        
        logger.info(f"IMDF package created: {zip_path}")
        return zip_path

    def _write_json(self, path: Path, data: dict) -> None:
        """Write JSON file."""
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


def convert_single(
    filepath: Path,
    floor: int,
    output_dir: Path,
    building_name: str = "Headquarters",
    anchor: tuple[float, float] = None,
    scale: float = 1.0,
) -> Path:
    """Convert a single DXF file to IMDF."""
    converter = IMDFConverter(
        building_name=building_name,
        anchor_coordinate=anchor,
        scale_factor=scale,
    )
    converter.parse_dxf(filepath, floor)
    return converter.generate_imdf(output_dir)


def convert_batch(
    directory: Path,
    output_dir: Path,
    building_name: str = "Headquarters",
    anchor: tuple[float, float] = None,
    scale: float = 1.0,
) -> Path:
    """Convert multiple DXF files to single IMDF package."""
    converter = IMDFConverter(
        building_name=building_name,
        anchor_coordinate=anchor,
        scale_factor=scale,
    )
    
    dxf_files = sorted(directory.glob("*.dxf"))
    
    for i, filepath in enumerate(dxf_files, start=1):
        # Extract floor number from filename
        match = re.search(r"(\d+)", filepath.stem)
        floor = int(match.group(1)) if match else i
        converter.parse_dxf(filepath, floor)
    
    return converter.generate_imdf(output_dir)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert DXF floor plans to IMDF for Azure Maps"
    )
    parser.add_argument("path", type=Path, help="DXF file or directory")
    parser.add_argument("--output", "-o", type=Path, default=Path("./imdf_output"))
    parser.add_argument("--floor", "-f", type=int, default=1)
    parser.add_argument("--building", "-b", type=str, default="Headquarters")
    parser.add_argument("--lat", type=float, default=47.6062, help="Anchor latitude")
    parser.add_argument("--lon", type=float, default=-122.3321, help="Anchor longitude")
    parser.add_argument("--scale", "-s", type=float, default=1.0)
    parser.add_argument("--batch", action="store_true")
    
    args = parser.parse_args()
    anchor = (args.lon, args.lat)
    
    if args.batch or args.path.is_dir():
        zip_path = convert_batch(
            args.path, args.output, args.building, anchor, args.scale
        )
    else:
        zip_path = convert_single(
            args.path, args.floor, args.output, args.building, anchor, args.scale
        )
    
    print(f"\n✅ IMDF package created: {zip_path}")
    print(f"\nNext steps:")
    print(f"1. Upload to Azure Maps Creator:")
    print(f"   az maps creator dataset create \\")
    print(f"     --resource-group <your-rg> \\")
    print(f"     --account-name <your-maps-account> \\")
    print(f"     --input-path {zip_path}")
    print(f"\n2. Create tileset from dataset")
    print(f"3. Update .env with tileset/stateset IDs")


if __name__ == "__main__":
    main()
