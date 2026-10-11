"""
Arcs the street network does not connect.

A missing drive path is not given a substitute distance. The arc stays in the
variable index so the flow constraints still name it, and it is fixed at zero,
so a route from that house to the other has to visit somewhere else in between.
"""

import pyomo.environ as pyo


def forbid_blocked_arcs(model: pyo.ConcreteModel, data: dict) -> None:
    """
    Fixes x at zero on every pair the instance lists in blocked_arcs.

    Args:
        model (pyo.ConcreteModel): A built model whose x is indexed by (i, j) or (i, j, ...).
        data (dict): Instance payload. blocked_arcs is a list of (i, j) pairs, or absent.
    """
    blocked = {(int(origin), int(destination)) for origin, destination in data.get("blocked_arcs", ())}
    if not blocked:
        return
    for index in model.x:
        if (int(index[0]), int(index[1])) in blocked:
            model.x[index].fix(0)
