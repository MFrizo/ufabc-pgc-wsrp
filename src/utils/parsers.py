"""
Module: parsers
Description: Translates the optimized mathematical variables (e.g., binary matrices)
             into human-readable chronological routes. Applies graph traversal to
             ensure sequential ordering of the visited properties.
"""

from typing import Iterable, Optional, cast, Any
import pyomo.environ as pyo


def print_routes(model: pyo.ConcreteModel, elapsed_time: Optional[float] = None) -> None:
    """
    Extracts the active edges from the TSP model and prints the route in order.

    Args:
        model (pyo.ConcreteModel): The solved Pyomo model containing optimized variables.
        elapsed_time (Optional[float]): Solver execution time in seconds, printed alongside the distance.
    """
    print("\n" + "=" * 50)
    print("ROUTE OPTIMIZATION RESULTS")
    print("=" * 50)

    # 1. Edge Extraction
    # We map origin to destination for all edges where x[i,j] is approximately 1.
    # We use > 0.5 to prevent floating-point inaccuracies from solvers (e.g., 0.999999).
    active_edges = {}
    nodes = cast(Iterable, model.V)
    for i in nodes:
        for j in nodes:
            if i != j:
                if pyo.value(cast(Any, model.x)[i, j]) > 0.5:
                    active_edges[i] = j

    # 2. Chronological Traversal (Linked-list approach)
    # The route must always start at the Depot (Node 0)
    current_node = 0
    route_sequence = [str(current_node)]

    # 3. Graph Traversal Loop
    # We follow the active edges sequentially until we loop back to the depot
    while True:
        next_node = active_edges.get(current_node)

        if next_node is None:
            print("[ERROR] Flow conservation broken. Dead end reached.")
            return

        route_sequence.append(str(next_node))

        # If the solver brought us back to the depot, the closed route is complete
        if next_node == 0:
            break

        current_node = next_node

    # 4. Human-Readable Output
    formatted_route = " -> ".join(route_sequence)
    total_cost = pyo.value(model.obj)

    print(f"Optimal Sequence : {formatted_route}")
    print(f"Total Distance   : {total_cost:.2f} units")
    if elapsed_time is not None:
        print(f"Total Time       : {elapsed_time:.4f} seconds")
    print("=" * 50 + "\n")
