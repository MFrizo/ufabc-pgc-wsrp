"""
Module: module_0
Description: Mathematical formulation of the Base Model (M0) for the WSRP.
             Implemented as a single-broker closed route Traveling Salesman
             Problem (TSP) using the Miller-Tucker-Zemlin (MTZ) formulation.
"""

import pyomo.environ as pyo

def build_model_m0(data: dict) -> pyo.ConcreteModel:
    """
    Constructs the MILP polyhedron for the M0 routing problem (TSP).

    Args:
        data (dict): A dictionary containing instance parameters:
            - 'num_nodes' (int): Total number of nodes |V|. Node 0 is the depot.
            - 'distance_matrix' (list of lists): 2D array of travel distances (c_ij).

    Returns:
        pyo.ConcreteModel: The unoptimized abstract mathematical model.
    """
    model = pyo.ConcreteModel(name="WSRP_Base_M0_TSP")

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

    # =========================================================================
    # 3. DECISION VARIABLES
    # =========================================================================
    # x_{ij} = 1 if the broker travels directly from node i to node j, else 0
    model.x = pyo.Var(model.V, model.V, domain=pyo.Binary, doc="Edge traversal boolean variable")

    # u_w >= 0: Continuous variable mapping the access order of each node w in C
    model.u = pyo.Var(model.C, domain=pyo.NonNegativeReals, doc="Sequence position variable for MTZ")

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

    model.out_degree_constraint = pyo.Constraint(model.V, rule=out_degree_rule, doc="Constraint 1.1")

    # 5.2 In-degree Constraint: Exactly one arrival for every node
    def in_degree_rule(model_instance, j):
        return sum(model_instance.x[i, j] for i in model_instance.V if i != j) == 1

    model.in_degree_constraint = pyo.Constraint(model.V, rule=in_degree_rule, doc="Constraint 1.2")

    # 5.3 Subtour Elimination Constraints (MTZ)
    def mtz_rule(model_instance, i, j):
        if i == j:
            return pyo.Constraint.Skip
        # The number of properties 'n' represents the maximum position index.
        # Formula: u_i - u_j + n * x_ij <= n - 1
        n = num_nodes - 1
        return model_instance.u[i] - model_instance.u[j] + n * model_instance.x[i, j] <= n - 1

    model.mtz_constraint = pyo.Constraint(model.C, model.C, rule=mtz_rule, doc="Constraint 1.3")

    # 5.4 Redundancy: Explicitly prevent self-loops mathematically
    def no_self_loop_rule(model_instance, i):
        return model_instance.x[i, i] == 0

    model.no_self_loop_constraint = pyo.Constraint(model.V, rule=no_self_loop_rule, doc="No self-loops")

    return model
