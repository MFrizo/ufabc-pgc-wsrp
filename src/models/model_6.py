"""
Module: model_6
Description: Mathematical formulation of Model 6 (M6) for the WSRP.
             Implemented as a Fleet Size and Mix Vehicle Routing Problem with Time Windows
             (FSMVRPTW): the TDVRPTW of M5, where the number of brokers is minimized first
             and their total time out of the base second.
             The constraints are exactly M5's, so the model is built by M5 and only the
             objective is replaced.
"""

import pyomo.environ as pyo

from src.models.model_5 import build_model_m5, latest_departure


def compute_fleet_weight(data: dict, time_weight: float) -> float:
    """
    Computes a fleet weight W1 large enough that one broker fewer always outweighs
    any saving in time: W1 > W2 * (largest possible total time out of the base).

    No broker leaves the base before e_0 or gets back later than his latest departure
    plus the slowest trip, so each one is out for at most that long.

    Args:
        data (dict): Instance payload (see build_model_m5).
        time_weight (float): Weight W2 of the time out of the base.

    Returns:
        float: The fleet weight W1.
    """
    num_nodes = data['num_nodes']
    slowest_trip = max(max(max(row) for row in travel) for travel in data['travel_times'])
    longest_day = max(latest_departure(data, i) for i in range(num_nodes)) + slowest_trip - data['earliest_start'][0]

    return time_weight * data['num_brokers'] * longest_day + 1


def build_model_m6(data: dict) -> pyo.ConcreteModel:
    """
    Constructs the MILP polyhedron for the M6 routing problem (FSMVRPTW).

    Args:
        data (dict): The instance parameters of build_model_m5, plus:
            - 'time_weight' (float, optional): Weight W2 of the time out of the base. Defaults to 1.
            - 'fleet_weight' (float, optional): Weight W1 of each broker who leaves the base.
              Computed by compute_fleet_weight if absent.

    Returns:
        pyo.ConcreteModel: The unoptimized abstract mathematical model.
    """
    model = build_model_m5(data)
    model.name = "WSRP_M6_FSMVRPTW"

    # =========================================================================
    # PARAMETERS (Objective weights)
    # =========================================================================
    # W2: Small weight that leaves the time out of the base as the second criterion
    time_weight = data.get('time_weight', 1.0)
    model.time_weight = pyo.Param(initialize=time_weight, doc="Time weight W2")

    # W1: Large weight that makes the number of brokers the first criterion
    fleet_weight = data.get('fleet_weight', compute_fleet_weight(data, time_weight))
    model.fleet_weight = pyo.Param(initialize=fleet_weight, doc="Fleet weight W1")

    # =========================================================================
    # OBJECTIVE FUNCTION
    # =========================================================================
    def objective_rule(model_instance):
        """Minimize W1 * sum(x_0jk) + W2 * sum(w0k return - w0k departure)."""
        brokers_used = sum(model_instance.x[0, j, k] for k in model_instance.K for j in model_instance.C)
        time_out = sum(model_instance.w_return[k] - model_instance.w_departure[k] for k in model_instance.K)
        return model_instance.fleet_weight * brokers_used + model_instance.time_weight * time_out

    model.del_component(model.obj)
    model.obj = pyo.Objective(rule=objective_rule, sense=pyo.minimize,
                              doc="Minimize brokers first, time out of the base second")

    return model
