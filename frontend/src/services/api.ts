import axios from 'axios';

// Get API configuration from environment variables
const API_URL = import.meta.env.VITE_API_URL || '';
const API_PREFIX = import.meta.env.VITE_API_PREFIX || '/api';

// Build the base URL: if API_URL is set, use it with prefix; otherwise just use prefix for relative URLs
const baseURL = API_URL ? `${API_URL}${API_PREFIX}` : API_PREFIX;

const api = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Types
export interface SearchResult {
  type: 'employee' | 'room';
  id: number;
  name: string;
  floor: number;
  building: string;
  feature_id: string | null;
  // Employee specific
  email?: string;
  department?: string;
  title?: string;
  desk_id?: string;
  // Room specific
  display_name?: string;
  category?: string;
  capacity?: number;
  amenities?: string[];
  is_bookable?: boolean;
  is_accessible?: boolean;
}

export interface ParsedIntent {
  intent_type: string;
  target_name: string | null;
  target_category: string | null;
  floor: number | null;
  additional_context: string | null;
  confidence: number;
}

export interface SearchResponse {
  query: string;
  intent: ParsedIntent;
  results: SearchResult[];
  result_count: number;
}

export interface MapConfig {
  client_id: string;
  subscription_key: string;
  tileset_id: string;
  stateset_id: string;
  routeset_id: string;
  dataset_id: string;
}

export interface FloorInfo {
  floor_number: number;
  name: string;
  ordinal: number;
}

export interface BuildingInfo {
  building_id: string;
  name: string;
  floors: FloorInfo[];
}

// API functions
export async function search(
  query: string,
  options?: {
    floor?: number;
    currentX?: number;
    currentY?: number;
  }
): Promise<SearchResponse> {
  const response = await api.post<SearchResponse>('/search', {
    query,
    floor: options?.floor,
    current_x: options?.currentX,
    current_y: options?.currentY,
  });
  return response.data;
}

export async function quickSearch(
  query: string,
  floor?: number
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query });
  if (floor !== undefined) {
    params.append('floor', floor.toString());
  }
  const response = await api.get<SearchResponse>(`/search/quick?${params}`);
  return response.data;
}

export async function getMapConfig(): Promise<MapConfig> {
  const response = await api.get<MapConfig>('/map/config');
  return response.data;
}

export async function getBuildingInfo(): Promise<BuildingInfo> {
  const response = await api.get<BuildingInfo>('/map/building');
  return response.data;
}

// Floor plan GeoJSON
export async function getFloorPlan(floor: number): Promise<GeoJSON.FeatureCollection> {
  const response = await api.get<GeoJSON.FeatureCollection>(`/map/floor/${floor}`);
  return response.data;
}

// Wayfinding types
export interface WayfindingRequest {
  from_lat: number;
  from_lon: number;
  to_feature_id: string;
  facility_id?: string;
}

export interface WayfindingLeg {
  floor_ordinal: number;
  points: Array<{ latitude: number; longitude: number }>;
  distance_meters: number;
  instruction?: string;
}

export interface WayfindingResponse {
  success: boolean;
  legs: WayfindingLeg[];
  total_distance_meters: number;
  estimated_time_seconds: number;
}

export async function getWayfindingPath(request: WayfindingRequest): Promise<WayfindingResponse> {
  const response = await api.post<WayfindingResponse>('/map/wayfinding', request);
  return response.data;
}

// Feature state management
export interface FeatureState {
  feature_id: string;
  states: Record<string, any>;
}

export async function updateFeatureState(
  featureId: string,
  states: Record<string, any>
): Promise<{ success: boolean }> {
  const response = await api.post<{ success: boolean }>('/map/feature-state', {
    feature_id: featureId,
    states,
  });
  return response.data;
}

export async function getFeatureState(featureId: string): Promise<FeatureState> {
  const response = await api.get<FeatureState>(`/map/feature-state/${featureId}`);
  return response.data;
}

// Floorplan GeoJSON API (IMDF-based)
export interface FloorplanLevel {
  id: string;
  ordinal: number;
  name: string;
  short_name: string;
}

export interface FloorplanLevelsResponse {
  levels: FloorplanLevel[];
}

export interface GeoJSONFeature {
  type: 'Feature';
  id: string;
  feature_type: string;
  geometry: {
    type: 'Polygon' | 'Point' | 'LineString';
    coordinates: any;
  };
  properties: {
    category?: string;
    name?: { en: string } | string;
    level_id?: string;
    display_point?: { type: string; coordinates: [number, number] };
    [key: string]: any;
  };
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
}

export async function getFloorplanLevels(): Promise<FloorplanLevelsResponse> {
  const response = await api.get<FloorplanLevelsResponse>('/floorplan/levels');
  return response.data;
}

export async function getFloorplanUnits(floorNumber: number): Promise<GeoJSONFeatureCollection> {
  const response = await api.get<GeoJSONFeatureCollection>(`/floorplan/units/floor/${floorNumber}`);
  return response.data;
}

export async function getFloorplanOpenings(floorNumber: number): Promise<GeoJSONFeatureCollection> {
  const response = await api.get<GeoJSONFeatureCollection>(`/floorplan/openings/floor/${floorNumber}`);
  return response.data;
}

export async function getFloorplanAll(floorNumber: number): Promise<GeoJSONFeatureCollection> {
  const response = await api.get<GeoJSONFeatureCollection>(`/floorplan/all/floor/${floorNumber}`);
  return response.data;
}

export async function getFloorplanAmenities(floorNumber: number): Promise<GeoJSONFeatureCollection> {
  const response = await api.get<GeoJSONFeatureCollection>(`/floorplan/amenities/floor/${floorNumber}`);
  return response.data;
}

// Navigation types and functions
export interface NavigationStep {
  from_unit: string;
  to_unit: string;
  distance_meters: number;
  instruction: string;
  level_id: string | null;
  from_level_id?: string | null;
  floor_change?: boolean;
  from_floor?: number;
  to_floor?: number;
}

export interface NavigationResponse {
  success: boolean;
  path: string[];
  geometry: {
    type: 'LineString';
    coordinates: [number, number][];
  };
  total_distance_meters: number;
  estimated_time_seconds: number;
  destination_name?: string;
  destination_level?: string;
  start_name?: string;
  start_level?: string;
  is_multi_floor?: boolean;
  steps: NavigationStep[];
  error?: string;
  from_unit_id?: string;
  from_unit_name?: string;
}

export interface NavigationRequest {
  from_unit_id?: string;
  from_lon?: number;
  from_lat?: number;
  to_unit_id: string;
  level_id?: string;
}

export async function getNavigationPath(request: NavigationRequest): Promise<NavigationResponse> {
  const response = await api.post<NavigationResponse>('/floorplan/navigate', request);
  return response.data;
}

export async function getNavigationSimple(fromUnitId: string, toUnitId: string): Promise<NavigationResponse> {
  const response = await api.get<NavigationResponse>(`/floorplan/navigate/from/${fromUnitId}/to/${toUnitId}`);
  return response.data;
}

// Smart navigation with auto-selected starting point (Main Entrance by default)
export async function getSmartNavigation(toUnitId: string, fromUnitId?: string): Promise<NavigationResponse> {
  const body: { to_unit_id: string; from_unit_id?: string } = {
    to_unit_id: toUnitId,
  };
  
  // Only include from_unit_id if it's actually provided
  if (fromUnitId) {
    body.from_unit_id = fromUnitId;
  }
  
  const response = await api.post<NavigationResponse>('/floorplan/navigate/smart', body);
  return response.data;
}

export interface UnitInfo {
  id: string;
  name: string;
  category: string;
  level_id: string;
  centroid: [number, number];
}

export interface UnitsListResponse {
  units: UnitInfo[];
  count: number;
}

export async function listAllUnits(): Promise<UnitsListResponse> {
  const response = await api.get<UnitsListResponse>('/floorplan/units/list');
  return response.data;
}

export default api;
