#!/usr/bin/env python3
"""
Azure Maps IMDF Setup Workflow Script.

This script guides you through the complete workflow:
1. Convert DWG → DXF (manual step)
2. Convert DXF → IMDF GeoJSON package
3. Upload IMDF to Azure Maps Creator
4. Create tileset, stateset, and routeset
5. Update .env with generated IDs
6. Sync rooms between PostGIS and Azure Maps

Usage:
    python -m app.scripts.setup_azure_maps --help
    python -m app.scripts.setup_azure_maps convert --dxf path/to/floorplans
    python -m app.scripts.setup_azure_maps upload --imdf ./imdf_output
    python -m app.scripts.setup_azure_maps sync
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_step(step: int, text: str):
    """Print a step indicator."""
    print(f"\n[Step {step}] {text}")
    print("-" * 50)


async def convert_dxf_to_imdf(dxf_path: str, output_dir: str, floor: int, building_name: str):
    """Convert DXF files to IMDF format."""
    from app.scripts.convert_to_imdf import IMDFConverter
    
    print_step(1, "Converting DXF to IMDF")
    
    converter = IMDFConverter(building_name=building_name)
    
    dxf_path = Path(dxf_path)
    if dxf_path.is_dir():
        # Process all DXF files in directory
        for idx, dxf_file in enumerate(sorted(dxf_path.glob("*.dxf"))):
            print(f"Processing: {dxf_file.name} (Floor {floor + idx})")
            converter.parse_dxf(str(dxf_file), floor=floor + idx)
    else:
        print(f"Processing: {dxf_path.name}")
        converter.parse_dxf(str(dxf_path), floor=floor)
    
    # Generate IMDF package (returns path to ZIP file)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    
    zip_path = converter.generate_imdf(str(output))
    
    print(f"\n✅ IMDF package created: {zip_path}")
    print(f"   - Units (rooms) extracted: {len(converter.units)}")
    print(f"   - Levels (floors): {len(converter.levels)}")
    
    return str(zip_path)


async def upload_to_azure_maps(imdf_zip_path: str):
    """Upload IMDF to Azure Maps Creator and create all resources."""
    from app.services.azure_maps_service import full_pipeline
    from app.core.config import get_settings
    
    settings = get_settings()
    
    if not settings.azure_maps_subscription_key:
        print("❌ Error: AZURE_MAPS_SUBSCRIPTION_KEY not set in .env")
        print("   Get your key from Azure Portal → Azure Maps account → Authentication")
        return None
    
    print_step(2, "Uploading to Azure Maps Creator")
    
    try:
        result = await full_pipeline(imdf_zip_path)
        
        print(f"\n✅ Azure Maps resources created:")
        print(f"   Dataset ID:  {result['dataset_id']}")
        print(f"   Tileset ID:  {result['tileset_id']}")
        print(f"   Stateset ID: {result['stateset_id']}")
        
        # Update .env file
        update_env_file(result)
        
        return result
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def update_env_file(azure_ids: dict):
    """Update .env file with Azure Maps IDs."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    
    if not env_path.exists():
        print(f"⚠️  .env file not found at {env_path}")
        return
    
    # Read current content
    content = env_path.read_text()
    
    # Update IDs
    replacements = {
        "AZURE_MAPS_DATASET_ID=": f"AZURE_MAPS_DATASET_ID={azure_ids.get('dataset_id', '')}",
        "AZURE_MAPS_TILESET_ID=": f"AZURE_MAPS_TILESET_ID={azure_ids.get('tileset_id', '')}",
        "AZURE_MAPS_STATESET_ID=": f"AZURE_MAPS_STATESET_ID={azure_ids.get('stateset_id', '')}",
    }
    
    for old, new in replacements.items():
        # Find and replace the line
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith(old.split("=")[0]):
                lines[i] = new
        content = "\n".join(lines)
    
    env_path.write_text(content)
    print(f"\n✅ Updated .env file with Azure Maps IDs")


async def sync_rooms():
    """Sync rooms between PostGIS and Azure Maps."""
    from app.services.indoor_navigation_service import indoor_navigation_service
    from app.core.database import async_session
    
    print_step(3, "Syncing rooms with Azure Maps features")
    
    async with async_session() as session:
        linked = await indoor_navigation_service.link_rooms_to_features(session)
        print(f"\n✅ Linked {linked} rooms to Azure Maps features")


async def import_to_postgis(dxf_path: str, floor: int, building: str):
    """Import DXF geometry directly to PostGIS."""
    from app.scripts.import_floorplan import import_floorplan
    
    print_step(1, "Importing floor plan to PostGIS")
    
    await import_floorplan(
        dxf_path=dxf_path,
        floor=floor,
        building=building,
    )
    
    print(f"\n✅ Floor plan imported to PostGIS")


def print_prerequisites():
    """Print setup prerequisites."""
    print_header("Azure Maps IMDF Setup Prerequisites")
    
    print("""
Before running this script, ensure you have:

1. Azure Maps Account
   - Create at: https://portal.azure.com
   - Service: Azure Maps
   - Pricing tier: Gen2 (required for Creator)

2. Azure Maps Creator Resource
   - Create within your Azure Maps account
   - Region: Must match your Maps account

3. Credentials in .env:
   AZURE_MAPS_SUBSCRIPTION_KEY=<your-key>
   AZURE_MAPS_CLIENT_ID=<optional-for-aad>

4. Floor plan files in DXF format
   - Convert DWG → DXF using:
     • ODA File Converter (free): https://www.opendesign.com/guestfiles/oda_file_converter
     • LibreCAD (free, open source)
     • AutoCAD (File > Save As > DXF)
     • Online converters

5. DXF Requirements:
   - Rooms as closed polylines (LWPOLYLINE/POLYLINE)
   - Room names as TEXT/MTEXT near room centers
   - Doors as LINE or ARC entities
   - Consistent layer naming (e.g., ROOM, DOOR, TEXT)
""")


def main():
    parser = argparse.ArgumentParser(
        description="Azure Maps IMDF Setup Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show prerequisites
  python -m app.scripts.setup_azure_maps prereqs
  
  # Convert DXF to IMDF
  python -m app.scripts.setup_azure_maps convert --dxf ./floorplans --floor 1
  
  # Upload IMDF to Azure Maps
  python -m app.scripts.setup_azure_maps upload --imdf ./imdf_output/imdf_package.zip
  
  # Full workflow
  python -m app.scripts.setup_azure_maps full --dxf ./floorplans --floor 1
  
  # Sync rooms after upload
  python -m app.scripts.setup_azure_maps sync
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Prerequisites command
    subparsers.add_parser("prereqs", help="Show setup prerequisites")
    
    # Convert command
    convert_parser = subparsers.add_parser("convert", help="Convert DXF to IMDF")
    convert_parser.add_argument("--dxf", required=True, help="Path to DXF file or directory")
    convert_parser.add_argument("--floor", type=int, default=1, help="Starting floor number")
    convert_parser.add_argument("--output", default="./imdf_output", help="Output directory")
    convert_parser.add_argument("--building", default="Headquarters", help="Building name")
    
    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload IMDF to Azure Maps")
    upload_parser.add_argument("--imdf", required=True, help="Path to IMDF ZIP package")
    
    # Sync command
    subparsers.add_parser("sync", help="Sync rooms with Azure Maps features")
    
    # Full workflow command
    full_parser = subparsers.add_parser("full", help="Run full workflow")
    full_parser.add_argument("--dxf", required=True, help="Path to DXF file or directory")
    full_parser.add_argument("--floor", type=int, default=1, help="Starting floor number")
    full_parser.add_argument("--output", default="./imdf_output", help="Output directory")
    full_parser.add_argument("--building", default="Headquarters", help="Building name")
    
    # PostGIS import command (alternative to Azure Maps)
    postgis_parser = subparsers.add_parser("postgis", help="Import to PostGIS only (no Azure)")
    postgis_parser.add_argument("--dxf", required=True, help="Path to DXF file")
    postgis_parser.add_argument("--floor", type=int, default=1, help="Floor number")
    postgis_parser.add_argument("--building", default="HQ", help="Building name")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "prereqs":
        print_prerequisites()
        return
    
    if args.command == "convert":
        asyncio.run(convert_dxf_to_imdf(
            args.dxf, args.output, args.floor, args.building
        ))
    
    elif args.command == "upload":
        asyncio.run(upload_to_azure_maps(args.imdf))
    
    elif args.command == "sync":
        asyncio.run(sync_rooms())
    
    elif args.command == "full":
        async def full_workflow():
            print_header("Azure Maps IMDF Full Workflow")
            
            # Step 1: Convert
            zip_path = await convert_dxf_to_imdf(
                args.dxf, args.output, args.floor, args.building
            )
            
            if not zip_path:
                return
            
            # Step 2: Upload
            result = await upload_to_azure_maps(zip_path)
            
            if not result:
                return
            
            # Step 3: Sync
            await sync_rooms()
            
            print_header("Setup Complete!")
            print("""
Your Azure Maps indoor map is ready!

Next steps:
1. Restart the backend server to load new .env values
2. Open the frontend at http://localhost:5173
3. The indoor map should now display your floor plans

To update room availability in real-time:
- Use the /api/map/feature-state endpoint
- Or integrate with your booking system
            """)
        
        asyncio.run(full_workflow())
    
    elif args.command == "postgis":
        asyncio.run(import_to_postgis(args.dxf, args.floor, args.building))


if __name__ == "__main__":
    main()
