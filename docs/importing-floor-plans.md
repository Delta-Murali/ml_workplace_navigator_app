# Importing Floor Plan Data (DWG Files)

## Overview

This guide explains how to import your AutoCAD `.dwg` floor plan files into the PostgreSQL/PostGIS database for indoor navigation.

## Prerequisites

1. **PostgreSQL with PostGIS** - Your database must have the PostGIS extension
2. **DXF files** - Convert your `.dwg` files to `.dxf` format (see below)
3. **Properly organized CAD layers** - For automatic detection of rooms, paths, etc.

## Step 1: Convert DWG to DXF

DWG is a proprietary AutoCAD format. You need to convert to DXF first:

### Option A: AutoCAD (if available)
```
File → Save As → Select "DXF" format
```

### Option B: LibreCAD (Free)
1. Download from https://librecad.org/
2. Open your .dwg file
3. File → Export → Export as DXF

### Option C: Online Converters
- https://cloudconvert.com/dwg-to-dxf
- https://convertio.co/dwg-dxf/

### Option D: ODA File Converter (Free)
1. Download from https://www.opendesign.com/guestfiles/oda_file_converter
2. Batch convert multiple DWG files

## Step 2: Prepare Your CAD Layers

The importer auto-detects geometry types based on layer names:

| Layer Pattern | What It Detects |
|--------------|-----------------|
| `ROOM*`, `SPACE*`, `AREA*` | Room polygons |
| `WALL*`, `STRUCT*` | Wall geometry |
| `DOOR*`, `OPENING*` | Door locations |
| `PATH*`, `NAV*`, `CORRIDOR*`, `HALLWAY*` | Navigation paths |
| `DESK*`, `FURNITURE*`, `WORKSTATION*` | Desk locations |
| `TEXT*`, `LABEL*`, `ANNOTATION*` | Room names/labels |
| `POI*`, `MARKER*` | Points of interest |

**Tip:** If your layers use different names, you can either:
1. Rename layers in your CAD software before export
2. Modify the `LAYER_PATTERNS` in `import_floorplan.py`

## Step 3: Initialize the Database

First, make sure your `.env` has valid PostgreSQL credentials:

```bash
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/workplace_nav
```

Then initialize the database:

```bash
cd backend
source venv/bin/activate
python -m app.scripts.init_db
```

## Step 4: Import Floor Plans

### Single Floor
```bash
python -m app.scripts.import_floorplan data/floorplans/floor1.dxf --floor 1
```

### Multiple Floors (Batch)
Place all DXF files in a directory with floor numbers in filenames:
```
data/floorplans/
├── floor_01.dxf
├── floor_02.dxf
├── floor_03.dxf
```

Then run:
```bash
python -m app.scripts.import_floorplan data/floorplans/ --batch
```

### Options
```bash
--floor, -f    Floor number (default: 1)
--building, -b Building ID (default: "HQ")
--scale, -s    Scale factor, e.g., 0.001 for mm→m (default: 1.0)
--batch        Import all DXF files in directory
```

## Step 5: Verify Import

Check the database:

```sql
-- Count imported rooms
SELECT floor, COUNT(*) as room_count 
FROM rooms 
GROUP BY floor;

-- View room categories
SELECT category, COUNT(*) 
FROM rooms 
GROUP BY category;

-- Check navigation graph
SELECT COUNT(*) FROM navigation_nodes;
SELECT COUNT(*) FROM navigation_edges;
```

Or use the API:
```bash
curl http://localhost:8000/api/search?q=meeting%20room
```

## Coordinate Systems & Scaling

### CAD Coordinates
Most CAD files use arbitrary coordinate systems:
- Units might be millimeters, inches, or feet
- Origin (0,0) is usually building-specific

### PostGIS Coordinates
We use SRID 4326 (WGS84 lat/long) for Azure Maps compatibility.

### Handling Coordinates

**Option 1: Keep CAD Coordinates (Simplest)**
- Set `scale_factor=1.0`
- Works for indoor-only navigation
- Azure Maps will need configuration to match

**Option 2: Geo-reference (Recommended for Azure Maps)**
- Determine real-world coordinates of building corners
- Calculate `origin_offset` and `scale_factor`:
  ```python
  # Example: Building corner at -122.3320, 47.6060
  # CAD origin at (0, 0), CAD units in mm
  importer = FloorPlanImporter(
      floor=1,
      scale_factor=0.000001,  # mm to approximate degrees
      origin_offset=(-122.3320, 47.6060),
  )
  ```

## Troubleshooting

### "No rooms found"
- Check that room polygons are on layers matching `ROOM*`, `SPACE*`, etc.
- Ensure polygons are closed (start point = end point)
- Verify minimum area threshold (default: 0.1 sq units)

### "Navigation paths missing"
- Paths must be on layers matching `PATH*`, `NAV*`, etc.
- Draw continuous polylines along hallways
- Connect paths to room centroids for routing

### "Room names not detected"
- Add TEXT entities inside room polygons
- Or place TEXT near room centroids
- Layer should match `TEXT*`, `LABEL*`, etc.

### "Invalid geometry errors"
- CAD drawings may have self-intersecting polygons
- The importer tries `buffer(0)` to fix
- For complex issues, clean geometry in CAD software

## Advanced: Custom Import Script

For specialized requirements, create a custom import:

```python
from app.scripts.import_floorplan import FloorPlanImporter

importer = FloorPlanImporter(
    floor=1,
    building="Building-A",
    scale_factor=0.001,  # mm to meters
    origin_offset=(-122.33, 47.60),  # geo-coordinates
)

# Custom layer patterns
importer.LAYER_PATTERNS["rooms"] = re.compile(r"^(MY_ROOMS|SPACES)")

# Parse and import
importer.parse_dxf(Path("my_floor.dxf"))
await importer.import_to_database()
```

## Data Model

### Rooms Table
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| name | VARCHAR | URL-safe identifier |
| display_name | VARCHAR | Human-readable name |
| category | ENUM | Room type (Meeting Room, etc.) |
| floor | INTEGER | Floor number |
| building | VARCHAR | Building ID |
| boundary | GEOMETRY(POLYGON) | Room polygon |
| centroid | GEOMETRY(POINT) | Room center for routing |
| feature_id | VARCHAR | Azure Maps feature ID |

### Navigation Graph
| Table | Purpose |
|-------|---------|
| navigation_nodes | Intersection/waypoints on paths |
| navigation_edges | Walkable connections between nodes |

## Next Steps

After importing floor plans:

1. **Configure Azure Maps** - Upload floor plans to Azure Maps Creator
2. **Sync Feature IDs** - Match Azure Maps features with database rooms
3. **Add Employee Data** - Import employee roster with desk assignments
4. **Test Navigation** - Use the search API to find and route to rooms
