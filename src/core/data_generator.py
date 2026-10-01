"""
Module: data_generator
Description: Acts as a Data Fixture to generate synthetic, reproducible instances
             for the WSRP models (M0 - TSP, M1 - TSPTW). It computes a fully
             connected graph where edge weights represent Euclidean distances.
"""

import math
import numpy as np
from typing import Any


def generate_wsrp_m0_instance(num_properties: int = 5, random_seed: int = 42) -> dict[str, Any]:
    """
    Generates a synthetic dataset for the single-broker TSP routing problem.

    Args:
        num_properties (int): The number of properties to be visited.
        random_seed (int): Seed for the PRNG to ensure scientific reproducibility.

    Returns:
        dict[str, Any]: A dictionary containing the number of nodes, coordinates,
                        and the computed distance matrix.
    """
    # 1. Enforcing Reproducibility
    rng = np.random.default_rng(random_seed)

    # Total nodes: Depot (1) + Properties (num_properties)
    num_nodes = num_properties + 1

    # 2. Spatial Distribution
    # Generating random (x, y) coordinates in a 100x100 grid map
    # Index 0 will always represent the Depot (Real Estate Agency)
    coordinates = rng.random((num_nodes, 2)) * 100.0

    # 3. Distance Matrix Computation
    # Creating an N x N matrix initialized with zeros
    distance_matrix = np.zeros((num_nodes, num_nodes))

    for i in range(num_nodes):
        for j in range(num_nodes):
            if i != j:
                # Calculating Euclidean distance between node i and node j
                dist = math.hypot(coordinates[i][0] - coordinates[j][0],
                                  coordinates[i][1] - coordinates[j][1])
                # Rounding to 2 decimal places to avoid floating-point representation issues
                distance_matrix[i][j] = round(dist, 2)

    # 4. Packaging the payload
    data_payload = {
        'num_nodes': num_nodes,
        'coordinates': coordinates.tolist(),
        'distance_matrix': distance_matrix.tolist()
    }

    return data_payload


def generate_wsrp_m1_instance(num_properties: int = 5, random_seed: int = 42, travel_time: int = 30,
                              service_time: int = 60, horizon: int = 600, fixed_ratio: float = 0.2,
                              window_width: tuple[int, int] = (120, 360)) -> dict[str, Any]:
    """
    Generates a synthetic dataset for the single-broker TSPTW routing problem.

    The graph is the same as the M0 instance for the same seed. Time windows are
    built around a hidden reference schedule, which guarantees the instance is
    feasible. A share of the visits gets a fixed start time (e_i = l_i), emulating
    visits already scheduled by the visitors.

    Args:
        num_properties (int): The number of properties to be visited.
        random_seed (int): Seed for the PRNG to ensure scientific reproducibility.
        travel_time (int): Constant travel time T between any two nodes, in minutes.
        service_time (int): Constant visit duration S, in minutes.
        horizon (int): Length of the working day, in minutes (e.g. 600 = 08:00 to 18:00).
        fixed_ratio (float): Share of the properties with a fixed start time.
        window_width (tuple[int, int]): Min and max width of a flexible time window, in minutes.

    Returns:
        dict[str, Any]: The M0 payload plus the time parameters (T, S) and
                        the time windows (e_i, l_i) for every node.
    """
    # Every visit must fit in the day: n * (T + S) minutes of mandatory work
    slack = horizon - num_properties * (travel_time + service_time)
    if slack < 0:
        raise ValueError(f"Horizon of {horizon} min cannot fit {num_properties} visits "
                         f"of {service_time} min with {travel_time} min of travel between them.")

    # 1. Spatial Graph (identical to M0 for the same seed)
    data_payload = generate_wsrp_m0_instance(num_properties=num_properties, random_seed=random_seed)
    num_nodes = data_payload['num_nodes']

    # 2. Enforcing Reproducibility
    # Separate stream from the graph's, so changing time parameters never moves the nodes
    rng = np.random.default_rng([random_seed, 1])

    # 3. Hidden Reference Schedule
    # A random visiting order where the day's slack is spread as idle gaps between visits
    reference_order = rng.permutation(np.arange(1, num_nodes))
    gaps = rng.random(num_properties + 1)
    idle_before = np.cumsum(gaps / gaps.sum() * slack)[:num_properties]

    reference_start = [0] * num_nodes
    for position, node in enumerate(reference_order):
        reference_start[node] = math.floor(travel_time + position * (travel_time + service_time)
                                           + idle_before[position])

    # 4. Time Windows
    # The depot (node 0) may be left at any time of the day
    earliest_start = [0] * num_nodes
    latest_start = [horizon] * num_nodes

    num_fixed = round(fixed_ratio * num_properties)
    fixed_visits = sorted(int(node) for node in rng.choice(np.arange(1, num_nodes), size=num_fixed, replace=False))

    for node in range(1, num_nodes):
        if node in fixed_visits:
            # Visit already scheduled by the visitor: e_i = l_i
            earliest_start[node] = reference_start[node]
            latest_start[node] = reference_start[node]
        else:
            # Flexible visit: a window containing the reference start time
            width = int(rng.integers(window_width[0], window_width[1] + 1))
            opening = reference_start[node] - int(rng.integers(0, width + 1))
            earliest_start[node] = max(0, opening)
            latest_start[node] = min(horizon - service_time, opening + width)

    # 5. Packaging the payload
    data_payload.update({
        'travel_time': travel_time,
        'service_time': service_time,
        'earliest_start': earliest_start,
        'latest_start': latest_start,
        'fixed_visits': fixed_visits
    })

    return data_payload


if __name__ == "__main__":
    # Quick sanity check for the terminal
    mock_data = generate_wsrp_m0_instance(num_properties=5)
    print("--- Instance Generation Successful ---")
    print(f"Total Nodes (Depot + Properties): {mock_data['num_nodes']}")
    print("Distance Matrix (0 to 2):")
    for row in mock_data['distance_matrix'][:3]:
        print(row)
