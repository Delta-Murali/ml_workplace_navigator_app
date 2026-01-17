"""Database initialization and schema creation script.

Run this once to set up the database tables and PostGIS extension.

Usage:
    python -m app.scripts.init_db
"""

import asyncio
import logging

from sqlalchemy import text
from sqlmodel import SQLModel

from app.core.database import engine
from app.models import Employee, Room  # Import all models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database():
    """Initialize database with PostGIS and all tables."""
    
    async with engine.begin() as conn:
        # Enable PostGIS extension
        logger.info("Enabling PostGIS extension...")
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            logger.info("PostGIS extension enabled")
        except Exception as e:
            logger.warning(f"PostGIS extension note: {e}")
        
        # Create all tables
        logger.info("Creating database tables...")
        await conn.run_sync(SQLModel.metadata.create_all)
        
        # Create spatial indexes for better query performance
        logger.info("Creating spatial indexes...")
        
        index_statements = [
            # Employee desk location index
            """
            CREATE INDEX IF NOT EXISTS idx_employees_desk_location 
            ON employees USING GIST (desk_location)
            """,
            # Room boundary index
            """
            CREATE INDEX IF NOT EXISTS idx_rooms_boundary 
            ON rooms USING GIST (boundary)
            """,
            # Room centroid index
            """
            CREATE INDEX IF NOT EXISTS idx_rooms_centroid 
            ON rooms USING GIST (centroid)
            """,
            # Navigation tables (if they exist)
            """
            DO $$ 
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'navigation_nodes') THEN
                    CREATE INDEX IF NOT EXISTS idx_nav_nodes_geom ON navigation_nodes USING GIST (geom);
                END IF;
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'navigation_edges') THEN
                    CREATE INDEX IF NOT EXISTS idx_nav_edges_geom ON navigation_edges USING GIST (geom);
                END IF;
            END $$
            """,
        ]
        
        for stmt in index_statements:
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                logger.warning(f"Index creation note: {e}")
        
        logger.info("Database initialization complete!")
        
        # Print table info
        result = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """))
        tables = [row[0] for row in result.fetchall()]
        logger.info(f"Tables created: {', '.join(tables)}")


def main():
    """CLI entry point."""
    print("Initializing database...")
    print("Make sure your DATABASE_URL in .env points to a PostgreSQL server with PostGIS")
    print()
    
    asyncio.run(init_database())
    
    print()
    print("Next steps:")
    print("1. Convert your .dwg files to .dxf format")
    print("2. Run: python -m app.scripts.import_floorplan <file.dxf> --floor <number>")


if __name__ == "__main__":
    main()
