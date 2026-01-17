"""Indoor navigation service using Azure Maps.

Provides:
- Wayfinding between indoor locations
- Feature state updates (occupied, available, etc.)
- Sync between PostGIS rooms and Azure Maps features
"""

import logging
from typing import Any

import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.models.room import Room

logger = logging.getLogger(__name__)
settings = get_settings()


class IndoorNavigationService:
    """Service for Azure Maps indoor navigation and feature states."""

    def __init__(self):
        self.base_url = "https://us.atlas.microsoft.com"
        self.api_version = "2.0"
        self.subscription_key = settings.azure_maps_subscription_key
        self.stateset_id = settings.azure_maps_stateset_id
        self.routeset_id = settings.azure_maps_routeset_id
        self.dataset_id = settings.azure_maps_dataset_id

    @property
    def _params(self) -> dict:
        """Common query parameters for all requests."""
        return {
            "api-version": self.api_version,
            "subscription-key": self.subscription_key,
        }

    async def get_wayfinding_path(
        self,
        from_lat: float,
        from_lon: float,
        to_feature_id: str,
        facility_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get indoor wayfinding path between two points.
        
        Args:
            from_lat: Starting latitude
            from_lon: Starting longitude
            to_feature_id: Azure Maps feature ID for destination
            facility_id: Building/facility ID
            
        Returns:
            Wayfinding response with path legs and instructions
        """
        if not self.routeset_id:
            logger.warning("Routeset ID not configured, cannot compute wayfinding path")
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/wayfinding/path",
                    params={
                        **self._params,
                        "routesetId": self.routeset_id,
                        "facilityId": facility_id or "",
                        "fromPoint": f"{from_lat},{from_lon}",
                        "toPoint": to_feature_id,
                        "minWidth": "1.0",  # Minimum corridor width in meters
                    },
                    timeout=30.0,
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Wayfinding failed: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                logger.error(f"Wayfinding request failed: {e}")
                return None

    async def update_feature_state(
        self,
        feature_id: str,
        states: dict[str, Any],
    ) -> bool:
        """
        Update the state of a feature (room, desk, etc.) in Azure Maps.
        
        Common states:
        - occupied: bool
        - available: bool
        - temperature: number
        - occupancy: number (current people count)
        
        Args:
            feature_id: Azure Maps feature ID
            states: Dictionary of state key-value pairs
            
        Returns:
            True if update successful
        """
        if not self.stateset_id:
            logger.warning("Stateset ID not configured")
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(
                    f"{self.base_url}/featureStateSets/{self.stateset_id}/featureStates/{feature_id}",
                    params=self._params,
                    json={"states": states},
                    timeout=10.0,
                )
                
                if response.status_code in [200, 204]:
                    logger.info(f"Updated feature {feature_id} state: {states}")
                    return True
                else:
                    logger.error(f"Feature state update failed: {response.status_code}")
                    return False
                    
            except Exception as e:
                logger.error(f"Feature state update failed: {e}")
                return False

    async def get_feature_state(self, feature_id: str) -> dict[str, Any] | None:
        """
        Get current state of a feature.
        
        Args:
            feature_id: Azure Maps feature ID
            
        Returns:
            Dictionary of current states
        """
        if not self.stateset_id:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/featureStateSets/{self.stateset_id}/featureStates/{feature_id}",
                    params=self._params,
                    timeout=10.0,
                )
                
                if response.status_code == 200:
                    return response.json()
                return None
                    
            except Exception as e:
                logger.error(f"Failed to get feature state: {e}")
                return None

    async def sync_room_availability(
        self,
        session: AsyncSession,
        room_id: int,
        is_available: bool,
    ) -> bool:
        """
        Sync room availability between PostGIS and Azure Maps.
        
        Args:
            session: Database session
            room_id: Local room ID
            is_available: Availability status
            
        Returns:
            True if sync successful
        """
        # Get room from database
        result = await session.execute(
            select(Room).where(Room.id == room_id)
        )
        room = result.scalar_one_or_none()
        
        if not room or not room.azure_maps_feature_id:
            logger.warning(f"Room {room_id} not found or has no Azure Maps feature ID")
            return False
        
        # Update Azure Maps feature state
        return await self.update_feature_state(
            room.azure_maps_feature_id,
            {"available": is_available}
        )

    async def get_dataset_features(
        self,
        feature_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get features from the Azure Maps dataset.
        
        Args:
            feature_type: Optional filter by feature type (unit, opening, etc.)
            
        Returns:
            List of features with their properties
        """
        if not self.dataset_id:
            return []

        async with httpx.AsyncClient() as client:
            try:
                params = {**self._params}
                if feature_type:
                    params["filter"] = f"featureClass eq '{feature_type}'"
                
                response = await client.get(
                    f"{self.base_url}/wfs/datasets/{self.dataset_id}/collections/unit/items",
                    params=params,
                    timeout=30.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("features", [])
                return []
                    
            except Exception as e:
                logger.error(f"Failed to get dataset features: {e}")
                return []

    async def link_rooms_to_features(self, session: AsyncSession) -> int:
        """
        Automatically link PostGIS rooms to Azure Maps features by name matching.
        
        Returns:
            Number of rooms linked
        """
        # Get all features from Azure Maps
        features = await self.get_dataset_features("unit")
        if not features:
            return 0
        
        # Get all rooms from database
        result = await session.execute(select(Room))
        rooms = result.scalars().all()
        
        linked_count = 0
        
        for room in rooms:
            # Try to match by name or room number
            for feature in features:
                props = feature.get("properties", {})
                feature_name = props.get("name", "").lower()
                feature_id = feature.get("id")
                
                if (
                    room.name.lower() in feature_name or
                    feature_name in room.name.lower() or
                    (room.room_number and room.room_number.lower() in feature_name)
                ):
                    room.azure_maps_feature_id = feature_id
                    session.add(room)
                    linked_count += 1
                    break
        
        await session.commit()
        logger.info(f"Linked {linked_count} rooms to Azure Maps features")
        return linked_count


# Create singleton service instance
indoor_navigation_service = IndoorNavigationService()
