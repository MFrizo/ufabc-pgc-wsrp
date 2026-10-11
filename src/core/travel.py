"""
Module: travel
Description: Street-network distances and free-flow durations for real instances, and the
             detour factor that scales the straight-line distances of synthetic ones.
             Both are computed once and read from data/travel, so building an instance
             stays offline and a seed still draws the same MILP. The São Paulo index
             covers every unique listing coordinate, so any sample of that city is
             routed, with or without a neighborhood. Rebuild it with
             python -m src.core.travel city (needs osmnx and scipy, which the solver
             does not). python -m src.core.travel rebuilds only the detour factor.
"""

import json
import math
from pathlib import Path
from typing import Any, Optional

from src.utils.real_catalog import KM_PER_DEGREE_LAT, KM_PER_DEGREE_LON

TRAVEL_DIR = Path(__file__).resolve().parents[2] / "data" / "travel"
DETOUR_PATH = TRAVEL_DIR / "detour_factor.json"
CITY_INDEX_PATH = TRAVEL_DIR / "sao_paulo.npz"
CITY_INDEX_JSON = TRAVEL_DIR / "sao_paulo.json"

# The only city whose listings have a street index. Any sample of that city,
# with or without a neighborhood, is routed from this index.
INDEXED_CITY = "São Paulo"

# Lat/lon is stored and compared at this precision, about 0.1 m, so a seed's
# centroid matches the cache without floating-point noise.
COORD_DECIMALS = 6

# What `python main.py --model m1 --dataset real --city "São Paulo"` builds:
# m1's default seed and the generator's default size, drawn from the whole city.
WHOLE_CITY_SAMPLE = {"city": INDEXED_CITY, "num_properties": 5, "random_seed": 8}

# Draws the listing pairs the detour factor is measured on. Not an instance seed.
# The pairs are listings in one neighborhood, so the ratio is a local street sample.
DETOUR_NEIGHBORHOOD = "Moema"
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

# A snap farther than this is not a drive-network node of the point.
MAX_SNAP_METERS = 400

_detour_cache: Optional[dict[str, Any]] = None
_index_cache: Optional[dict[str, Any]] = None


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
    Street-network matrix for these points, when every house is in the city index.

    House-to-house distances are the precomputed shortest paths between listing
    coordinates. The agency is the sample centroid, which is not a listing, so
    its row and column are shortest paths on the same drive graph from that
    centroid's nearest node.

    Args:
        points (list[list[float]]): (lat, lon) of each node, agency first.

    Returns:
        Optional[dict[str, Any]]: city, distance_m and duration_s, or None when a
            house is not an indexed listing or the agency will not snap.
    """
    index = _city_index()
    if index is None or len(points) < 2:
        return None
    rows = []
    for lat, lon in points[1:]:
        row = index["row_of"].get((round(float(lat), COORD_DECIMALS), round(float(lon), COORD_DECIMALS)))
        if row is None:
            return None
        rows.append(row)

    size = len(points)
    distance_m = [[0.0] * size for _ in range(size)]
    duration_s = [[0.0] * size for _ in range(size)]
    stored_m = index["distance_m"]
    stored_s = index["duration_s"]
    for left, i in enumerate(rows):
        for right, j in enumerate(rows):
            meters = float(stored_m[i, j])
            seconds = float(stored_s[i, j])
            if math.isnan(meters) or math.isnan(seconds):
                distance_m[left + 1][right + 1] = None
                duration_s[left + 1][right + 1] = None
            else:
                distance_m[left + 1][right + 1] = round(meters, 1)
                duration_s[left + 1][right + 1] = round(seconds, 1)

    agency = _snap_stored_node(index, points[0][0], points[0][1])
    if agency is None:
        return None
    targets = index["point_node"][rows]
    outbound_m = _dijkstra(index["fwd_indptr"], index["fwd_indices"], index["fwd_length"], agency, targets)
    outbound_s = _dijkstra(index["fwd_indptr"], index["fwd_indices"], index["fwd_time"], agency, targets)
    inbound_m = _dijkstra(index["rev_indptr"], index["rev_indices"], index["rev_length"], agency, targets)
    inbound_s = _dijkstra(index["rev_indptr"], index["rev_indices"], index["rev_time"], agency, targets)
    for offset, node in enumerate(targets):
        node = int(node)
        going = (float(outbound_m[node]), float(outbound_s[node]))
        returning = (float(inbound_m[node]), float(inbound_s[node]))
        if not math.isfinite(going[0]) or not math.isfinite(going[1]):
            distance_m[0][offset + 1] = None
            duration_s[0][offset + 1] = None
        else:
            distance_m[0][offset + 1] = round(going[0], 1)
            duration_s[0][offset + 1] = round(going[1], 1)
        if not math.isfinite(returning[0]) or not math.isfinite(returning[1]):
            distance_m[offset + 1][0] = None
            duration_s[offset + 1][0] = None
        else:
            distance_m[offset + 1][0] = round(returning[0], 1)
            duration_s[offset + 1][0] = round(returning[1], 1)
    return {"city": INDEXED_CITY, "distance_m": distance_m, "duration_s": duration_s}


def indexed_coordinates() -> Optional[set[tuple[float, float]]]:
    """
    Listing coordinates the street index can route, or None when it has not been built.

    Returns:
        Optional[set[tuple[float, float]]]: (lat, lon) rounded to COORD_DECIMALS.
    """
    index = _city_index()
    if index is None:
        return None
    return set(index["row_of"])


def _detour() -> dict[str, Any]:
    global _detour_cache
    if _detour_cache is None:
        _detour_cache = json.loads(DETOUR_PATH.read_text(encoding="utf-8"))
    return _detour_cache


def _city_index() -> Optional[dict[str, Any]]:
    """The São Paulo listing index and drive graph, loaded once."""
    global _index_cache
    if _index_cache is not None:
        return _index_cache
    if not CITY_INDEX_PATH.is_file():
        return None
    import numpy as np

    blob = np.load(CITY_INDEX_PATH)
    points = blob["points"]
    row_of = {
        (round(float(lat), COORD_DECIMALS), round(float(lon), COORD_DECIMALS)): index
        for index, (lat, lon) in enumerate(points)
    }
    _index_cache = {
        "points": points,
        "row_of": row_of,
        "distance_m": blob["distance_m"],
        "duration_s": blob["duration_s"],
        "point_node": blob["point_node"],
        "node_lat": blob["node_lat"],
        "node_lon": blob["node_lon"],
        "fwd_indptr": blob["fwd_indptr"],
        "fwd_indices": blob["fwd_indices"],
        "fwd_length": blob["fwd_length"],
        "fwd_time": blob["fwd_time"],
        "rev_indptr": blob["rev_indptr"],
        "rev_indices": blob["rev_indices"],
        "rev_length": blob["rev_length"],
        "rev_time": blob["rev_time"],
    }
    return _index_cache


def build_road_cache() -> None:
    """
    Downloads the Moema drive network and writes the detour factor. Needs osmnx.
    Re-running replaces data/travel/detour_factor.json. The city index is separate:
    python -m src.core.travel city.
    """
    try:
        import networkx as nx
        import osmnx as ox
    except ImportError as error:
        raise ImportError("Building the road cache needs osmnx. The solver only reads the cached files.") from error

    import numpy as np

    from src.core.listings import select_listings
    from src.utils.real_catalog import REAL_CATALOG, clean_real_catalog

    catalog = clean_real_catalog(str(REAL_CATALOG))
    moema = select_listings(catalog, INDEXED_CITY, DETOUR_NEIGHBORHOOD)

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

    pairs = _detour_pairs(graph, nx, unique)
    ratios = [pair["road_m"] / pair["straight_m"] for pair in pairs]
    if len(ratios) < 10:
        raise RuntimeError(f"Only {len(ratios)} routed pairs; the detour factor needs at least 10.")
    factor = round(float(np.median(ratios)), 4)

    TRAVEL_DIR.mkdir(parents=True, exist_ok=True)
    DETOUR_PATH.write_text(json.dumps({
        "factor": factor,
        "method": "median of directed road meters over straight-line meters",
        "city": INDEXED_CITY,
        "neighborhood": DETOUR_NEIGHBORHOOD,
        "seed": DETOUR_SAMPLE_SEED,
        "pairs_drawn": DETOUR_PAIRS,
        "source": "OSMnx shortest paths on the OpenStreetMap drive network",
        "pairs": pairs,
    }, indent=2) + "\n", encoding="utf-8")
    global _detour_cache
    _detour_cache = None
    print(f"Detour factor {factor} from {len(pairs)} directed pairs.")


def build_city_index() -> None:
    """
    Writes the street index of every unique listing coordinate in São Paulo.

    Needs osmnx and scipy. The drive network is the bounding box of every listing
    in the city, padded by 0.03°. House-to-house shortest paths are stored for
    every pair. The graph itself is stored too, so a later sample can route its
    own agency centroid, which is not a listing. Re-running replaces the index.
    """
    try:
        import osmnx as ox
        import scipy.sparse as sp
        from scipy.sparse.csgraph import dijkstra
    except ImportError as error:
        raise ImportError(
            "Building the city index needs osmnx and scipy. The solver only reads the cached files."
        ) from error

    import numpy as np

    from src.core.listings import select_listings
    from src.utils.real_catalog import REAL_CATALOG, clean_real_catalog

    catalog = select_listings(clean_real_catalog(str(REAL_CATALOG)), INDEXED_CITY, None)
    points = sorted({(round(float(lat), COORD_DECIMALS), round(float(lon), COORD_DECIMALS))
                     for lat, lon in zip(catalog["lat"], catalog["lon"])})
    print(f"Indexing {len(points)} unique coordinates from {len(catalog)} listings in {INDEXED_CITY}.")

    pad = 0.03
    bbox = (float(catalog["lon"].min()) - pad, float(catalog["lat"].min()) - pad,
            float(catalog["lon"].max()) + pad, float(catalog["lat"].max()) + pad)
    graph = _download_city_graph(ox, bbox)
    print(f"Routing on {graph.number_of_nodes()} nodes.")
    graph = ox.add_edge_speeds(graph)
    graph = ox.add_edge_travel_times(graph)

    packed = _pack_graph(graph)
    snapped = _snapped_nodes(graph, [list(point) for point in points])
    node_of = {node: index for index, node in enumerate(packed["ids"])}
    point_node = np.array([node_of[node] for node in snapped], dtype=np.int32)
    sources = np.unique(point_node)
    print(f"Shortest paths among {len(sources)} drive nodes.")
    among_m = _pairwise(sp, dijkstra, packed["fwd_indptr"], packed["fwd_indices"], packed["fwd_length"], sources)
    among_s = _pairwise(sp, dijkstra, packed["fwd_indptr"], packed["fwd_indices"], packed["fwd_time"], sources)
    place = np.empty(packed["fwd_indptr"].size - 1, dtype=np.int32)
    place[sources] = np.arange(len(sources), dtype=np.int32)
    left = place[point_node]
    distance_m = among_m[np.ix_(left, left)]
    duration_s = among_s[np.ix_(left, left)]
    missing = ~np.isfinite(distance_m) | ~np.isfinite(duration_s)
    unreachable = int(missing.sum())
    distance_m[missing] = np.nan
    duration_s[missing] = np.nan
    np.fill_diagonal(distance_m, 0.0)
    np.fill_diagonal(duration_s, 0.0)
    if unreachable:
        print(f"{unreachable} directed pairs have no drive path and are not arcs.")

    TRAVEL_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        CITY_INDEX_PATH,
        points=np.asarray(points, dtype=np.float64),
        distance_m=np.round(distance_m, 1).astype(np.float32),
        duration_s=np.round(duration_s, 1).astype(np.float32),
        point_node=point_node,
        node_lat=packed["node_lat"],
        node_lon=packed["node_lon"],
        fwd_indptr=packed["fwd_indptr"],
        fwd_indices=packed["fwd_indices"],
        fwd_length=packed["fwd_length"],
        fwd_time=packed["fwd_time"],
        rev_indptr=packed["rev_indptr"],
        rev_indices=packed["rev_indices"],
        rev_length=packed["rev_length"],
        rev_time=packed["rev_time"],
    )
    CITY_INDEX_JSON.write_text(json.dumps({
        "city": INDEXED_CITY,
        "neighborhood": None,
        "listings": int(len(catalog)),
        "unique_points": len(points),
        "unreachable_pairs": unreachable,
        "source": ("OSMnx shortest paths on the OpenStreetMap drive network of every "
                   "São Paulo listing. distance_m is meters. duration_s is free-flow seconds "
                   "from edge speeds (the posted maxspeed, or OSMnx's speed for the highway type), "
                   "not live traffic. Any sample of these coordinates uses this index."),
        "matrix": CITY_INDEX_PATH.name,
        "osmnx": ox.__version__,
        "downloaded": "2026-10-10",
    }, indent=2) + "\n", encoding="utf-8")
    global _index_cache
    _index_cache = None
    print(f"Indexed {len(points)} coordinates for the whole of {INDEXED_CITY}.")


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


def _download_city_graph(ox: Any, bbox: tuple[float, float, float, float]) -> Any:
    """Drive network of the city bounding box. Uses the Overpass cache when it is warm."""
    import socket

    ox.settings.use_cache = True
    ox.settings.cache_folder = "/tmp/osmnx-sao-paulo"
    ox.settings.requests_timeout = 300
    ox.settings.doh_url_template = None
    # OSMnx pins one address of overpass-api.de. The first IPv4 often does not
    # connect, so use the first address that accepts a connection.
    resolve = socket.gethostbyname
    overpass_ip = _reachable_address("overpass-api.de")

    def overpass_address(name: str) -> str:
        if name == "overpass-api.de":
            return overpass_ip
        return resolve(name)

    socket.gethostbyname = overpass_address
    # One query for the whole city is more than Overpass reliably answers.
    ox.settings.max_query_area_size = 250_000_000
    ox.settings.log_console = True
    ox.settings.useful_tags_node = []
    ox.settings.useful_tags_way = ["highway", "oneway", "maxspeed"]
    print(f"Downloading the drive network for {INDEXED_CITY}, bbox "
          f"{tuple(round(value, 4) for value in bbox)}.")
    return ox.graph_from_bbox(bbox, network_type="drive", truncate_by_edge=True)


def _pack_graph(graph: Any) -> dict[str, Any]:
    """Directed edges as two CSRs, one per direction, with length and free-flow time."""
    import numpy as np

    ids = []
    node_of = {}
    node_lat = []
    node_lon = []
    for node, data in graph.nodes(data=True):
        node_of[node] = len(ids)
        ids.append(node)
        node_lat.append(float(data["y"]))
        node_lon.append(float(data["x"]))
    sources = []
    targets = []
    lengths = []
    times = []
    for origin, destination, data in graph.edges(data=True):
        if origin == destination:
            continue
        length = float(data["length"])
        travel = float(data["travel_time"])
        if length < 0 or travel < 0 or not math.isfinite(length) or not math.isfinite(travel):
            continue
        sources.append(node_of[origin])
        targets.append(node_of[destination])
        lengths.append(length)
        times.append(travel)
    forward = _csr(len(ids), sources, targets, lengths, times)
    backward = _csr(len(ids), targets, sources, lengths, times)
    return {
        "ids": ids,
        "node_lat": np.asarray(node_lat, dtype=np.float64),
        "node_lon": np.asarray(node_lon, dtype=np.float64),
        "fwd_indptr": forward[0], "fwd_indices": forward[1], "fwd_length": forward[2], "fwd_time": forward[3],
        "rev_indptr": backward[0], "rev_indices": backward[1], "rev_length": backward[2], "rev_time": backward[3],
    }


def _csr(node_count: int, sources: list[int], targets: list[int],
         lengths: list[float], times: list[float]) -> tuple[Any, Any, Any, Any]:
    """Edges sorted by origin. The reverse call swaps sources and targets."""
    import numpy as np

    origin = np.asarray(sources, dtype=np.int32)
    destination = np.asarray(targets, dtype=np.int32)
    length = np.asarray(lengths, dtype=np.float32)
    travel = np.asarray(times, dtype=np.float32)
    order = np.argsort(origin, kind="stable")
    origin = origin[order]
    destination = destination[order]
    length = length[order]
    travel = travel[order]
    counts = np.bincount(origin, minlength=node_count)
    indptr = np.zeros(node_count + 1, dtype=np.int32)
    np.cumsum(counts, out=indptr[1:])
    return indptr, destination, length, travel


def _pairwise(sp: Any, dijkstra: Any, indptr: Any, indices: Any, weights: Any, sources: Any) -> Any:
    """Shortest paths between sources, in source order. Missing paths stay infinite."""
    import numpy as np

    graph = sp.csr_matrix((weights, indices, indptr), shape=(len(indptr) - 1, len(indptr) - 1))
    out = np.empty((len(sources), len(sources)), dtype=np.float64)
    batch = 48
    for start in range(0, len(sources), batch):
        chosen = sources[start:start + batch]
        distances = dijkstra(graph, directed=True, indices=chosen)
        out[start:start + len(chosen)] = distances[:, sources]
        print(f"  {min(start + batch, len(sources))}/{len(sources)}", flush=True)
    return out


def _snap_stored_node(index: dict[str, Any], lat: float, lon: float) -> Optional[int]:
    """Nearest stored drive node, or None when it is farther than MAX_SNAP_METERS."""
    import numpy as np

    latitudes = index["node_lat"]
    longitudes = index["node_lon"]
    km_per_degree_lon = KM_PER_DEGREE_LON * np.cos(np.radians((latitudes + lat) / 2.0))
    meters = np.hypot((latitudes - lat) * KM_PER_DEGREE_LAT, (longitudes - lon) * km_per_degree_lon) * 1000.0
    nearest = int(np.argmin(meters))
    if float(meters[nearest]) > MAX_SNAP_METERS:
        return None
    return nearest


def _dijkstra(indptr: Any, indices: Any, weights: Any, source: int, targets: Any) -> Any:
    """
    Distances from source along one CSR. Stops once every target is settled.

    Args:
        indptr, indices, weights: A directed CSR.
        source (int): Origin node in that CSR.
        targets: Node indices that have to be reached.

    Returns:
        The distance of every node. A node with no path stays infinite.
    """
    import heapq

    import numpy as np

    dist = np.full(len(indptr) - 1, np.inf)
    source = int(source)
    dist[source] = 0.0
    pending = {int(target) for target in targets}
    pending.discard(source)
    heap = [(0.0, source)]
    while heap and pending:
        current, node = heapq.heappop(heap)
        if current > dist[node]:
            continue
        pending.discard(node)
        start = int(indptr[node])
        end = int(indptr[node + 1])
        for cursor in range(start, end):
            nxt = int(indices[cursor])
            nxt_dist = current + float(weights[cursor])
            if nxt_dist < dist[nxt]:
                dist[nxt] = nxt_dist
                heapq.heappush(heap, (nxt_dist, nxt))
    return dist


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
        if meters[nearest] > MAX_SNAP_METERS:
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
        build_city_index()
    else:
        build_road_cache()
