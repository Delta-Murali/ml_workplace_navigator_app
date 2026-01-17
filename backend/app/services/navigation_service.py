"""Indoor navigation service using local pathfinding.

Provides wayfinding between rooms using a graph-based approach built from IMDF data.
Uses openings (doors) to determine connectivity between units (rooms).
"""

import heapq
import json
import math
from pathlib import Path
from typing import Any

# Path to IMDF GeoJSON files
_base_dir = Path(__file__).parent.parent.parent / "floorplan_geojson"
if (_base_dir / "imdf_package").exists():
    GEOJSON_DIR = _base_dir / "imdf_package"
else:
    GEOJSON_DIR = _base_dir / "imdf_output"


def load_geojson(filename: str) -> dict[str, Any]:
    """Load a GeoJSON file from the floorplan directory."""
    filepath = GEOJSON_DIR / filename
    if not filepath.exists():
        return {"type": "FeatureCollection", "features": []}
    with open(filepath) as f:
        return json.load(f)


def get_centroid(geometry: dict) -> tuple[float, float]:
    """Calculate the centroid of a polygon geometry."""
    geom_type = geometry.get("type")
    
    if geom_type == "Point":
        coords = geometry["coordinates"]
        return (coords[0], coords[1])
    
    elif geom_type == "Polygon":
        # Get first ring (exterior)
        ring = geometry["coordinates"][0]
        n = len(ring)
        if n == 0:
            return (0, 0)
        
        # Calculate centroid of polygon
        sum_x = sum(pt[0] for pt in ring)
        sum_y = sum(pt[1] for pt in ring)
        return (sum_x / n, sum_y / n)
    
    elif geom_type == "LineString":
        coords = geometry["coordinates"]
        if len(coords) == 0:
            return (0, 0)
        # Midpoint of line
        mid_idx = len(coords) // 2
        return (coords[mid_idx][0], coords[mid_idx][1])
    
    return (0, 0)


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth's radius in meters
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


class NavigationGraph:
    """Graph representation of indoor space for pathfinding."""
    
    def __init__(self):
        self.nodes: dict[str, dict] = {}  # unit_id -> {centroid, properties, level_id}
        self.edges: dict[str, list[str]] = {}  # unit_id -> [connected_unit_ids]
        self.edge_weights: dict[tuple[str, str], float] = {}  # (from, to) -> distance
        self.door_positions: dict[tuple[str, str], tuple[float, float]] = {}  # (unit1, unit2) -> door coordinates
        
    def build_from_imdf(self):
        """Build navigation graph from IMDF GeoJSON files."""
        # Load units (rooms)
        units_data = load_geojson("unit.geojson")
        
        for feature in units_data.get("features", []):
            unit_id = feature.get("id")
            if not unit_id:
                continue
            
            props = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            
            # Use display_point if available, otherwise calculate centroid
            if "display_point" in props and props["display_point"]:
                dp = props["display_point"]
                centroid = (dp["coordinates"][0], dp["coordinates"][1])
            else:
                centroid = get_centroid(geometry)
            
            self.nodes[unit_id] = {
                "centroid": centroid,
                "properties": props,
                "level_id": props.get("level_id"),
                "category": props.get("category"),
                "name": props.get("name", ""),
            }
            self.edges[unit_id] = []
        
        # Load openings (doors) to determine connectivity
        openings_data = load_geojson("opening.geojson")
        
        for feature in openings_data.get("features", []):
            props = feature.get("properties", {})
            unit_ids = props.get("unit_ids", [])
            geometry = feature.get("geometry", {})
            door_pos = get_centroid(geometry)
            
            # Each opening connects 2 units
            if len(unit_ids) >= 2:
                for i in range(len(unit_ids)):
                    for j in range(i + 1, len(unit_ids)):
                        self._add_edge_with_door(unit_ids[i], unit_ids[j], door_pos)
            
            # Also check for category-based connections
            category = props.get("category", "")
            if category in ("passage", "entrance"):
                # Passages and entrances might connect to adjacent walkways
                level_id = props.get("level_id")
                geometry = feature.get("geometry", {})
                opening_point = get_centroid(geometry)
                
                # Find walkways on the same level
                for unit_id, node in self.nodes.items():
                    if node["level_id"] == level_id and node["category"] == "walkway":
                        # Check proximity (within ~10m)
                        dist = haversine_distance(
                            opening_point[0], opening_point[1],
                            node["centroid"][0], node["centroid"][1]
                        )
                        if dist < 15:  # 15 meters
                            for uid in unit_ids:
                                if uid in self.nodes:
                                    self._add_edge(uid, unit_id)
        
        # Connect all walkways on the same level (they form a connected path)
        self._connect_walkways()
        
        # Connect units adjacent to walkways
        self._connect_rooms_to_walkways()
        
        # Connect stairs and elevators across floors for multi-floor navigation
        self._connect_vertical_circulation()
        
        # If no stairs/elevators found, create synthetic vertical connections
        self._connect_floors_synthetically()
    
    def _add_edge(self, unit1: str, unit2: str):
        """Add bidirectional edge between two units."""
        if unit1 not in self.nodes or unit2 not in self.nodes:
            return
        
        if unit2 not in self.edges.get(unit1, []):
            self.edges.setdefault(unit1, []).append(unit2)
        if unit1 not in self.edges.get(unit2, []):
            self.edges.setdefault(unit2, []).append(unit1)
        
        # Calculate weight (distance)
        c1 = self.nodes[unit1]["centroid"]
        c2 = self.nodes[unit2]["centroid"]
        dist = haversine_distance(c1[0], c1[1], c2[0], c2[1])
        
        self.edge_weights[(unit1, unit2)] = dist
        self.edge_weights[(unit2, unit1)] = dist
    
    def _add_edge_with_door(self, unit1: str, unit2: str, door_pos: tuple[float, float]):
        """Add bidirectional edge between two units with a door position."""
        if unit1 not in self.nodes or unit2 not in self.nodes:
            return
        
        if unit2 not in self.edges.get(unit1, []):
            self.edges.setdefault(unit1, []).append(unit2)
        if unit1 not in self.edges.get(unit2, []):
            self.edges.setdefault(unit2, []).append(unit1)
        
        # Store door position for both directions
        self.door_positions[(unit1, unit2)] = door_pos
        self.door_positions[(unit2, unit1)] = door_pos
        
        # Calculate weight using door position (distance from centroid to door)
        c1 = self.nodes[unit1]["centroid"]
        c2 = self.nodes[unit2]["centroid"]
        
        # Distance = from unit1 centroid to door + door to unit2 centroid
        dist1_to_door = haversine_distance(c1[0], c1[1], door_pos[0], door_pos[1])
        dist_door_to2 = haversine_distance(door_pos[0], door_pos[1], c2[0], c2[1])
        total_dist = dist1_to_door + dist_door_to2
        
        self.edge_weights[(unit1, unit2)] = total_dist
        self.edge_weights[(unit2, unit1)] = total_dist
    
    def _connect_walkways(self):
        """Connect walkways on the same level."""
        # Group walkways by level
        level_walkways: dict[str, list[str]] = {}
        for unit_id, node in self.nodes.items():
            if node["category"] == "walkway":
                level_id = node["level_id"]
                level_walkways.setdefault(level_id, []).append(unit_id)
        
        # Connect walkways within each level by proximity
        for level_id, walkways in level_walkways.items():
            for i, w1 in enumerate(walkways):
                for w2 in walkways[i+1:]:
                    c1 = self.nodes[w1]["centroid"]
                    c2 = self.nodes[w2]["centroid"]
                    dist = haversine_distance(c1[0], c1[1], c2[0], c2[1])
                    
                    # Connect if close enough (walkways should be adjacent)
                    if dist < 50:  # 50 meters
                        self._add_edge(w1, w2)
    
    def _connect_rooms_to_walkways(self):
        """Connect rooms to nearby walkways (implicit door connections)."""
        for unit_id, node in self.nodes.items():
            if node["category"] in ("walkway", "stairs", "elevator"):
                continue
            
            # Find nearest walkway on same level
            nearest_walkway = None
            min_dist = float("inf")
            
            for other_id, other_node in self.nodes.items():
                if other_node["category"] != "walkway":
                    continue
                if other_node["level_id"] != node["level_id"]:
                    continue
                
                c1 = node["centroid"]
                c2 = other_node["centroid"]
                dist = haversine_distance(c1[0], c1[1], c2[0], c2[1])
                
                if dist < min_dist:
                    min_dist = dist
                    nearest_walkway = other_id
            
            # Connect if within reasonable distance (increased to 50m)
            if nearest_walkway and min_dist < 50:  # 50 meters
                self._add_edge(unit_id, nearest_walkway)
        
        # Also connect special areas like reception, entrance to nearest walkway
        special_categories = ["reception", "entrance", "lobby"]
        for unit_id, node in self.nodes.items():
            if node["category"] not in special_categories:
                continue
            
            # Ensure connected to something
            if not self.edges.get(unit_id):
                nearest = None
                min_dist = float("inf")
                for other_id, other_node in self.nodes.items():
                    if other_id == unit_id:
                        continue
                    if other_node["level_id"] != node["level_id"]:
                        continue
                    c1 = node["centroid"]
                    c2 = other_node["centroid"]
                    dist = haversine_distance(c1[0], c1[1], c2[0], c2[1])
                    if dist < min_dist:
                        min_dist = dist
                        nearest = other_id
                if nearest:
                    self._add_edge(unit_id, nearest)
    
    def _connect_vertical_circulation(self):
        """Connect stairs and elevators across different floors for multi-floor navigation."""
        # Collect all stairs and elevators
        stairs: list[tuple[str, str]] = []  # (id, level)
        elevators: list[tuple[str, str]] = []
        
        for unit_id, node in self.nodes.items():
            category = node.get("category", "")
            if category == "stairs":
                stairs.append((unit_id, node["level_id"]))
            elif category == "elevator":
                elevators.append((unit_id, node["level_id"]))
        
        # Simple approach: Connect ALL stairs to each other across floors
        print(f"Found {len(stairs)} stairs and {len(elevators)} elevators")
        
        # Connect all stairs together (simpler approach)
        for i in range(len(stairs)):
            for j in range(i + 1, len(stairs)):
                unit1_id, level1 = stairs[i]
                unit2_id, level2 = stairs[j]
                
                # Only connect if on different floors
                if level1 != level2:
                    self.edges.setdefault(unit1_id, []).append(unit2_id)
                    self.edges.setdefault(unit2_id, []).append(unit1_id)
                    self.edge_weights[(unit1_id, unit2_id)] = 20  # 20 meters for stairs
                    self.edge_weights[(unit2_id, unit1_id)] = 20
                    print(f"Connected stairs: {unit1_id} ({level1}) <-> {unit2_id} ({level2})")
        
        # Connect all elevators together
        for i in range(len(elevators)):
            for j in range(i + 1, len(elevators)):
                unit1_id, level1 = elevators[i]
                unit2_id, level2 = elevators[j]
                
                # Only connect if on different floors
                if level1 != level2:
                    self.edges.setdefault(unit1_id, []).append(unit2_id)
                    self.edges.setdefault(unit2_id, []).append(unit1_id)
                    self.edge_weights[(unit1_id, unit2_id)] = 15  # 15 meters for elevator
                    self.edge_weights[(unit2_id, unit1_id)] = 15
                    print(f"Connected elevators: {unit1_id} ({level1}) <-> {unit2_id} ({level2})")
        
        # Connect stairs/elevators to nearby walkways on their floor
        for unit_id, node in self.nodes.items():
            category = node.get("category", "")
            if category not in ("stairs", "elevator"):
                continue
            
            # Find ALL walkways on the same floor and connect
            level_id = node["level_id"]
            centroid = node["centroid"]
            
            for other_id, other_node in self.nodes.items():
                if other_node["category"] != "walkway":
                    continue
                if other_node["level_id"] != level_id:
                    continue
                
                other_centroid = other_node["centroid"]
                dist = haversine_distance(centroid[0], centroid[1], other_centroid[0], other_centroid[1])
                
                # Connect if within reasonable distance (50m to ensure connection)
                if dist < 50:  # 50 meters
                    self._add_edge(unit_id, other_id)
                    print(f"Connected {category} {unit_id} to walkway {other_id} (dist: {dist:.1f}m)")
    
    def _connect_floors_synthetically(self):
        """
        Create synthetic connections between floors ONLY if no stairs/elevators exist.
        This is a fallback for buildings without proper vertical circulation defined.
        """
        # Check if we have any stairs or elevators that connect different floors
        has_vertical_circulation = False
        for unit_id, node in self.nodes.items():
            category = node.get("category", "")
            if category in ("stairs", "elevator"):
                # Check if this unit has connections to other floors
                for neighbor in self.edges.get(unit_id, []):
                    if neighbor in self.nodes:
                        neighbor_level = self.nodes[neighbor].get("level_id")
                        if neighbor_level != node.get("level_id"):
                            has_vertical_circulation = True
                            break
            if has_vertical_circulation:
                break
        
        if has_vertical_circulation:
            print("Stairs/elevators found with cross-floor connections - skipping synthetic connections")
            return
        
        print("No vertical circulation found - creating synthetic floor connections")
        
        # Group walkways by floor
        walkways_by_floor: dict[str, list[tuple[str, tuple[float, float]]]] = {}
        
        for unit_id, node in self.nodes.items():
            category = node.get("category", "")
            if category != "walkway":
                continue
            
            level_id = node.get("level_id")
            centroid = node["centroid"]
            walkways_by_floor.setdefault(level_id, []).append((unit_id, centroid))
        
        # Get sorted list of floors
        floor_ids = sorted(walkways_by_floor.keys())
        
        # Connect walkways between adjacent floors
        for i in range(len(floor_ids) - 1):
            floor1 = floor_ids[i]
            floor2 = floor_ids[i + 1]
            
            walkways1 = walkways_by_floor.get(floor1, [])
            walkways2 = walkways_by_floor.get(floor2, [])
            
            if not walkways1 or not walkways2:
                continue
            
            # Find the closest pair of walkways between the two floors
            min_dist = float("inf")
            best_pair = None
            
            for unit1_id, centroid1 in walkways1:
                for unit2_id, centroid2 in walkways2:
                    # Calculate horizontal distance (ignoring vertical component)
                    dist = haversine_distance(centroid1[0], centroid1[1], centroid2[0], centroid2[1])
                    
                    if dist < min_dist:
                        min_dist = dist
                        best_pair = (unit1_id, unit2_id)
            
            # Connect the closest pair if they're reasonably aligned (within 20m horizontally)
            if best_pair and min_dist < 20:  # 20 meters horizontal distance
                unit1, unit2 = best_pair
                # Add connection with HIGH weight to discourage this path if stairs exist
                self.edges.setdefault(unit1, []).append(unit2)
                self.edges.setdefault(unit2, []).append(unit1)
                self.edge_weights[(unit1, unit2)] = 100  # High weight - prefer stairs/elevator
                self.edge_weights[(unit2, unit1)] = 100
                
                print(f"Synthetic floor connection: {unit1} ({floor1}) <-> {unit2} ({floor2})")
    
    def find_path(self, from_unit: str, to_unit: str) -> list[str] | None:
        """Find shortest path using Dijkstra's algorithm."""
        if from_unit not in self.nodes or to_unit not in self.nodes:
            return None
        
        if from_unit == to_unit:
            return [from_unit]
        
        # Dijkstra's algorithm
        distances = {from_unit: 0}
        previous = {}
        pq = [(0, from_unit)]
        visited = set()
        
        while pq:
            current_dist, current = heapq.heappop(pq)
            
            if current in visited:
                continue
            visited.add(current)
            
            if current == to_unit:
                break
            
            for neighbor in self.edges.get(current, []):
                if neighbor in visited:
                    continue
                
                weight = self.edge_weights.get((current, neighbor), 10)  # Default 10m
                distance = current_dist + weight
                
                if distance < distances.get(neighbor, float("inf")):
                    distances[neighbor] = distance
                    previous[neighbor] = current
                    heapq.heappush(pq, (distance, neighbor))
        
        # Reconstruct path
        if to_unit not in previous and from_unit != to_unit:
            return None
        
        path = []
        current = to_unit
        while current:
            path.append(current)
            current = previous.get(current)
        
        path.reverse()
        return path
    
    def find_path_from_point(
        self,
        from_lon: float,
        from_lat: float,
        to_unit: str,
        level_id: str | None = None,
    ) -> list[str] | None:
        """Find path from a geographic point to a destination unit."""
        # Find nearest node to starting point
        nearest_unit = None
        min_dist = float("inf")
        
        for unit_id, node in self.nodes.items():
            # Prefer same level if specified
            if level_id and node["level_id"] != level_id:
                continue
            
            c = node["centroid"]
            dist = haversine_distance(from_lon, from_lat, c[0], c[1])
            
            if dist < min_dist:
                min_dist = dist
                nearest_unit = unit_id
        
        if not nearest_unit:
            # Try without level filter
            for unit_id, node in self.nodes.items():
                c = node["centroid"]
                dist = haversine_distance(from_lon, from_lat, c[0], c[1])
                if dist < min_dist:
                    min_dist = dist
                    nearest_unit = unit_id
        
        if not nearest_unit:
            return None
        
        return self.find_path(nearest_unit, to_unit)
    
    def get_path_geometry(self, path: list[str]) -> dict:
        """Convert path to GeoJSON LineString for visualization using door positions."""
        if not path:
            return {"type": "LineString", "coordinates": []}
        
        coordinates = []
        
        # Start at first unit's centroid
        if path[0] in self.nodes:
            c = self.nodes[path[0]]["centroid"]
            coordinates.append([c[0], c[1]])
        
        # Route through doors between consecutive units
        for i in range(len(path) - 1):
            from_unit = path[i]
            to_unit = path[i + 1]
            
            # Check if we have a door position for this edge
            door_key = (from_unit, to_unit)
            if door_key in self.door_positions:
                # Add door position as waypoint
                door_pos = self.door_positions[door_key]
                coordinates.append([door_pos[0], door_pos[1]])
            
            # Add destination unit's centroid
            if to_unit in self.nodes:
                c = self.nodes[to_unit]["centroid"]
                coordinates.append([c[0], c[1]])
        
        return {
            "type": "LineString",
            "coordinates": coordinates,
        }
    
    def get_path_details(self, path: list[str]) -> dict:
        """Get detailed path information including distance and instructions."""
        if not path:
            return {
                "success": False,
                "path": [],
                "geometry": {"type": "LineString", "coordinates": []},
                "total_distance_meters": 0,
                "estimated_time_seconds": 0,
                "steps": [],
            }
        
        total_distance = 0
        steps = []
        
        # Track floor changes for multi-floor navigation
        start_level = self.nodes.get(path[0], {}).get("level_id", "")
        end_level = self.nodes.get(path[-1], {}).get("level_id", "")
        is_multi_floor = start_level != end_level
        
        for i in range(len(path) - 1):
            from_unit = path[i]
            to_unit = path[i + 1]
            
            from_node = self.nodes.get(from_unit, {})
            to_node = self.nodes.get(to_unit, {})
            
            distance = self.edge_weights.get((from_unit, to_unit), 10)
            total_distance += distance
            
            # Generate instruction
            from_name = from_node.get("name", from_unit)
            to_name = to_node.get("name", to_unit)
            if isinstance(from_name, dict):
                from_name = from_name.get("en", from_unit)
            if isinstance(to_name, dict):
                to_name = to_name.get("en", to_unit)
            
            from_category = from_node.get("category", "")
            to_category = to_node.get("category", "")
            from_level = from_node.get("level_id")
            to_level = to_node.get("level_id")
            
            # Detect floor changes
            floor_change = from_level != to_level
            
            # Extract floor numbers for instructions
            from_floor_num = from_level.replace("level-", "").replace("level_", "").lstrip("0") or "0" if from_level else "0"
            to_floor_num = to_level.replace("level-", "").replace("level_", "").lstrip("0") or "0" if to_level else "0"
            
            # Generate appropriate instruction
            if floor_change and from_category == "stairs":
                instruction = f"🚶 Take stairs from Floor {from_floor_num} to Floor {to_floor_num}"
            elif floor_change and from_category == "elevator":
                instruction = f"🛗 Take elevator from Floor {from_floor_num} to Floor {to_floor_num}"
            elif floor_change and to_category == "stairs":
                instruction = f"🚶 Take stairs to reach Floor {to_floor_num}"
            elif floor_change and to_category == "elevator":
                instruction = f"🛗 Take elevator to reach Floor {to_floor_num}"
            elif to_category == "stairs" and not floor_change:
                instruction = f"Walk to the stairwell"
            elif to_category == "elevator" and not floor_change:
                instruction = f"Walk to the elevator"
            elif to_category == "walkway":
                instruction = f"Continue through {to_name}" if "hallway" in to_name.lower() or "f1" in to_name.lower() or "f2" in to_name.lower() else "Continue through hallway"
            elif floor_change:
                # Floor changed but not via stairs/elevator
                instruction = f"📍 Go to Floor {to_floor_num} - {to_name}"
            elif to_category == "entrance":
                instruction = f"Start at {to_name}"
            elif to_category == "reception":
                instruction = f"Pass through {to_name}"
            elif i == len(path) - 2:  # Last step
                instruction = f"🎯 Arrive at {to_name}"
            else:
                instruction = f"Go to {to_name}"
            
            steps.append({
                "from_unit": from_unit,
                "to_unit": to_unit,
                "distance_meters": round(distance, 1),
                "instruction": instruction,
                "level_id": to_level,
                "from_level_id": from_level,
                "floor_change": floor_change,
                "from_floor": int(from_floor_num) if from_floor_num.isdigit() else 0,
                "to_floor": int(to_floor_num) if to_floor_num.isdigit() else 0,
            })
        
        # Estimated walking time (average walking speed ~1.4 m/s)
        estimated_time = total_distance / 1.4
        
        # Get destination info
        dest_node = self.nodes.get(path[-1], {})
        dest_name = dest_node.get("name", path[-1])
        dest_level = dest_node.get("level_id", "")
        if isinstance(dest_name, dict):
            dest_name = dest_name.get("en", path[-1])
        
        # Get start info
        start_node = self.nodes.get(path[0], {})
        start_name = start_node.get("name", path[0])
        if isinstance(start_name, dict):
            start_name = start_name.get("en", path[0])
        
        return {
            "success": True,
            "path": path,
            "geometry": self.get_path_geometry(path),
            "total_distance_meters": round(total_distance, 1),
            "estimated_time_seconds": round(estimated_time),
            "destination_name": dest_name,
            "destination_level": dest_level,
            "start_name": start_name,
            "start_level": start_level,
            "is_multi_floor": is_multi_floor,
            "steps": steps,
        }
    
    def find_unit_by_name(self, name: str, level_id: str | None = None) -> str | None:
        """Find a unit ID by name (partial match)."""
        name_lower = name.lower()
        
        for unit_id, node in self.nodes.items():
            if level_id and node["level_id"] != level_id:
                continue
            
            unit_name = node.get("name", "")
            if isinstance(unit_name, dict):
                unit_name = unit_name.get("en", "")
            
            if name_lower in unit_name.lower():
                return unit_id
        
        return None


# Global navigation graph instance
_navigation_graph: NavigationGraph | None = None


def get_navigation_graph() -> NavigationGraph:
    """Get or create the navigation graph singleton."""
    global _navigation_graph
    
    if _navigation_graph is None:
        _navigation_graph = NavigationGraph()
        _navigation_graph.build_from_imdf()
    
    return _navigation_graph


def reload_navigation_graph():
    """Force reload of the navigation graph."""
    global _navigation_graph
    _navigation_graph = None
    return get_navigation_graph()
