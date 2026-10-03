"""
Module: model_7
Description: Mathematical formulation of Model 7 (M7) for the WSRP.
             Implemented as a Multi-Objective Dynamic Open Multi-Depot Vehicle Routing
             Problem with Soft Time Windows and Site-Dependency (MO-DOMDVRPTW-SD), focused
             on the agency: every broker leaves his own home, takes a lunch break and ends
             the day at his last visit. The number of brokers is minimized first, then the
             distance, the delays and the overtime.
             Models the initial optimization of the day; re-running it when the visits
             change, from the brokers' current positions, is up to the caller.
"""

import pyomo.environ as pyo

# Rules of Case 8.a, in minutes from the start of the day (08:00)
DELAY_TOLERANCE = 10            # tol: Max minutes a visit starts early or late
LUNCH_DURATION = 60             # s_ak: Length of the lunch break
LUNCH_WINDOW = (180, 360)       # The lunch starts between 11:00 and 14:00

# Default weights of the multi-objective function
DISTANCE_WEIGHT = 1.0           # W_dist: Standard weight of the distance
DELAY_WEIGHT = 10.0             # W_atraso: Penalty per minute of delay
OVERTIME_WEIGHT = 100.0         # W_extra: Much higher penalty per minute of overtime


def build_model_m7(data: dict) -> pyo.ConcreteModel:
    """
    Constructs the MILP polyhedron for the M7 routing problem (MO-DOMDVRPTW-SD).

    Args:
        data (dict): A dictionary containing instance parameters:
            - 'num_nodes' (int): Number of nodes of the generator. Nodes 1..n are the properties;
              node 0, the agency, isn't used, as every broker leaves his own home.
            - 'num_brokers' (int): Number of brokers |K|.
            - 'distance_matrix' (list of lists): 2D array of distances c_ij between properties.
            - 'travel_times' (list): 2D array of travel times t_ij between properties, in its
              first (and only) period.
            - 'home_distances' (list): Distance from the home of each broker to each node.
            - 'home_travel_times' (list): Travel time from the home of each broker to each node,
              in its first (and only) period.
            - 'service_times' (list): Duration s_i of the visit at every property.
            - 'earliest_start' (list): Scheduled start h_i of the visit at every property.
            - 'assigned_broker' (list): Broker already assigned to each property, 0 if none.
            - 'shift_start' / 'shift_end' (list): Start E_k and regular end L_k of each broker's day.
            - 'fleet_weight', 'distance_weight', 'delay_weight', 'overtime_weight' (float, optional):
              Weights of the objective. The fleet weight is computed if absent.

    Returns:
        pyo.ConcreteModel: The unoptimized abstract mathematical model.
    """
    model = pyo.ConcreteModel(name="WSRP_M7_MO_DOMDVRPTW_SD")

    num_properties = data['num_nodes'] - 1
    num_brokers = data['num_brokers']

    # =========================================================================
    # 1. SETS (Indices)
    # =========================================================================
    # K = {1, ..., k}: Set of brokers available
    model.K = pyo.Set(initialize=range(1, num_brokers + 1), doc="Brokers")

    # C = {1, ..., n}: Set of properties to be visited
    model.C = pyo.Set(initialize=range(1, num_properties + 1), doc="Properties")

    # D, F, A: Home (d_k), virtual end of the day (f_k) and virtual lunch (a_k) of each broker
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

    # V = C U D U F U A: Set of all nodes
    model.V = model.C | model.D | model.F | model.A

    # Arcs each broker may take: from his home to a property or to lunch, from a property
    # to another property, to lunch or to the end of the day, and from lunch to a property
    # or to the end of the day
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

    # =========================================================================
    # 2. PARAMETERS (Data)
    # =========================================================================
    # c_ij / t_ij: Distance and travel time of each arc. The end of the day and the lunch
    # are virtual nodes, so the trips to and from them have no distance and no time
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

    # s_i: Duration of the visit at node i; the lunch lasts s_ak = 60 minutes
    def service_rule(model_instance, i):
        if i in model_instance.C:
            return data['service_times'][i]
        return LUNCH_DURATION if i in model_instance.A else 0.0

    model.service = pyo.Param(model.V, initialize=service_rule, doc="Service time s_i")

    # h_i: Scheduled start of the visit at property i
    def scheduled_rule(model_instance, i):
        return data['earliest_start'][i]

    model.scheduled = pyo.Param(model.C, initialize=scheduled_rule, doc="Scheduled start h_i")

    # tol: Max minutes a visit starts before or after its scheduled time
    model.tolerance = pyo.Param(initialize=DELAY_TOLERANCE, doc="Tolerance tol")

    # E_k / L_k: Start and regular end of each broker's working day
    def shift_start_rule(model_instance, k):
        return data['shift_start'][k - 1]

    def shift_end_rule(model_instance, k):
        return data['shift_end'][k - 1]

    model.shift_start = pyo.Param(model.K, initialize=shift_start_rule, doc="Day start E_k")
    model.shift_end = pyo.Param(model.K, initialize=shift_end_rule, doc="Day end L_k")

    # P_ik: Compatibility matrix. A visit with another broker already assigned has P_ik = 0
    def eligibility_rule(model_instance, i, k):
        assigned = data['assigned_broker'][i]
        return 1 if assigned in (0, k) else 0

    model.eligibility = pyo.Param(model.C, model.K, initialize=eligibility_rule, doc="Compatibility P_ik")

    # H: No start time of an optimal schedule goes past the end of the latest visit or lunch
    horizon = max(max(data['earliest_start'][i] + DELAY_TOLERANCE + data['service_times'][i] for i in model.C),
                  LUNCH_WINDOW[1] + LUNCH_DURATION, max(data['shift_start']))

    # M: Big-M constant that deactivates the time-flow constraint when x_ijk = 0
    big_m = data.get('big_m', horizon + max(pyo.value(model.service[i]) for i in model.V)
                     + max(pyo.value(model.travel_time[arc]) for arc in model.ARCS))
    model.big_m = pyo.Param(initialize=big_m, doc="Big-M constant")

    # W_dist, W_atraso, W_extra: Weights of the routes, the delays and the overtime
    model.distance_weight = pyo.Param(initialize=data.get('distance_weight', DISTANCE_WEIGHT), doc="W_dist")
    model.delay_weight = pyo.Param(initialize=data.get('delay_weight', DELAY_WEIGHT), doc="W_atraso")
    model.overtime_weight = pyo.Param(initialize=data.get('overtime_weight', OVERTIME_WEIGHT), doc="W_extra")

    # W_frota: Larger than the routes, delays and overtime of any plan put together, so one
    # broker fewer always comes first. A plan has at most one paid trip per property and home
    max_routes = ((num_properties + num_brokers) * max(pyo.value(model.distance[arc]) for arc in model.ARCS)
                  * pyo.value(model.distance_weight)
                  + num_properties * DELAY_TOLERANCE * pyo.value(model.delay_weight)
                  + sum(max(0, horizon - pyo.value(model.shift_end[k])) for k in model.K)
                  * pyo.value(model.overtime_weight))
    model.fleet_weight = pyo.Param(initialize=data.get('fleet_weight', max_routes + 1), doc="W_frota")

    # =========================================================================
    # 3. DECISION VARIABLES
    # =========================================================================
    # x_{ijk} = 1 if broker k travels directly from node i to node j, else 0
    model.x = pyo.Var(model.ARCS, domain=pyo.Binary, doc="Edge traversal by broker")

    # y_k = 1 if broker k works in the day, else 0
    model.y = pyo.Var(model.K, domain=pyo.Binary, doc="Broker works")

    # w_i >= 0: Start time of the service (or of the trip) at node i
    model.w = pyo.Var(model.V, domain=pyo.NonNegativeReals, bounds=(0, horizon), doc="Start time")

    # atraso_i >= 0: Minutes of delay of the visit at property i
    model.delay = pyo.Var(model.C, domain=pyo.NonNegativeReals, doc="Delay atraso_i")

    # he_k >= 0: Minutes of overtime of broker k
    model.overtime = pyo.Var(model.K, domain=pyo.NonNegativeReals, doc="Overtime he_k")

    # =========================================================================
    # 4. OBJECTIVE FUNCTION
    # =========================================================================
    def objective_rule(model_instance):
        """Minimize W_frota * sum(y_k) + W_dist * sum(c_ij * x_ijk) + W_atraso * sum(atraso_i) + W_extra * sum(he_k)."""
        return (model_instance.fleet_weight * sum(model_instance.y[k] for k in model_instance.K)
                + model_instance.distance_weight * sum(model_instance.distance[arc] * model_instance.x[arc]
                                                       for arc in model_instance.ARCS)
                + model_instance.delay_weight * sum(model_instance.delay[i] for i in model_instance.C)
                + model_instance.overtime_weight * sum(model_instance.overtime[k] for k in model_instance.K))

    model.obj = pyo.Objective(rule=objective_rule, sense=pyo.minimize,
                              doc="Minimize brokers first, then distance, delays and overtime")

    # =========================================================================
    # 5. CONSTRAINTS
    # =========================================================================
    def arcs_from(model_instance, i, k):
        return [model_instance.x[i, j, k] for j in model_instance.V if (i, j, k) in model_instance.ARCS]

    def arcs_into(model_instance, j, k):
        return [model_instance.x[i, j, k] for i in model_instance.V if (i, j, k) in model_instance.ARCS]

    # 5.1 Single Service: every property is left exactly once, by exactly one broker,
    # who must be allowed to visit it
    def single_service_rule(model_instance, i):
        return sum(sum(arcs_from(model_instance, i, k)) for k in model_instance.K) == 1

    def compatibility_rule(model_instance, i, k):
        return sum(arcs_from(model_instance, i, k)) <= model_instance.eligibility[i, k]

    model.single_service_constraint = pyo.Constraint(model.C, rule=single_service_rule, doc="Constraint 5.1")
    model.compatibility_constraint = pyo.Constraint(model.C, model.K, rule=compatibility_rule,
                                                    doc="Constraint 5.1 compatibility")

    # 5.2 Flow Conservation and Open Routes: a broker who works leaves his home once, ends
    # the day once at his virtual end node, and leaves every node he enters
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

    # 5.3 Time Flow: the next node starts only after start + service + travel
    # Formula: w_i + s_i + t_ij - M * (1 - x_ijk) <= w_j
    def time_flow_rule(model_instance, i, j, k):
        return (model_instance.w[i] + model_instance.service[i] + model_instance.travel_time[i, j, k]
                - model_instance.big_m * (1 - model_instance.x[i, j, k]) <= model_instance.w[j])

    model.time_flow_constraint = pyo.Constraint(model.ARCS, rule=time_flow_rule, doc="Constraint 5.3")

    # 5.4 Soft Time Windows: a visit starts at its scheduled time, at most tol minutes
    # early or late, and the minutes late are its delay
    # Formula: w_i >= h_i - tol, w_i <= h_i + atraso_i, atraso_i <= tol
    def early_start_rule(model_instance, i):
        return model_instance.w[i] >= model_instance.scheduled[i] - model_instance.tolerance

    def soft_window_rule(model_instance, i):
        return model_instance.w[i] <= model_instance.scheduled[i] + model_instance.delay[i]

    def delay_tolerance_rule(model_instance, i):
        return model_instance.delay[i] <= model_instance.tolerance

    model.early_start_constraint = pyo.Constraint(model.C, rule=early_start_rule, doc="Constraint 5.4 early")
    model.soft_window_constraint = pyo.Constraint(model.C, rule=soft_window_rule, doc="Constraint 5.4")
    model.delay_tolerance_constraint = pyo.Constraint(model.C, rule=delay_tolerance_rule, doc="Constraint 5.4 tol")

    # 5.5 Working Day: a broker doesn't leave home before his day starts, and the end of
    # his day past its regular end is overtime
    # Formula: w_dk >= E_k, w_fk <= L_k + he_k
    def day_start_rule(model_instance, k):
        return model_instance.w[model_instance.depot[k]] >= model_instance.shift_start[k]

    def day_end_rule(model_instance, k):
        return model_instance.w[model_instance.end[k]] <= model_instance.shift_end[k] + model_instance.overtime[k]

    model.day_start_constraint = pyo.Constraint(model.K, rule=day_start_rule, doc="Constraint 5.5 start")
    model.day_end_constraint = pyo.Constraint(model.K, rule=day_end_rule, doc="Constraint 5.5 end")

    # 5.6 Lunch Break: a broker who works goes through his lunch node, starting it
    # between 11:00 and 14:00
    def lunch_visit_rule(model_instance, k):
        return sum(arcs_into(model_instance, model_instance.lunch[k], k)) == model_instance.y[k]

    def lunch_window_rule(model_instance, k):
        return LUNCH_WINDOW[0], model_instance.w[model_instance.lunch[k]], LUNCH_WINDOW[1]

    model.lunch_visit_constraint = pyo.Constraint(model.K, rule=lunch_visit_rule, doc="Constraint 5.6")
    model.lunch_window_constraint = pyo.Constraint(model.K, rule=lunch_window_rule, doc="Constraint 5.6 window")

    return model
