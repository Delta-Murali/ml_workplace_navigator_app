import { useEffect, useRef, useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getMapConfig, getBuildingInfo, getWayfindingPath } from '@/services/api';
import { Navigation, MapPin, Loader2, AlertTriangle } from 'lucide-react';

// Azure Maps SDK types
declare global {
  interface Window {
    atlas: any;
  }
}

interface MapProps {
  floor: number;
  destination: string | null;
  currentLocation?: { x: number; y: number } | null;
  onDestinationReached?: () => void;
  onFloorChange?: (floor: number) => void;
  onFeatureClick?: (featureId: string, properties: any) => void;
}

export function Map({
  floor,
  destination,
  currentLocation,
  onDestinationReached,
  onFloorChange,
  onFeatureClick,
}: MapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const indoorManagerRef = useRef<any>(null);
  const routeSourceRef = useRef<any>(null);
  
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sdkLoaded, setSdkLoaded] = useState(false);

  const { data: mapConfig } = useQuery({
    queryKey: ['mapConfig'],
    queryFn: getMapConfig,
  });

  const { data: buildingInfo } = useQuery({
    queryKey: ['buildingInfo'],
    queryFn: getBuildingInfo,
  });

  // Load Azure Maps SDK dynamically
  useEffect(() => {
    if (window.atlas) {
      setSdkLoaded(true);
      return;
    }

    const loadSDK = async () => {
      // Load CSS
      const cssLink = document.createElement('link');
      cssLink.rel = 'stylesheet';
      cssLink.href = 'https://atlas.microsoft.com/sdk/javascript/mapcontrol/3/atlas.min.css';
      document.head.appendChild(cssLink);

      // Load Indoor CSS
      const indoorCssLink = document.createElement('link');
      indoorCssLink.rel = 'stylesheet';
      indoorCssLink.href = 'https://atlas.microsoft.com/sdk/javascript/indoor/0.2/atlas-indoor.min.css';
      document.head.appendChild(indoorCssLink);

      // Load main SDK script
      const script = document.createElement('script');
      script.src = 'https://atlas.microsoft.com/sdk/javascript/mapcontrol/3/atlas.min.js';
      script.async = true;
      
      script.onload = () => {
        // Load Indoor module after main SDK
        const indoorScript = document.createElement('script');
        indoorScript.src = 'https://atlas.microsoft.com/sdk/javascript/indoor/0.2/atlas-indoor.min.js';
        indoorScript.async = true;
        indoorScript.onload = () => setSdkLoaded(true);
        indoorScript.onerror = () => setError('Failed to load Azure Maps Indoor SDK');
        document.head.appendChild(indoorScript);
      };
      
      script.onerror = () => setError('Failed to load Azure Maps SDK');
      document.head.appendChild(script);
    };

    loadSDK();
  }, []);

  // Initialize map when SDK is ready
  useEffect(() => {
    if (!sdkLoaded || !mapRef.current || !mapConfig) return;
    
    // Check if Azure Maps is configured
    if (!mapConfig.tileset_id) {
      setError('Azure Maps not configured. Add credentials to backend/.env');
      setIsLoading(false);
      return;
    }

    try {
      const atlas = window.atlas;
      
      // Create map instance
      const map = new atlas.Map(mapRef.current, {
        center: [-122.3321, 47.6062], // Default center - update per building
        zoom: 19,
        style: 'blank', // Use blank for indoor-only view
        language: 'en-US',
        authOptions: {
          authType: atlas.AuthenticationType.subscriptionKey,
          subscriptionKey: mapConfig.subscription_key,
        },
      });

      mapInstanceRef.current = map;

      map.events.add('ready', () => {
        // Add zoom and compass controls
        map.controls.add([
          new atlas.control.ZoomControl(),
          new atlas.control.CompassControl(),
        ], { position: 'top-left' });

        // Initialize Indoor Manager for IMDF-based indoor maps
        const indoorManager = new atlas.indoor.IndoorManager(map, {
          tilesetId: mapConfig.tileset_id,
          statesetId: mapConfig.stateset_id || undefined,
          levelControl: new atlas.indoor.LevelControl({ position: 'top-right' }),
        });

        indoorManagerRef.current = indoorManager;

        // Listen for floor/level changes from Indoor Manager
        map.events.add('levelchanged', indoorManager, (e: any) => {
          if (onFloorChange) {
            const newFloor = e.levelNumber + 1; // Convert ordinal to floor number
            onFloorChange(newFloor);
          }
        });

        // Create data source for navigation routes
        const routeSource = new atlas.source.DataSource('route-source');
        map.sources.add(routeSource);
        routeSourceRef.current = routeSource;

        // Add route layer with styling
        map.layers.add(new atlas.layer.LineLayer(routeSource, 'route-layer', {
          strokeColor: '#4F46E5',
          strokeWidth: 5,
          lineJoin: 'round',
          lineCap: 'round',
        }));

        // Add "You are here" marker layer
        map.layers.add(new atlas.layer.SymbolLayer(routeSource, 'marker-layer', {
          iconOptions: {
            image: 'marker-blue',
            allowOverlap: true,
          },
          filter: ['==', ['get', 'type'], 'current-location'],
        }));

        setIsLoading(false);
      });

      // Handle feature clicks for room selection
      map.events.add('click', (e: any) => {
        if (e.shapes && e.shapes.length > 0) {
          const shape = e.shapes[0];
          const properties = shape.getProperties?.() || {};
          const featureId = shape.getId?.() || properties.id;
          
          if (featureId && onFeatureClick) {
            onFeatureClick(featureId, properties);
          }
        }
      });

      return () => {
        indoorManagerRef.current?.dispose();
        mapInstanceRef.current?.dispose();
        mapInstanceRef.current = null;
        indoorManagerRef.current = null;
      };
    } catch (err) {
      setError(`Map initialization failed: ${err}`);
      setIsLoading(false);
    }
  }, [sdkLoaded, mapConfig, onFloorChange, onFeatureClick]);

  // Handle floor changes from parent component
  useEffect(() => {
    if (!indoorManagerRef.current || !buildingInfo) return;

    const levelOrdinal = floor - 1; // Convert floor number to ordinal (0-based)
    
    try {
      const facilityId = buildingInfo.building_id || 'default-facility';
      indoorManagerRef.current.setFacility(facilityId, levelOrdinal);
    } catch (err) {
      console.error('Failed to change floor:', err);
    }
  }, [floor, buildingInfo]);

  // Draw navigation route when destination changes
  const drawRoute = useCallback(async (destinationFeatureId: string) => {
    if (!mapInstanceRef.current || !routeSourceRef.current) return;

    try {
      const atlas = window.atlas;
      const startCoord = currentLocation 
        ? [currentLocation.x, currentLocation.y]
        : [-122.3321, 47.6062];

      // Call backend wayfinding API (proxies to Azure Maps)
      const wayfinding = await getWayfindingPath({
        from_lat: startCoord[1],
        from_lon: startCoord[0],
        to_feature_id: destinationFeatureId,
        facility_id: buildingInfo?.building_id,
      });

      routeSourceRef.current.clear();

      if (wayfinding.success && wayfinding.legs.length > 0) {
        // Draw the route path for each leg
        for (const leg of wayfinding.legs) {
          const coordinates: [number, number][] = leg.points.map(p => [p.longitude, p.latitude]);

          if (coordinates.length > 0) {
            const line = new atlas.data.LineString(coordinates);
            routeSourceRef.current.add(new atlas.Shape(line));
          }
        }
      }
    } catch (err) {
      console.error('Failed to draw route:', err);
    }
  }, [currentLocation, buildingInfo]);

  useEffect(() => {
    if (destination) {
      drawRoute(destination);
    } else {
      routeSourceRef.current?.clear();
    }
  }, [destination, drawRoute]);

  // Add current location marker
  useEffect(() => {
    if (!mapInstanceRef.current || !routeSourceRef.current || !currentLocation) return;
    
    const atlas = window.atlas;
    const point = new atlas.data.Point([currentLocation.x, currentLocation.y]);
    const shape = new atlas.Shape(point, 'current-location-marker');
    shape.addProperty('type', 'current-location');
    routeSourceRef.current.add(shape);
  }, [currentLocation]);

  // Show error state with configuration instructions
  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-100 dark:bg-dark-800">
        <div className="text-center p-6 max-w-md">
          <div className="w-16 h-16 mx-auto mb-4 bg-amber-100 dark:bg-amber-900/30 rounded-full flex items-center justify-center">
            <AlertTriangle className="w-8 h-8 text-amber-600 dark:text-amber-400" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Azure Maps Configuration Required
          </h3>
          <p className="text-gray-500 dark:text-gray-400 text-sm mb-4">
            {error}
          </p>
          <div className="text-left bg-gray-50 dark:bg-dark-700 rounded-lg p-4 text-xs">
            <p className="text-gray-600 dark:text-gray-300 font-medium mb-2">Setup steps:</p>
            <ol className="list-decimal list-inside space-y-1 text-gray-500 dark:text-gray-400">
              <li>Convert DWG floor plans to DXF format</li>
              <li>Run IMDF converter script</li>
              <li>Upload IMDF to Azure Maps Creator</li>
              <li>Add credentials to backend/.env</li>
            </ol>
            <div className="mt-3 font-mono text-primary-600 dark:text-primary-400">
              AZURE_MAPS_SUBSCRIPTION_KEY=...
              <br />
              AZURE_MAPS_TILESET_ID=...
              <br />
              AZURE_MAPS_STATESET_ID=...
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      {/* Map container - Azure Maps renders here */}
      <div
        ref={mapRef}
        className="absolute inset-0"
        style={{ background: '#e5e7eb' }}
      />

      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 dark:bg-dark-800 z-10">
          <div className="text-center">
            <Loader2 className="w-8 h-8 text-primary-600 animate-spin mx-auto mb-3" />
            <p className="text-gray-500 dark:text-gray-400">Loading indoor map...</p>
          </div>
        </div>
      )}

      {/* Current location marker info - shown when loc param is present */}
      {!isLoading && currentLocation && (
        <div className="absolute bottom-24 left-4 z-10">
          <div className="btn-secondary flex items-center gap-2 shadow-lg">
            <MapPin className="w-4 h-4 text-primary-600" />
            <span className="text-sm">You are here</span>
          </div>
        </div>
      )}

      {/* Navigation active indicator */}
      {destination && !isLoading && (
        <div className="absolute top-4 left-4 right-16 z-10">
          <div className="card p-4 shadow-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary-100 dark:bg-primary-900/30 rounded-lg">
                  <Navigation className="w-5 h-5 text-primary-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">
                    Navigating...
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Follow the blue path to your destination
                  </p>
                </div>
              </div>
              <button
                onClick={onDestinationReached}
                className="text-sm text-primary-600 dark:text-primary-400 font-medium hover:underline"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
