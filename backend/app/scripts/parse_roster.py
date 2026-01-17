"""CSV Roster Parser Script.

Parses employee roster CSV and loads into PostGIS database
with spatial geometry for desk locations.

Usage:
    python -m app.scripts.parse_roster data/employees.csv
"""

import asyncio
import csv
import sys
from pathlib import Path

from shapely.geometry import Point
from geoalchemy2.shape import from_shape
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, init_db
from app.models.employee import Employee


async def parse_and_load_roster(csv_path: str) -> int:
    """Parse CSV roster and load employees into database.
    
    Expected CSV columns:
    - employee_id: Unique identifier
    - name: Full name
    - email: Email address
    - department: Department name
    - title: Job title (optional)
    - desk_id: Desk identifier (optional)
    - floor: Floor number
    - building: Building name (default: HQ)
    - desk_x: Desk X coordinate (longitude)
    - desk_y: Desk Y coordinate (latitude)
    - feature_id: Azure Maps Feature ID (optional)
    
    Returns:
        Number of employees loaded.
    """
    # Initialize database
    await init_db()
    
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"Error: File not found: {csv_path}")
        return 0
    
    loaded = 0
    
    async with async_session_maker() as session:
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Parse coordinates
                desk_location = None
                if row.get('desk_x') and row.get('desk_y'):
                    try:
                        x = float(row['desk_x'])
                        y = float(row['desk_y'])
                        point = Point(x, y)
                        desk_location = from_shape(point, srid=4326)
                    except (ValueError, TypeError):
                        print(f"Warning: Invalid coordinates for {row.get('employee_id')}")
                
                # Create employee record
                employee = Employee(
                    employee_id=row['employee_id'],
                    name=row['name'],
                    email=row['email'],
                    department=row['department'],
                    title=row.get('title'),
                    desk_id=row.get('desk_id'),
                    floor=int(row.get('floor', 1)),
                    building=row.get('building', 'HQ'),
                    desk_location=desk_location,
                    feature_id=row.get('feature_id'),
                )
                
                session.add(employee)
                loaded += 1
                
                # Batch commit every 100 records
                if loaded % 100 == 0:
                    await session.commit()
                    print(f"Loaded {loaded} employees...")
        
        # Final commit
        await session.commit()
    
    print(f"Successfully loaded {loaded} employees.")
    return loaded


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m app.scripts.parse_roster <csv_file>")
        print("\nExample CSV format:")
        print("employee_id,name,email,department,title,desk_id,floor,building,desk_x,desk_y,feature_id")
        print('E001,John Doe,john@company.com,Engineering,Software Engineer,D-101,2,HQ,-122.33,47.60,FEAT_001')
        sys.exit(1)
    
    csv_path = sys.argv[1]
    asyncio.run(parse_and_load_roster(csv_path))


if __name__ == "__main__":
    main()
