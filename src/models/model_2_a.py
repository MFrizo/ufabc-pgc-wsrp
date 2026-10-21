"""
Module: model_2_a
Description: Mathematical formulation of M2.a for the WSRP.
             M2 (HC-DOMDVRPTW-SD, broker-focused model with booked and flexible visits)
             reformulated without a single global Big-M constant:
             1. Iterative time-window domain reduction [a_i, b_i] by shift and network reachability;
             2. Arc-specific tightened Big-M parameters M^r_{ij} = max(0, b_i + s_i + t^r_{ij} - a_j),
                shift-specific span bounds M^r_span = max(0, b_{f_r} - E_r), lifted shift-end bounds,
                and fixing of time-infeasible arcs;
             3. Desrochers and Laporte (1991) lifted time-window bounds, shift-aggregated
                time propagation, and two-cycle elimination constraints.
"""

import pyomo.environ as pyo

from src.models.blocked import forbid_blocked_arcs
from src.models.model_2 import DELAY_TOLERANCE, FUEL_REAIS_PER_MAP_UNIT, tie_break_minute_weight


def build_model_m2_a(data: dict) -> pyo.ConcreteModel:
    """
    Constructs the tightened and lifted MTZ MILP polyhedron for M2.a (reformulation of M2).

    Args:
        data (dict): Instance dictionary with the same keys as build_model_m2.

    Returns:
        pyo.ConcreteModel: The unoptimized mathematical model.
    """
    model = pyo.ConcreteModel(name="WSRP_M2_A_HC_DOMDVRPTW_SD_LIFTED_MTZ")

    num_properties = data['num_nodes'] - 1
    fixed_visits = sorted(data.get('fixed_visits', range(1, num_properties + 1)))
    latest_start = data.get('latest_start', data['earliest_start'])

    routes = [(k, label, origin, destination, start, end)
              for k, broker_shifts in enumerate(data['shifts'], start=1)
              for (start, end), label, origin, destination in zip(broker_shifts, ('A', 'B'),
                                                                   ('home', 'lunch_spot'), ('lunch_spot', 'home'))]
    num_routes = len(routes)

    # =========================================================================
    # 1. SETS (Indices)
    # =========================================================================
    model.K = pyo.Set(initialize=range(1, data['num_brokers'] + 1), doc="Brokers")
    model.R = pyo.Set(initialize=range(1, num_routes + 1), doc="Shifts t_k")

    model.C = pyo.Set(initialize=range(1, num_properties + 1), doc="Properties")
    model.C_h = pyo.Set(initialize=fixed_visits, within=model.C, doc="Booked visits")
    model.C_w = pyo.Set(initialize=[i for i in model.C if i not in model.C_h], within=model.C,
                        doc="Flexible visits")

    def depot_rule(model_instance, r):
        return num_properties + r

    def end_rule(model_instance, r):
        return num_properties + num_routes + r

    model.depot = pyo.Param(model.R, initialize=depot_rule, doc="Origin d_tk")
    model.end = pyo.Param(model.R, initialize=end_rule, doc="End of the shift f_tk")

    model.D = pyo.Set(initialize=[depot_rule(model, r) for r in model.R], doc="Origins")
    model.F = pyo.Set(initialize=[end_rule(model, r) for r in model.R], doc="Ends of the shifts")

    model.V = model.C | model.D | model.F

    model.route_broker = pyo.Param(model.R, initialize=lambda m, r: routes[r - 1][0], doc="Broker of the shift")
    model.route_name = pyo.Param(model.R, initialize=lambda m, r: f"{routes[r - 1][0]}{routes[r - 1][1]}",
                                 within=pyo.Any, doc="Name of the shift")

    def arcs_rule(model_instance):
        for r in model_instance.R:
            d, f = depot_rule(model_instance, r), end_rule(model_instance, r)
            for j in model_instance.C:
                yield d, j, r
            for i in model_instance.C:
                for j in [*model_instance.C, f]:
                    if i != j:
                        yield i, j, r

    model.ARCS = pyo.Set(dimen=3, initialize=arcs_rule, doc="Arcs (i, j, t_k) shift t_k may take")
    model.PAIRS = pyo.Set(dimen=2, initialize=[(i, j) for i in model.C for j in model.C if i != j],
                          doc="Ordered property pairs (i, j)")
    model.UPPER_PAIRS = pyo.Set(dimen=2, initialize=[(i, j) for i in model.C for j in model.C if i < j],
                                doc="Unordered property pairs (i, j) with i < j")

    # =========================================================================
    # 2. PARAMETERS (Data & Time-Window Preprocessing)
    # =========================================================================
    def distance_rule(model_instance, i, j, r):
        k, _, origin, destination, _, _ = routes[r - 1]
        if i in model_instance.C and j in model_instance.C:
            return data['distance_matrix'][i][j]
        if i in model_instance.D:
            return data[f'{origin}_distances'][k - 1][j]
        return data[f'{destination}_distances'][k - 1][i]

    def travel_time_rule(model_instance, i, j, r):
        k, _, origin, destination, _, _ = routes[r - 1]
        if i in model_instance.C and j in model_instance.C:
            return data['travel_times'][0][i][j]
        if i in model_instance.D:
            return data[f'{origin}_travel_times'][0][k - 1][j]
        return data[f'{destination}_travel_times'][0][k - 1][i]

    model.distance = pyo.Param(model.ARCS, initialize=distance_rule, doc="Distance c_ij")
    model.travel_time = pyo.Param(model.ARCS, initialize=travel_time_rule, doc="Travel time t_ij")

    def service_rule(model_instance, i):
        return data['service_times'][i] if i in model_instance.C else 0.0

    model.service = pyo.Param(model.V, initialize=service_rule, doc="Service time s_i")

    model.scheduled = pyo.Param(model.C_h, initialize=lambda m, i: data['earliest_start'][i],
                                doc="Scheduled start h_i")
    model.earliest = pyo.Param(model.C_w, initialize=lambda m, i: data['earliest_start'][i], doc="Earliest start e_i")
    model.latest = pyo.Param(model.C_w, initialize=lambda m, i: latest_start[i], doc="Latest start l_i")
    model.tolerance = pyo.Param(initialize=DELAY_TOLERANCE, doc="Tolerance tol")

    model.shift_start = pyo.Param(model.R, initialize=lambda m, r: routes[r - 1][4], doc="Shift start E_tk")
    model.shift_end = pyo.Param(model.R, initialize=lambda m, r: routes[r - 1][5], doc="Shift end L_tk")

    def eligibility_rule(model_instance, i, r):
        assigned = data['assigned_broker'][i]
        return 1 if assigned in (0, routes[r - 1][0]) else 0

    model.eligibility = pyo.Param(model.C, model.R, initialize=eligibility_rule, doc="Compatibility P_itk")

    horizon = (max([pyo.value(model.shift_end[r]) for r in model.R]
                   + [data['earliest_start'][i] + DELAY_TOLERANCE + data['service_times'][i] for i in model.C_h]
                   + [latest_start[i] + data['service_times'][i] for i in model.C_w])
               + max((pyo.value(model.travel_time[arc]) for arc in model.ARCS), default=0.0))

    # 2.1 Time-Window Preprocessing (Domain Reduction)
    win_a, win_b = _preprocess_time_windows(model, data)
    model.window_start = pyo.Param(model.V, initialize=win_a, doc="Tightened earliest start a_i")
    model.window_end = pyo.Param(model.V, initialize=win_b, doc="Tightened latest start b_i")

    # 2.2 Arc-Specific Tightened M^r_{ij} = max(0, b_i + s_i + t^r_{ij} - a_j)
    def arc_big_m_rule(model_instance, i, j, r):
        span = (pyo.value(model_instance.window_end[i])
                + pyo.value(model_instance.service[i])
                + pyo.value(model_instance.travel_time[i, j, r])
                - pyo.value(model_instance.window_start[j]))
        return max(0.0, span)

    model.arc_big_m = pyo.Param(model.ARCS, initialize=arc_big_m_rule, doc="Arc-specific M^r_{ij}")

    # 2.3 Shift-Specific Span Tightened M^r_{span} = max(0, b_{f_r} - a_{d_r})
    def span_big_m_rule(model_instance, r):
        d, f = model_instance.depot[r], model_instance.end[r]
        return max(0.0, pyo.value(model_instance.window_end[f]) - pyo.value(model_instance.window_start[d]))

    model.span_big_m = pyo.Param(model.R, initialize=span_big_m_rule, doc="Shift-specific M^r_{span}")

    max_shifts = max((len(broker_shifts) for broker_shifts in data['shifts']), default=1)
    max_minutes = num_properties * DELAY_TOLERANCE + horizon * max_shifts
    minute_weight = tie_break_minute_weight(max_minutes)
    model.fuel_cost = pyo.Param(initialize=data.get('fuel_cost', FUEL_REAIS_PER_MAP_UNIT), doc="Reais per map unit")
    model.delay_weight = pyo.Param(initialize=data.get('delay_weight', minute_weight), doc="W_atraso")
    model.fairness_weight = pyo.Param(initialize=data.get('fairness_weight', minute_weight), doc="W_fair")

    # =========================================================================
    # 3. DECISION VARIABLES
    # =========================================================================
    model.x = pyo.Var(model.ARCS, domain=pyo.Binary, doc="Edge traversal by shift")

    def w_bounds_rule(model_instance, i):
        return pyo.value(model_instance.window_start[i]), pyo.value(model_instance.window_end[i])

    model.w = pyo.Var(model.V, domain=pyo.NonNegativeReals, bounds=w_bounds_rule, doc="Start time")

    model.delay = pyo.Var(model.C, domain=pyo.NonNegativeReals, doc="Delay atraso_i")
    for i in model.C_w:
        model.delay[i].fix(0)

    model.shift_span = pyo.Var(model.R, domain=pyo.NonNegativeReals, doc="Shift span sigma_tk")
    model.workload = pyo.Var(model.K, domain=pyo.NonNegativeReals, doc="Workload omega_k")
    model.max_workload = pyo.Var(domain=pyo.NonNegativeReals, doc="Longest workload Omega")

    # =========================================================================
    # 4. OBJECTIVE FUNCTION
    # =========================================================================
    def objective_rule(model_instance):
        """Minimize the fuel paid on the driven arcs, then delay and the longest workload as tie-breaks."""
        return (model_instance.fuel_cost * sum(model_instance.distance[arc] * model_instance.x[arc]
                                               for arc in model_instance.ARCS)
                + model_instance.delay_weight * sum(model_instance.delay[i] for i in model_instance.C_h)
                + model_instance.fairness_weight * model_instance.max_workload)

    model.obj = pyo.Objective(rule=objective_rule, sense=pyo.minimize,
                              doc="Minimize the fuel the brokers pay")

    # =========================================================================
    # 5. CONSTRAINTS
    # =========================================================================
    def arcs_from(model_instance, i, r):
        return [model_instance.x[i, j, r] for j in model_instance.V if (i, j, r) in model_instance.ARCS]

    def arcs_into(model_instance, j, r):
        return [model_instance.x[i, j, r] for i in model_instance.V if (i, j, r) in model_instance.ARCS]

    # 5.1 Single Service & Compatibility
    def single_service_rule(model_instance, i):
        return sum(sum(arcs_from(model_instance, i, r)) for r in model_instance.R) == 1

    def compatibility_rule(model_instance, i, r):
        return sum(arcs_from(model_instance, i, r)) <= model_instance.eligibility[i, r]

    model.single_service_constraint = pyo.Constraint(model.C, rule=single_service_rule, doc="Constraint 5.1")
    model.compatibility_constraint = pyo.Constraint(model.C, model.R, rule=compatibility_rule,
                                                    doc="Constraint 5.1 compatibility")

    # 5.2 Directed Open Routes
    def origin_departure_rule(model_instance, r):
        return sum(arcs_from(model_instance, model_instance.depot[r], r)) <= 1

    def end_arrival_rule(model_instance, r):
        return (sum(arcs_into(model_instance, model_instance.end[r], r))
                == sum(arcs_from(model_instance, model_instance.depot[r], r)))

    def flow_conservation_rule(model_instance, h, r):
        return sum(arcs_into(model_instance, h, r)) - sum(arcs_from(model_instance, h, r)) == 0

    model.origin_departure_constraint = pyo.Constraint(model.R, rule=origin_departure_rule, doc="Constraint 5.2 origin")
    model.end_arrival_constraint = pyo.Constraint(model.R, rule=end_arrival_rule, doc="Constraint 5.2 end")
    model.flow_conservation_constraint = pyo.Constraint(model.C, model.R, rule=flow_conservation_rule,
                                                        doc="Constraint 5.2 flow")

    forbid_blocked_arcs(model, data)
    _fix_time_infeasible_arcs(model)

    # 5.3 Tightened Arc-Specific and Shift-Lifted Time Flow
    # Formula: w_i - w_j + M^r_{ij} * x_{ijr} <= b_i - a_j
    def time_flow_rule(model_instance, i, j, r):
        if i in model_instance.C and j in model_instance.C:
            return pyo.Constraint.Skip
        if model_instance.x[i, j, r].fixed and pyo.value(model_instance.x[i, j, r]) == 0:
            return pyo.Constraint.Skip
        if pyo.value(model_instance.arc_big_m[i, j, r]) <= 0.0:
            return pyo.Constraint.Skip
        return (model_instance.w[i] - model_instance.w[j]
                + model_instance.arc_big_m[i, j, r] * model_instance.x[i, j, r]
                <= model_instance.window_end[i] - model_instance.window_start[j])

    # For property pairs (i, j) in C x C, at most one shift traverses (i, j), so summing
    # M^r_{ij} * x_{ijr} across all r in R into one inequality replaces |R| rows with 1 tighter row.
    def pair_time_flow_rule(model_instance, i, j):
        active_r = [r for r in model_instance.R
                    if not (model_instance.x[i, j, r].fixed and pyo.value(model_instance.x[i, j, r]) == 0)
                    and pyo.value(model_instance.arc_big_m[i, j, r]) > 0.0]
        if not active_r:
            return pyo.Constraint.Skip
        return (model_instance.w[i] - model_instance.w[j]
                + sum(model_instance.arc_big_m[i, j, r] * model_instance.x[i, j, r] for r in active_r)
                <= model_instance.window_end[i] - model_instance.window_start[j])

    # Bidirectional 2-cycle elimination coupling (i, j) and (j, i) across all shifts
    def two_cycle_rule(model_instance, i, j):
        terms = [model_instance.x[u, v, r]
                 for (u, v) in ((i, j), (j, i))
                 for r in model_instance.R
                 if not (model_instance.x[u, v, r].fixed and pyo.value(model_instance.x[u, v, r]) == 0)]
        if len(terms) <= 1:
            return pyo.Constraint.Skip
        return sum(terms) <= 1

    model.time_flow_constraint = pyo.Constraint(model.ARCS, rule=time_flow_rule, doc="Constraint 5.3")
    model.pair_time_flow_constraint = pyo.Constraint(model.PAIRS, rule=pair_time_flow_rule,
                                                     doc="Constraint 5.3 lifted pair")
    model.two_cycle_constraint = pyo.Constraint(model.UPPER_PAIRS, rule=two_cycle_rule,
                                                doc="Constraint 5.3 two-cycle")

    # 5.3b Desrochers and Laporte (1991) Lifted Time-Window Bounds
    def lifted_early_rule(model_instance, i):
        a_i = pyo.value(model_instance.window_start[i])
        terms = []
        for r in model_instance.R:
            for j in model_instance.V:
                if (j, i, r) in model_instance.ARCS:
                    if model_instance.x[j, i, r].fixed and pyo.value(model_instance.x[j, i, r]) == 0:
                        continue
                    coeff = max(0.0, (pyo.value(model_instance.window_start[j])
                                      + pyo.value(model_instance.service[j])
                                      + pyo.value(model_instance.travel_time[j, i, r]) - a_i))
                    if coeff > 0.0:
                        terms.append(coeff * model_instance.x[j, i, r])
        if not terms:
            return pyo.Constraint.Skip
        return model_instance.w[i] >= a_i + sum(terms)

    def lifted_late_rule(model_instance, i):
        b_i = pyo.value(model_instance.window_end[i])
        s_i = pyo.value(model_instance.service[i])
        terms = []
        for r in model_instance.R:
            l_r = pyo.value(model_instance.shift_end[r])
            for j in model_instance.V:
                if (i, j, r) in model_instance.ARCS:
                    if model_instance.x[i, j, r].fixed and pyo.value(model_instance.x[i, j, r]) == 0:
                        continue
                    if j in model_instance.C:
                        latest_at_j = min(pyo.value(model_instance.window_end[j]),
                                          l_r - pyo.value(model_instance.service[j]))
                        latest_dep = latest_at_j - s_i - pyo.value(model_instance.travel_time[i, j, r])
                    else:
                        latest_dep = l_r - s_i
                    coeff = max(0.0, b_i - latest_dep)
                    if coeff > 0.0:
                        terms.append(coeff * model_instance.x[i, j, r])
        if not terms:
            return pyo.Constraint.Skip
        return model_instance.w[i] <= b_i - sum(terms)

    model.lifted_early_constraint = pyo.Constraint(model.C, rule=lifted_early_rule,
                                                   doc="Constraint 5.3b lifted early")
    model.lifted_late_constraint = pyo.Constraint(model.C, rule=lifted_late_rule,
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
        return model_instance.earliest[i], model_instance.w[i], model_instance.latest[i]

    model.flexible_window_constraint = pyo.Constraint(model.C_w, rule=flexible_window_rule, doc="Constraint 5.4b")

    # 5.5 Hard Shift Limits (tightened shift-end without global Big-M + linear shift/fleet duration bounds)
    def shift_start_rule(model_instance, r):
        return model_instance.w[model_instance.depot[r]] >= model_instance.shift_start[r]

    # When property i is visited in shift r, w_i + s_i <= L_r; lifted across all shifts r in R:
    # w_i + sum_{r in R} max(0, b_i + s_i - L_r) * sum_{j: (i,j,r) in ARCS} x_{ijr} <= b_i
    def shift_end_rule(model_instance, i):
        b_i = pyo.value(model_instance.window_end[i])
        s_i = pyo.value(model_instance.service[i])
        terms = []
        for r in model_instance.R:
            coeff = max(0.0, b_i + s_i - pyo.value(model_instance.shift_end[r]))
            if coeff <= 0.0:
                continue
            active_out = [model_instance.x[i, j, r] for j in model_instance.V
                          if (i, j, r) in model_instance.ARCS
                          and not (model_instance.x[i, j, r].fixed and pyo.value(model_instance.x[i, j, r]) == 0)]
            if active_out:
                terms.append(coeff * sum(active_out))
        if not terms:
            return pyo.Constraint.Skip
        return model_instance.w[i] + sum(terms) <= b_i

    def shift_duration_rule(model_instance, r):
        return (sum(model_instance.service[i] * model_instance.x[i, j, r]
                    for (i, j, route) in model_instance.ARCS if route == r)
                + sum(model_instance.travel_time[i, j, r] * model_instance.x[i, j, r]
                      for (i, j, route) in model_instance.ARCS if route == r and j in model_instance.C)
                <= model_instance.shift_end[r] - model_instance.shift_start[r])

    def fleet_duration_rule(model_instance):
        return (sum(model_instance.service[i] for i in model_instance.C)
                + sum(model_instance.travel_time[i, j, r] * model_instance.x[i, j, r]
                      for (i, j, r) in model_instance.ARCS if j in model_instance.C)
                <= sum(model_instance.shift_end[r] - model_instance.shift_start[r] for r in model_instance.R))

    model.shift_start_constraint = pyo.Constraint(model.R, rule=shift_start_rule, doc="Constraint 5.5 start")
    model.shift_end_constraint = pyo.Constraint(model.C, rule=shift_end_rule, doc="Constraint 5.5 end")
    model.shift_duration_constraint = pyo.Constraint(model.R, rule=shift_duration_rule, doc="Constraint 5.5 duration")
    model.fleet_duration_constraint = pyo.Constraint(rule=fleet_duration_rule, doc="Constraint 5.5 fleet duration")

    # 5.6 Workload Fairness (tightened shift-specific M^r_{span} + linear active duration lower bound)
    shifts_of = {}
    for route in model.R:
        shifts_of.setdefault(pyo.value(model.route_broker[route]), []).append(route)

    def shift_span_rule(model_instance, r):
        departs = sum(arcs_from(model_instance, model_instance.depot[r], r))
        return (model_instance.shift_span[r] >= model_instance.w[model_instance.end[r]]
                - model_instance.w[model_instance.depot[r]] - model_instance.span_big_m[r] * (1 - departs))

    def shift_span_duration_rule(model_instance, r):
        return (model_instance.shift_span[r]
                >= sum((model_instance.service[i] + model_instance.travel_time[i, j, r]) * model_instance.x[i, j, r]
                       for (i, j, route) in model_instance.ARCS if route == r))

    def workload_rule(model_instance, k):
        shifts = shifts_of.get(k, [])
        if not shifts:
            return model_instance.workload[k] == 0
        return model_instance.workload[k] == sum(model_instance.shift_span[r] for r in shifts)

    def max_workload_rule(model_instance, k):
        if k not in shifts_of:
            return pyo.Constraint.Skip
        return model_instance.max_workload >= model_instance.workload[k]

    model.shift_span_constraint = pyo.Constraint(model.R, rule=shift_span_rule, doc="Constraint 5.6 span")
    model.shift_span_duration_constraint = pyo.Constraint(model.R, rule=shift_span_duration_rule,
                                                          doc="Constraint 5.6 linear span")
    model.workload_constraint = pyo.Constraint(model.K, rule=workload_rule, doc="Constraint 5.6 workload")
    model.max_workload_constraint = pyo.Constraint(model.K, rule=max_workload_rule, doc="Constraint 5.6 max")

    return model


def _preprocess_time_windows(model: pyo.ConcreteModel, data: dict) -> tuple[dict, dict]:
    """
    Tightens individual node time windows [a_i, b_i] by iterative forward and backward
    shift and network reachability propagation until convergence.
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

    for r in model.R:
        d = pyo.value(model.depot[r])
        f = pyo.value(model.end[r])
        e_r = float(pyo.value(model.shift_start[r]))
        l_r = float(pyo.value(model.shift_end[r]))
        win_a[d] = e_r
        win_b[d] = l_r
        win_a[f] = e_r
        max_end = max([e_r] + [min(win_b[i], l_r - float(pyo.value(model.service[i])))
                               + float(pyo.value(model.service[i]))
                               + float(pyo.value(model.travel_time[i, f, r]))
                               for i in model.C if pyo.value(model.eligibility[i, r]) == 1])
        win_b[f] = max(e_r, max_end)

    distances = data['distance_matrix']
    compatible_arcs = []
    for (i, j, r) in model.ARCS:
        if i in model.C and pyo.value(model.eligibility[i, r]) == 0:
            continue
        if j in model.C and pyo.value(model.eligibility[j, r]) == 0:
            continue
        if i in model.C and j in model.C and i != j and distances[i][j] == 0:
            continue
        step = float(pyo.value(model.service[i]) + pyo.value(model.travel_time[i, j, r]))
        compatible_arcs.append((i, j, r, step))

    changed = True
    while changed:
        changed = False
        active_in = {j: [] for j in model.C}
        active_out = {i: [] for i in model.C}
        for (i, j, r, step) in compatible_arcs:
            l_r = float(pyo.value(model.shift_end[r]))
            if i in model.C and win_a[i] + float(pyo.value(model.service[i])) > l_r + 1e-9:
                continue
            if j in model.C:
                s_j = float(pyo.value(model.service[j]))
                latest_j = min(win_b[j], l_r - s_j)
                if win_a[i] + step <= latest_j + 1e-9:
                    active_in[j].append((i, step))
                    if i in active_out:
                        active_out[i].append((latest_j - step))
            else:
                # j == f_r: the constraint at the end of shift r is w_i + s_i <= L_r
                s_i = float(pyo.value(model.service[i]))
                if win_a[i] + s_i <= l_r + 1e-9 and win_a[i] + step <= win_b[j] + 1e-9:
                    active_out[i].append(l_r - s_i)

        for j in model.C:
            if active_in[j]:
                earliest_arrival = min(win_a[i] + step for (i, step) in active_in[j])
                new_a = max(win_a[j], min(win_b[j], earliest_arrival))
                if new_a > win_a[j] + 1e-9:
                    win_a[j] = new_a
                    changed = True

        for i in model.C:
            if active_out[i]:
                latest_departure = max(active_out[i])
                new_b = min(win_b[i], max(win_a[i], latest_departure))
                if new_b < win_b[i] - 1e-9:
                    win_b[i] = new_b
                    changed = True

    for r in model.R:
        d = pyo.value(model.depot[r])
        f = pyo.value(model.end[r])
        e_r = float(pyo.value(model.shift_start[r]))
        l_r = float(pyo.value(model.shift_end[r]))
        fe_ends = [min(win_b[i], l_r - float(pyo.value(model.service[i])))
                   + float(pyo.value(model.service[i]))
                   + float(pyo.value(model.travel_time[i, f, r]))
                   for i in model.C
                   if pyo.value(model.eligibility[i, r]) == 1
                   and win_a[i] + float(pyo.value(model.service[i])) <= l_r + 1e-9]
        win_b[f] = max([e_r] + fe_ends)
        dep_starts = [min(win_b[j], l_r - float(pyo.value(model.service[j])))
                      - float(pyo.value(model.travel_time[d, j, r]))
                      for j in model.C
                      if pyo.value(model.eligibility[j, r]) == 1
                      and win_a[j] + float(pyo.value(model.service[j])) <= l_r + 1e-9]
        win_b[d] = min(l_r, max([e_r] + dep_starts))

    return win_a, win_b


def _fix_time_infeasible_arcs(model: pyo.ConcreteModel) -> None:
    """Fixes x_{ijr} = 0 on arcs that violate shift end limits or tightened node time windows."""
    for (i, j, r) in model.ARCS:
        if model.x[i, j, r].fixed:
            continue
        l_r = pyo.value(model.shift_end[r])
        if i in model.C and pyo.value(model.window_start[i]) + pyo.value(model.service[i]) > l_r + 1e-9:
            model.x[i, j, r].fix(0)
            continue
        earliest_arrival = (pyo.value(model.window_start[i])
                            + pyo.value(model.service[i])
                            + pyo.value(model.travel_time[i, j, r]))
        if earliest_arrival > pyo.value(model.window_end[j]) + 1e-9:
            model.x[i, j, r].fix(0)
            continue
        if j in model.C and max(earliest_arrival, pyo.value(model.window_start[j])) + pyo.value(model.service[j]) > l_r + 1e-9:
            model.x[i, j, r].fix(0)
