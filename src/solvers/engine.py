"""
Module: engine
Description: Execution engine applying the Strategy Design Pattern for MILP solvers.
             It bridges the Pyomo abstract mathematical model with the optimization 
             backend via in-memory Python API (e.g., gurobipy).
"""

import time
import pyomo.environ as pyo
from typing import Tuple, Any


def solve_model(model: pyo.ConcreteModel, solver_name: str = 'gurobi_direct', time_limit: int = 60,
                mip_gap: float = 0.01) -> Tuple[pyo.ConcreteModel, dict[str, Any]]:
    """
    Executes the optimization process using the specified solver.

    Args:
        model (pyo.ConcreteModel): The instantiated abstract polyhedron.
        solver_name (str): The target solver. Defaults to 'gurobi_direct' to use gurobipy.
        time_limit (int): Maximum CPU time allowed in seconds.
        mip_gap (float): Relative tolerance for the optimality gap.

    Returns:
        Tuple containing the optimized model and a dictionary of benchmark metrics.
    """
    # 1. Strategy Instantiation
    try:
        solver = pyo.SolverFactory(solver_name)
    except Exception as e:
        raise ValueError(f"Failed to initialize solver '{solver_name}'. Error: {e}")

    # 2. Heuristic Stop Criteria Injection
    # NP-Hard problems require bounds to prevent infinite branch-and-bound trees.
    if 'gurobi' in solver_name:
        solver.options['TimeLimit'] = time_limit
        solver.options['MIPGap'] = mip_gap
    elif solver_name == 'cbc':
        solver.options['sec'] = time_limit
        solver.options['ratio'] = mip_gap

    # 3. Execution and Benchmarking
    start_time = time.time()

    # tee=True streams the solver's internal logs (Cuts, Nodes, Gap) to the terminal
    results = solver.solve(model, tee=True)

    cpu_time = round(time.time() - start_time, 4)

    # 4. Metrics Extraction
    metrics = {
        'cpu_time_seconds': cpu_time,
        'solver_status': str(results.solver.status),
        'termination_condition': str(results.solver.termination_condition)
    }

    return model, metrics
