import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Navigation, MapPin, Loader2, AlertTriangle, Route, Clock, Footprints, X, ArrowUpDown, Box, Layers, ChevronRight, Sparkles, Building2, ArrowRight } from 'lucide-react';
import { getFloorplanUnits, getFloorplanLevels, getFloorplanAmenities, getFloorplanOpenings, getSmartNavigation, type NavigationResponse } from '@/services/api';

interface MapProps {
  floor: number;
  destination: string | null;
  startingPoint?: string | null;
  currentLocation?: { x: number; y: number } | null;
  onDestinationReached?: () => void;
  onFloorChange?: (floor: number) => void;
  onFeatureClick?: (featureId: string, properties: any) => void;
  onSetDestination?: (featureId: string) => void;
  onSetStartingPoint?: (featureId: string) => void;
}

// Modern, professional color palette - Soft, cohesive pastels with good contrast
const CATEGORY_COLORS: Record<string, string> = {
  // Meeting Spaces - Cool blues/purples
  'conferenceroom': '#818CF8', // Soft indigo
  'huddleroom': '#A78BFA', // Light violet
  'phonebooth': '#C4B5FD', // Pale purple
  
  // Work Spaces - Calm greens/teals
  'office': '#6EE7B7', // Soft mint
  'privateoffice': '#5EEAD4', // Teal mint
  'workspace': '#99F6E4', // Light teal
  
  // Common Areas - Warm corals/oranges
  'breakroom': '#FCA5A5', // Soft coral
  'cafeteria': '#FDBA74', // Peach
  'lounge': '#FCD34D', // Soft gold
  'reception': '#F9A8D4', // Soft pink
  
  // Utilities - Neutral tones
  'restroom': '#A5B4FC', // Soft periwinkle
  'wellness': '#C7D2FE', // Lavender
  'storage': '#D1D5DB', // Cool gray
  'serverroom': '#9CA3AF', // Medium gray
  'mailroom': '#BEF264', // Soft lime
  'copyroom': '#A7F3D0', // Pale green
  
  // Navigation - Distinct colors
  'entrance': '#67E8F9', // Sky blue
  'walkway': '#F3F4F6', // Very light gray
  'elevator': '#CBD5E1', // Slate
  'stairs': '#E2E8F0', // Light slate
  
  'default': '#F8FAFC', // Near white
};

export function MapLibreMap({
  floor,
  destination,
  startingPoint,
  currentLocation,
  onDestinationReached,
  onFeatureClick,
  onSetDestination,
  onSetStartingPoint,
}: MapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [_selectedFeature, setSelectedFeature] = useState<string | null>(null);
  const [navigationRoute, setNavigationRoute] = useState<NavigationResponse | null>(null);
  const [isNavigating, setIsNavigating] = useState(false);
  const [navigationError, setNavigationError] = useState<string | null>(null);
  const [clickedFeature, setClickedFeature] = useState<{id: string; name: string; category: string} | null>(null);
  const [is3DView, setIs3DView] = useState(false);
  const [isLegendCollapsed, setIsLegendCollapsed] = useState(true);

  // Force-connect floors for multi-floor navigation on mount
  useEffect(() => {
    const connectFloors = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/floorplan/navigate/force-connect-floors', {
          method: 'POST',
        });
        const data = await response.json();
        console.log('🔗 Multi-floor connections established:', data);
      } catch (err) {
        console.error('Failed to establish multi-floor connections:', err);
      }
    };
    connectFloors();
  }, []);

  // Fetch floor levels
  const { data: levelsData } = useQuery({
    queryKey: ['floorplanLevels'],
    queryFn: getFloorplanLevels,
  });

  // Fetch units for current floor
  const { data: unitsData, isLoading: unitsLoading } = useQuery({
    queryKey: ['floorplanUnits', floor],
    queryFn: () => getFloorplanUnits(floor),
    enabled: !!floor,
  });

  // Fetch amenities (workstations) for current floor
  const { data: amenitiesData } = useQuery({
    queryKey: ['floorplanAmenities', floor],
    queryFn: () => getFloorplanAmenities(floor),
    enabled: !!floor,
  });

  // Fetch openings (doors) for current floor
  const { data: openingsData } = useQuery({
    queryKey: ['floorplanOpenings', floor],
    queryFn: () => getFloorplanOpenings(floor),
    enabled: !!floor,
  });

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    console.log('Initializing MapLibre map...');

    try {
      const map = new maplibregl.Map({
        container: mapContainerRef.current,
        style: {
          version: 8,
          sources: {},
          glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
          layers: [
            {
              id: 'background',
              type: 'background',
              paint: {
                'background-color': '#FAFBFC', // Clean, crisp white background
              },
            },
          ],
        },
        center: [-96.797, 32.7767], // Will be updated when data loads
        zoom: 18,
        pitch: 0,
        bearing: 0,
        maxPitch: 70,
      });

      // Add navigation control (zoom) to top-right, below our custom controls
      map.addControl(new maplibregl.NavigationControl(), 'top-right');

      map.on('load', () => {
        console.log('Map loaded successfully');
        mapRef.current = map;
        setIsLoading(false);
      });

      map.on('error', (e) => {
        console.error('Map error:', e);
        setError('Failed to load map');
      });

      return () => {
        map.remove();
        mapRef.current = null;
      };
    } catch (err) {
      console.error('Map initialization error:', err);
      setError(`Failed to initialize map: ${err}`);
      setIsLoading(false);
    }
  }, []);

  // Update floor data when floor changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !unitsData || unitsLoading) {
      console.log('Skipping floor data update:', { hasMap: !!map, hasUnitsData: !!unitsData, unitsLoading });
      return;
    }

    const features = unitsData.features || [];
    console.log(`Loading ${features.length} features for floor ${floor}`);
    
    // Remove existing layers and source
    if (map.getLayer('units-3d')) map.removeLayer('units-3d');
    if (map.getLayer('units-fill')) map.removeLayer('units-fill');
    if (map.getLayer('units-outline')) map.removeLayer('units-outline');
    if (map.getLayer('units-labels')) map.removeLayer('units-labels');
    if (map.getLayer('units-highlight')) map.removeLayer('units-highlight');
    if (map.getSource('units')) map.removeSource('units');

    if (features.length === 0) {
      console.log('No features for floor', floor);
      return;
    }

    // Add source - backend sends feature IDs, tell MapLibre to use them
    map.addSource('units', {
      type: 'geojson',
      data: unitsData,
      generateId: false, // Don't auto-generate IDs, use feature IDs from GeoJSON
    });

    // Add fill layer with category-based colors - Modern pastel look
    map.addLayer({
      id: 'units-fill',
      type: 'fill',
      source: 'units',
      paint: {
        'fill-color': [
          'match',
          ['get', 'category'],
          'conferenceroom', CATEGORY_COLORS['conferenceroom'],
          'huddleroom', CATEGORY_COLORS['huddleroom'],
          'office', CATEGORY_COLORS['office'],
          'privateoffice', CATEGORY_COLORS['privateoffice'],
          'workspace', CATEGORY_COLORS['workspace'],
          'restroom', CATEGORY_COLORS['restroom'],
          'breakroom', CATEGORY_COLORS['breakroom'],
          'reception', CATEGORY_COLORS['reception'],
          'entrance', CATEGORY_COLORS['entrance'],
          'walkway', CATEGORY_COLORS['walkway'],
          'elevator', CATEGORY_COLORS['elevator'],
          'stairs', CATEGORY_COLORS['stairs'],
          'storage', CATEGORY_COLORS['storage'],
          'serverroom', CATEGORY_COLORS['serverroom'],
          'lounge', CATEGORY_COLORS['lounge'],
          'wellness', CATEGORY_COLORS['wellness'],
          'phonebooth', CATEGORY_COLORS['phonebooth'],
          'mailroom', CATEGORY_COLORS['mailroom'],
          'copyroom', CATEGORY_COLORS['copyroom'],
          'cafeteria', CATEGORY_COLORS['cafeteria'],
          /* default */ CATEGORY_COLORS.default,
        ],
        'fill-opacity': is3DView ? 0 : 0.85, // Higher opacity for more solid look
      },
    });

    // Add 3D extrusion layer (only visible in 3D mode) - Modern look
    map.addLayer({
      id: 'units-3d',
      type: 'fill-extrusion',
      source: 'units',
      paint: {
        'fill-extrusion-color': [
          'match',
          ['get', 'category'],
          'conferenceroom', CATEGORY_COLORS['conferenceroom'],
          'huddleroom', CATEGORY_COLORS['huddleroom'],
          'office', CATEGORY_COLORS['office'],
          'privateoffice', CATEGORY_COLORS['privateoffice'],
          'workspace', CATEGORY_COLORS['workspace'],
          'restroom', CATEGORY_COLORS['restroom'],
          'breakroom', CATEGORY_COLORS['breakroom'],
          'reception', CATEGORY_COLORS['reception'],
          'entrance', CATEGORY_COLORS['entrance'],
          'walkway', '#F3F4F6', // Very light for walkways in 3D
          'elevator', CATEGORY_COLORS['elevator'],
          'stairs', CATEGORY_COLORS['stairs'],
          'storage', CATEGORY_COLORS['storage'],
          'serverroom', CATEGORY_COLORS['serverroom'],
          'lounge', CATEGORY_COLORS['lounge'],
          'wellness', CATEGORY_COLORS['wellness'],
          'phonebooth', CATEGORY_COLORS['phonebooth'],
          'mailroom', CATEGORY_COLORS['mailroom'],
          'copyroom', CATEGORY_COLORS['copyroom'],
          'cafeteria', CATEGORY_COLORS['cafeteria'],
          /* default */ CATEGORY_COLORS.default,
        ],
        'fill-extrusion-height': [
          'match',
          ['get', 'category'],
          'walkway', 0.5, // Very low for walkways
          'entrance', 2,
          'elevator', 12, // Taller for elevator
          'stairs', 12, // Taller for stairs
          'conferenceroom', 8, // Medium for conference
          'privateoffice', 8,
          8, // Default height
        ],
        'fill-extrusion-base': 0,
        'fill-extrusion-opacity': is3DView ? 0.9 : 0,
      },
    });

    // Add outline layer - subtle, refined borders
    map.addLayer({
      id: 'units-outline',
      type: 'line',
      source: 'units',
      paint: {
        'line-color': [
          'match',
          ['get', 'category'],
          'walkway', '#E5E7EB',
          'stairs', '#CBD5E1',
          'elevator', '#CBD5E1',
          '#94A3B8', // Default soft slate outline
        ],
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          16, 0.3,
          18, 0.5,
          20, 0.75,
          22, 1,
        ],
      },
    });

    // Add highlight layer for selected/hovered - Modern glow effect
    map.addLayer({
      id: 'units-highlight',
      type: 'line',
      source: 'units',
      paint: {
        'line-color': '#6366F1',
        'line-width': 2.5,
        'line-blur': 1,
      },
      filter: ['==', ['id'], ''],
    });

    // Add labels - clean, readable typography
    map.addLayer({
      id: 'units-labels',
      type: 'symbol',
      source: 'units',
      layout: {
        'text-field': ['get', 'name'],
        'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
        'text-size': [
          'interpolate',
          ['linear'],
          ['zoom'],
          16, 9,
          18, 11,
          20, 13,
          22, 15,
        ],
        'text-anchor': 'center',
        'text-allow-overlap': false,
        'text-ignore-placement': false,
        'text-optional': true,
        'text-max-width': 10,
        'text-padding': 2,
        'text-letter-spacing': 0.01,
      },
      paint: {
        'text-color': '#1F2937',
        'text-halo-color': '#FFFFFF',
        'text-halo-width': 2,
        'text-halo-blur': 0.5,
      },
    });

    // Fit bounds to features with responsive padding
    if (features.length > 0) {
      const bounds = new maplibregl.LngLatBounds();
      features.forEach((feature: any) => {
        if (feature.geometry?.coordinates) {
          const coords = feature.geometry.coordinates[0];
          coords.forEach((coord: [number, number]) => {
            bounds.extend(coord);
          });
        }
      });
      
      // Responsive padding based on screen size
      const isMobile = window.innerWidth < 640;
      const isTablet = window.innerWidth >= 640 && window.innerWidth < 1024;
      const padding = isMobile ? 20 : isTablet ? 40 : 60;
      
      map.fitBounds(bounds, {
        padding: {
          top: padding + 60, // Extra for header
          bottom: padding + 80, // Extra for navigation panel
          left: padding,
          right: padding,
        },
        duration: 500,
      });
    }

  }, [unitsData, unitsLoading, floor, is3DView]);

  // Display amenities (workstations) on the map
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !amenitiesData) {
      return;
    }

    const features = amenitiesData.features || [];
    console.log(`Loading ${features.length} amenities for floor ${floor}`);

    // Remove existing amenity layers
    if (map.getLayer('amenities')) map.removeLayer('amenities');
    if (map.getLayer('amenities-labels')) map.removeLayer('amenities-labels');
    if (map.getSource('amenities')) map.removeSource('amenities');

    if (features.length === 0) {
      return;
    }

    // Add amenities source
    map.addSource('amenities', {
      type: 'geojson',
      data: amenitiesData,
    });

    // Add workstation markers - subtle, modern style
    map.addLayer({
      id: 'amenities',
      type: 'circle',
      source: 'amenities',
      paint: {
        'circle-radius': 4,
        'circle-color': '#94A3B8', // Soft slate
        'circle-stroke-width': 1,
        'circle-stroke-color': 'rgba(255, 255, 255, 0.9)',
        'circle-opacity': 0.75,
      },
    });

    // No employee name labels - keep it clean

    // Add click handler for workstations
    const handleAmenityClick = (e: maplibregl.MapMouseEvent) => {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ['amenities'],
      });

      if (features.length > 0) {
        const feature = features[0];
        const props = feature.properties;
        
        // Create popup with employee info
        const popup = new maplibregl.Popup({ closeButton: true, closeOnClick: true })
          .setLngLat((feature.geometry as any).coordinates)
          .setHTML(`
            <div class="p-3">
              <div class="flex items-center gap-2 mb-2">
                <div class="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
                  <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </div>
                <div>
                  <p class="font-medium text-gray-900 dark:text-white">${props.employee_name || 'Unknown'}</p>
                  <p class="text-xs text-gray-500">${props.department || ''}</p>
                </div>
              </div>
              <div class="space-y-1 text-sm">
                <p class="text-gray-600"><span class="font-medium">Desk:</span> ${props.name || ''}</p>
                <p class="text-gray-600"><span class="font-medium">ID:</span> ${props.employee_id || ''}</p>
              </div>
            </div>
          `)
          .addTo(map);

        popupRef.current = popup;
      }
    };

    const handleAmenityMouseEnter = () => {
      map.getCanvas().style.cursor = 'pointer';
    };

    const handleAmenityMouseLeave = () => {
      map.getCanvas().style.cursor = '';
    };

    map.on('click', 'amenities', handleAmenityClick);
    map.on('mouseenter', 'amenities', handleAmenityMouseEnter);
    map.on('mouseleave', 'amenities', handleAmenityMouseLeave);

    return () => {
      map.off('click', 'amenities', handleAmenityClick);
      map.off('mouseenter', 'amenities', handleAmenityMouseEnter);
      map.off('mouseleave', 'amenities', handleAmenityMouseLeave);
    };
  }, [amenitiesData, floor]);

  // Display openings (doors/passages) on the map
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !openingsData) {
      return;
    }

    const features = openingsData.features || [];
    console.log(`Loading ${features.length} openings (doors) for floor ${floor}`);

    // Remove existing opening layers
    if (map.getLayer('openings-line')) map.removeLayer('openings-line');
    if (map.getLayer('openings-glow')) map.removeLayer('openings-glow');
    if (map.getLayer('openings-icons')) map.removeLayer('openings-icons');
    if (map.getSource('openings')) map.removeSource('openings');

    if (features.length === 0) {
      return;
    }

    // Add openings source
    map.addSource('openings', {
      type: 'geojson',
      data: openingsData,
    });

    // Add subtle glow effect for doors
    map.addLayer({
      id: 'openings-glow',
      type: 'line',
      source: 'openings',
      paint: {
        'line-color': [
          'match',
          ['get', 'category'],
          'entrance', '#6EE7B7', // Soft mint for entrances
          'door', '#FCD34D', // Soft gold for doors
          'passage', '#A5B4FC', // Soft periwinkle for passages
          '#C4B5FD', // Pale purple default
        ],
        'line-width': 6,
        'line-opacity': 0.4,
        'line-blur': 2,
      },
    });

    // Add door lines - refined
    map.addLayer({
      id: 'openings-line',
      type: 'line',
      source: 'openings',
      paint: {
        'line-color': [
          'match',
          ['get', 'category'],
          'entrance', '#34D399', // Mint green
          'door', '#FBBF24', // Soft amber
          'passage', '#818CF8', // Soft indigo
          '#A78BFA', // Light violet
        ],
        'line-width': 3,
        'line-opacity': 0.85,
      },
      layout: {
        'line-cap': 'round',
      },
    });

    // Add door indicators using circles at midpoints
    // Convert LineStrings to Points at their midpoint for icons
    const doorPoints: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: features.map((f: any) => {
        const coords = f.geometry.coordinates;
        // Get midpoint of the line
        const midX = (coords[0][0] + coords[coords.length - 1][0]) / 2;
        const midY = (coords[0][1] + coords[coords.length - 1][1]) / 2;
        return {
          type: 'Feature' as const,
          properties: f.properties,
          geometry: {
            type: 'Point' as const,
            coordinates: [midX, midY],
          },
        };
      }),
    };

    if (map.getSource('openings-points')) {
      (map.getSource('openings-points') as maplibregl.GeoJSONSource).setData(doorPoints);
    } else {
      map.addSource('openings-points', {
        type: 'geojson',
        data: doorPoints,
      });
    }

    // Add door icon circles - modern style
    if (!map.getLayer('openings-icons')) {
      map.addLayer({
        id: 'openings-icons',
        type: 'circle',
        source: 'openings-points',
        paint: {
          'circle-radius': 5,
          'circle-color': [
            'match',
            ['get', 'category'],
            'entrance', '#34D399',
            'door', '#FBBF24',
            'passage', '#818CF8',
            '#A78BFA',
          ],
          'circle-stroke-width': 1.5,
          'circle-stroke-color': 'rgba(255, 255, 255, 0.9)',
        },
      });
    }

  }, [openingsData, floor]);

  // Toggle 3D view
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (is3DView) {
      map.easeTo({
        pitch: 60,
        bearing: -20,
        duration: 1000,
      });
    } else {
      map.easeTo({
        pitch: 0,
        bearing: 0,
        duration: 1000,
      });
    }
  }, [is3DView]);

  // Fetch navigation route when destination is set
  useEffect(() => {
    if (!destination) {
      setNavigationRoute(null);
      setNavigationError(null);
      return;
    }

    const fetchRoute = async () => {
      console.log('🧭 Starting navigation:', {
        destination,
        startingPoint: startingPoint || 'auto-selected',
      });
      
      setIsNavigating(true);
      setNavigationError(null);
      try {
        // Use custom start point if provided, otherwise use smart navigation (Main Entrance)
        const route = startingPoint
          ? await getSmartNavigation(destination, startingPoint)
          : await getSmartNavigation(destination);
        
        console.log('🧭 Navigation response:', route);
        
        if (route.success) {
          console.log('✅ Navigation successful:', {
            distance: route.total_distance_meters,
            time: route.estimated_time_seconds,
            steps: route.steps.length,
          });
          setNavigationRoute(route);
        } else {
          console.error('❌ Navigation failed:', route.error);
          setNavigationError(route.error || 'Could not find a route');
          setNavigationRoute(null);
        }
      } catch (err) {
        console.error('❌ Navigation error:', err);
        setNavigationError('Failed to calculate route');
        setNavigationRoute(null);
      } finally {
        setIsNavigating(false);
      }
    };

    fetchRoute();
  }, [destination, startingPoint]);

  // Draw navigation route on map
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Remove existing route layers
    if (map.getLayer('navigation-route')) map.removeLayer('navigation-route');
    if (map.getLayer('navigation-route-outline')) map.removeLayer('navigation-route-outline');
    if (map.getLayer('navigation-points')) map.removeLayer('navigation-points');
    if (map.getSource('navigation-route')) map.removeSource('navigation-route');
    if (map.getSource('navigation-points')) map.removeSource('navigation-points');

    if (!navigationRoute || !navigationRoute.geometry.coordinates.length) {
      return;
    }

    // Add route line source
    map.addSource('navigation-route', {
      type: 'geojson',
      data: {
        type: 'Feature',
        properties: {},
        geometry: navigationRoute.geometry,
      },
    });

    // Add route glow/outline - soft indigo glow
    map.addLayer({
      id: 'navigation-route-outline',
      type: 'line',
      source: 'navigation-route',
      layout: {
        'line-join': 'round',
        'line-cap': 'round',
      },
      paint: {
        'line-color': '#A5B4FC', // Soft periwinkle
        'line-width': 12,
        'line-opacity': 0.35,
        'line-blur': 3,
      },
    });

    // Add main route line - clean solid design
    map.addLayer({
      id: 'navigation-route',
      type: 'line',
      source: 'navigation-route',
      layout: {
        'line-join': 'round',
        'line-cap': 'round',
      },
      paint: {
        'line-color': '#6366F1', // Indigo
        'line-width': 4,
        'line-opacity': 0.95,
      },
    });

    // Add start/end markers
    const coordinates = navigationRoute.geometry.coordinates;
    if (coordinates.length >= 2) {
      const startPoint = coordinates[0];
      const endPoint = coordinates[coordinates.length - 1];

      map.addSource('navigation-points', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [
            {
              type: 'Feature',
              properties: { type: 'start' },
              geometry: { type: 'Point', coordinates: startPoint },
            },
            {
              type: 'Feature',
              properties: { type: 'end' },
              geometry: { type: 'Point', coordinates: endPoint },
            },
          ],
        },
      });

      map.addLayer({
        id: 'navigation-points',
        type: 'circle',
        source: 'navigation-points',
        paint: {
          'circle-radius': 7,
          'circle-color': [
            'match',
            ['get', 'type'],
            'start', '#34D399', // Soft mint green
            'end', '#F87171', // Soft coral red
            '#818CF8', // Soft indigo
          ],
          'circle-stroke-width': 2.5,
          'circle-stroke-color': 'rgba(255, 255, 255, 0.95)',
        },
      });

      // Fit bounds to show entire route with responsive padding
      const bounds = new maplibregl.LngLatBounds();
      coordinates.forEach((coord: [number, number]) => bounds.extend(coord));
      const isMobile = window.innerWidth < 640;
      const isTablet = window.innerWidth >= 640 && window.innerWidth < 1024;
      const routePadding = isMobile ? 40 : isTablet ? 60 : 80;
      map.fitBounds(bounds, {
        padding: {
          top: routePadding + 60,
          bottom: routePadding + 120, // Extra for navigation panel
          left: routePadding,
          right: routePadding,
        },
        duration: 500,
      });
    }
  }, [navigationRoute]);

  // Handle feature click
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer('units-fill')) {
      console.log('Click handler setup skipped - map or layer not ready');
      return;
    }

    console.log('Setting up click handlers on units-fill layer');

    const handleClick = (e: maplibregl.MapMouseEvent) => {
      // Remove existing popup
      if (popupRef.current) {
        popupRef.current.remove();
        popupRef.current = null;
      }

      const features = map.queryRenderedFeatures(e.point, {
        layers: ['units-fill'],
      });

      if (features.length > 0) {
        const feature = features[0];
        // Use feature_id from properties (backend stores the real ID here)
        const featureId = feature.properties?.feature_id || feature.id as string;
        const properties = feature.properties;

        console.log('Room clicked:', featureId, properties);

        setSelectedFeature(featureId);
        
        // Highlight selected feature using feature_id property
        map.setFilter('units-highlight', ['==', ['get', 'feature_id'], featureId]);

        // Parse name from properties
        let featureName = properties.name || featureId;
        if (typeof featureName === 'string' && featureName.startsWith('{')) {
          try {
            featureName = JSON.parse(featureName).en || featureName;
          } catch {}
        }
        
        const category = properties.category || '';
        
        // Store clicked feature info
        console.log('Setting clickedFeature:', { id: featureId, name: featureName, category });
        setClickedFeature({ id: featureId, name: featureName, category });

        if (onFeatureClick) {
          const parsedProps = { ...properties };
          if (typeof parsedProps.name === 'string' && parsedProps.name.startsWith('{')) {
            try {
              parsedProps.name = JSON.parse(parsedProps.name);
            } catch {}
          }
          onFeatureClick(featureId, parsedProps);
        }
      } else {
        console.log('Clicked outside of rooms');
        setSelectedFeature(null);
        setClickedFeature(null);
        map.setFilter('units-highlight', ['==', ['id'], '']);
      }
    };

    const handleMouseEnter = () => {
      map.getCanvas().style.cursor = 'pointer';
    };

    const handleMouseLeave = () => {
      map.getCanvas().style.cursor = '';
    };

    map.on('click', handleClick);
    map.on('mouseenter', 'units-fill', handleMouseEnter);
    map.on('mouseleave', 'units-fill', handleMouseLeave);

    return () => {
      map.off('click', handleClick);
      map.off('mouseenter', 'units-fill', handleMouseEnter);
      map.off('mouseleave', 'units-fill', handleMouseLeave);
    };
  }, [onFeatureClick, unitsData, onSetDestination, onSetStartingPoint]);

  // Handle destination highlight
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer('units-highlight')) return;

    if (destination) {
      map.setFilter('units-highlight', ['==', ['id'], destination]);
      
      // Try to zoom to destination feature
      const features = unitsData?.features?.filter((f: any) => f.id === destination);
      if (features && features.length > 0) {
        const coords = features[0].geometry.coordinates[0];
        const bounds = new maplibregl.LngLatBounds();
        coords.forEach((coord: [number, number]) => bounds.extend(coord));
        map.fitBounds(bounds, { padding: 100, duration: 500 });
      }
    } else {
      map.setFilter('units-highlight', ['==', ['id'], '']);
    }
  }, [destination, unitsData]);

  // Handle current location marker
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !currentLocation) return;

    // Remove existing marker
    const existingMarker = document.querySelector('.current-location-marker');
    if (existingMarker) existingMarker.remove();

    // Add marker at current location
    const el = document.createElement('div');
    el.className = 'current-location-marker';
    el.style.cssText = `
      width: 20px;
      height: 20px;
      background: #4F46E5;
      border: 3px solid white;
      border-radius: 50%;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    `;

    new maplibregl.Marker({ element: el })
      .setLngLat([currentLocation.x, currentLocation.y])
      .addTo(map);
  }, [currentLocation]);

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-100 dark:bg-dark-800">
        <div className="text-center p-6 max-w-md">
          <div className="w-16 h-16 mx-auto mb-4 bg-amber-100 dark:bg-amber-900/30 rounded-full flex items-center justify-center">
            <AlertTriangle className="w-8 h-8 text-amber-600 dark:text-amber-400" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Map Error
          </h3>
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            {error}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full" style={{ minHeight: '500px' }}>
      {/* Map container */}
      <div
        ref={mapContainerRef}
        className="absolute inset-0"
        style={{ background: '#e5e7eb', width: '100%', height: '100%' }}
      />

      {/* Loading overlay */}
      {(isLoading || unitsLoading) && (
        <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-gray-50/95 to-gray-100/95 dark:from-dark-900/95 dark:to-dark-800/95 z-10 backdrop-blur-sm">
          <div className="text-center">
            <div className="relative">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-indigo-600 flex items-center justify-center mx-auto mb-4 shadow-xl shadow-primary-500/30 animate-pulse">
                <Building2 className="w-8 h-8 text-white" />
              </div>
              <div className="absolute -inset-1 bg-gradient-to-br from-primary-500 to-indigo-600 rounded-2xl blur-lg opacity-30 animate-pulse" />
            </div>
            <p className="text-gray-600 dark:text-gray-300 font-medium">Loading floor plan...</p>
            <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">Preparing your workspace map</p>
          </div>
        </div>
      )}

      {/* Floor indicator - responsive positioning */}
      {!isLoading && levelsData && !navigationRoute && !isNavigating && (
        <div className="absolute top-20 sm:top-32 right-2 sm:right-4 z-10 animate-slide-up">
          <div className="bg-white/95 dark:bg-dark-800/95 backdrop-blur-sm rounded-lg sm:rounded-xl shadow-lg border border-gray-200/50 dark:border-gray-700/50 px-2 sm:px-3 py-1.5 sm:py-2">
            <div className="flex items-center gap-2 sm:gap-2.5">
              <div className="w-6 h-6 sm:w-8 sm:h-8 rounded-md sm:rounded-lg bg-gradient-to-br from-primary-500 to-indigo-600 flex items-center justify-center shadow-md">
                <Building2 className="w-3 h-3 sm:w-4 sm:h-4 text-white" />
              </div>
              <div>
                <p className="text-[8px] sm:text-[9px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500">Floor</p>
                <p className="text-lg sm:text-xl font-bold text-gray-900 dark:text-white -mt-0.5">{floor}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3D View Toggle Button - responsive positioning */}
      <div className="absolute top-2 sm:top-4 right-12 sm:right-14 z-10 flex flex-col gap-2">
        <button
          onClick={() => setIs3DView(!is3DView)}
          className={`group relative flex items-center gap-1.5 sm:gap-2.5 px-2.5 sm:px-4 py-2 sm:py-2.5 rounded-lg sm:rounded-xl shadow-lg transition-all duration-300 hover:scale-105 active:scale-95 ${
            is3DView 
              ? 'bg-gradient-to-r from-primary-600 to-indigo-600 text-white shadow-primary-500/25' 
              : 'bg-white/95 dark:bg-dark-800/95 backdrop-blur-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-dark-700 border border-gray-200/50 dark:border-gray-700/50'
          }`}
          title={is3DView ? 'Switch to 2D View' : 'Switch to 3D View'}
        >
          <Box className={`w-3.5 h-3.5 sm:w-4 sm:h-4 transition-transform duration-300 ${is3DView ? 'rotate-12' : ''}`} />
          <span className="text-xs sm:text-sm font-semibold">{is3DView ? '3D' : '2D'}</span>
          {is3DView && <Sparkles className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-amber-300 animate-pulse" />}
        </button>
      </div>

      {/* Unified Map Legend - Compact design with collapse */}
      {!navigationRoute && !isNavigating && (
        <div className={`absolute bottom-2 sm:bottom-4 right-2 sm:right-4 z-10 transition-all duration-300 ${isLegendCollapsed ? 'w-auto' : 'w-[220px] sm:w-[260px]'}`}>
          <div className="bg-white/95 dark:bg-dark-800/95 backdrop-blur-sm rounded-xl shadow-lg border border-gray-200/50 dark:border-gray-700/50 overflow-hidden">
            {/* Header - Always visible */}
            <button
              onClick={() => setIsLegendCollapsed(!isLegendCollapsed)}
              className="w-full px-2.5 sm:px-3 py-1.5 sm:py-2 bg-gray-50/80 dark:bg-dark-700/80 border-b border-gray-200/50 dark:border-gray-700/50 flex items-center justify-between hover:bg-gray-100/80 dark:hover:bg-dark-600/80 transition-all touch-manipulation"
            >
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 sm:w-6 sm:h-6 rounded-md bg-gradient-to-br from-primary-500 to-indigo-600 flex items-center justify-center">
                  <Layers className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-white" />
                </div>
                <span className="font-semibold text-[10px] sm:text-xs text-gray-700 dark:text-gray-300">Legend</span>
              </div>
              <ChevronRight className={`w-3 h-3 sm:w-3.5 sm:h-3.5 text-gray-400 transition-transform duration-300 ${isLegendCollapsed ? '' : 'rotate-90'}`} />
            </button>
            
            {/* Collapsible Content */}
            <div className={`transition-all duration-300 overflow-hidden ${isLegendCollapsed ? 'max-h-0' : 'max-h-[300px] sm:max-h-[400px]'}`}>
              <div className="p-2 sm:p-2.5 space-y-1.5 sm:space-y-2">
                {/* Rooms Section */}
                <div>
                  <p className="text-[8px] sm:text-[9px] uppercase tracking-wider font-bold text-gray-400 mb-1 sm:mb-1.5">Spaces</p>
                  <div className="grid grid-cols-2 gap-x-1.5 sm:gap-x-2 gap-y-0.5">
                    {[
                      { key: 'conferenceroom', label: 'Conference' },
                      { key: 'huddleroom', label: 'Huddle' },
                      { key: 'office', label: 'Office' },
                      { key: 'workspace', label: 'Workspace' },
                      { key: 'restroom', label: 'Restroom' },
                      { key: 'breakroom', label: 'Break Room' },
                      { key: 'reception', label: 'Reception' },
                      { key: 'cafeteria', label: 'Cafeteria' },
                    ].map(({ key, label }) => (
                      <div key={key} className="flex items-center gap-1 sm:gap-1.5 py-0.5">
                        <div className="w-2 h-2 sm:w-2.5 sm:h-2.5 rounded-sm flex-shrink-0" style={{ background: CATEGORY_COLORS[key] }} />
                        <span className="text-[9px] sm:text-[10px] text-gray-600 dark:text-gray-400">{label}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="border-t border-gray-200/50 dark:border-gray-700/50" />

                {/* Access & Transport */}
                <div>
                  <p className="text-[8px] sm:text-[9px] uppercase tracking-wider font-bold text-gray-400 mb-1 sm:mb-1.5">Access & Transport</p>
                  <div className="grid grid-cols-2 gap-x-1.5 sm:gap-x-2 gap-y-0.5">
                    {[
                      { color: '#34D399', label: 'Entrance', round: true },
                      { color: '#FBBF24', label: 'Door', round: true },
                      { color: '#818CF8', label: 'Passage', round: true },
                      { key: 'walkway', label: 'Hallway' },
                      { key: 'elevator', label: 'Elevator' },
                      { key: 'stairs', label: 'Stairs' },
                    ].map((item, idx) => (
                      <div key={idx} className="flex items-center gap-1 sm:gap-1.5 py-0.5">
                        <div 
                          className={`w-2 h-2 sm:w-2.5 sm:h-2.5 flex-shrink-0 ${item.round ? 'rounded-full' : 'rounded-sm'}`}
                          style={{ background: item.color || CATEGORY_COLORS[item.key!] }} 
                        />
                        <span className="text-[9px] sm:text-[10px] text-gray-600 dark:text-gray-400">{item.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Current location marker info */}
      {!isLoading && currentLocation && (
        <div className="absolute bottom-4 right-4 z-10">
          <div className="btn-secondary flex items-center gap-2 shadow-lg">
            <MapPin className="w-4 h-4 text-primary-600" />
            <span className="text-sm">You are here</span>
          </div>
        </div>
      )}

      {/* Feature action panel - responsive popup */}
      {clickedFeature && !isLoading && clickedFeature.id !== destination && (
        <div className="absolute top-2 sm:top-4 left-2 right-2 sm:left-auto sm:right-4 sm:w-80 z-20 animate-slide-up">
          <div className="relative group">
            <div className="absolute -inset-0.5 bg-gradient-to-br from-primary-500/20 via-indigo-500/20 to-purple-500/20 rounded-xl sm:rounded-2xl blur opacity-75 group-hover:opacity-100 transition-opacity duration-300" />
            <div className="relative card-premium p-3 sm:p-4 bg-white/98 dark:bg-dark-800/98">
              <div className="flex items-start justify-between gap-2 sm:gap-3 mb-3 sm:mb-4">
                <div className="flex items-center gap-2 sm:gap-3 flex-1 min-w-0">
                  <div 
                    className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg sm:rounded-xl flex-shrink-0 flex items-center justify-center shadow-lg" 
                    style={{ 
                      background: `linear-gradient(135deg, ${CATEGORY_COLORS[clickedFeature.category] || CATEGORY_COLORS.default}, ${CATEGORY_COLORS[clickedFeature.category] || CATEGORY_COLORS.default}dd)`,
                      boxShadow: `0 8px 16px -4px ${CATEGORY_COLORS[clickedFeature.category] || CATEGORY_COLORS.default}40`
                    }}
                  >
                    <MapPin className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-sm sm:text-base text-gray-900 dark:text-white truncate">
                      {clickedFeature.name}
                    </p>
                    <p className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400 capitalize truncate flex items-center gap-1 sm:gap-1.5 mt-0.5">
                      <span className="w-1 h-1 sm:w-1.5 sm:h-1.5 rounded-full bg-emerald-500" />
                      {clickedFeature.category?.replace(/([A-Z])/g, ' $1').trim() || 'Room'}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setClickedFeature(null)}
                  className="p-1.5 sm:p-2 rounded-lg sm:rounded-xl text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-700 transition-all flex-shrink-0"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              
              {/* Action buttons */}
              <div className="flex gap-2 sm:gap-2.5">
                {/* Navigate Here button */}
                <button
                  onClick={() => {
                    onSetDestination?.(clickedFeature.id);
                    setClickedFeature(null);
                  }}
                  className="flex-1 group flex items-center justify-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2.5 sm:py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-lg sm:rounded-xl text-xs sm:text-sm font-semibold transition-all shadow-lg shadow-blue-500/25 hover:shadow-xl hover:shadow-blue-500/30 hover:scale-[1.02] active:scale-[0.98]"
                >
                  <Navigation className="w-3.5 h-3.5 sm:w-4 sm:h-4 transition-transform group-hover:rotate-45" />
                  <span>Navigate</span>
                  <ArrowRight className="w-2.5 h-2.5 sm:w-3 sm:h-3 opacity-60 group-hover:translate-x-0.5 transition-transform" />
                </button>
                
                {/* I'm Here button - shows when there's a destination to set start point */}
                {destination && (
                  <button
                    onClick={() => {
                      onSetStartingPoint?.(clickedFeature.id);
                      setClickedFeature(null);
                    }}
                    className="flex-1 group flex items-center justify-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2.5 sm:py-3 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white rounded-lg sm:rounded-xl text-xs sm:text-sm font-semibold transition-all shadow-lg shadow-emerald-500/25 hover:shadow-xl hover:shadow-emerald-500/30 hover:scale-[1.02] active:scale-[0.98]"
                  >
                    <MapPin className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                    <span>I'm Here</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Navigation Panel - compact design */}
      {(destination || navigationRoute || isNavigating) && !isLoading && (
        <div className="absolute bottom-2 sm:bottom-4 left-2 sm:left-4 w-[calc(100%-1rem)] sm:w-[360px] sm:max-w-[calc(100vw-2rem)] z-10 animate-slide-up safe-area-bottom">
          <div className="bg-white/95 dark:bg-dark-800/95 backdrop-blur-sm rounded-xl shadow-xl border border-gray-200/50 dark:border-gray-700/50 overflow-hidden">
            {/* Loading state */}
            {isNavigating && (
              <div className="flex items-center gap-2 sm:gap-3 p-2.5 sm:p-3">
                <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-gradient-to-br from-primary-500 to-indigo-600 flex items-center justify-center">
                  <Loader2 className="w-4 h-4 sm:w-5 sm:h-5 text-white animate-spin" />
                </div>
                <div>
                  <p className="font-medium text-xs sm:text-sm text-gray-900 dark:text-white">Finding best route...</p>
                  <p className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">Calculating optimal path</p>
                </div>
              </div>
            )}

            {/* Navigation error */}
            {navigationError && !isNavigating && (
              <div className="flex items-center justify-between p-2.5 sm:p-3">
                <div className="flex items-center gap-2 sm:gap-3">
                  <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
                    <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                  </div>
                  <div>
                    <p className="font-semibold text-xs sm:text-sm text-gray-900 dark:text-white">Route Not Found</p>
                    <p className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400 line-clamp-1">{navigationError}</p>
                  </div>
                </div>
                <button
                  onClick={onDestinationReached}
                  className="px-2.5 sm:px-3 py-1 sm:py-1.5 text-[10px] sm:text-xs font-medium text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors touch-manipulation"
                >
                  Clear
                </button>
              </div>
            )}

            {/* Active navigation route */}
            {navigationRoute && navigationRoute.success && !isNavigating && (
              <div className="flex flex-col max-h-[300px] sm:max-h-[400px]">
                {/* Header with destination info */}
                <div className="flex items-center justify-between p-2.5 sm:p-3 border-b border-gray-200/50 dark:border-gray-700/50 bg-gray-50/50 dark:bg-dark-700/50">
                  <div className="flex items-center gap-2 sm:gap-3 flex-1 min-w-0">
                    <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
                      <Route className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-bold text-xs sm:text-sm text-gray-900 dark:text-white truncate">
                        {navigationRoute.destination_name || 'Destination'}
                      </p>
                      <div className="flex items-center gap-1.5 sm:gap-2 text-[10px] sm:text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        <span className="flex items-center gap-0.5 sm:gap-1">
                          <Footprints className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-blue-500" />
                          {navigationRoute.total_distance_meters < 1000
                            ? `${Math.round(navigationRoute.total_distance_meters)}m`
                            : `${(navigationRoute.total_distance_meters / 1000).toFixed(1)}km`}
                        </span>
                        <span className="text-gray-300 dark:text-gray-600">•</span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3 text-emerald-500" />
                          {navigationRoute.estimated_time_seconds < 60
                            ? `${navigationRoute.estimated_time_seconds}s`
                            : `${Math.round(navigationRoute.estimated_time_seconds / 60)} min`}
                        </span>
                        {navigationRoute.is_multi_floor && (
                          <>
                            <span className="text-gray-300 dark:text-gray-600">•</span>
                            <span className="flex items-center gap-1 text-purple-600 dark:text-purple-400">
                              <ArrowUpDown className="w-3 h-3" />
                              Multi
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={onDestinationReached}
                    className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-all flex-shrink-0"
                    title="End navigation"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Multi-floor route summary */}
                {navigationRoute.is_multi_floor && navigationRoute.start_name && (
                  <div className="mx-3 mt-2 bg-purple-50 dark:bg-purple-900/20 rounded-lg px-3 py-2 border border-purple-200/50 dark:border-purple-800/50">
                    <div className="flex items-center gap-2">
                      <div className="flex flex-col items-center">
                        <div className="w-2 h-2 rounded-full bg-emerald-500" />
                        <div className="w-0.5 h-4 bg-gradient-to-b from-emerald-500 to-blue-500" />
                        <div className="w-2 h-2 rounded-full bg-blue-500" />
                      </div>
                      <div className="flex-1 text-xs space-y-1">
                        <p className="text-gray-600 dark:text-gray-400 truncate">
                          <span className="font-semibold text-emerald-600">From:</span> {navigationRoute.start_name} <span className="text-gray-400">(F{navigationRoute.start_level?.replace('level-', '')})</span>
                        </p>
                        <p className="text-gray-600 dark:text-gray-400 truncate">
                          <span className="font-semibold text-blue-600">To:</span> {navigationRoute.destination_name} <span className="text-gray-400">(F{navigationRoute.destination_level?.replace('level-', '')})</span>
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Navigation steps */}
                {navigationRoute.steps.length > 0 && (
                  <div className="flex-1 overflow-hidden flex flex-col min-h-0">
                    <div className="flex items-center justify-between px-3 py-2 bg-gray-50/80 dark:bg-dark-700/50">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Directions</p>
                      <span className="text-[10px] bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded-full font-medium">
                        {navigationRoute.steps.length} steps
                      </span>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-1.5 custom-scrollbar" style={{ maxHeight: '220px' }}>
                      {navigationRoute.steps.map((step, idx) => (
                        <div 
                          key={idx} 
                          className={`flex items-start gap-2 p-2 rounded-lg ${
                            step.floor_change 
                              ? 'bg-amber-50 dark:bg-amber-900/20 border border-amber-200/50 dark:border-amber-800/50' 
                              : 'bg-gray-50 dark:bg-dark-700/50'
                          }`}
                        >
                          <span className={`flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center font-bold text-[10px] ${
                            step.floor_change 
                              ? 'bg-amber-500 text-white' 
                              : 'bg-blue-500 text-white'
                          }`}>
                            {idx + 1}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs text-gray-700 dark:text-gray-300 leading-snug">
                              {step.instruction}
                              <span className="text-gray-400 ml-1">({Math.round(step.distance_meters)}m)</span>
                            </p>
                            {step.floor_change && (
                              <span className="inline-flex items-center gap-1 mt-1 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                                <ArrowUpDown className="w-2.5 h-2.5" />
                                Floor Change
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Destination selected but no route yet (no starting point) */}
            {destination && !navigationRoute && !isNavigating && !navigationError && (
              <div className="flex items-center justify-between p-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500 to-indigo-600 flex items-center justify-center animate-pulse">
                    <Navigation className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="font-bold text-sm text-gray-900 dark:text-white">Destination Selected</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Click a room to set start point</p>
                  </div>
                </div>
                <button
                  onClick={onDestinationReached}
                  className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-dark-700 rounded-lg transition-all"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Export as default Map for backward compatibility
export { MapLibreMap as Map };
