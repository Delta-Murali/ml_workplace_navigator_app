# Azure Maps Indoor Maps Integration

This document describes how to set up Azure Maps Indoor Maps using the IMDF (Indoor Mapping Data Format) workflow.

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│  DWG Files  │ ──► │  DXF Files  │ ──► │  IMDF Package    │
│ (AutoCAD)   │     │ (Open Fmt)  │     │  (GeoJSON ZIP)   │
└─────────────┘     └─────────────┘     └────────┬─────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    Azure Maps Creator                        │
├─────────────────────────────────────────────────────────────┤
│  Dataset ──► Tileset ──► Stateset ──► Routeset             │
│  (IMDF)      (Tiles)     (States)     (Wayfinding)         │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                          │
├─────────────────────────────────────────────────────────────┤
│  Azure Maps Web SDK + Indoor Module                          │
│  • Indoor floor plans                                        │
│  • Level/floor switching                                     │
│  • Real-time feature states (availability)                   │
│  • Indoor wayfinding routes                                  │
└─────────────────────────────────────────────────────────────┘
```

## Setup Steps

### 1. Prerequisites

- **Azure Maps Account** (Gen2 pricing tier for Creator features)
- **Azure Maps Creator** resource in the same region
- **DXF format** floor plans (convert from DWG if needed)

### 2. Convert DWG to DXF

Use one of these free tools:
- [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) (recommended)
- LibreCAD (open source)
- Online converters

### 3. Convert DXF to IMDF

```bash
cd backend
source venv/bin/activate

# Convert a single floor
python -m app.scripts.setup_azure_maps convert \
  --dxf ./floorplans/floor1.dxf \
  --floor 1 \
  --building "Headquarters"

# Convert multiple floors (directory)
python -m app.scripts.setup_azure_maps convert \
  --dxf ./floorplans/ \
  --floor 1 \
  --output ./imdf_output
```

### 4. Upload to Azure Maps Creator

```bash
# Set your Azure Maps subscription key first
export AZURE_MAPS_SUBSCRIPTION_KEY=your_key_here

# Upload IMDF package
python -m app.scripts.setup_azure_maps upload \
  --imdf ./imdf_output/imdf_package.zip
```

This creates:
- **Dataset** - Your IMDF data stored in Azure
- **Tileset** - Map tiles for rendering
- **Stateset** - Real-time feature states

The script automatically updates your `.env` file with the generated IDs.

### 5. Sync Rooms with PostGIS

```bash
# Link PostGIS rooms to Azure Maps features
python -m app.scripts.setup_azure_maps sync
```

### 6. Full Workflow (All Steps)

```bash
python -m app.scripts.setup_azure_maps full \
  --dxf ./floorplans/ \
  --floor 1 \
  --building "Headquarters"
```

## Configuration

### Backend `.env`

```env
# Azure Maps (from Azure Maps Creator after IMDF upload)
AZURE_MAPS_SUBSCRIPTION_KEY=your_subscription_key
AZURE_MAPS_CLIENT_ID=optional_for_aad_auth
AZURE_MAPS_TILESET_ID=auto_populated_after_upload
AZURE_MAPS_STATESET_ID=auto_populated_after_upload
AZURE_MAPS_ROUTESET_ID=auto_populated_after_upload
AZURE_MAPS_DATASET_ID=auto_populated_after_upload
```

## API Endpoints

### Map Configuration
```
GET /api/map/config
```
Returns Azure Maps credentials for frontend SDK initialization.

### Building Info
```
GET /api/map/building
```
Returns building and floor information for level selector.

### Indoor Wayfinding
```
POST /api/map/wayfinding
{
  "from_lat": 47.6062,
  "from_lon": -122.3321,
  "to_feature_id": "unit_123",
  "facility_id": "hq-main"
}
```
Returns navigation path between two indoor locations.

### Feature State Management
```
POST /api/map/feature-state
{
  "feature_id": "unit_123",
  "states": {
    "available": true,
    "temperature": 72
  }
}

GET /api/map/feature-state/{feature_id}
```
Update/retrieve real-time feature states (room availability, etc.)

## Frontend Integration

The Map component automatically:
1. Loads Azure Maps SDK and Indoor module
2. Initializes IndoorManager with tileset/stateset
3. Handles floor switching via LevelControl
4. Draws navigation routes from wayfinding API
5. Shows real-time feature states (available/occupied colors)

## DXF Layer Requirements

For best results, structure your DXF files with these layers:
- `ROOM` or `A-ROOM` - Closed polylines for room boundaries
- `DOOR` or `A-DOOR` - Lines/arcs for door openings
- `TEXT` or `A-TEXT` - Room names/numbers
- `FURNITURE` - Optional furniture layout

## IMDF Structure

The converter generates these IMDF files:
- `manifest.json` - Package metadata
- `building.geojson` - Building footprint
- `level.geojson` - Floor levels
- `unit.geojson` - Rooms and spaces
- `opening.geojson` - Doors and passages
- `amenity.geojson` - Points of interest
- `anchor.geojson` - Wayfinding anchors

## Troubleshooting

### "Tileset ID not configured"
Run the upload command or manually set `AZURE_MAPS_TILESET_ID` in `.env`

### "Failed to load Azure Maps SDK"
Check network connectivity and that Azure Maps subscription key is valid

### Rooms not linking to features
Ensure room names in PostGIS match the TEXT labels in your DXF files

### Wayfinding returns empty path
Verify that:
1. Routeset was created from the dataset
2. Both start and end points are within the facility
3. There's a navigable path between locations

## Resources

- [Azure Maps Creator Documentation](https://docs.microsoft.com/azure/azure-maps/creator-indoor-maps)
- [IMDF Specification](https://register.apple.com/resources/imdf/)
- [Azure Maps Indoor Module](https://docs.microsoft.com/azure/azure-maps/how-to-use-indoor-module)
