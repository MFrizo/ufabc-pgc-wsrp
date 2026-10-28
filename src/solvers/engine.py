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


def get_objective_breakdown(model: pyo.ConcreteModel) -> list[dict[str, Any]]:
    """
    Extracts the evaluated values of all objective components from a solved model.

    Args:
        model (pyo.ConcreteModel): The solved model (optionally defining model.multiobj_specs).

    Returns:
        list[dict[str, Any]]: A list of dictionaries with name, value, default_weight, and unit.
    """
    specs = getattr(model, 'multiobj_specs', None)
    if not specs:
        breakdown = []
        if hasattr(model, 'y') and hasattr(model, 'K'):
            fleet_val = sum(pyo.value(model.y[k]) for k in model.K)
            breakdown.append({'name': 'fleet', 'value': fleet_val, 'unit': 'brokers'})
        if hasattr(model, 'overtime') and hasattr(model, 'K'):
            overtime_val = sum(pyo.value(model.overtime[k]) for k in model.K)
            breakdown.append({'name': 'overtime', 'value': overtime_val, 'unit': 'min'})
        if hasattr(model, 'delay') and hasattr(model, 'C_h'):
            delay_val = sum(pyo.value(model.delay[i]) for i in model.C_h)
            breakdown.append({'name': 'delay', 'value': delay_val, 'unit': 'min'})
        if hasattr(model, 'travel_time') and hasattr(model, 'x') and hasattr(model, 'ARCS'):
            travel_val = sum(pyo.value(model.travel_time[arc]) * pyo.value(model.x[arc]) for arc in model.ARCS)
            breakdown.append({'name': 'travel_time', 'value': travel_val, 'unit': 'min'})
        if hasattr(model, 'distance') and hasattr(model, 'x') and hasattr(model, 'ARCS'):
            dist_val = sum(pyo.value(model.distance[arc]) * pyo.value(model.x[arc]) for arc in model.ARCS)
            breakdown.append({'name': 'distance', 'value': dist_val, 'unit': 'units'})
        if hasattr(model, 'max_workload'):
            breakdown.append({'name': 'max_workload', 'value': pyo.value(model.max_workload), 'unit': 'min'})
        if hasattr(model, 'broker_cost'):
            breakdown.append({'name': 'broker_cost', 'value': pyo.value(model.broker_cost), 'unit': 'min'})
        return breakdown

    breakdown = []
    for spec in specs:
        val = pyo.value(spec['expr'])
        breakdown.append({
            'name': spec['name'],
            'value': val,
            'default_weight': spec.get('default_weight'),
            'hierarchical_priority': spec.get('hierarchical_priority'),
            'hierarchical_weight': spec.get('hierarchical_weight'),
            'unit': spec.get('unit', ''),
        })
    return breakdown


def solve_model(model: pyo.ConcreteModel, solver_name: str = 'gurobi_direct',
                time_limit: Optional[float] = None, mip_gap: float = 0.01,
                raw: bool = False, multiobj: Optional[bool] = None,
                multiobj_mode: str = 'hierarchical',
                multiobj_specs: Optional[list[dict[str, Any]]] = None,
                tee: bool = True, popmusic: bool = False,
                popmusic_alpha: Optional[int] = None,
                popmusic_delta: Optional[int] = None,
                popmusic_r: Optional[int] = None,
                popmusic_sub_time_limit: Optional[float] = 30.0,
                popmusic_node_limit: Optional[int] = None,
                popmusic_seed: int = 42,
                solver_options: Optional[dict[str, Any]] = None) -> Tuple[pyo.ConcreteModel, dict[str, Any]]:
    """
    Executes the optimization process using the specified solver. Supports standard single-objective,
    Gurobi native multi-objective optimization (hierarchical, blended, lexicographic), and the
    POPMUSIC matheuristic decomposition framework (Algorithm 1 of Queiroga, Sadykov, & Uchoa, 2021).

    Args:
        model (pyo.ConcreteModel): The instantiated abstract polyhedron.
        solver_name (str): The target solver. Defaults to 'gurobi_direct' to use gurobipy.
        time_limit (Optional[float]): Maximum wall-clock time allowed in seconds.
            None runs until the solver proves optimality.
        mip_gap (float): Relative tolerance for the optimality gap.
        raw (bool): Gurobi only. Applies GUROBI_RAW_PARAMS, leaving a plain LP-based
            branch-and-bound with no pre-processing, cuts or heuristics.
        multiobj (bool): If True, activates Gurobi's native multi-objective API (setObjectiveN)
            instead of scalarizing parts into a single objective.
        multiobj_mode (str): Configuration strategy for multi-objective optimization:
            - 'hierarchical': Solves by priority levels (e.g. Priority 2: Fleet, Priority 1: Time/Delay/Overtime,
              Priority 0: Distance tie-breaker).
            - 'blended': All objectives at Priority 0, multiplied by their scalar default weights.
            - 'lexicographic': Sequential strict priorities for each component.
        multiobj_specs (Optional[list[dict]]): Custom multi-objective specifications. If None,
            reads model.multiobj_specs.
        tee (bool): Stream solver logs to the console. Defaults to True.
        popmusic (bool): If True, solves the model via the POPMUSIC matheuristic decomposition
            (Algorithm 1 of Queiroga, Sadykov, & Uchoa, 2021).
        popmusic_alpha (Optional[int]): Initial target customer dimension alpha for dim_sp.
        popmusic_delta (Optional[int]): Step size delta to increase dim_sp.
        popmusic_r (Optional[int]): Optional route-count hint used when alpha is not set.
        popmusic_sub_time_limit (Optional[float]): Time limit in seconds per POPMUSIC subproblem.
        popmusic_node_limit (Optional[int]): Branch-and-bound node limit per POPMUSIC subproblem.
        popmusic_seed (int): Random seed for shuffling customer vector L in POPMUSIC.
        solver_options (Optional[dict[str, Any]]): Extra solver options injected before solving.

    Returns:
        Tuple containing the optimized model and a dictionary of benchmark metrics.
    """
    if popmusic:
        from src.solvers.popmusic import solve_popmusic
        return solve_popmusic(
            model=model,
            solver_name=solver_name,
            alpha=popmusic_alpha,
            delta=popmusic_delta,
            sub_size=popmusic_r,
            sub_time_limit=popmusic_sub_time_limit,
            sub_node_limit=popmusic_node_limit,
            time_limit=time_limit,
            mip_gap=mip_gap,
            raw=raw,
            multiobj=multiobj,
            multiobj_mode=multiobj_mode,
            multiobj_specs=multiobj_specs,
            seed=popmusic_seed,
            tee=tee,
        )

    # 1. Strategy Instantiation
    try:
        solver = pyo.SolverFactory(solver_name)
    except Exception as e:
        raise ValueError(f"Failed to initialize solver '{solver_name}'. Error: {e}")

    # 2. Heuristic Stop Criteria Injection
    if 'gurobi' in solver_name:
        if time_limit is not None:
            solver.options['TimeLimit'] = time_limit
        solver.options['MIPGap'] = mip_gap
        if raw:
            for param_name, param_value in GUROBI_RAW_PARAMS.items():
                solver.options[param_name] = param_value
        if solver_options:
            for param_name, param_value in solver_options.items():
                if param_value is not None:
                    solver.options[param_name] = param_value
    elif solver_name == 'cbc':
        if multiobj:
            raise ValueError("Multi-objective optimization is only supported with Gurobi ('gurobi_direct', 'gurobi').")
        if time_limit is not None:
            solver.options['sec'] = time_limit
        solver.options['ratio'] = mip_gap
        if solver_options:
            for param_name, param_value in solver_options.items():
                if param_value is not None:
                    solver.options[param_name] = param_value

    start_time = time.time()

    # 3. Execution (Standard vs Multi-Objective)
    if multiobj is None:
        multiobj = getattr(model, 'is_multiobj', False)

    if multiobj:
        if hasattr(model, 'multiobj_mode') and multiobj_mode == 'hierarchical':
            multiobj_mode = model.multiobj_mode

    if multiobj:
        if 'gurobi' not in solver_name:
            raise ValueError(f"Solver '{solver_name}' does not support Gurobi native multi-objective optimization.")

        specs = multiobj_specs if multiobj_specs is not None else getattr(model, 'multiobj_specs', None)
        if not specs:
            raise ValueError(
                f"Model '{getattr(model, 'name', 'unnamed')}' has no multiobj_specs defined. "
                "Pass multiobj_specs explicitly or define model.multiobj_specs."
            )

        solver._tee = tee
        solver._presolve(model)
        grb = solver._solver_model

        for i, spec in enumerate(specs):
            if multiobj_mode == 'hierarchical':
                priority = spec.get('hierarchical_priority', 0)
                weight = spec.get('hierarchical_weight', 1.0)
            elif multiobj_mode == 'blended':
                priority = 0
                weight = spec.get('default_weight', 1.0)
            elif multiobj_mode == 'lexicographic':
                priority = spec.get('lexicographic_priority', len(specs) - 1 - i)
                weight = 1.0
            else:
                priority = spec.get('priority', 0)
                weight = spec.get('weight', 1.0)

            abstol = spec.get('abstol', 0.0)
            reltol = spec.get('reltol', 0.0)
            name = spec.get('name', f"obj_{i}")

            # Translate Pyomo expression to Gurobi LinExpr
            g_expr, _, _ = solver._get_expr_from_pyomo_expr(spec['expr'], 1)
            grb.setObjectiveN(g_expr, index=i, priority=priority, weight=weight,
                              abstol=abstol, reltol=reltol, name=name)

        solver._apply_solver()
        results = solver._postsolve()
        solver.load_vars()

        cpu_time = round(time.time() - start_time, 4)

        multiobj_results = []
        if hasattr(grb, 'NumObj') and grb.NumObj > 0 and grb.SolCount > 0:
            for i in range(grb.NumObj):
                grb.params.ObjNumber = i
                multiobj_results.append({
                    'index': i,
                    'name': grb.ObjNName,
                    'value': grb.ObjNVal,
                    'priority': grb.ObjNPriority,
                    'weight': grb.ObjNWeight,
                    'abstol': grb.ObjNAbsTol,
                    'reltol': grb.ObjNRelTol,
                    'unit': specs[i].get('unit', '') if i < len(specs) else '',
                })

        metrics = {
            'cpu_time_seconds': cpu_time,
            'solver_status': str(results.solver.status),
            'termination_condition': str(results.solver.termination_condition),
            'solver_mode': 'raw' if raw and 'gurobi' in solver_name else 'default',
            'multiobj': True,
            'multiobj_mode': multiobj_mode,
            'multiobj_results': multiobj_results,
            'iterations': getattr(grb, 'IterCount', None),
            'node_count': getattr(grb, 'NodeCount', None),
        }
    else:
        results = solver.solve(model, tee=tee)
        cpu_time = round(time.time() - start_time, 4)

        grb = getattr(solver, '_solver_model', None)
        metrics = {
            'cpu_time_seconds': cpu_time,
            'solver_status': str(results.solver.status),
            'termination_condition': str(results.solver.termination_condition),
            'solver_mode': 'raw' if raw and 'gurobi' in solver_name else 'default',
            'multiobj': False,
            'multiobj_mode': 'none',
            'iterations': getattr(grb, 'IterCount', None) if grb else None,
            'node_count': getattr(grb, 'NodeCount', None) if grb else None,
        }

    return model, metrics
