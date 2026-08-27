"""
Module: data_generator
Description: Acts as a Data Fixture to generate synthetic, reproducible instances
             for the WSRP Base Model (M0 - TSP). It computes a fully connected
             graph where edge weights represent Euclidean distances.
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


if __name__ == "__main__":
    # Quick sanity check for the terminal
    mock_data = generate_wsrp_m0_instance(num_properties=5)
    print("--- Instance Generation Successful ---")
    print(f"Total Nodes (Depot + Properties): {mock_data['num_nodes']}")
    print("Distance Matrix (0 to 2):")
    for row in mock_data['distance_matrix'][:3]:
        print(row)
