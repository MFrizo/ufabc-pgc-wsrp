"""
Module: model_3
Description: Pareto front between the agency and the brokers.
             The feasible set is M1's: open routes from home, a lunch break, soft windows,
             overtime and a 12-hour day. M2's rules that the two models do not share — the
             broker's own shifts, his day off, and the trip to the lunch spot he picked —
             are the brokers' objective, not constraints. The front is the epsilon-constraint
             method on the number of brokers (Mavrotas, 2009).
"""

import math
from typing import Optional

import pyomo.environ as pyo

from src.models.model_1 import MAX_DAY_LENGTH, build_model_m1
from src.solvers.engine import solve_model

# One map unit per minute at M1's single speed, NORMAL_SPEED = 2 units per minute.
DRIVING_SPEED = 2.0


def build_model_m3(data: dict, fleet_cap: Optional[int] = None) -> pyo.ConcreteModel:
    """
    Builds one point of the front: M1's constraints, the brokers' cost minimized, and at
    most fleet_cap brokers at work. Absent, every broker may work.

    Args:
        data (dict): An M1 instance. It also reads 'shifts', 'lunch_spot_distances' and,
            when present, the home and lunch-spot coordinates.
        fleet_cap (int | None): Upper bound on the number of brokers who work.

    Returns:
        pyo.ConcreteModel: The unsolved model. Its active objective is the brokers' cost
            plus a travel-time tie-break smaller than one minute of that cost.
    """
    if 'shifts' not in data:
        raise ValueError("M3 needs each broker's shifts, including an empty list for a day off.")

    model = build_model_m1(data)
    model.obj.deactivate()

    on_shift = [k for k in model.K if data['shifts'][k - 1]]
    day_off = [k for k in model.K if not data['shifts'][k - 1]]
    model.K_on = pyo.Set(initialize=on_shift, doc="Brokers who have shifts")
    model.K_off = pyo.Set(initialize=day_off, doc="Brokers on their day off")

    shift_index = [(k, s) for k in on_shift for s in range(len(data['shifts'][k - 1]))]
    model.SHIFTS = pyo.Set(dimen=2, initialize=shift_index, doc="(broker, shift)")
    model.outside = pyo.Var(model.K_on, domain=pyo.NonNegativeReals, doc="Minutes of the route outside his shifts")
    model.overlap = pyo.Var(model.SHIFTS, domain=pyo.NonNegativeReals, doc="Minutes of the route inside one shift")
    model.reaches_shift = pyo.Var(model.SHIFTS, domain=pyo.Binary, doc="The route has not ended before the shift")
    model.started_by_shift = pyo.Var(model.SHIFTS, domain=pyo.Binary, doc="The route has started by the end of the shift")
    big_m = pyo.value(model.big_m)

    def _shift_bounds(k, s):
        return data['shifts'][k - 1][s]

    def overlap_length_rule(model_instance, k, s):
        start, end = _shift_bounds(k, s)
        return model_instance.overlap[k, s] <= end - start

    def overlap_in_route_rule(model_instance, k, s):
        depot, end = model_instance.depot[k], model_instance.end[k]
        return (model_instance.overlap[k, s]
                <= model_instance.w[end] - model_instance.w[depot] + big_m * (1 - model_instance.y[k]))

    def overlap_if_reached_rule(model_instance, k, s):
        return model_instance.overlap[k, s] <= big_m * model_instance.reaches_shift[k, s]

    def overlap_if_started_rule(model_instance, k, s):
        return model_instance.overlap[k, s] <= big_m * model_instance.started_by_shift[k, s]

    def reached_upper_rule(model_instance, k, s):
        start, _ = _shift_bounds(k, s)
        return model_instance.w[model_instance.end[k]] - start <= big_m * model_instance.reaches_shift[k, s]

    def reached_lower_rule(model_instance, k, s):
        start, _ = _shift_bounds(k, s)
        return (model_instance.w[model_instance.end[k]] - start
                >= -big_m * (1 - model_instance.reaches_shift[k, s]))

    def overlap_after_start_rule(model_instance, k, s):
        start, _ = _shift_bounds(k, s)
        return (model_instance.overlap[k, s]
                <= model_instance.w[model_instance.end[k]] - start
                + big_m * (1 - model_instance.reaches_shift[k, s]))

    def started_upper_rule(model_instance, k, s):
        _, end = _shift_bounds(k, s)
        return (model_instance.w[model_instance.depot[k]] - end
                <= big_m * (1 - model_instance.started_by_shift[k, s]))

    def started_lower_rule(model_instance, k, s):
        _, end = _shift_bounds(k, s)
        return model_instance.w[model_instance.depot[k]] - end >= -big_m * model_instance.started_by_shift[k, s]

    def overlap_before_end_rule(model_instance, k, s):
        _, end = _shift_bounds(k, s)
        return (model_instance.overlap[k, s]
                <= end - model_instance.w[model_instance.depot[k]]
                + big_m * (1 - model_instance.started_by_shift[k, s]))

    def outside_rule(model_instance, k):
        depot, end = model_instance.depot[k], model_instance.end[k]
        covered = sum(model_instance.overlap[k, s] for s in range(len(data['shifts'][k - 1])))
        return (model_instance.outside[k]
                >= model_instance.w[end] - model_instance.w[depot] - covered
                - big_m * (1 - model_instance.y[k]))

    model.overlap_length_constraint = pyo.Constraint(model.SHIFTS, rule=overlap_length_rule)
    model.overlap_in_route_constraint = pyo.Constraint(model.SHIFTS, rule=overlap_in_route_rule)
    model.overlap_if_reached_constraint = pyo.Constraint(model.SHIFTS, rule=overlap_if_reached_rule)
    model.overlap_if_started_constraint = pyo.Constraint(model.SHIFTS, rule=overlap_if_started_rule)
    model.reached_upper_constraint = pyo.Constraint(model.SHIFTS, rule=reached_upper_rule)
    model.reached_lower_constraint = pyo.Constraint(model.SHIFTS, rule=reached_lower_rule)
    model.overlap_after_start_constraint = pyo.Constraint(model.SHIFTS, rule=overlap_after_start_rule)
    model.started_upper_constraint = pyo.Constraint(model.SHIFTS, rule=started_upper_rule)
    model.started_lower_constraint = pyo.Constraint(model.SHIFTS, rule=started_lower_rule)
    model.overlap_before_end_constraint = pyo.Constraint(model.SHIFTS, rule=overlap_before_end_rule)
    model.outside_constraint = pyo.Constraint(model.K_on, rule=outside_rule)

    pairs = []
    detour_minutes = {}
    for k in model.K:
        lunch = pyo.value(model.lunch[k])
        incoming = [i for (i, j, broker) in model.ARCS if broker == k and j == lunch]
        outgoing = [j for (i, j, broker) in model.ARCS if broker == k and i == lunch]
        for i in incoming:
            for j in outgoing:
                pairs.append((i, j, k))
                detour_minutes[i, j, k] = _detour_minutes(data, model, k, i, j)

    model.LUNCH_PAIRS = pyo.Set(dimen=3, initialize=pairs, doc="(predecessor, successor, broker) of the lunch")
    model.z = pyo.Var(model.LUNCH_PAIRS, domain=pyo.Binary, doc="Lunch sits between this pair")

    def lunch_pairs_cover_rule(model_instance, k):
        return sum(model_instance.z[i, j, k] for (i, j, broker) in model_instance.LUNCH_PAIRS
                   if broker == k) == model_instance.y[k]

    def lunch_predecessor_rule(model_instance, i, k):
        lunch = pyo.value(model_instance.lunch[k])
        if (i, lunch, k) not in model_instance.ARCS:
            return pyo.Constraint.Skip
        return (sum(model_instance.z[i, j, k] for (pred, j, broker) in model_instance.LUNCH_PAIRS
                    if broker == k and pred == i)
                == model_instance.x[i, lunch, k])

    def lunch_successor_rule(model_instance, j, k):
        lunch = pyo.value(model_instance.lunch[k])
        if (lunch, j, k) not in model_instance.ARCS:
            return pyo.Constraint.Skip
        return (sum(model_instance.z[i, j, k] for (i, succ, broker) in model_instance.LUNCH_PAIRS
                    if broker == k and succ == j)
                == model_instance.x[lunch, j, k])

    model.LUNCH_FROM = pyo.Set(dimen=2, initialize=[(i, k) for (i, j, k) in pairs],
                               doc="Predecessor of a lunch and its broker")
    model.LUNCH_TO = pyo.Set(dimen=2, initialize=[(j, k) for (i, j, k) in pairs],
                             doc="Successor of a lunch and its broker")
    model.lunch_cover_constraint = pyo.Constraint(model.K, rule=lunch_pairs_cover_rule)
    model.lunch_predecessor_constraint = pyo.Constraint(model.LUNCH_FROM, rule=lunch_predecessor_rule)
    model.lunch_successor_constraint = pyo.Constraint(model.LUNCH_TO, rule=lunch_successor_rule)

    def broker_cost_rule(model_instance):
        shift_minutes = sum(model_instance.outside[k] for k in model_instance.K_on)
        day_off_minutes = MAX_DAY_LENGTH * sum(model_instance.y[k] for k in model_instance.K_off)
        lunch_minutes = sum(detour_minutes[i, j, k] * model_instance.z[i, j, k]
                            for (i, j, k) in model_instance.LUNCH_PAIRS)
        return shift_minutes + day_off_minutes + lunch_minutes

    model.broker_cost = pyo.Expression(rule=broker_cost_rule, doc="Brokers' objective f2, in minutes")

    max_travel = max(pyo.value(model.travel_time[arc]) for arc in model.ARCS)
    paid_arcs = (data['num_nodes'] - 1) + data['num_brokers']
    tie_break = 0.0 if max_travel == 0 else 1.0 / (paid_arcs * max_travel + 1.0)

    def objective_rule(model_instance):
        travel = sum(model_instance.travel_time[arc] * model_instance.x[arc] for arc in model_instance.ARCS)
        return model_instance.broker_cost + tie_break * travel

    model.broker_objective = pyo.Objective(rule=objective_rule, sense=pyo.minimize,
                                           doc="Minimize the brokers' cost, then travel time")

    cap = data['num_brokers'] if fleet_cap is None else fleet_cap

    def fleet_cap_rule(model_instance):
        return sum(model_instance.y[k] for k in model_instance.K) <= cap

    model.fleet_cap_constraint = pyo.Constraint(rule=fleet_cap_rule, doc="At most this many brokers work")
    model.fleet_cap = pyo.Param(initialize=cap, doc="Fleet cap m")
    return model


def pareto_front(data: dict, solver_name: str = 'gurobi_direct') -> list[dict]:
    """
    The non-dominated plans of M3. One MILP per fleet size: minimize the brokers' cost
    with at most m brokers at work, for m from 1 up to the fleet. A size the visits do
    not fit is skipped. A plan is kept when no other plan uses fewer brokers and costs
    the brokers less.

    Args:
        data (dict): The instance passed to build_model_m3.
        solver_name (str): Solver name forwarded to solve_model.

    Returns:
        list[dict]: Points ordered by the number of brokers. Each one has 'brokers',
            'fleet_cap', 'broker_cost', 'travel_time', 'delay' and 'overtime'.
    """
    points = []
    for cap in range(1, data['num_brokers'] + 1):
        model = build_model_m3(data, fleet_cap=cap)
        solved, metrics = solve_model(model, solver_name=solver_name, mip_gap=0.0, raw=True)
        if metrics['termination_condition'] != 'optimal':
            continue
        points.append(_point(solved, cap))
    return _nondominated(points)


def _point(model: pyo.ConcreteModel, cap: int) -> dict:
    """Objective values of one solved fleet size."""
    brokers = int(round(sum(pyo.value(model.y[k]) for k in model.K)))
    travel = sum(pyo.value(model.travel_time[arc]) * pyo.value(model.x[arc]) for arc in model.ARCS)
    return {
        'brokers': brokers,
        'fleet_cap': cap,
        'broker_cost': pyo.value(model.broker_cost),
        'travel_time': travel,
        'delay': sum(pyo.value(model.delay[i]) for i in model.C),
        'overtime': sum(pyo.value(model.overtime[k]) for k in model.K),
    }


def _nondominated(points: list[dict]) -> list[dict]:
    """Drops plans that use more brokers without costing the brokers less."""
    best = {}
    for point in points:
        key = point['brokers']
        current = best.get(key)
        if current is None or point['broker_cost'] < current['broker_cost'] - 1e-4:
            best[key] = point
        elif abs(point['broker_cost'] - current['broker_cost']) <= 1e-4 and point['travel_time'] < current['travel_time']:
            best[key] = point

    ordered = [best[key] for key in sorted(best)]
    front = []
    for point in ordered:
        if any(other['brokers'] <= point['brokers']
               and other['broker_cost'] <= point['broker_cost'] + 1e-4
               and (other['brokers'] < point['brokers'] or other['broker_cost'] < point['broker_cost'] - 1e-4)
               for other in ordered):
            continue
        front.append(point)
    return front


def _detour_minutes(data: dict, model: pyo.ConcreteModel, k: int, i: int, j: int) -> float:
    """
    Extra minutes, at DRIVING_SPEED, of going from i to the broker's lunch spot and on to j
    instead of straight from i to j. The virtual end of the day has no onward trip.
    """
    added = _lunch_distance(data, model, k, i) + _lunch_distance(data, model, k, j)
    skipped = 0.0 if _is_end(model, k, j) else _direct_distance(data, model, k, i, j)
    return max(0.0, added - skipped) / DRIVING_SPEED


def _lunch_distance(data: dict, model: pyo.ConcreteModel, k: int, node: int) -> float:
    """Distance from a node to the broker's lunch spot. The virtual end is not a place."""
    if node in model.C:
        return data['lunch_spot_distances'][k - 1][node]
    if node == pyo.value(model.depot[k]):
        return _home_to_lunch(data, k)
    return 0.0


def _direct_distance(data: dict, model: pyo.ConcreteModel, k: int, i: int, j: int) -> float:
    """Distance of the arc the lunch replaces."""
    if i in model.C and j in model.C:
        return data['distance_matrix'][i][j]
    if i == pyo.value(model.depot[k]) and j in model.C:
        return data['home_distances'][k - 1][j]
    return 0.0


def _home_to_lunch(data: dict, k: int) -> float:
    """Distance from the broker's home to his lunch spot, on the same scale as his other trips."""
    homes = data.get('home_coordinates')
    spots = data.get('lunch_spot_coordinates')
    if not homes or not spots:
        return 0.0
    home, spot = homes[k - 1], spots[k - 1]
    straight = math.hypot(home[0] - spot[0], home[1] - spot[1])
    if straight == 0 or 'coordinates' not in data:
        return round(straight, 2)
    node = next((index for index, point in enumerate(data['coordinates']) if point != home), None)
    if node is None:
        return round(straight, 2)
    node_straight = math.hypot(home[0] - data['coordinates'][node][0], home[1] - data['coordinates'][node][1])
    if node_straight == 0:
        return round(straight, 2)
    scale = data['home_distances'][k - 1][node] / node_straight
    return round(straight * scale, 2)


def _is_end(model: pyo.ConcreteModel, k: int, node: int) -> bool:
    return node == pyo.value(model.end[k])
