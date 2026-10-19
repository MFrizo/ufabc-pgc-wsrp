"""
Module: model_1_a
Description: Mathematical formulation of M1.a for the WSRP.
             M1 (MO-DOMDVRPTW-SD with booked and flexible visits) reformulated
             without a single global Big-M constant:
             1. Iterative time-window domain reduction [a_i, b_i] by network reachability;
             2. Arc-specific tightened Big-M parameters M^k_{ij} = max(0, b_i + s_i + t^k_{ij} - a_j)
                and fixing of time-infeasible arcs (a_i + s_i + t^k_{ij} > b_j);
             3. Desrochers and Laporte (1991) lifted time-window bounds, broker-aggregated
                time propagation, and two-cycle elimination constraints (with the waiting-time
                validity correction noted by Yuan et al., 2020).
"""

import pyomo.environ as pyo

from src.models.blocked import forbid_blocked_arcs
from src.models.model_1 import (DELAY_TOLERANCE, DELAY_WEIGHT, LUNCH_DURATION, LUNCH_WINDOW,
                                MAX_DAY_LENGTH, OVERTIME_WEIGHT, TRAVEL_WEIGHT, tie_break_distance_weight)


def build_model_m1_a(data: dict) -> pyo.ConcreteModel:
    """
    Constructs the tightened and lifted MTZ MILP polyhedron for M1.a (reformulation of M1).

    Args:
        data (dict): Instance dictionary with the same keys as build_model_m1.

    Returns:
        pyo.ConcreteModel: The unoptimized mathematical model.
    """
    model = pyo.ConcreteModel(name="WSRP_M1_A_MO_DOMDVRPTW_SD_LIFTED_MTZ")

    num_properties = data['num_nodes'] - 1
    num_brokers = data['num_brokers']
    fixed_visits = sorted(data.get('fixed_visits', range(1, num_properties + 1)))
    latest_start = data.get('latest_start', data['earliest_start'])

    # =========================================================================
    # 1. SETS (Indices)
    # =========================================================================
    model.K = pyo.Set(initialize=range(1, num_brokers + 1), doc="Brokers")

    model.C = pyo.Set(initialize=range(1, num_properties + 1), doc="Properties")
    model.C_h = pyo.Set(initialize=fixed_visits, within=model.C, doc="Booked visits")
    model.C_w = pyo.Set(initialize=[i for i in model.C if i not in model.C_h], within=model.C,
                        doc="Flexible visits")

    def depot_rule(model_instance, k):
        return num_properties + k

    def end_rule(model_instance, k):
        return num_properties + num_brokers + k

    def lunch_rule(model_instance, k):
        return num_properties + 2 * num_brokers + k

    model.depot = pyo.Param(model.K, initialize=depot_rule, doc="Home d_k")
    model.end = pyo.Param(model.K, initialize=end_rule, doc="End of the day f_k")
    model.lunch = pyo.Param(model.K, initialize=lunch_rule, doc="Lunch a_k")

    model.D = pyo.Set(initialize=[depot_rule(model, k) for k in model.K], doc="Homes")
    model.F = pyo.Set(initialize=[end_rule(model, k) for k in model.K], doc="Ends of the day")
    model.A = pyo.Set(initialize=[lunch_rule(model, k) for k in model.K], doc="Lunches")

    model.V = model.C | model.D | model.F | model.A

    def arcs_rule(model_instance):
        for k in model_instance.K:
            d, f, a = depot_rule(model_instance, k), end_rule(model_instance, k), lunch_rule(model_instance, k)
            for j in [*model_instance.C, a]:
                yield d, j, k
            for i in model_instance.C:
                for j in [*model_instance.C, a, f]:
                    if i != j:
                        yield i, j, k
            for j in [*model_instance.C, f]:
                yield a, j, k

    model.ARCS = pyo.Set(dimen=3, initialize=arcs_rule, doc="Arcs (i, j, k) broker k may take")
    model.PAIRS = pyo.Set(dimen=2, initialize=[(i, j) for i in model.C for j in model.C if i != j],
                          doc="Ordered property pairs (i, j)")
    model.UPPER_PAIRS = pyo.Set(dimen=2, initialize=[(i, j) for i in model.C for j in model.C if i < j],
                                doc="Unordered property pairs (i, j) with i < j")

    # =========================================================================
    # 2. PARAMETERS (Data & Time-Window Preprocessing)
    # =========================================================================
    def broker_of_home(i):
        return i - num_properties

    def distance_rule(model_instance, i, j, k):
        if i in model_instance.C and j in model_instance.C:
            return data['distance_matrix'][i][j]
        if i in model_instance.D and j in model_instance.C:
            return data['home_distances'][broker_of_home(i) - 1][j]
        return 0.0

    def travel_time_rule(model_instance, i, j, k):
        if i in model_instance.C and j in model_instance.C:
            return data['travel_times'][0][i][j]
        if i in model_instance.D and j in model_instance.C:
            return data['home_travel_times'][0][broker_of_home(i) - 1][j]
        return 0.0

    model.distance = pyo.Param(model.ARCS, initialize=distance_rule, doc="Distance c_ij")
    model.travel_time = pyo.Param(model.ARCS, initialize=travel_time_rule, doc="Travel time t_ij")

    def service_rule(model_instance, i):
        if i in model_instance.C:
            return data['service_times'][i]
        return LUNCH_DURATION if i in model_instance.A else 0.0

    model.service = pyo.Param(model.V, initialize=service_rule, doc="Service time s_i")

    model.scheduled = pyo.Param(model.C_h, initialize=lambda m, i: data['earliest_start'][i],
                                doc="Scheduled start h_i")
    model.earliest = pyo.Param(model.C_w, initialize=lambda m, i: data['earliest_start'][i], doc="Earliest start e_i")
    model.latest = pyo.Param(model.C_w, initialize=lambda m, i: latest_start[i], doc="Latest start l_i")
    model.tolerance = pyo.Param(initialize=DELAY_TOLERANCE, doc="Tolerance tol")

    def shift_start_rule(model_instance, k):
        return data['shift_start'][k - 1]

    def shift_end_rule(model_instance, k):
        return data['shift_end'][k - 1]

    model.shift_start = pyo.Param(model.K, initialize=shift_start_rule, doc="Day start E_k")
    model.shift_end = pyo.Param(model.K, initialize=shift_end_rule, doc="Day end L_k")
    model.max_day_length = pyo.Param(initialize=data.get('max_day_length', MAX_DAY_LENGTH), doc="Max day length J_max")

    def eligibility_rule(model_instance, i, k):
        assigned = data['assigned_broker'][i]
        return 1 if assigned in (0, k) else 0

    model.eligibility = pyo.Param(model.C, model.K, initialize=eligibility_rule, doc="Compatibility P_ik")

    horizon = max([data['earliest_start'][i] + DELAY_TOLERANCE + data['service_times'][i] for i in model.C_h]
                  + [latest_start[i] + data['service_times'][i] for i in model.C_w]
                  + [LUNCH_WINDOW[1] + LUNCH_DURATION, max(data['shift_start'])])

    # 2.1 Time-Window Preprocessing (Domain Reduction)
    win_a, win_b = _preprocess_time_windows(model, data, horizon)
    model.window_start = pyo.Param(model.V, initialize=win_a, doc="Tightened earliest start a_i")
    model.window_end = pyo.Param(model.V, initialize=win_b, doc="Tightened latest start b_i")

    # 2.2 Arc-Specific Tightened M^k_{ij} = max(0, b_i + s_i + t^k_{ij} - a_j)
    def arc_big_m_rule(model_instance, i, j, k):
        span = (pyo.value(model_instance.window_end[i])
                + pyo.value(model_instance.service[i])
                + pyo.value(model_instance.travel_time[i, j, k])
                - pyo.value(model_instance.window_start[j]))
        return max(0.0, span)

    model.arc_big_m = pyo.Param(model.ARCS, initialize=arc_big_m_rule, doc="Arc-specific M^k_{ij}")

    paid_arcs = num_properties + num_brokers
    max_distance = max(pyo.value(model.distance[arc]) for arc in model.ARCS)
    model.travel_weight = pyo.Param(initialize=data.get('travel_weight', TRAVEL_WEIGHT), doc="W_time")
    model.distance_weight = pyo.Param(
        initialize=data.get('distance_weight', tie_break_distance_weight(paid_arcs, max_distance)), doc="W_dist")
    model.delay_weight = pyo.Param(initialize=data.get('delay_weight', DELAY_WEIGHT), doc="W_atraso")
    model.overtime_weight = pyo.Param(initialize=data.get('overtime_weight', OVERTIME_WEIGHT), doc="W_extra")

    max_routes = (paid_arcs * max(pyo.value(model.travel_time[arc]) for arc in model.ARCS)
                  * pyo.value(model.travel_weight)
                  + paid_arcs * max_distance * pyo.value(model.distance_weight)
                  + len(model.C_h) * DELAY_TOLERANCE * pyo.value(model.delay_weight)
                  + sum(max(0, horizon - pyo.value(model.shift_end[k])) for k in model.K)
                  * pyo.value(model.overtime_weight))
    model.fleet_weight = pyo.Param(initialize=data.get('fleet_weight', max_routes + 1), doc="W_frota")

    # =========================================================================
    # 3. DECISION VARIABLES
    # =========================================================================
    model.x = pyo.Var(model.ARCS, domain=pyo.Binary, doc="Edge traversal by broker")
    model.y = pyo.Var(model.K, domain=pyo.Binary, doc="Broker works")

    def w_bounds_rule(model_instance, i):
        return pyo.value(model_instance.window_start[i]), pyo.value(model_instance.window_end[i])

    model.w = pyo.Var(model.V, domain=pyo.NonNegativeReals, bounds=w_bounds_rule, doc="Start time")

    model.delay = pyo.Var(model.C, domain=pyo.NonNegativeReals, doc="Delay atraso_i")
    for i in model.C_w:
        model.delay[i].fix(0)

    model.overtime = pyo.Var(model.K, domain=pyo.NonNegativeReals, doc="Overtime he_k")

    # =========================================================================
    # 4. OBJECTIVE FUNCTION
    # =========================================================================
    def objective_rule(model_instance):
        """Minimize W_frota * sum(y_k) + W_time * sum(t_ij * x_ijk) + W_dist * sum(c_ij * x_ijk) + W_atraso * sum(atraso_i) + W_extra * sum(he_k)."""
        return (model_instance.fleet_weight * sum(model_instance.y[k] for k in model_instance.K)
                + model_instance.travel_weight * sum(model_instance.travel_time[arc] * model_instance.x[arc]
                                                     for arc in model_instance.ARCS)
                + model_instance.distance_weight * sum(model_instance.distance[arc] * model_instance.x[arc]
                                                       for arc in model_instance.ARCS)
                + model_instance.delay_weight * sum(model_instance.delay[i] for i in model_instance.C_h)
                + model_instance.overtime_weight * sum(model_instance.overtime[k] for k in model_instance.K))

    model.obj = pyo.Objective(rule=objective_rule, sense=pyo.minimize,
                              doc="Minimize brokers first, then travel time, delays and overtime")

    # =========================================================================
    # 5. CONSTRAINTS
    # =========================================================================
    def arcs_from(model_instance, i, k):
        return [model_instance.x[i, j, k] for j in model_instance.V if (i, j, k) in model_instance.ARCS]

    def arcs_into(model_instance, j, k):
        return [model_instance.x[i, j, k] for i in model_instance.V if (i, j, k) in model_instance.ARCS]

    # 5.1 Single Service & Compatibility
    def single_service_rule(model_instance, i):
        return sum(sum(arcs_from(model_instance, i, k)) for k in model_instance.K) == 1

    def compatibility_rule(model_instance, i, k):
        return sum(arcs_from(model_instance, i, k)) <= model_instance.eligibility[i, k]

    model.single_service_constraint = pyo.Constraint(model.C, rule=single_service_rule, doc="Constraint 5.1")
    model.compatibility_constraint = pyo.Constraint(model.C, model.K, rule=compatibility_rule,
                                                    doc="Constraint 5.1 compatibility")

    # 5.2 Flow Conservation and Open Routes
    def home_departure_rule(model_instance, k):
        return sum(arcs_from(model_instance, model_instance.depot[k], k)) == model_instance.y[k]

    def end_arrival_rule(model_instance, k):
        return sum(arcs_into(model_instance, model_instance.end[k], k)) == model_instance.y[k]

    def flow_conservation_rule(model_instance, h, k):
        if h in model_instance.A and h != model_instance.lunch[k]:
            return pyo.Constraint.Skip
        return sum(arcs_into(model_instance, h, k)) - sum(arcs_from(model_instance, h, k)) == 0

    model.home_departure_constraint = pyo.Constraint(model.K, rule=home_departure_rule, doc="Constraint 5.2 home")
    model.end_arrival_constraint = pyo.Constraint(model.K, rule=end_arrival_rule, doc="Constraint 5.2 end")
    model.flow_conservation_constraint = pyo.Constraint(model.C | model.A, model.K, rule=flow_conservation_rule,
                                                        doc="Constraint 5.2 flow")

    forbid_blocked_arcs(model, data)
    _fix_time_infeasible_arcs(model)

    # 5.3 Tightened Arc-Specific and Broker-Lifted Time Flow
    # Formula: w_i - w_j + M^k_{ij} * x_{ijk} <= b_i - a_j
    # When M^k_{ij} == 0 (i.e. b_i + s_i + t^k_{ij} <= a_j), variable bounds w_i <= b_i and
    # w_j >= a_j already enforce w_i + s_i + t^k_{ij} <= w_j. When x_{ijk} is fixed to 0,
    # w_i <= b_i and w_j >= a_j already enforce w_i - w_j <= b_i - a_j.
    def time_flow_rule(model_instance, i, j, k):
        if i in model_instance.C and j in model_instance.C:
            return pyo.Constraint.Skip
        if model_instance.x[i, j, k].fixed and pyo.value(model_instance.x[i, j, k]) == 0:
            return pyo.Constraint.Skip
        if pyo.value(model_instance.arc_big_m[i, j, k]) <= 0.0:
            return pyo.Constraint.Skip
        return (model_instance.w[i] - model_instance.w[j]
                + model_instance.arc_big_m[i, j, k] * model_instance.x[i, j, k]
                <= model_instance.window_end[i] - model_instance.window_start[j])

    # For property pairs (i, j) in C x C, at most one broker traverses (i, j), so summing
    # M^k_{ij} * x_{ijk} across all k in K into one inequality replaces |K| rows with 1 tighter row.
    def pair_time_flow_rule(model_instance, i, j):
        active_k = [k for k in model_instance.K
                    if not (model_instance.x[i, j, k].fixed and pyo.value(model_instance.x[i, j, k]) == 0)
                    and pyo.value(model_instance.arc_big_m[i, j, k]) > 0.0]
        if not active_k:
            return pyo.Constraint.Skip
        return (model_instance.w[i] - model_instance.w[j]
                + sum(model_instance.arc_big_m[i, j, k] * model_instance.x[i, j, k] for k in active_k)
                <= model_instance.window_end[i] - model_instance.window_start[j])

    # Bidirectional 2-cycle elimination coupling (i, j) and (j, i) across all brokers
    def two_cycle_rule(model_instance, i, j):
        terms = [model_instance.x[u, v, k]
                 for (u, v) in ((i, j), (j, i))
                 for k in model_instance.K
                 if not (model_instance.x[u, v, k].fixed and pyo.value(model_instance.x[u, v, k]) == 0)]
        if len(terms) <= 1:
            return pyo.Constraint.Skip
        return sum(terms) <= 1

    model.time_flow_constraint = pyo.Constraint(model.ARCS, rule=time_flow_rule, doc="Constraint 5.3")
    model.pair_time_flow_constraint = pyo.Constraint(model.PAIRS, rule=pair_time_flow_rule,
                                                     doc="Constraint 5.3 lifted pair")
    model.two_cycle_constraint = pyo.Constraint(model.UPPER_PAIRS, rule=two_cycle_rule,
                                                doc="Constraint 5.3 two-cycle")

    # 5.3b Desrochers and Laporte (1991) Lifted Time-Window Bounds
    # Formula: w_i >= a_i + sum_{(j,i,k)} max(0, a_j + s_j + t^k_{ji} - a_i) * x_{jik}
    #          w_i <= b_i - sum_{(i,j,k)} max(0, b_i - (b_j - s_i - t^k_{ij})) * x_{ijk}
    def lifted_early_rule(model_instance, i):
        a_i = pyo.value(model_instance.window_start[i])
        terms = []
        for k in model_instance.K:
            for j in model_instance.V:
                if (j, i, k) in model_instance.ARCS:
                    if model_instance.x[j, i, k].fixed and pyo.value(model_instance.x[j, i, k]) == 0:
                        continue
                    coeff = max(0.0, (pyo.value(model_instance.window_start[j])
                                      + pyo.value(model_instance.service[j])
                                      + pyo.value(model_instance.travel_time[j, i, k]) - a_i))
                    if coeff > 0.0:
                        terms.append(coeff * model_instance.x[j, i, k])
        if not terms:
            return pyo.Constraint.Skip
        return model_instance.w[i] >= a_i + sum(terms)

    def lifted_late_rule(model_instance, i):
        b_i = pyo.value(model_instance.window_end[i])
        s_i = pyo.value(model_instance.service[i])
        terms = []
        for k in model_instance.K:
            for j in model_instance.V:
                if (i, j, k) in model_instance.ARCS:
                    if model_instance.x[i, j, k].fixed and pyo.value(model_instance.x[i, j, k]) == 0:
                        continue
                    coeff = max(0.0, b_i - (pyo.value(model_instance.window_end[j])
                                            - s_i - pyo.value(model_instance.travel_time[i, j, k])))
                    if coeff > 0.0:
                        terms.append(coeff * model_instance.x[i, j, k])
        if not terms:
            return pyo.Constraint.Skip
        return model_instance.w[i] <= b_i - sum(terms)

    model.lifted_early_constraint = pyo.Constraint(model.C | model.A, rule=lifted_early_rule,
                                                   doc="Constraint 5.3b lifted early")
    model.lifted_late_constraint = pyo.Constraint(model.C | model.A, rule=lifted_late_rule,
                                                  doc="Constraint 5.3b lifted late")

    # 5.4 Soft Time Windows (booked visits) & 5.4b Flexible Windows
    def early_start_rule(model_instance, i):
        return model_instance.w[i] >= model_instance.scheduled[i] - model_instance.tolerance

    def soft_window_rule(model_instance, i):
        return model_instance.w[i] <= model_instance.scheduled[i] + model_instance.delay[i]

    def delay_tolerance_rule(model_instance, i):
        return model_instance.delay[i] <= model_instance.tolerance

    model.early_start_constraint = pyo.Constraint(model.C_h, rule=early_start_rule, doc="Constraint 5.4 early")
    model.soft_window_constraint = pyo.Constraint(model.C_h, rule=soft_window_rule, doc="Constraint 5.4")
    model.delay_tolerance_constraint = pyo.Constraint(model.C_h, rule=delay_tolerance_rule, doc="Constraint 5.4 tol")

    def flexible_window_rule(model_instance, i):
        return model_instance.window_start[i], model_instance.w[i], model_instance.window_end[i]

    model.flexible_window_constraint = pyo.Constraint(model.C_w, rule=flexible_window_rule, doc="Constraint 5.4b")

    # 5.5 Working Day (clock limits + linear route and fleet duration limits)
    def day_start_rule(model_instance, k):
        return model_instance.w[model_instance.depot[k]] >= model_instance.shift_start[k]

    def day_end_rule(model_instance, k):
        return model_instance.w[model_instance.end[k]] <= model_instance.shift_end[k] + model_instance.overtime[k]

    def day_length_rule(model_instance, k):
        return (model_instance.w[model_instance.end[k]] - model_instance.w[model_instance.depot[k]]
                <= model_instance.max_day_length)

    def route_duration_rule(model_instance, k):
        return (sum((model_instance.service[i] + model_instance.travel_time[i, j, k]) * model_instance.x[i, j, k]
                    for (i, j, broker) in model_instance.ARCS if broker == k)
                <= model_instance.max_day_length * model_instance.y[k])

    def fleet_duration_rule(model_instance):
        return (sum(model_instance.service[i] for i in model_instance.C)
                + sum(model_instance.travel_time[arc] * model_instance.x[arc] for arc in model_instance.ARCS)
                <= sum((model_instance.max_day_length - model_instance.service[model_instance.lunch[k]])
                       * model_instance.y[k] for k in model_instance.K))

    model.day_start_constraint = pyo.Constraint(model.K, rule=day_start_rule, doc="Constraint 5.5 start")
    model.day_end_constraint = pyo.Constraint(model.K, rule=day_end_rule, doc="Constraint 5.5 end")
    model.day_length_constraint = pyo.Constraint(model.K, rule=day_length_rule, doc="Constraint 5.5 length")
    model.route_duration_constraint = pyo.Constraint(model.K, rule=route_duration_rule, doc="Constraint 5.5 duration")
    model.fleet_duration_constraint = pyo.Constraint(rule=fleet_duration_rule, doc="Constraint 5.5 fleet duration")

    # 5.6 Lunch Break
    def lunch_visit_rule(model_instance, k):
        return sum(arcs_into(model_instance, model_instance.lunch[k], k)) == model_instance.y[k]

    def lunch_window_rule(model_instance, k):
        return LUNCH_WINDOW[0], model_instance.w[model_instance.lunch[k]], LUNCH_WINDOW[1]

    model.lunch_visit_constraint = pyo.Constraint(model.K, rule=lunch_visit_rule, doc="Constraint 5.6")
    model.lunch_window_constraint = pyo.Constraint(model.K, rule=lunch_window_rule, doc="Constraint 5.6 window")

    return model


def _preprocess_time_windows(model: pyo.ConcreteModel, data: dict, horizon: float) -> tuple[dict, dict]:
    """
    Tightens individual node time windows [a_i, b_i] by iterative forward and backward
    network reachability propagation until convergence.
    """
    win_a = {}
    win_b = {}
    latest_start = data.get('latest_start', data['earliest_start'])

    for i in model.C_h:
        h_i = float(data['earliest_start'][i])
        win_a[i] = max(0.0, h_i - DELAY_TOLERANCE)
        win_b[i] = h_i + DELAY_TOLERANCE

    for i in model.C_w:
        win_a[i] = float(data['earliest_start'][i])
        win_b[i] = float(latest_start[i])

    for k in model.K:
        d = pyo.value(model.depot[k])
        f = pyo.value(model.end[k])
        a = pyo.value(model.lunch[k])
        e_k = float(data['shift_start'][k - 1])
        win_a[d] = e_k
        win_b[d] = max(e_k, min(float(horizon), float(LUNCH_WINDOW[1])))
        win_a[a] = float(LUNCH_WINDOW[0])
        win_b[a] = float(LUNCH_WINDOW[1])
        win_a[f] = e_k
        win_b[f] = float(horizon)

    distances = data['distance_matrix']
    compatible_arcs = []
    for (i, j, k) in model.ARCS:
        if i in model.C and pyo.value(model.eligibility[i, k]) == 0:
            continue
        if j in model.C and pyo.value(model.eligibility[j, k]) == 0:
            continue
        if i in model.C and j in model.C and i != j and distances[i][j] == 0:
            continue
        step = float(pyo.value(model.service[i]) + pyo.value(model.travel_time[i, j, k]))
        compatible_arcs.append((i, j, k, step))

    changed = True
    while changed:
        changed = False
        active_in = {j: [] for j in model.C}
        active_out = {i: [] for i in model.C}
        for (i, j, _, step) in compatible_arcs:
            if win_a[i] + step <= win_b[j] + 1e-9:
                if j in active_in:
                    active_in[j].append((i, step))
                if i in active_out:
                    active_out[i].append((j, step))

        for j in model.C:
            if active_in[j]:
                earliest_arrival = min(win_a[i] + step for (i, step) in active_in[j])
                new_a = max(win_a[j], min(win_b[j], earliest_arrival))
                if new_a > win_a[j] + 1e-9:
                    win_a[j] = new_a
                    changed = True

        for i in model.C:
            if active_out[i]:
                latest_departure = max(win_b[j] - step for (j, step) in active_out[i])
                new_b = min(win_b[i], max(win_a[i], latest_departure))
                if new_b < win_b[i] - 1e-9:
                    win_b[i] = new_b
                    changed = True

    return win_a, win_b


def _fix_time_infeasible_arcs(model: pyo.ConcreteModel) -> None:
    """Fixes x_{ijk} = 0 on arcs whose earliest arrival exceeds the destination's latest start."""
    for (i, j, k) in model.ARCS:
        if model.x[i, j, k].fixed:
            continue
        earliest_arrival = (pyo.value(model.window_start[i])
                            + pyo.value(model.service[i])
                            + pyo.value(model.travel_time[i, j, k]))
        if earliest_arrival > pyo.value(model.window_end[j]) + 1e-9:
            model.x[i, j, k].fix(0)
