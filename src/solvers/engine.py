"""
Module: engine
Description: Execution engine applying the Strategy Design Pattern for MILP solvers.
             It bridges the Pyomo abstract mathematical model with the optimization 
             backend via in-memory Python API (e.g., gurobipy).
"""

import time
import pyomo.environ as pyo
from typing import Optional, Tuple, Any


# Branch-and-bound over LP relaxations cannot be disabled: it is the MILP algorithm
# itself. Node bound propagation and implied-integer detection have no public
# parameter either. Everything else Gurobi layers on top is turned off here.
GUROBI_RAW_PARAMS = {
    # Pre-processing
    'Presolve': 0,       # No model reductions before the solve
    'ScaleFlag': 0,      # No matrix scaling
    'OBBT': 0,           # No optimality-based bound tightening
    # Cutting planes
    'Cuts': 0,           # No cutting planes (covers every individual cut class)
    # Primal heuristics
    'Heuristics': 0,     # No primal heuristics at the nodes
    'RINS': 0,           # No Relaxation Induced Neighborhood Search
    'PumpPasses': 0,     # No feasibility pump
    'ZeroObjNodes': 0,   # No zero-objective heuristic
    'MinRelNodes': 0,    # No minimum-relaxation heuristic
    'NoRelHeurTime': 0,  # No heuristic run before the root relaxation
    # Structure detection
    'Symmetry': 0,       # No symmetry detection
    'Disconnected': 0,   # No exploitation of independent sub-models
    # Search strategy
    'Threads': 1,        # Sequential tree search, deterministic timings
    'Method': 1,         # Root LP solved by dual simplex only (no concurrent race)
    'NodeMethod': 1,     # Node LPs solved by dual simplex only
    'VarBranch': 2,      # Branch on the most fractional variable
    'DegenMoves': 0,     # No degenerate simplex moves at the root
}


def solve_model(model: pyo.ConcreteModel, solver_name: str = 'gurobi_direct',
                time_limit: Optional[float] = None, mip_gap: float = 0.01,
                raw: bool = False) -> Tuple[pyo.ConcreteModel, dict[str, Any]]:
    """
    Executes the optimization process using the specified solver.

    Args:
        model (pyo.ConcreteModel): The instantiated abstract polyhedron.
        solver_name (str): The target solver. Defaults to 'gurobi_direct' to use gurobipy.
        time_limit (Optional[float]): Maximum wall-clock time allowed in seconds.
            None runs until the solver proves optimality.
        mip_gap (float): Relative tolerance for the optimality gap.
        raw (bool): Gurobi only. Applies GUROBI_RAW_PARAMS, leaving a plain LP-based
            branch-and-bound with no pre-processing, cuts or heuristics.

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
        if time_limit is not None:
            solver.options['TimeLimit'] = time_limit
        solver.options['MIPGap'] = mip_gap
        if raw:
            for param_name, param_value in GUROBI_RAW_PARAMS.items():
                solver.options[param_name] = param_value
    elif solver_name == 'cbc':
        if time_limit is not None:
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
        'termination_condition': str(results.solver.termination_condition),
        'solver_mode': 'raw' if raw and 'gurobi' in solver_name else 'default'
    }

    return model, metrics
