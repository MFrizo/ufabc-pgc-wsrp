"""
Module: model_8
Description: Mathematical formulation of Model 8 (M8) for the WSRP.
             Implemented as a Human-Centric Dynamic Open Multi-Depot Vehicle Routing Problem
             with Soft Time Windows and Site-Dependency (HC-DOMDVRPTW-SD), focused on the
             brokers: each broker works his own morning shift, from home to the place he
             picks for lunch, and afternoon shift, from there back home, and no visit goes
             past the end of a shift. A weighted sum of the distance, which includes the trip
             from the last visit of each shift to its destination, and of the delays is minimized.
             Models the initial optimization of the day; re-running it when the visits
             change, from the brokers' current positions, is up to the caller.
"""

import pyomo.environ as pyo

# Rules of Case 8.b, in minutes
DELAY_TOLERANCE = 10            # tol: Max delay of a visit

# Default weights of the multi-objective function
DISTANCE_WEIGHT = 1.0           # W_dist: Standard weight of the distance
DELAY_WEIGHT = 10.0             # W_atraso: Penalty per minute of delay


def build_model_m8(data: dict) -> pyo.ConcreteModel:
    """
    Constructs the MILP polyhedron for the M8 routing problem (HC-DOMDVRPTW-SD).

    Args:
        data (dict): A dictionary containing instance parameters:
            - 'num_nodes' (int): Number of nodes of the generator. Nodes 1..n are the properties;
              node 0, the agency, isn't used, as every shift leaves the broker's own origin.
            - 'num_brokers' (int): Number of brokers |K|.
            - 'shifts' (list): (start E_tk, end L_tk) of the morning and afternoon shift of each
              broker, or no shift for the brokers off.
            - 'distance_matrix' (list of lists): 2D array of distances c_ij between properties.
            - 'travel_times' (list): 2D array of travel times t_ij between properties, in its
              first (and only) period.
            - 'home_distances' / 'lunch_spot_distances' (list): Distance from the home and from
              the lunch spot of each broker to each node.
            - 'home_travel_times' / 'lunch_spot_travel_times' (list): Travel time from the home and
              from the lunch spot of each broker to each node, in its first (and only) period.
            - 'service_times' (list): Duration s_i of the visit at every property.
            - 'earliest_start' (list): Scheduled start h_i of the visit at every property.
            - 'assigned_broker' (list): Broker already assigned to each property, 0 if none.
            - 'distance_weight', 'delay_weight' (float, optional): Weights of the objective.

    Returns:
        pyo.ConcreteModel: The unoptimized abstract mathematical model.
    """
    model = pyo.ConcreteModel(name="WSRP_M8_HC_DOMDVRPTW_SD")

    num_properties = data['num_nodes'] - 1

    # Each shift t_k of a broker who works is a route: the morning (A) goes from his home
    # to his lunch spot, the afternoon (B) from his lunch spot back home
    routes = [(k, label, origin, destination, start, end)
              for k, broker_shifts in enumerate(data['shifts'], start=1)
              for (start, end), label, origin, destination in zip(broker_shifts, ('A', 'B'),
                                                                   ('home', 'lunch_spot'), ('lunch_spot', 'home'))]
    num_routes = len(routes)

    # =========================================================================
    # 1. SETS (Indices)
    # =========================================================================
    # K = {1, ..., k}: Set of brokers available
    model.K = pyo.Set(initialize=range(1, data['num_brokers'] + 1), doc="Brokers")

    # R: Set of the shifts t_k of all brokers, one route each
    model.R = pyo.Set(initialize=range(1, num_routes + 1), doc="Shifts t_k")

    # C = {1, ..., n}: Set of properties to be visited
    model.C = pyo.Set(initialize=range(1, num_properties + 1), doc="Properties")

    # D, F: Origin (d_tk) and virtual end (f_tk) of each shift
    def depot_rule(model_instance, r):
        return num_properties + r

    def end_rule(model_instance, r):
        return num_properties + num_routes + r

    model.depot = pyo.Param(model.R, initialize=depot_rule, doc="Origin d_tk")
    model.end = pyo.Param(model.R, initialize=end_rule, doc="End of the shift f_tk")

    model.D = pyo.Set(initialize=[depot_rule(model, r) for r in model.R], doc="Origins")
    model.F = pyo.Set(initialize=[end_rule(model, r) for r in model.R], doc="Ends of the shifts")

    # V = C U D U F: Set of all nodes
    model.V = model.C | model.D | model.F

    # Broker and name (e.g. 1A) of each shift
    model.route_broker = pyo.Param(model.R, initialize=lambda m, r: routes[r - 1][0], doc="Broker of the shift")
    model.route_name = pyo.Param(model.R, initialize=lambda m, r: f"{routes[r - 1][0]}{routes[r - 1][1]}",
                                 within=pyo.Any, doc="Name of the shift")

    # Arcs each shift may take: from its origin to a property, from a property to another
    # one, and from a property to the end of the shift
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

    # =========================================================================
    # 2. PARAMETERS (Data)
    # =========================================================================
    # c_ij / t_ij: Distance and travel time of each arc. The trip to the end of a shift is
    # the trip to its destination: c_i,ftk = c_i,dest_tk
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

    # s_i: Duration of the visit at node i
    def service_rule(model_instance, i):
        return data['service_times'][i] if i in model_instance.C else 0.0

    model.service = pyo.Param(model.V, initialize=service_rule, doc="Service time s_i")

    # h_i: Scheduled start of the visit at property i
    def scheduled_rule(model_instance, i):
        return data['earliest_start'][i]

    model.scheduled = pyo.Param(model.C, initialize=scheduled_rule, doc="Scheduled start h_i")

    # tol: Max delay of a visit
    model.tolerance = pyo.Param(initialize=DELAY_TOLERANCE, doc="Delay tolerance tol")

    # E_tk / L_tk: Start and hard end of each shift
    model.shift_start = pyo.Param(model.R, initialize=lambda m, r: routes[r - 1][4], doc="Shift start E_tk")
    model.shift_end = pyo.Param(model.R, initialize=lambda m, r: routes[r - 1][5], doc="Shift end L_tk")

    # P_itk: Compatibility matrix. A visit with another broker already assigned has P_itk = 0
    def eligibility_rule(model_instance, i, r):
        assigned = data['assigned_broker'][i]
        return 1 if assigned in (0, routes[r - 1][0]) else 0

    model.eligibility = pyo.Param(model.C, model.R, initialize=eligibility_rule, doc="Compatibility P_itk")

    # H: No start time of an optimal schedule goes past the arrival at the latest destination
    horizon = (max(max(pyo.value(model.shift_end[r]) for r in model.R),
                   max(data['earliest_start'][i] + DELAY_TOLERANCE + data['service_times'][i] for i in model.C))
               + max(pyo.value(model.travel_time[arc]) for arc in model.ARCS))

    # M: Big-M constant that deactivates the time-flow and shift-end constraints when x = 0
    big_m = data.get('big_m', horizon + max(pyo.value(model.service[i]) for i in model.V)
                     + max(pyo.value(model.travel_time[arc]) for arc in model.ARCS))
    model.big_m = pyo.Param(initialize=big_m, doc="Big-M constant")

    # W_dist, W_atraso: Weights of the distance and of the delays
    model.distance_weight = pyo.Param(initialize=data.get('distance_weight', DISTANCE_WEIGHT), doc="W_dist")
    model.delay_weight = pyo.Param(initialize=data.get('delay_weight', DELAY_WEIGHT), doc="W_atraso")

    # =========================================================================
    # 3. DECISION VARIABLES
    # =========================================================================
    # x_{ijtk} = 1 if, in shift t_k, the broker travels directly from node i to node j, else 0
    model.x = pyo.Var(model.ARCS, domain=pyo.Binary, doc="Edge traversal by shift")

    # w_i >= 0: Start time of the service (or of the trip) at node i
    model.w = pyo.Var(model.V, domain=pyo.NonNegativeReals, bounds=(0, horizon), doc="Start time")

    # atraso_i >= 0: Minutes of delay of the visit at property i
    model.delay = pyo.Var(model.C, domain=pyo.NonNegativeReals, doc="Delay atraso_i")

    # =========================================================================
    # 4. OBJECTIVE FUNCTION
    # =========================================================================
    def objective_rule(model_instance):
        """Minimize W_dist * sum(c_ij * x_ijtk) + W_atraso * sum(atraso_i)."""
        return (model_instance.distance_weight * sum(model_instance.distance[arc] * model_instance.x[arc]
                                                     for arc in model_instance.ARCS)
                + model_instance.delay_weight * sum(model_instance.delay[i] for i in model_instance.C))

    model.obj = pyo.Objective(rule=objective_rule, sense=pyo.minimize, doc="Minimize weighted distance and delays")

    # =========================================================================
    # 5. CONSTRAINTS
    # =========================================================================
    def arcs_from(model_instance, i, r):
        return [model_instance.x[i, j, r] for j in model_instance.V if (i, j, r) in model_instance.ARCS]

    def arcs_into(model_instance, j, r):
        return [model_instance.x[i, j, r] for i in model_instance.V if (i, j, r) in model_instance.ARCS]

    # 5.1 Single Service: every property is left exactly once, in exactly one shift of one
    # broker, who must be allowed to visit it
    def single_service_rule(model_instance, i):
        return sum(sum(arcs_from(model_instance, i, r)) for r in model_instance.R) == 1

    def compatibility_rule(model_instance, i, r):
        return sum(arcs_from(model_instance, i, r)) <= model_instance.eligibility[i, r]

    model.single_service_constraint = pyo.Constraint(model.C, rule=single_service_rule, doc="Constraint 5.1")
    model.compatibility_constraint = pyo.Constraint(model.C, model.R, rule=compatibility_rule,
                                                    doc="Constraint 5.1 compatibility")

    # 5.2 Directed Open Routes: each shift leaves its origin at most once, ends at its virtual
    # end node if it leaves, and leaves every property it enters
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

    # 5.3 Time Flow: the next node starts only after start + service + travel
    # Formula: w_i + s_i + t_ij - M * (1 - x_ijtk) <= w_j
    def time_flow_rule(model_instance, i, j, r):
        return (model_instance.w[i] + model_instance.service[i] + model_instance.travel_time[i, j, r]
                - model_instance.big_m * (1 - model_instance.x[i, j, r]) <= model_instance.w[j])

    model.time_flow_constraint = pyo.Constraint(model.ARCS, rule=time_flow_rule, doc="Constraint 5.3")

    # 5.4 Soft Time Windows: a visit starts by its scheduled time plus its delay, which
    # never goes past the tolerance
    # Formula: w_i <= h_i + atraso_i, atraso_i <= tol
    def soft_window_rule(model_instance, i):
        return model_instance.w[i] <= model_instance.scheduled[i] + model_instance.delay[i]

    def delay_tolerance_rule(model_instance, i):
        return model_instance.delay[i] <= model_instance.tolerance

    model.soft_window_constraint = pyo.Constraint(model.C, rule=soft_window_rule, doc="Constraint 5.4")
    model.delay_tolerance_constraint = pyo.Constraint(model.C, rule=delay_tolerance_rule, doc="Constraint 5.4 tol")

    # 5.5 Hard Shift Limits: a shift starts when the broker leaves its origin, not before its
    # start, and its last visit ends by the end of the shift
    # Formula: w_dtk >= E_tk, w_i + s_i - M * (1 - x_i,ftk,tk) <= L_tk
    def shift_start_rule(model_instance, r):
        return model_instance.w[model_instance.depot[r]] >= model_instance.shift_start[r]

    def shift_end_rule(model_instance, i, r):
        return (model_instance.w[i] + model_instance.service[i]
                - model_instance.big_m * (1 - model_instance.x[i, model_instance.end[r], r])
                <= model_instance.shift_end[r])

    model.shift_start_constraint = pyo.Constraint(model.R, rule=shift_start_rule, doc="Constraint 5.5 start")
    model.shift_end_constraint = pyo.Constraint(model.C, model.R, rule=shift_end_rule, doc="Constraint 5.5 end")

    return model
