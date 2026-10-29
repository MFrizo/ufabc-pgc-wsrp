"""
Module: model_3_a
Description: Mathematical formulation of M3.a for the WSRP.
             Pareto front between the agency and the brokers without a global Big-M constant:
             1. Built on top of M1.a (tightened time windows [a_i, b_i], arc-specific M^k_{ij},
                Desrochers-Laporte lifted time-window bounds, and two-cycle elimination);
             2. Replaces all global Big-M constants in the shift-overlap indicator constraints
                with tight node/shift-specific bounds derived from [a_{d_k}, b_{d_k}],
                [a_{f_k}, b_{f_k}], and [E_{k,s}, L_{k,s}];
             3. Eliminates Big-M completely from overlap_in_route and outside_constraint via
                linear route-duration lower bounds on w_{f_k} - w_{d_k} and y_k-bounded overlaps,
                and prunes time-infeasible lunch pairs z_{ijk}.
"""

from typing import Optional

import pyomo.environ as pyo

from src.models.model_1 import MAX_DAY_LENGTH
from src.models.model_1_a import build_model_m1_a
from src.models.model_3 import _detour_minutes, _nondominated, _point
from src.solvers.engine import solve_model


def build_model_m3_a(data: dict, fleet_cap: Optional[int] = None) -> pyo.ConcreteModel:
    """
    Builds one point of the M3.a Pareto front: M1.a's tightened constraints, the brokers'
    cost minimized with tightened shift-overlap bounds, and at most fleet_cap brokers at work.

    Args:
        data (dict): An M1/M3 instance dictionary.
        fleet_cap (int | None): Upper bound on the number of brokers who work.

    Returns:
        pyo.ConcreteModel: The unsolved mathematical model.
    """
    if 'shifts' not in data:
        raise ValueError("M3.a needs each broker's shifts, including an empty list for a day off.")

    model = build_model_m1_a(data)
    model.name = "WSRP_M3_A_PARETO_LIFTED_MTZ"
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
    model.started_by_shift = pyo.Var(model.SHIFTS, domain=pyo.Binary,
                                     doc="The route has started by the end of the shift")

    def _shift_bounds(k, s):
        return data['shifts'][k - 1][s]

    # Tight shift-overlap indicator bounds from preprocessed [a_{d_k}, b_{d_k}] and [a_{f_k}, b_{f_k}]
    def reach_upper_m_rule(model_instance, k, s):
        start, _ = _shift_bounds(k, s)
        b_fk = pyo.value(model_instance.window_end[model_instance.end[k]])
        return max(0.0, b_fk - start)

    def reach_lower_m_rule(model_instance, k, s):
        start, _ = _shift_bounds(k, s)
        a_fk = pyo.value(model_instance.window_start[model_instance.end[k]])
        return max(0.0, start - a_fk)

    def start_upper_m_rule(model_instance, k, s):
        _, end = _shift_bounds(k, s)
        b_dk = pyo.value(model_instance.window_end[model_instance.depot[k]])
        return max(0.0, b_dk - end)

    def start_lower_m_rule(model_instance, k, s):
        _, end = _shift_bounds(k, s)
        a_dk = pyo.value(model_instance.window_start[model_instance.depot[k]])
        return max(0.0, end - a_dk)

    model.reach_upper_m = pyo.Param(model.SHIFTS, initialize=reach_upper_m_rule, doc="M^{+}_{reach, k, s}")
    model.reach_lower_m = pyo.Param(model.SHIFTS, initialize=reach_lower_m_rule, doc="M^{-}_{reach, k, s}")
    model.start_upper_m = pyo.Param(model.SHIFTS, initialize=start_upper_m_rule, doc="M^{+}_{start, k, s}")
    model.start_lower_m = pyo.Param(model.SHIFTS, initialize=start_lower_m_rule, doc="M^{-}_{start, k, s}")

    # Linear lower bound on route span w_{f_k} - w_{d_k} (also enforces w_{f_k} >= w_{d_k} when y_k = 0)
    def route_span_lower_rule(model_instance, k):
        depot, end = model_instance.depot[k], model_instance.end[k]
        return (model_instance.w[end] - model_instance.w[depot]
                >= sum((model_instance.service[i] + model_instance.travel_time[i, j, k]) * model_instance.x[i, j, k]
                       for (i, j, broker) in model_instance.ARCS if broker == k))

    def overlap_length_rule(model_instance, k, s):
        start, end = _shift_bounds(k, s)
        return model_instance.overlap[k, s] <= (end - start) * model_instance.y[k]

    def overlap_in_route_rule(model_instance, k, s):
        depot, end = model_instance.depot[k], model_instance.end[k]
        return model_instance.overlap[k, s] <= model_instance.w[end] - model_instance.w[depot]

    def overlap_if_reached_rule(model_instance, k, s):
        start, end = _shift_bounds(k, s)
        return model_instance.overlap[k, s] <= (end - start) * model_instance.reaches_shift[k, s]

    def overlap_if_started_rule(model_instance, k, s):
        start, end = _shift_bounds(k, s)
        return model_instance.overlap[k, s] <= (end - start) * model_instance.started_by_shift[k, s]

    def reached_upper_rule(model_instance, k, s):
        start, _ = _shift_bounds(k, s)
        return (model_instance.w[model_instance.end[k]] - start
                <= model_instance.reach_upper_m[k, s] * model_instance.reaches_shift[k, s])

    def reached_lower_rule(model_instance, k, s):
        start, _ = _shift_bounds(k, s)
        return (model_instance.w[model_instance.end[k]] - start
                >= -model_instance.reach_lower_m[k, s] * (1 - model_instance.reaches_shift[k, s]))

    def overlap_after_start_rule(model_instance, k, s):
        start, _ = _shift_bounds(k, s)
        return (model_instance.overlap[k, s]
                <= model_instance.w[model_instance.end[k]] - start
                + model_instance.reach_lower_m[k, s] * (1 - model_instance.reaches_shift[k, s]))

    def started_upper_rule(model_instance, k, s):
        _, end = _shift_bounds(k, s)
        return (model_instance.w[model_instance.depot[k]] - end
                <= model_instance.start_upper_m[k, s] * (1 - model_instance.started_by_shift[k, s]))

    def started_lower_rule(model_instance, k, s):
        _, end = _shift_bounds(k, s)
        return (model_instance.w[model_instance.depot[k]] - end
                >= -model_instance.start_lower_m[k, s] * model_instance.started_by_shift[k, s])

    def overlap_before_end_rule(model_instance, k, s):
        _, end = _shift_bounds(k, s)
        return (model_instance.overlap[k, s]
                <= end - model_instance.w[model_instance.depot[k]]
                + model_instance.start_upper_m[k, s] * (1 - model_instance.started_by_shift[k, s]))

    def outside_rule(model_instance, k):
        depot, end = model_instance.depot[k], model_instance.end[k]
        covered = sum(model_instance.overlap[k, s] for s in range(len(data['shifts'][k - 1])))
        return model_instance.outside[k] >= model_instance.w[end] - model_instance.w[depot] - covered

    model.route_span_lower_constraint = pyo.Constraint(model.K, rule=route_span_lower_rule)
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
    lunch_from = []
    lunch_to = []
    detour_minutes = {}
    for k in model.K:
        lunch = pyo.value(model.lunch[k])
        incoming = [i for (i, j, broker) in model.ARCS
                    if broker == k and j == lunch
                    and not (model.x[i, lunch, k].fixed and pyo.value(model.x[i, lunch, k]) == 0)]
        outgoing = [j for (i, j, broker) in model.ARCS
                    if broker == k and i == lunch
                    and not (model.x[lunch, j, k].fixed and pyo.value(model.x[lunch, j, k]) == 0)]
        for i in incoming:
            lunch_from.append((i, k))
        for j in outgoing:
            lunch_to.append((j, k))
        for i in incoming:
            for j in outgoing:
                if i == j:
                    continue
                pairs.append((i, j, k))
                detour_minutes[i, j, k] = _detour_minutes(data, model, k, i, j)

    model.LUNCH_PAIRS = pyo.Set(dimen=3, initialize=pairs, doc="(predecessor, successor, broker) of the lunch")
    model.z = pyo.Var(model.LUNCH_PAIRS, domain=pyo.Binary, doc="Lunch sits between this pair")

    # Fix z_{ijk} = 0 when i -> a_k -> j cannot satisfy the tightened time windows
    for (i, j, k) in model.LUNCH_PAIRS:
        lunch = pyo.value(model.lunch[k])
        earliest_lunch = max(pyo.value(model.window_start[lunch]),
                             pyo.value(model.window_start[i])
                             + pyo.value(model.service[i])
                             + pyo.value(model.travel_time[i, lunch, k]))
        earliest_at_j = (earliest_lunch
                         + pyo.value(model.service[lunch])
                         + pyo.value(model.travel_time[lunch, j, k]))
        if earliest_at_j > pyo.value(model.window_end[j]) + 1e-9:
            model.z[i, j, k].fix(0)

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

    model.LUNCH_FROM = pyo.Set(dimen=2, initialize=lunch_from,
                               doc="Predecessor of a lunch and its broker")
    model.LUNCH_TO = pyo.Set(dimen=2, initialize=lunch_to,
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


def pareto_front(data: dict, solver_name: str = 'gurobi_direct',
                 popmusic: bool = False, popmusic_r: int = 2,
                 popmusic_sub_time_limit: Optional[float] = 30.0) -> list[dict]:
    """
    The non-dominated plans of M3.a. One MILP per fleet size using build_model_m3_a.
    """
    points = []
    for cap in range(1, data['num_brokers'] + 1):
        model = build_model_m3_a(data, fleet_cap=cap)
        solved, metrics = solve_model(
            model, solver_name=solver_name, mip_gap=0.0, raw=not popmusic,
            popmusic=popmusic, popmusic_r=popmusic_r,
            popmusic_sub_time_limit=popmusic_sub_time_limit,
        )
        if metrics['termination_condition'] not in ('optimal', 'locallyOptimal'):
            continue
        points.append(_point(solved, cap))
    return _nondominated(points)
