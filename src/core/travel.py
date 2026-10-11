"""
Module: travel
Description: Street-network distances and free-flow durations for real instances, and the
             detour factor that scales the straight-line distances of synthetic ones.
             Both are computed once and read from data/travel, so building an instance
             stays offline and a seed still draws the same MILP. Rebuild the cache with
             python -m src.core.travel (needs osmnx, which the solver does not).
"""

import json
import math
from pathlib import Path
from typing import Any, Optional

from src.utils.real_catalog import KM_PER_DEGREE_LAT, KM_PER_DEGREE_LON

TRAVEL_DIR = Path(__file__).resolve().parents[2] / "data" / "travel"
DETOUR_PATH = TRAVEL_DIR / "detour_factor.json"
ROAD_MATRICES_PATH = TRAVEL_DIR / "road_matrices.json"

# Lat/lon is stored and compared at this precision, about 0.1 m, so a seed's
# centroid matches the cache without floating-point noise.
COORD_DECIMALS = 6

# The one real sample whose street matrix is cached. Same city, neighborhood,
# size and seed as the neighborhood checks in tests/test_real_instances.py.
CACHED_SAMPLE = {"city": "São Paulo", "neighborhood": "Moema", "num_properties": 5, "random_seed": 17}

# A sample drawn from every listing in the city, not from one neighborhood.
# Five properties and seed 8 are what `python main.py --model m1 --dataset real
# --city "São Paulo"` builds: m1's default seed, and the generator's default size.
WHOLE_CITY_SAMPLE = {"city": "São Paulo", "neighborhood": None, "num_properties": 5, "random_seed": 8}

# Draws the listing pairs the detour factor is measured on. Not an instance seed.
DETOUR_SAMPLE_SEED = 20261010
DETOUR_PAIRS = 24

# Weekday mean extra travel time versus free flow, TomTom Traffic Index 2025,
# São Paulo city center (the "center" series, Monday–Friday). Each value is
# 1 + congestion/100, with the congestion rounded to one decimal, for the hours
# inside that period of RUSH_HOURS. Hour H is H:00–(H+1):00.
# 08:00–10:00 (hours 8–9): 85.9%; 10:00–17:00 (hours 10–16): 79.6%;
# from 17:00 (hours 17–18): 100.5%.
# https://www.tomtom.com/traffic-index/city/sao-paulo/
SAO_PAULO_CONGESTION = {0: 1.859, 120: 1.796, 540: 2.005}

# NORMAL_SPEED is the midday speed of RUSH_HOURS, so a single period uses that factor.
NORMAL_PERIOD_START = 120

_detour_cache: Optional[dict[str, Any]] = None
_matrices_cache: Optional[dict[str, Any]] = None


def detour_factor() -> float:
    """
    Straight-line distances of a synthetic instance are multiplied by this.

    It is the median road distance over straight-line distance on a fixed sample
    of listing pairs, stored in data/travel/detour_factor.json. It does not depend
    on the instance seed.

    Returns:
        float: The factor, greater than 1 when the sampled trips detour.

    Raises:
        FileNotFoundError: If the cache has not been built.
    """
    if not DETOUR_PATH.is_file():
        raise FileNotFoundError(f"Missing {DETOUR_PATH}. Build it with: python -m src.core.travel")
    return float(_detour()["factor"])


def congestion_factors(city: str, speed_profile: list[tuple[int, float]]) -> list[float]:
    """
    Multiplier of the free-flow duration for each period of the speed profile.

    A single period is the midday factor, because that profile is the normal speed
    rather than the morning rush. Several periods must start at the same minutes
    as the São Paulo profile.

    Args:
        city (str): City the durations were routed in.
        speed_profile (list[tuple[int, float]]): Periods as (start minute, speed).

    Returns:
        list[float]: One congestion factor per period, aligned with speed_profile.

    Raises:
        ValueError: If the city has no profile, or a period start is not one of its.
    """
    if city != "São Paulo":
        raise ValueError(f"No congestion profile for {city}.")
    if len(speed_profile) == 1:
        return [SAO_PAULO_CONGESTION[NORMAL_PERIOD_START]]
    missing = [start for start, _ in speed_profile if start not in SAO_PAULO_CONGESTION]
    if missing:
        raise ValueError(f"No São Paulo congestion factor for period starts {missing}.")
    return [SAO_PAULO_CONGESTION[start] for start, _ in speed_profile]


def travel_minutes(duration_minutes: float, factor: float) -> int:
    """
    Whole minutes of a trip, rounded up, after scaling a free-flow duration.

    Args:
        duration_minutes (float): Free-flow duration, in minutes. Zero stays zero.
        factor (float): Congestion multiplier of the period the trip leaves in.

    Returns:
        int: The travel time in minutes.
    """
    if duration_minutes <= 0:
        return 0
    return math.ceil(duration_minutes * factor)


def minutes_from_seconds(seconds: float) -> float:
    """Free-flow seconds as minutes, at the precision the instance stores."""
    return round(seconds / 60.0, 4)


def straight_meters(origin: list[float], destination: list[float]) -> float:
    """
    Equirectangular distance between two (lat, lon) points, in meters, rounded to 0.1 m.
    Longitude is scaled at the midpoint latitude, with the catalog's kilometers per degree.
    """
    lat1, lon1 = origin
    lat2, lon2 = destination
    km_per_degree_lon = KM_PER_DEGREE_LON * math.cos(math.radians((lat1 + lat2) / 2.0))
    kilometers = math.hypot((lat1 - lat2) * KM_PER_DEGREE_LAT, (lon1 - lon2) * km_per_degree_lon)
    return round(kilometers * 1000.0, 1)


def rounded_points(latitudes: list[float], longitudes: list[float]) -> list[list[float]]:
    """
    Agency and houses as (lat, lon) rounded for the cache key.

    The agency is the centroid of the houses, the same point the map projection
    centers on. Rounding is part of the key, not of the projected coordinates.

    Args:
        latitudes (list[float]): Latitude of each house, in node order from 1 on.
        longitudes (list[float]): Longitude of each house, in the same order.

    Returns:
        list[list[float]]: The agency first, then each house.
    """
    origin = [round(sum(latitudes) / len(latitudes), COORD_DECIMALS),
              round(sum(longitudes) / len(longitudes), COORD_DECIMALS)]
    houses = [[round(float(lat), COORD_DECIMALS), round(float(lon), COORD_DECIMALS)]
              for lat, lon in zip(latitudes, longitudes)]
    return [origin, *houses]


def lookup_road_matrix(points: list[list[float]]) -> Optional[dict[str, Any]]:
    """
    Street-network matrix for these points, if this exact sequence was cached.

    Args:
        points (list[list[float]]): (lat, lon) of each node, agency first.

    Returns:
        Optional[dict[str, Any]]: The cache entry (city, distance_m, duration_s), or
            None when this sequence was not computed.
    """
    if not ROAD_MATRICES_PATH.is_file():
        return None
    key = _point_key(points)
    for entry in _matrices()["matrices"]:
        if _point_key(entry["points"]) == key:
            return entry
    return None


def _point_key(points: list[list[float]]) -> tuple[tuple[float, float], ...]:
    return tuple((round(float(lat), COORD_DECIMALS), round(float(lon), COORD_DECIMALS)) for lat, lon in points)


def _detour() -> dict[str, Any]:
    global _detour_cache
    if _detour_cache is None:
        _detour_cache = json.loads(DETOUR_PATH.read_text(encoding="utf-8"))
    return _detour_cache


def _matrices() -> dict[str, Any]:
    global _matrices_cache
    if _matrices_cache is None:
        _matrices_cache = json.loads(ROAD_MATRICES_PATH.read_text(encoding="utf-8"))
    return _matrices_cache


def build_road_cache() -> None:
    """
    Downloads the Moema drive network and writes the detour factor and the one
    cached street matrix. Needs osmnx. Re-running replaces data/travel.
    """
    try:
        import networkx as nx
        import osmnx as ox
    except ImportError as error:
        raise ImportError("Building the road cache needs osmnx. The solver only reads the cached files.") from error

    import numpy as np

    from src.core.listings import sample_listings, select_listings
    from src.utils.real_catalog import REAL_CATALOG, clean_real_catalog

    catalog = clean_real_catalog(str(REAL_CATALOG))
    moema = select_listings(catalog, CACHED_SAMPLE["city"], CACHED_SAMPLE["neighborhood"])
    chosen = sample_listings(moema, CACHED_SAMPLE["num_properties"], CACHED_SAMPLE["random_seed"])
    instance_points = rounded_points(chosen["lat"].tolist(), chosen["lon"].tolist())

    unique = sorted({(round(float(lat), COORD_DECIMALS), round(float(lon), COORD_DECIMALS))
                     for lat, lon in zip(moema["lat"], moema["lon"])})
    latitudes = [lat for lat, _ in unique]
    longitudes = [lon for _, lon in unique]
    pad = 0.02
    bbox = (min(longitudes) - pad, min(latitudes) - pad, max(longitudes) + pad, max(latitudes) + pad)

    ox.settings.use_cache = True
    ox.settings.cache_folder = "/tmp/osmnx-moema"
    ox.settings.timeout = 180
    print(f"Downloading the drive network for bbox {tuple(round(value, 4) for value in bbox)}.")
    graph = ox.graph_from_bbox(bbox, network_type="drive", truncate_by_edge=True)
    print(f"Routing on {graph.number_of_nodes()} nodes.")
    graph = ox.add_edge_speeds(graph)
    graph = ox.add_edge_travel_times(graph)

    matrix = _route_matrix(graph, nx, instance_points)
    pairs = _detour_pairs(graph, nx, unique)
    ratios = [pair["road_m"] / pair["straight_m"] for pair in pairs]
    if len(ratios) < 10:
        raise RuntimeError(f"Only {len(ratios)} routed pairs; the detour factor needs at least 10.")
    factor = round(float(np.median(ratios)), 4)

    TRAVEL_DIR.mkdir(parents=True, exist_ok=True)
    DETOUR_PATH.write_text(json.dumps({
        "factor": factor,
        "method": "median of directed road meters over straight-line meters",
        "city": CACHED_SAMPLE["city"],
        "neighborhood": CACHED_SAMPLE["neighborhood"],
        "seed": DETOUR_SAMPLE_SEED,
        "pairs_drawn": DETOUR_PAIRS,
        "source": "OSMnx shortest paths on the OpenStreetMap drive network",
        "pairs": pairs,
    }, indent=2) + "\n", encoding="utf-8")
    _upsert_matrix({
        "city": CACHED_SAMPLE["city"],
        "neighborhood": CACHED_SAMPLE["neighborhood"],
        "sample": {"num_properties": CACHED_SAMPLE["num_properties"],
                   "random_seed": CACHED_SAMPLE["random_seed"]},
        "points": instance_points,
        "distance_m": matrix["distance_m"],
        "duration_s": matrix["duration_s"],
    }, ox.__version__)
    global _detour_cache
    _detour_cache = None
    print(f"Detour factor {factor} from {len(pairs)} directed pairs.")
    print(f"Cached {len(instance_points)} nodes for {CACHED_SAMPLE['neighborhood']}.")


def cache_whole_city() -> None:
    """
    Adds the street matrix of WHOLE_CITY_SAMPLE to the cache, leaving the other
    matrices in place. Needs osmnx. The drive network is the bounding box of
    every listing in the city, so a trip can use roads that the five houses
    do not sit on.
    """
    try:
        import networkx as nx
        import osmnx as ox
    except ImportError as error:
        raise ImportError("Building the road cache needs osmnx. The solver only reads the cached files.") from error

    from src.core.listings import sample_listings, select_listings
    from src.utils.real_catalog import REAL_CATALOG, clean_real_catalog

    sample = WHOLE_CITY_SAMPLE
    catalog = select_listings(clean_real_catalog(str(REAL_CATALOG)), sample["city"], sample["neighborhood"])
    chosen = sample_listings(catalog, sample["num_properties"], sample["random_seed"])
    points = rounded_points(chosen["lat"].tolist(), chosen["lon"].tolist())
    if lookup_road_matrix(points) is not None:
        print(f"Street matrix already cached for {sample['city']} "
              f"({sample['num_properties']} properties, seed {sample['random_seed']}).")
        return

    pad = 0.03
    bbox = (float(catalog["lon"].min()) - pad, float(catalog["lat"].min()) - pad,
            float(catalog["lon"].max()) + pad, float(catalog["lat"].max()) + pad)
    ox.settings.use_cache = True
    ox.settings.cache_folder = "/tmp/osmnx-sao-paulo"
    ox.settings.requests_timeout = 300
    ox.settings.doh_url_template = None
    # OSMnx pins one address of overpass-api.de. The first IPv4 often does not
    # connect, so use the first address that accepts a connection.
    import socket
    _resolve = socket.gethostbyname
    _overpass_ip = _reachable_address("overpass-api.de")

    def _overpass_address(name: str) -> str:
        if name == "overpass-api.de":
            return _overpass_ip
        return _resolve(name)

    socket.gethostbyname = _overpass_address
    # One query for the whole city is more than Overpass reliably answers.
    ox.settings.max_query_area_size = 250_000_000
    ox.settings.log_console = True
    ox.settings.useful_tags_node = []
    ox.settings.useful_tags_way = ["highway", "oneway", "maxspeed"]
    print(f"Downloading the drive network for {sample['city']}, bbox "
          f"{tuple(round(value, 4) for value in bbox)}.")
    graph = ox.graph_from_bbox(bbox, network_type="drive", truncate_by_edge=True)
    print(f"Routing on {graph.number_of_nodes()} nodes.")
    graph = ox.add_edge_speeds(graph)
    graph = ox.add_edge_travel_times(graph)
    matrix = _route_matrix(graph, nx, points)
    _upsert_matrix({
        "city": sample["city"],
        "neighborhood": sample["neighborhood"],
        "sample": {"num_properties": sample["num_properties"], "random_seed": sample["random_seed"]},
        "points": points,
        "distance_m": matrix["distance_m"],
        "duration_s": matrix["duration_s"],
    }, ox.__version__)
    print(f"Cached {len(points)} nodes for the whole of {sample['city']}.")


def _upsert_matrix(entry: dict[str, Any], osmnx_version: str) -> None:
    """Inserts or replaces the cache entry with the same point sequence."""
    if ROAD_MATRICES_PATH.is_file():
        payload = json.loads(ROAD_MATRICES_PATH.read_text(encoding="utf-8"))
    else:
        payload = {
            "source": ("OSMnx shortest paths on the OpenStreetMap drive network. "
                       "distance_m is meters. duration_s is free-flow seconds from edge speeds "
                       "(the posted maxspeed, or OSMnx's speed for the highway type), not live traffic."),
            "osmnx": osmnx_version,
            "downloaded": "2026-10-10",
            "matrices": [],
        }
    payload["osmnx"] = osmnx_version
    key = _point_key(entry["points"])
    matrices = payload["matrices"]
    for index, old in enumerate(matrices):
        if _point_key(old["points"]) == key:
            matrices[index] = entry
            break
    else:
        matrices.append(entry)
    TRAVEL_DIR.mkdir(parents=True, exist_ok=True)
    ROAD_MATRICES_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    global _matrices_cache
    _matrices_cache = None


def _reachable_address(host: str) -> str:
    """First address of host that accepts a TCP connection, or the hostname."""
    import socket

    tried = []
    for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        address = info[4][0]
        if address in tried:
            continue
        tried.append(address)
        try:
            sock = socket.create_connection((address, 443), timeout=5)
        except OSError:
            continue
        sock.close()
        return address
    return host


def _route_matrix(graph: Any, nx: Any, points: list[list[float]]) -> dict[str, list[list[float]]]:
    """Distance in meters and free-flow seconds between every point, both directions."""
    nodes = _snapped_nodes(graph, points)
    size = len(points)
    distance_m = [[0.0] * size for _ in range(size)]
    duration_s = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            if i == j:
                continue
            distance_m[i][j], duration_s[i][j] = _path(graph, nx, nodes[i], nodes[j])
    return {"distance_m": distance_m, "duration_s": duration_s}


def _detour_pairs(graph: Any, nx: Any, unique: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """
    Directed road and straight-line lengths for a fixed sample of listing pairs.
    A pair that does not route, or whose ends fall on the same point, is dropped.
    """
    import itertools

    import numpy as np

    combinations = list(itertools.combinations(range(len(unique)), 2))
    rng = np.random.default_rng(DETOUR_SAMPLE_SEED)
    chosen = rng.choice(len(combinations), size=DETOUR_PAIRS, replace=False)
    pairs = []
    for index in chosen:
        left, right = combinations[int(index)]
        ends = [list(unique[left]), list(unique[right])]
        try:
            nodes = _snapped_nodes(graph, ends)
        except RuntimeError:
            continue
        for origin, destination, source, target in (
                (ends[0], ends[1], nodes[0], nodes[1]), (ends[1], ends[0], nodes[1], nodes[0])):
            straight = straight_meters(origin, destination)
            if straight < 30:
                continue
            try:
                road, _ = _path(graph, nx, source, target)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            if road <= 0:
                continue
            pairs.append({"from": origin, "to": destination, "road_m": road, "straight_m": straight})
    return pairs


def _snapped_nodes(graph: Any, points: list[list[float]]) -> list[Any]:
    """Nearest drive-network node of each point. Refuses a snap farther than 400 m."""
    import numpy as np

    ids = np.empty(graph.number_of_nodes(), dtype=object)
    latitudes = np.empty(graph.number_of_nodes())
    longitudes = np.empty(graph.number_of_nodes())
    for index, (node, data) in enumerate(graph.nodes(data=True)):
        ids[index] = node
        latitudes[index] = data["y"]
        longitudes[index] = data["x"]
    snapped = []
    for lat, lon in points:
        km_per_degree_lon = KM_PER_DEGREE_LON * np.cos(np.radians((latitudes + lat) / 2.0))
        meters = np.hypot((latitudes - lat) * KM_PER_DEGREE_LAT, (longitudes - lon) * km_per_degree_lon) * 1000.0
        nearest = int(np.argmin(meters))
        if meters[nearest] > 400:
            raise RuntimeError(f"({lat}, {lon}) snaps more than 400 m from the drive network.")
        snapped.append(ids[nearest])
    return snapped


def _path(graph: Any, nx: Any, source: Any, target: Any) -> tuple[float, float]:
    """Shortest-path meters and free-flow seconds. The same node is a zero trip."""
    if source == target:
        return 0.0, 0.0
    meters = round(float(nx.shortest_path_length(graph, source, target, weight="length")), 1)
    seconds = round(float(nx.shortest_path_length(graph, source, target, weight="travel_time")), 1)
    return meters, seconds


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "city":
        cache_whole_city()
    else:
        build_road_cache()
