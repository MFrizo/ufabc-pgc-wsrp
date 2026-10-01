"""
Module: model_3
Description: Mathematical formulation of Model 3 (M3) for the WSRP.
             Implemented as a Site-Dependent Vehicle Routing Problem with Time Windows
             (SDVRPTW): the VRPTW of M2, where some visits already have a broker and
             only that broker may do them.
"""

import pyomo.environ as pyo

from src.models.model_1 import compute_big_m


def build_model_m3(data: dict) -> pyo.ConcreteModel:
    """
    Constructs the MILP polyhedron for the M3 routing problem (SDVRPTW).

    Args:
        data (dict): A dictionary containing instance parameters:
            - 'num_nodes' (int): Total number of nodes |V|. Node 0 is the shared base.
            - 'num_brokers' (int): Number of brokers |K|.
            - 'distance_matrix' (list of lists): 2D array of travel distances (c_ij).
            - 'travel_time' (float): Constant travel time T between any two nodes.
            - 'service_time' (float): Constant visit duration S for every property.
            - 'earliest_start' (list): Earliest start time e_i for every node in V.
            - 'latest_start' (list): Latest start time l_i for every node in V.
            - 'assigned_broker' (list): Broker already assigned to each node, 0 if none.
            - 'big_m' (float, optional): Big-M constant. Computed by compute_big_m if absent.

    Returns:
        pyo.ConcreteModel: The unoptimized abstract mathematical model.
    """
    model = pyo.ConcreteModel(name="WSRP_M3_SDVRPTW")

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

    # =========================================================================
    # 2. PARAMETERS (Data)
    # =========================================================================
    def distance_rule(model_instance, i, j):
        return data['distance_matrix'][i][j]

    model.distance = pyo.Param(model.V, model.V, initialize=distance_rule, doc="Distance/Cost c_ij")

    # T: Constant travel time between any two nodes
    model.travel_time = pyo.Param(initialize=data['travel_time'], doc="Travel time T")

    # s_i: Service time, s_0 = 0 at the base and s_i = S for every property
    def service_rule(model_instance, i):
        return 0.0 if i == 0 else data['service_time']

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

    # M: Big-M constant that deactivates the time-flow constraint when x_ijk = 0
    big_m = data.get('big_m', compute_big_m(data))
    model.big_m = pyo.Param(initialize=big_m, doc="Big-M constant")

    # =========================================================================
    # 3. DECISION VARIABLES
    # =========================================================================
    # x_{ijk} = 1 if broker k travels directly from node i to node j, else 0
    model.x = pyo.Var(model.V, model.V, model.K, domain=pyo.Binary, doc="Edge traversal by broker")

    # w_i >= 0: Start time of the visit at node i (w_0 is the departure from the base)
    model.w = pyo.Var(model.V, domain=pyo.NonNegativeReals, doc="Visit start time")

    # =========================================================================
    # 4. OBJECTIVE FUNCTION
    # =========================================================================
    def objective_rule(model_instance):
        """Minimize the total travel cost of all brokers: sum(c_ij * x_ijk)."""
        return sum(model_instance.distance[i, j] * model_instance.x[i, j, k]
                   for k in model_instance.K for i in model_instance.V for j in model_instance.V if i != j)

    model.obj = pyo.Objective(rule=objective_rule, sense=pyo.minimize, doc="Minimize total distance")

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

    # 5.5 Time Flow: the next visit starts only after start + service + travel
    # Formula: w_i + s_i + T - M * (1 - x_ijk) <= w_j
    def time_flow_rule(model_instance, i, j, k):
        if i == j:
            return pyo.Constraint.Skip
        return (model_instance.w[i] + model_instance.service[i] + model_instance.travel_time
                - model_instance.big_m * (1 - model_instance.x[i, j, k]) <= model_instance.w[j])

    model.time_flow_constraint = pyo.Constraint(model.V, model.C, model.K, rule=time_flow_rule,
                                                doc="Constraint 4.5")

    # 5.6 Time Windows: every visit starts within its agreed window
    # Formula: e_i <= w_i <= l_i
    def time_window_rule(model_instance, i):
        return model_instance.earliest[i], model_instance.w[i], model_instance.latest[i]

    model.time_window_constraint = pyo.Constraint(model.V, rule=time_window_rule, doc="Constraint 4.6")

    # 5.7 Redundancy: Explicitly prevent self-loops mathematically
    def no_self_loop_rule(model_instance, i, k):
        return model_instance.x[i, i, k] == 0

    model.no_self_loop_constraint = pyo.Constraint(model.V, model.K, rule=no_self_loop_rule, doc="No self-loops")

    return model
