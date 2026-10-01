"""
Module: model_5
Description: Mathematical formulation of Model 5 (M5) for the WSRP.
             Implemented as a Time-Dependent Vehicle Routing Problem with Time Windows
             (TDVRPTW): the VRPTWWVST of M4, where the travel time of a trip depends on
             the period of the day it leaves in, and the brokers' total time out of the
             base is minimized instead of the distance.
"""

import pyomo.environ as pyo


def latest_departure(data: dict, i: int) -> float:
    """
    Latest time a broker can leave node i: the end of its latest visit, or the end of
    the base's window for the base.

    Args:
        data (dict): Instance payload (see build_model_m5).
        i (int): Node index.

    Returns:
        float: The latest departure time from node i.
    """
    return data['latest_start'][i] + data['service_times'][i]


def compute_big_m(data: dict) -> float:
    """
    Computes the smallest single Big-M value that keeps the time-flow
    constraints (4.5) inactive whenever x_ijk = 0 or the period isn't chosen.

    For any feasible schedule, a trip from i to j leaving in period p gives
    departure_i + t_ij^p - start_j <= latest_departure_i + t_ij^p - e_j, where
    e_0 bounds the return to the base, so the maximum over all arcs and periods is
    a valid bound.

    Args:
        data (dict): Instance payload (see build_model_m5).

    Returns:
        float: The Big-M constant.
    """
    num_nodes = data['num_nodes']
    earliest = data['earliest_start']

    bound = max(latest_departure(data, i) + travel[i][j] - earliest[j]
                for travel in data['travel_times']
                for i in range(num_nodes) for j in range(num_nodes) if i != j)

    return max(bound, 0.0)


def build_model_m5(data: dict) -> pyo.ConcreteModel:
    """
    Constructs the MILP polyhedron for the M5 routing problem (TDVRPTW).

    Args:
        data (dict): A dictionary containing instance parameters:
            - 'num_nodes' (int): Total number of nodes |V|. Node 0 is the shared base.
            - 'num_brokers' (int): Number of brokers |K|.
            - 'distance_matrix' (list of lists): 2D array of travel distances (c_ij).
            - 'period_starts' (list): Start minute of each period of the day, the first at 0.
            - 'travel_times' (list): For each period, the 2D array of travel times t_ij of a
              trip leaving in it.
            - 'service_times' (list): Duration s_i of the visit at every node, s_0 = 0.
            - 'earliest_start' (list): Earliest start time e_i for every node in V.
            - 'latest_start' (list): Latest start time l_i for every node in V.
            - 'assigned_broker' (list): Broker already assigned to each node, 0 if none.
            - 'big_m' (float, optional): Big-M constant. Computed by compute_big_m if absent.

    Returns:
        pyo.ConcreteModel: The unoptimized abstract mathematical model.
    """
    model = pyo.ConcreteModel(name="WSRP_M5_TDVRPTW")

    # =========================================================================
    # 1. SETS (Indices)
    # =========================================================================
    # V = {0, 1, ..., n}: Set of all vertices, where 0 is the shared base
    num_nodes = data['num_nodes']
    model.V = pyo.Set(initialize=range(num_nodes), doc="All nodes including the base")

    # C = V \ {0}: Set of customers/properties to be visited
    model.C = pyo.Set(initialize=range(1, num_nodes), doc="Property nodes only")

    # K = {1, ..., k}: Set of brokers
    model.K = pyo.Set(initialize=range(1, data['num_brokers'] + 1), doc="Brokers")

    # P = {0, 1, ..., p}: Set of periods of the day with their own travel times
    num_periods = len(data['period_starts'])
    model.P = pyo.Set(initialize=range(num_periods), doc="Periods of the day")

    # =========================================================================
    # 2. PARAMETERS (Data)
    # =========================================================================
    def distance_rule(model_instance, i, j):
        return data['distance_matrix'][i][j]

    model.distance = pyo.Param(model.V, model.V, initialize=distance_rule, doc="Distance/Cost c_ij")

    # t_ij^p: Travel time from i to j of a trip leaving in period p
    def travel_time_rule(model_instance, p, i, j):
        return data['travel_times'][p][i][j]

    model.travel_time = pyo.Param(model.P, model.V, model.V, initialize=travel_time_rule,
                                  doc="Travel time t_ij^p")

    # [b_p, b_p+1]: Bounds of each period. The last one ends at the latest possible
    # departure, as no trip leaves later than that
    last_departure = max(latest_departure(data, i) for i in range(num_nodes))

    def period_start_rule(model_instance, p):
        return data['period_starts'][p]

    def period_end_rule(model_instance, p):
        return data['period_starts'][p + 1] if p + 1 < num_periods else max(last_departure, data['period_starts'][p])

    model.period_start = pyo.Param(model.P, initialize=period_start_rule, doc="Period start b_p")
    model.period_end = pyo.Param(model.P, initialize=period_end_rule, doc="Period end b_p+1")

    # s_i: Service time of the visit at node i, s_0 = 0 at the base
    def service_rule(model_instance, i):
        return data['service_times'][i]

    model.service = pyo.Param(model.V, initialize=service_rule, doc="Service time s_i")

    # e_i / l_i: Earliest and latest allowed start time of the visit at node i
    def earliest_rule(model_instance, i):
        return data['earliest_start'][i]

    def latest_rule(model_instance, i):
        return data['latest_start'][i]

    model.earliest = pyo.Param(model.V, initialize=earliest_rule, doc="Earliest start e_i")
    model.latest = pyo.Param(model.V, initialize=latest_rule, doc="Latest start l_i")

    # P_ik: Eligibility matrix. A visit with a broker already assigned has P_ik = 1 only
    # for that broker; a visit without one has P_ik = 1 for every broker
    def eligibility_rule(model_instance, i, k):
        assigned = data['assigned_broker'][i]
        return 1 if assigned in (0, k) else 0

    model.eligibility = pyo.Param(model.C, model.K, initialize=eligibility_rule, doc="Eligibility P_ik")

    # M: Big-M constant that deactivates the time-flow constraints of unused arcs and periods
    big_m = data.get('big_m', compute_big_m(data))
    model.big_m = pyo.Param(initialize=big_m, doc="Big-M constant")

    # =========================================================================
    # 3. DECISION VARIABLES
    # =========================================================================
    # x_{ijk} = 1 if broker k travels directly from node i to node j, else 0
    model.x = pyo.Var(model.V, model.V, model.K, domain=pyo.Binary, doc="Edge traversal by broker")

    # w_i >= 0: Start time of the visit at property i
    model.w = pyo.Var(model.C, domain=pyo.NonNegativeReals, doc="Visit start time")

    # w0k departure / return: Time broker k leaves and gets back to the base
    model.w_departure = pyo.Var(model.K, domain=pyo.NonNegativeReals, doc="Base departure w0k")
    model.w_return = pyo.Var(model.K, domain=pyo.NonNegativeReals, doc="Base return w0k")

    # z_ip = 1 if the broker leaves property i (at w_i + s_i) in period p, else 0
    model.z = pyo.Var(model.C, model.P, domain=pyo.Binary, doc="Departure period of a property")

    # z_base_kp = 1 if broker k leaves the base in period p, else 0
    model.z_base = pyo.Var(model.K, model.P, domain=pyo.Binary, doc="Departure period from the base")

    # =========================================================================
    # 4. OBJECTIVE FUNCTION
    # =========================================================================
    def objective_rule(model_instance):
        """Minimize the brokers' total time out of the base: sum(w0k return - w0k departure)."""
        return sum(model_instance.w_return[k] - model_instance.w_departure[k] for k in model_instance.K)

    model.obj = pyo.Objective(rule=objective_rule, sense=pyo.minimize, doc="Minimize total time out of the base")

    # =========================================================================
    # 5. CONSTRAINTS
    # =========================================================================

    # 5.1 Single Service: every property is left exactly once, by exactly one broker
    def single_service_rule(model_instance, i):
        return sum(model_instance.x[i, j, k] for k in model_instance.K
                   for j in model_instance.V if j != i) == 1

    model.single_service_constraint = pyo.Constraint(model.C, rule=single_service_rule, doc="Constraint 4.1")

    # 5.2 Compatibility: a broker only leaves a property he is allowed to visit
    # Formula: sum_j x_ijk <= P_ik
    def compatibility_rule(model_instance, i, k):
        return (sum(model_instance.x[i, j, k] for j in model_instance.V if j != i)
                <= model_instance.eligibility[i, k])

    model.compatibility_constraint = pyo.Constraint(model.C, model.K, rule=compatibility_rule,
                                                    doc="Constraint 4.2")

    # 5.3 Flow Conservation: the broker who enters a property is the one who leaves it
    def flow_conservation_rule(model_instance, h, k):
        return (sum(model_instance.x[i, h, k] for i in model_instance.V if i != h)
                - sum(model_instance.x[h, j, k] for j in model_instance.V if j != h) == 0)

    model.flow_conservation_constraint = pyo.Constraint(model.C, model.K, rule=flow_conservation_rule,
                                                        doc="Constraint 4.3")

    # 5.4 Base Departure: each broker leaves the base at most once. Together with 5.3,
    # a broker who leaves the base also returns to it
    def base_departure_rule(model_instance, k):
        return sum(model_instance.x[0, j, k] for j in model_instance.C) <= 1

    model.base_departure_constraint = pyo.Constraint(model.K, rule=base_departure_rule, doc="Constraint 4.4")

    # 5.5 Departure Periods: every departure falls in exactly one period, within its bounds.
    # A departure exactly on a boundary may take either period
    def property_period_rule(model_instance, i):
        return sum(model_instance.z[i, p] for p in model_instance.P) == 1

    def property_period_start_rule(model_instance, i):
        return (sum(model_instance.period_start[p] * model_instance.z[i, p] for p in model_instance.P)
                <= model_instance.w[i] + model_instance.service[i])

    def property_period_end_rule(model_instance, i):
        return (model_instance.w[i] + model_instance.service[i]
                <= sum(model_instance.period_end[p] * model_instance.z[i, p] for p in model_instance.P))

    def base_period_rule(model_instance, k):
        return sum(model_instance.z_base[k, p] for p in model_instance.P) == 1

    def base_period_start_rule(model_instance, k):
        return (sum(model_instance.period_start[p] * model_instance.z_base[k, p] for p in model_instance.P)
                <= model_instance.w_departure[k])

    def base_period_end_rule(model_instance, k):
        return (model_instance.w_departure[k]
                <= sum(model_instance.period_end[p] * model_instance.z_base[k, p] for p in model_instance.P))

    model.property_period_constraint = pyo.Constraint(model.C, rule=property_period_rule, doc="Departure period")
    model.property_period_start_constraint = pyo.Constraint(model.C, rule=property_period_start_rule,
                                                            doc="Departure period start")
    model.property_period_end_constraint = pyo.Constraint(model.C, rule=property_period_end_rule,
                                                          doc="Departure period end")
    model.base_period_constraint = pyo.Constraint(model.K, rule=base_period_rule, doc="Base departure period")
    model.base_period_start_constraint = pyo.Constraint(model.K, rule=base_period_start_rule,
                                                        doc="Base departure period start")
    model.base_period_end_constraint = pyo.Constraint(model.K, rule=base_period_end_rule,
                                                      doc="Base departure period end")

    # 5.6 Time Flow: the next visit starts only after start + service + travel, with the
    # travel time of the period the broker leaves in
    # Formula: w_i + s_i + t_ij(w_i + s_i) - M * (1 - x_ijk) <= w_j
    def time_flow_rule(model_instance, i, j, k, p):
        if i == j:
            return pyo.Constraint.Skip
        return (model_instance.w[i] + model_instance.service[i] + model_instance.travel_time[p, i, j]
                - model_instance.big_m * (2 - model_instance.x[i, j, k] - model_instance.z[i, p])
                <= model_instance.w[j])

    model.time_flow_constraint = pyo.Constraint(model.C, model.C, model.K, model.P, rule=time_flow_rule,
                                                doc="Constraint 4.5")

    # From the base, the trip leaves at the broker's own departure time w0k
    def base_time_flow_rule(model_instance, j, k, p):
        return (model_instance.w_departure[k] + model_instance.travel_time[p, 0, j]
                - model_instance.big_m * (2 - model_instance.x[0, j, k] - model_instance.z_base[k, p])
                <= model_instance.w[j])

    model.base_time_flow_constraint = pyo.Constraint(model.C, model.K, model.P, rule=base_time_flow_rule,
                                                     doc="Constraint 4.5 from the base")

    # Back to the base, the arrival is the broker's return time w0k
    def return_time_flow_rule(model_instance, i, k, p):
        return (model_instance.w[i] + model_instance.service[i] + model_instance.travel_time[p, i, 0]
                - model_instance.big_m * (2 - model_instance.x[i, 0, k] - model_instance.z[i, p])
                <= model_instance.w_return[k])

    model.return_time_flow_constraint = pyo.Constraint(model.C, model.K, model.P, rule=return_time_flow_rule,
                                                       doc="Return to the base")

    # A broker who stays at the base spends no time out of it
    def return_after_departure_rule(model_instance, k):
        return model_instance.w_departure[k] <= model_instance.w_return[k]

    model.return_after_departure_constraint = pyo.Constraint(model.K, rule=return_after_departure_rule,
                                                             doc="Return after departure")

    # 5.7 Time Windows: every visit starts within its agreed window, and every broker
    # leaves the base within the base's window
    # Formula: e_i <= w_i <= l_i
    def time_window_rule(model_instance, i):
        return model_instance.earliest[i], model_instance.w[i], model_instance.latest[i]

    def base_window_rule(model_instance, k):
        return model_instance.earliest[0], model_instance.w_departure[k], model_instance.latest[0]

    model.time_window_constraint = pyo.Constraint(model.C, rule=time_window_rule, doc="Constraint 4.6")
    model.base_window_constraint = pyo.Constraint(model.K, rule=base_window_rule, doc="Constraint 4.6 at the base")

    # 5.8 Redundancy: Explicitly prevent self-loops mathematically
    def no_self_loop_rule(model_instance, i, k):
        return model_instance.x[i, i, k] == 0

    model.no_self_loop_constraint = pyo.Constraint(model.V, model.K, rule=no_self_loop_rule, doc="No self-loops")

    return model
