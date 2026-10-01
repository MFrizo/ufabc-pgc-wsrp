"""
Module: model_1
Description: Mathematical formulation of Model 1 (M1) for the WSRP.
             Implemented as a single-broker closed route Traveling Salesman
             Problem with Time Windows (TSPTW). The start-time variables (w_i)
             together with the Big-M time-flow constraints replace the MTZ
             constraints of M0 as the subtour elimination mechanism.
"""

import pyomo.environ as pyo


def compute_big_m(data: dict) -> float:
    """
    Computes the smallest single Big-M value that keeps the time-flow
    constraint (4.3) inactive whenever x_ij = 0.

    For any feasible schedule, w_i + s_i + T - w_j <= l_i + s_i + T - e_j,
    so the maximum of the right-hand side over all arcs is a valid bound.

    Args:
        data (dict): Instance payload (see build_model_m1).

    Returns:
        float: The Big-M constant.
    """
    num_nodes = data['num_nodes']
    earliest = data['earliest_start']
    latest = data['latest_start']
    service = [0.0] + [data['service_time']] * (num_nodes - 1)

    bound = max(latest[i] + service[i] + data['travel_time'] - earliest[j]
                for i in range(num_nodes) for j in range(1, num_nodes) if i != j)

    return max(bound, 0.0)


def build_model_m1(data: dict) -> pyo.ConcreteModel:
    """
    Constructs the MILP polyhedron for the M1 routing problem (TSPTW).

    Args:
        data (dict): A dictionary containing instance parameters:
            - 'num_nodes' (int): Total number of nodes |V|. Node 0 is the depot.
            - 'distance_matrix' (list of lists): 2D array of travel distances (c_ij).
            - 'travel_time' (float): Constant travel time T between any two nodes.
            - 'service_time' (float): Constant visit duration S for every property.
            - 'earliest_start' (list): Earliest start time e_i for every node in V.
            - 'latest_start' (list): Latest start time l_i for every node in V.
            - 'big_m' (float, optional): Big-M constant. Computed by compute_big_m if absent.

    Returns:
        pyo.ConcreteModel: The unoptimized abstract mathematical model.
    """
    if 'earliest_start' not in data:
        raise ValueError("M1 requires time windows, but the instance has none: "
                         "its visits do not fit in the generator's horizon.")

    model = pyo.ConcreteModel(name="WSRP_M1_TSPTW")

    # =========================================================================
    # 1. SETS (Indices)
    # =========================================================================
    # V = {0, 1, ..., n}: Set of all vertices, where 0 is the depot/home
    num_nodes = data['num_nodes']
    model.V = pyo.Set(initialize=range(num_nodes), doc="All nodes including depot")

    # C = V \ {0}: Set of customers/properties to be visited
    model.C = pyo.Set(initialize=range(1, num_nodes), doc="Property nodes only")

    # =========================================================================
    # 2. PARAMETERS (Data)
    # =========================================================================
    def distance_rule(model_instance, i, j):
        return data['distance_matrix'][i][j]

    model.distance = pyo.Param(model.V, model.V, initialize=distance_rule, doc="Distance/Cost c_ij")

    # T: Constant travel time between any two nodes (t_ij = T)
    model.travel_time = pyo.Param(initialize=data['travel_time'], doc="Travel time T")

    # s_i: Service time, s_0 = 0 at the depot and s_i = S for every property
    def service_rule(model_instance, i):
        return 0.0 if i == 0 else data['service_time']

    model.service = pyo.Param(model.V, initialize=service_rule, doc="Service time s_i")

    # e_i / l_i: Earliest and latest allowed start time of the job at node i
    def earliest_rule(model_instance, i):
        return data['earliest_start'][i]

    def latest_rule(model_instance, i):
        return data['latest_start'][i]

    model.earliest = pyo.Param(model.V, initialize=earliest_rule, doc="Earliest start e_i")
    model.latest = pyo.Param(model.V, initialize=latest_rule, doc="Latest start l_i")

    # M: Big-M constant that deactivates the time-flow constraint when x_ij = 0
    big_m = data.get('big_m', compute_big_m(data))
    model.big_m = pyo.Param(initialize=big_m, doc="Big-M constant")

    # =========================================================================
    # 3. DECISION VARIABLES
    # =========================================================================
    # x_{ij} = 1 if the broker travels directly from node i to node j, else 0
    model.x = pyo.Var(model.V, model.V, domain=pyo.Binary, doc="Edge traversal boolean variable")

    # w_i >= 0: Start time of the job at node i (w_0 is the departure from the depot)
    model.w = pyo.Var(model.V, domain=pyo.NonNegativeReals, doc="Job start time")

    # =========================================================================
    # 4. OBJECTIVE FUNCTION
    # =========================================================================
    def objective_rule(model_instance):
        """Minimize the total travel cost: sum(c_ij * x_ij) for all i, j in V."""
        return sum(model_instance.distance[i, j] * model_instance.x[i, j]
                   for i in model_instance.V for j in model_instance.V if i != j)

    model.obj = pyo.Objective(rule=objective_rule, sense=pyo.minimize, doc="Minimize total distance")

    # =========================================================================
    # 5. CONSTRAINTS
    # =========================================================================

    # 5.1 Out-degree Constraint: Exactly one departure for every node
    def out_degree_rule(model_instance, i):
        return sum(model_instance.x[i, j] for j in model_instance.V if j != i) == 1

    model.out_degree_constraint = pyo.Constraint(model.V, rule=out_degree_rule, doc="Constraint 4.1")

    # 5.2 In-degree Constraint: Exactly one arrival for every node
    def in_degree_rule(model_instance, j):
        return sum(model_instance.x[i, j] for i in model_instance.V if i != j) == 1

    model.in_degree_constraint = pyo.Constraint(model.V, rule=in_degree_rule, doc="Constraint 4.2")

    # 5.3 Time Flow: the next job starts only after start + service + travel
    # Formula: w_i + s_i + T - M * (1 - x_ij) <= w_j
    def time_flow_rule(model_instance, i, j):
        if i == j:
            return pyo.Constraint.Skip
        return (model_instance.w[i] + model_instance.service[i] + model_instance.travel_time
                - model_instance.big_m * (1 - model_instance.x[i, j]) <= model_instance.w[j])

    model.time_flow_constraint = pyo.Constraint(model.V, model.C, rule=time_flow_rule, doc="Constraint 4.3")

    # 5.4 Time Windows: every job starts within its agreed window
    # Formula: e_i <= w_i <= l_i
    def time_window_rule(model_instance, i):
        return model_instance.earliest[i], model_instance.w[i], model_instance.latest[i]

    model.time_window_constraint = pyo.Constraint(model.V, rule=time_window_rule, doc="Constraint 4.4")

    # 5.5 Redundancy: Explicitly prevent self-loops mathematically
    def no_self_loop_rule(model_instance, i):
        return model_instance.x[i, i] == 0

    model.no_self_loop_constraint = pyo.Constraint(model.V, rule=no_self_loop_rule, doc="No self-loops")

    return model
