"""Azure Maps Creator integration service.

Handles:
- Uploading IMDF packages to Azure Maps Creator
- Creating datasets, tilesets, and statesets
- Syncing feature IDs back to local database
"""

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AzureMapsCreatorService:
    """Service for Azure Maps Creator operations."""

    def __init__(self):
        self.base_url = "https://us.atlas.microsoft.com"
        self.api_version = "2.0"
        self.subscription_key = settings.azure_maps_subscription_key
    
    @property
    def _params(self) -> dict:
        """Common query parameters."""
        return {
            "api-version": self.api_version,
            "subscription-key": self.subscription_key,
        }

    async def upload_imdf(self, zip_path: str) -> str:
        """
        Upload IMDF package and create dataset.
        
        Returns:
            Dataset ID (udid)
        """
        async with httpx.AsyncClient() as client:
            # 1. Upload the IMDF package
            logger.info("Uploading IMDF package...")
            print(f"   Uploading {zip_path}...")
            
            with open(zip_path, "rb") as f:
                file_content = f.read()
            
            print(f"   File size: {len(file_content)} bytes")
            
            response = await client.post(
                f"{self.base_url}/mapData",
                params={
                    **self._params,
                    "dataFormat": "zip",
                },
                content=file_content,
                headers={"Content-Type": "application/octet-stream"},
                timeout=120.0,
            )
            
            print(f"   Response status: {response.status_code}")
            print(f"   Response headers: {dict(response.headers)}")
            
            if response.status_code not in [200, 201, 202]:
                error_text = response.text or f"HTTP {response.status_code}"
                print(f"   Response body: {error_text}")
                raise Exception(f"Upload failed ({response.status_code}): {error_text}")
            
            # Get operation location for long-running operation
            operation_url = response.headers.get("Operation-Location")
            print(f"   Operation URL: {operation_url}")
            
            if operation_url:
                # Poll until complete
                udid = await self._poll_operation(client, operation_url)
            else:
                udid = response.json().get("udid")
            
            logger.info(f"IMDF uploaded. UDID: {udid}")
            return udid

    async def create_dataset(self, udid: str, description: str = "Floor plans") -> str:
        """
        Create a dataset from uploaded data.
        
        Returns:
            Dataset ID
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/datasets",
                params={
                    **self._params,
                    "udid": udid,
                    "description": description,
                },
                timeout=300.0,
            )
            
            if response.status_code not in [200, 201, 202]:
                raise Exception(f"Dataset creation failed: {response.text}")
            
            operation_url = response.headers.get("Operation-Location")
            
            if operation_url:
                result = await self._poll_operation(client, operation_url)
                dataset_id = result
            else:
                dataset_id = response.json().get("datasetId")
            
            logger.info(f"Dataset created: {dataset_id}")
            return dataset_id

    async def create_tileset(self, dataset_id: str, description: str = "Indoor tiles") -> str:
        """
        Create a tileset from dataset for map rendering.
        
        Returns:
            Tileset ID
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/tilesets",
                params={
                    **self._params,
                    "datasetId": dataset_id,
                    "description": description,
                },
                timeout=300.0,
            )
            
            if response.status_code not in [200, 201, 202]:
                raise Exception(f"Tileset creation failed: {response.text}")
            
            operation_url = response.headers.get("Operation-Location")
            
            if operation_url:
                tileset_id = await self._poll_operation(client, operation_url)
            else:
                tileset_id = response.json().get("tilesetId")
            
            logger.info(f"Tileset created: {tileset_id}")
            return tileset_id

    async def create_stateset(
        self, 
        dataset_id: str, 
        style_rules: list[dict] = None
    ) -> str:
        """
        Create a stateset for dynamic feature styling.
        
        Returns:
            Stateset ID
        """
        # Default style rules for room occupancy/status
        if style_rules is None:
            style_rules = [
                {
                    "keyName": "occupied",
                    "type": "boolean",
                    "rules": [
                        {
                            "true": "#FF0000",  # Red when occupied
                            "false": "#00FF00",  # Green when available
                        }
                    ],
                },
                {
                    "keyName": "category",
                    "type": "string",
                    "rules": [
                        {"conferenceroom": "#4F46E5"},
                        {"restroom": "#10B981"},
                        {"elevator": "#F59E0B"},
                        {"cafeteria": "#EC4899"},
                    ],
                },
            ]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/featureStateSets",
                params={
                    **self._params,
                    "datasetId": dataset_id,
                },
                json={"styles": style_rules},
                timeout=60.0,
            )
            
            if response.status_code not in [200, 201]:
                raise Exception(f"Stateset creation failed: {response.text}")
            
            stateset_id = response.json().get("statesetId")
            logger.info(f"Stateset created: {stateset_id}")
            return stateset_id

    async def get_features(self, dataset_id: str) -> list[dict]:
        """
        Get all features from a dataset.
        
        Returns:
            List of feature objects with IDs
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/wfs/datasets/{dataset_id}/collections/unit/items",
                params=self._params,
                timeout=60.0,
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get features: {response.text}")
            
            return response.json().get("features", [])

    async def _poll_operation(
        self, 
        client: httpx.AsyncClient, 
        operation_url: str,
        max_attempts: int = 60,
        interval: float = 5.0,
    ) -> str:
        """Poll a long-running operation until complete."""
        for _ in range(max_attempts):
            response = await client.get(
                operation_url,
                params={"subscription-key": self.subscription_key},
            )
            
            data = response.json()
            status = data.get("status", "").lower()
            
            if status == "succeeded":
                # Return the resource ID from the response
                return data.get("resourceLocation", "").split("/")[-1]
            elif status == "failed":
                raise Exception(f"Operation failed: {data}")
            
            await asyncio.sleep(interval)
        
        raise Exception("Operation timed out")


async def full_pipeline(imdf_zip_path: str) -> dict[str, str]:
    """
    Run the full Azure Maps Creator pipeline.
    
    1. Upload IMDF
    2. Create Dataset
    3. Create Tileset
    4. Create Stateset
    
    Returns:
        Dict with all created resource IDs
    """
    service = AzureMapsCreatorService()
    
    # Upload
    udid = await service.upload_imdf(imdf_zip_path)
    
    # Create dataset
    dataset_id = await service.create_dataset(udid)
    
    # Create tileset (for rendering)
    tileset_id = await service.create_tileset(dataset_id)
    
    # Create stateset (for dynamic styling)
    stateset_id = await service.create_stateset(dataset_id)
    
    result = {
        "udid": udid,
        "dataset_id": dataset_id,
        "tileset_id": tileset_id,
        "stateset_id": stateset_id,
    }
    
    logger.info(f"Pipeline complete: {result}")
    
    print("\n" + "=" * 50)
    print("✅ Azure Maps Creator Setup Complete!")
    print("=" * 50)
    print(f"\nAdd these to your .env file:\n")
    print(f"AZURE_MAPS_TILESET_ID={tileset_id}")
    print(f"AZURE_MAPS_STATESET_ID={stateset_id}")
    print(f"AZURE_MAPS_DATASET_ID={dataset_id}")
    print("=" * 50)
    
    return result
