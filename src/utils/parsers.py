"""
Module: parsers
Description: Translates the optimized mathematical variables (e.g., binary matrices)
             into human-readable chronological routes. Applies graph traversal to
             ensure sequential ordering of the visited properties.
"""

from typing import Iterable, Optional, cast, Any
import pyomo.environ as pyo


def extract_route(model: pyo.ConcreteModel) -> Optional[list[int]]:
    """
    Follows the active edges of a solved single-route model starting from the depot.

    Args:
        model (pyo.ConcreteModel): The solved Pyomo model containing optimized variables.

    Returns:
        Optional[list[int]]: The closed node sequence (starting and ending at 0),
                             or None if flow conservation is broken.
    """
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
    route_sequence = [current_node]

    # 3. Graph Traversal Loop
    # We follow the active edges sequentially until we loop back to the depot
    while True:
        next_node = active_edges.get(current_node)

        if next_node is None:
            return None

        route_sequence.append(next_node)

        # If the solver brought us back to the depot, the closed route is complete
        if next_node == 0:
            return route_sequence

        current_node = next_node


def print_routes(model: pyo.ConcreteModel, elapsed_time: Optional[float] = None, solver_mode: Optional[str] = None) -> None:
    """
    Extracts the active edges from the TSP model and prints the route in order.

    Args:
        model (pyo.ConcreteModel): The solved Pyomo model containing optimized variables.
        elapsed_time (Optional[float]): Solver execution time in seconds, printed alongside the distance.
        solver_mode (Optional[str]): Solver mode the execution happened: 'raw' or 'default'.
    """
    print("\n" + "=" * 50)
    print("ROUTE OPTIMIZATION RESULTS")
    print("=" * 50)

    route_sequence = extract_route(model)
    if route_sequence is None:
        print("[ERROR] Flow conservation broken. Dead end reached.")
        return

    # Human-Readable Output
    formatted_route = " -> ".join(str(node) for node in route_sequence)
    total_cost = pyo.value(model.obj)

    print(f"Optimal Sequence : {formatted_route}")
    print(f"Total Distance   : {total_cost:.2f} units")
    if elapsed_time is not None:
        print(f"Total Time       : {elapsed_time:.4f} seconds")
    if solver_mode is not None:
        print(f"Solver Mode      : {solver_mode}")
    print("=" * 50 + "\n")


def print_schedule(model: pyo.ConcreteModel) -> None:
    """
    Prints the start time of every job along the route next to its time window (TSPTW models).

    Args:
        model (pyo.ConcreteModel): The solved Pyomo model containing the start-time variables (w).
    """
    print("=" * 50)
    print("SCHEDULE (minutes from the start of the day)")
    print("=" * 50)

    route_sequence = extract_route(model)
    if route_sequence is None:
        print("[ERROR] Flow conservation broken. Dead end reached.")
        return

    _print_schedule_rows(model, route_sequence)
    print("=" * 50 + "\n")


def extract_broker_routes(model: pyo.ConcreteModel) -> Optional[dict[int, list[int]]]:
    """
    Follows the active edges of every broker of a solved multi-broker model, starting from the base.

    Args:
        model (pyo.ConcreteModel): The solved Pyomo model with edge variables x[i, j, k].

    Returns:
        Optional[dict[int, list[int]]]: The closed route of each broker who leaves the base,
                                        or None if flow conservation is broken.
    """
    model_any = cast(Any, model)
    nodes = list(model_any.V)
    routes = {}

    for k in model_any.K:
        active_edges = {i: j for i in nodes for j in nodes
                        if i != j and pyo.value(model_any.x[i, j, k]) > 0.5}

        # Brokers who never leave the base have no route
        if 0 not in active_edges:
            continue

        route_sequence = [0]
        while route_sequence[-1] != 0 or len(route_sequence) == 1:
            next_node = active_edges.get(route_sequence[-1])
            if next_node is None or len(route_sequence) > len(nodes):
                return None
            route_sequence.append(next_node)

        routes[k] = route_sequence

    return routes


def print_broker_routes(model: pyo.ConcreteModel, elapsed_time: Optional[float] = None,
                        solver_mode: Optional[str] = None) -> None:
    """
    Prints the route of every broker of a solved multi-broker model.

    Args:
        model (pyo.ConcreteModel): The solved Pyomo model with edge variables x[i, j, k].
        elapsed_time (Optional[float]): Solver execution time in seconds, printed alongside the distance.
        solver_mode (Optional[str]): Solver mode the execution happened: 'raw' or 'default'.
    """
    print("\n" + "=" * 50)
    print("ROUTE OPTIMIZATION RESULTS")
    print("=" * 50)

    routes = extract_broker_routes(model)
    if routes is None:
        print("[ERROR] Flow conservation broken. Dead end reached.")
        return

    for k, route_sequence in routes.items():
        print(f"{f'Broker {k}':<17}: {' -> '.join(str(node) for node in route_sequence)}")

    print(f"Brokers Used     : {len(routes)} of {len(cast(Any, model).K)}")
    print(f"Total Distance   : {pyo.value(model.obj):.2f} units")
    if elapsed_time is not None:
        print(f"Total Time       : {elapsed_time:.4f} seconds")
    if solver_mode is not None:
        print(f"Solver Mode      : {solver_mode}")
    print("=" * 50 + "\n")


def print_broker_schedules(model: pyo.ConcreteModel) -> None:
    """
    Prints the schedule of every broker of a solved multi-broker model.

    Args:
        model (pyo.ConcreteModel): The solved Pyomo model with start-time variables (w).
    """
    print("=" * 50)
    print("SCHEDULE (minutes from the start of the day)")
    print("=" * 50)

    routes = extract_broker_routes(model)
    if routes is None:
        print("[ERROR] Flow conservation broken. Dead end reached.")
        return

    for k, route_sequence in routes.items():
        print(f"Broker {k}")
        _print_schedule_rows(model, route_sequence)

    print("=" * 50 + "\n")


def print_results(model: pyo.ConcreteModel, elapsed_time: Optional[float] = None,
                  solver_mode: Optional[str] = None) -> None:
    """
    Prints the routes of a solved model and, when it has start times, its schedule.
    The printers are picked from the components the model defines (K for brokers,
    w for start times), so the callers don't need to know which model was solved.

    Args:
        model (pyo.ConcreteModel): The solved Pyomo model.
        elapsed_time (Optional[float]): Solver execution time in seconds, printed alongside the distance.
        solver_mode (Optional[str]): Solver mode the execution happened: 'raw' or 'default'.
    """
    if hasattr(model, 'K'):
        print_broker_routes(model, elapsed_time=elapsed_time, solver_mode=solver_mode)
        print_broker_schedules(model)
    else:
        print_routes(model, elapsed_time=elapsed_time, solver_mode=solver_mode)
        if hasattr(model, 'w'):
            print_schedule(model)


def _print_schedule_rows(model: pyo.ConcreteModel, route_sequence: list[int]) -> None:
    """
    Prints the start, end and time window of every visit of a closed route.

    Args:
        model (pyo.ConcreteModel): The solved Pyomo model with start-time variables (w).
        route_sequence (list[int]): Closed node sequence, starting and ending at the base.
    """
    model_any = cast(Any, model)
    print(f"{'Node':>4} | {'Start':>7} | {'End':>7} | {'Window':>12}")

    # The trailing base is the return trip, which has no start-time variable
    for node in route_sequence[:-1]:
        start = pyo.value(model_any.w[node])
        end = start + pyo.value(model_any.service[node])
        window = f"[{pyo.value(model_any.earliest[node]):g}, {pyo.value(model_any.latest[node]):g}]"
        print(f"{node:>4} | {start:>7.2f} | {end:>7.2f} | {window:>12}")
