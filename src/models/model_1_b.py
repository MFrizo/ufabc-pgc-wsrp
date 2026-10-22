"""
Module: model_1_b
Description: Mathematical formulation of M1.b for the WSRP.
             Native Gurobi multi-objective implementation of M1.a (MO-DOMDVRPTW-SD with
             tightened and lifted MTZ formulation). Instead of scalarizing the 5 objectives
             into a single weighted sum with an artificial Big-W fleet weight and an
             infinitesimal distance tie-breaker, M1.b leverages Gurobi's native multi-objective
             optimization engine (setObjectiveN) with hierarchical priority tiers:
             - Priority 2: Fleet size (minimize active brokers first)
             - Priority 1: Operational costs (driving time, delay, and overtime blended by their weights)
             - Priority 0: Total distance (pure tie-breaker between plans with equal time, delay, and overtime)
"""

import pyomo.environ as pyo

from src.models.model_1_a import build_model_m1_a


def build_model_m1_b(data: dict, multiobj_mode: str = 'hierarchical') -> pyo.ConcreteModel:
    """
    Constructs the M1.b model for native Gurobi multi-objective optimization.

    Inherits the tightened time-window domain reduction, arc-specific Big-M parameters,
    and lifted MTZ cuts from M1.a, while attaching explicit multi-objective component
    expressions and specifications for Gurobi's setObjectiveN solver API.

    Args:
        data (dict): Instance dictionary with the same keys as build_model_m1_a.
        multiobj_mode (str): Multi-objective strategy ('hierarchical', 'blended', or
            'lexicographic'). Defaults to 'hierarchical'.

    Returns:
        pyo.ConcreteModel: The mathematical model configured with is_multiobj=True
            and model.multiobj_specs.
    """
    model = build_model_m1_a(data)
    model.name = "WSRP_M1_B_GUROBI_MULTIOBJ_LIFTED_MTZ"
    model.is_multiobj = True
    model.multiobj_mode = multiobj_mode

    # Objective component expressions
    model.fleet_cost = pyo.Expression(
        expr=sum(model.y[k] for k in model.K), doc="Fleet size (brokers used)"
    )
    model.travel_time_cost = pyo.Expression(
        expr=sum(model.travel_time[arc] * model.x[arc] for arc in model.ARCS),
        doc="Total travel time (min)",
    )
    model.distance_cost = pyo.Expression(
        expr=sum(model.distance[arc] * model.x[arc] for arc in model.ARCS),
        doc="Total distance (units)",
    )
    model.delay_cost = pyo.Expression(
        expr=sum(model.delay[i] for i in model.C_h), doc="Total delay (min)"
    )
    model.overtime_cost = pyo.Expression(
        expr=sum(model.overtime[k] for k in model.K), doc="Total overtime (min)"
    )

    # Multi-objective specification for Gurobi's built-in multi-objective feature:
    # - In hierarchical mode:
    #     Priority 2: Fleet size (min brokers first)
    #     Priority 1: Operational costs (travel, delay, overtime blended by weights)
    #     Priority 0: Distance (tie-breaker between plans with equal time/delay/overtime)
    # - In blended mode:
    #     Priority 0 for all, with their default scalar weights.
    # - In lexicographic mode:
    #     Strict descending priorities from 4 down to 0.
    model.multiobj_specs = [
        {
            'name': 'fleet',
            'expr': model.fleet_cost,
            'default_weight': pyo.value(model.fleet_weight),
            'hierarchical_priority': 2,
            'hierarchical_weight': 1.0,
            'lexicographic_priority': 4,
            'unit': 'brokers',
        },
        {
            'name': 'overtime',
            'expr': model.overtime_cost,
            'default_weight': pyo.value(model.overtime_weight),
            'hierarchical_priority': 1,
            'hierarchical_weight': pyo.value(model.overtime_weight),
            'lexicographic_priority': 3,
            'unit': 'min',
        },
        {
            'name': 'delay',
            'expr': model.delay_cost,
            'default_weight': pyo.value(model.delay_weight),
            'hierarchical_priority': 1,
            'hierarchical_weight': pyo.value(model.delay_weight),
            'lexicographic_priority': 2,
            'unit': 'min',
        },
        {
            'name': 'travel_time',
            'expr': model.travel_time_cost,
            'default_weight': pyo.value(model.travel_weight),
            'hierarchical_priority': 1,
            'hierarchical_weight': pyo.value(model.travel_weight),
            'lexicographic_priority': 1,
            'unit': 'min',
        },
        {
            'name': 'distance',
            'expr': model.distance_cost,
            'default_weight': pyo.value(model.distance_weight),
            'hierarchical_priority': 0,
            'hierarchical_weight': 1.0,
            'lexicographic_priority': 0,
            'unit': 'units',
        },
    ]

    return model
