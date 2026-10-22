"""
Module: popmusic
Description: Implementation of the POPMUSIC (Partial OPtimization Metaheuristic Under Special
             Intensification Conditions) matheuristic framework (Taillard & Voß, 2002) for
             the WSRP Pyomo/Gurobi models.

             Decomposes a multi-broker WSRP instance into parts (one part per broker's route
             or shift set), constructs an initial feasible solution S_0, and iteratively
             re-optimizes sub-problems of r spatially/temporally proximate brokers using the
             exact MILP solver while holding the complement fixed.
"""

from itertools import combinations
import math
import time
from typing import Any, Optional, Tuple, cast

import pyomo.environ as pyo

from src.solvers.engine import get_objective_breakdown, solve_model
from src.utils.logger import project_logger
from src.utils.parsers import extract_broker_routes, extract_open_routes, extract_route


def _extract_model_routes(model: pyo.ConcreteModel) -> Optional[Any]:
    """Extracts routes regardless of model family (open routes, closed routes, single broker)."""
    model_any = cast(Any, model)
    if not hasattr(model, 'x') or any(v.value is None for v in model_any.x.values()):
        return None
    if hasattr(model, 'end'):
        return extract_open_routes(model)
    elif hasattr(model, 'K'):
        return extract_broker_routes(model)
    return extract_route(model)


def _broker_route_owners(model: pyo.ConcreteModel) -> dict[int, list[int]]:
    """
    Maps each broker k in K to the route-owner indices that belong to k.
    In shift-based models (M2, M2.a), a broker owns up to two shifts in R;
    in all other multi-broker models, the route owner is k itself.
    """
    model_any = cast(Any, model)
    brokers = list(model_any.K)
    if hasattr(model, 'R') and hasattr(model, 'route_broker'):
        mapping: dict[int, list[int]] = {k: [] for k in brokers}
        for r in model_any.R:
            k = int(round(pyo.value(model_any.route_broker[r])))
            mapping[k].append(r)
        return mapping
    return {k: [k] for k in brokers}


def _owner_to_broker(model: pyo.ConcreteModel) -> dict[int, int]:
    """Maps each route owner (shift r or broker k) back to its broker k in K."""
    mapping = {}
    for k, owners in _broker_route_owners(model).items():
        for owner in owners:
            mapping[owner] = k
    return mapping


def _broker_assigned_properties(model: pyo.ConcreteModel) -> dict[int, set[int]]:
    """
    Extracts the set of properties C_k currently visited by each broker k in K
    from the model's current x variable values.
    """
    model_any = cast(Any, model)
    properties = set(model_any.C)
    owner_broker = _owner_to_broker(model)
    assigned: dict[int, set[int]] = {k: set() for k in model_any.K}

    if hasattr(model, 'ARCS'):
        for i, j, owner in model_any.ARCS:
            val = pyo.value(model_any.x[i, j, owner], exception=False)
            if val is not None and val > 0.5:
                k = owner_broker[owner]
                if i in properties:
                    assigned[k].add(i)
                if j in properties:
                    assigned[k].add(j)
    else:
        for k in model_any.K:
            for i in model_any.V:
                for j in model_any.V:
                    if i != j:
                        val = pyo.value(model_any.x[i, j, k], exception=False)
                        if val is not None and val > 0.5:
                            if i in properties:
                                assigned[k].add(i)
                            if j in properties:
                                assigned[k].add(j)

    return assigned


def _pair_distance(model: pyo.ConcreteModel, i: int, j: int, owner: Optional[int] = None) -> float:
    """Evaluates distance between node i and node j in the model."""
    if i == j:
        return 0.0
    model_any = cast(Any, model)
    if hasattr(model, 'ARCS'):
        if owner is not None and (i, j, owner) in model_any.ARCS:
            return float(pyo.value(model_any.distance[i, j, owner]))
        for r in _owner_to_broker(model):
            if (i, j, r) in model_any.ARCS:
                return float(pyo.value(model_any.distance[i, j, r]))
        return 0.0
    return float(pyo.value(model_any.distance[i, j]))


def _compute_broker_proximity_matrix(
    model: pyo.ConcreteModel,
    assigned_props: dict[int, set[int]],
) -> dict[tuple[int, int], float]:
    """
    Computes the pairwise proximity dist(k1, k2) between brokers based on their
    currently visited properties and home/depot origins.

    Smaller values mean the two brokers operate in closer spatial neighborhoods
    and are stronger candidates to be grouped into a POPMUSIC sub-problem.
    """
    model_any = cast(Any, model)
    brokers = list(model_any.K)
    broker_owners = _broker_route_owners(model)
    dist_matrix: dict[tuple[int, int], float] = {}

    for k1 in brokers:
        dist_matrix[k1, k1] = 0.0
        for k2 in brokers:
            if k1 >= k2:
                continue

            props1 = assigned_props.get(k1, set())
            props2 = assigned_props.get(k2, set())

            if props1 and props2:
                # Average symmetric inter-property distance between the two routes
                total = 0.0
                count = 0
                for u in props1:
                    for v in props2:
                        d_uv = _pair_distance(model, u, v)
                        d_vu = _pair_distance(model, v, u)
                        total += 0.5 * (d_uv + d_vu)
                        count += 1
                score = total / count if count > 0 else math.inf
            elif props1 or props2:
                # One broker is active and the other is idle: measure distance from the idle
                # broker's depot/origin to the active broker's properties so POPMUSIC can
                # either offload visits to the idle broker or merge routes.
                active_props = props1 if props1 else props2
                idle_k = k2 if props1 else k1
                owners = broker_owners[idle_k]
                if not owners:
                    # Broker is on a day off (no shifts in M2)
                    score = math.inf
                elif hasattr(model, 'depot'):
                    total = 0.0
                    count = 0
                    for owner in owners:
                        d_node = int(round(pyo.value(model_any.depot[owner])))
                        for p in active_props:
                            total += _pair_distance(model, d_node, p, owner=owner)
                            count += 1
                    score = total / count if count > 0 else 0.0
                else:
                    # Shared base at node 0
                    total = sum(_pair_distance(model, 0, p) for p in active_props)
                    score = total / len(active_props)
            else:
                # Both brokers are idle
                score = math.inf

            dist_matrix[k1, k2] = score
            dist_matrix[k2, k1] = score

    return dist_matrix


def _select_subproblem_brokers(
    seed_k: int,
    brokers: list[int],
    sub_size: int,
    dist_matrix: dict[tuple[int, int], float],
    explored_subsets: set[frozenset[int]],
) -> Optional[list[int]]:
    """
    Constructs a sub-problem R_i of size `sub_size` around `seed_k` by sorting all other
    brokers by proximity dist(seed_k, k). If the closest r-1 subset was already solved for
    the current incumbent, tries the next-closest neighbor combination containing `seed_k`.
    """
    others = [k for k in brokers if k != seed_k]
    others.sort(key=lambda k: (dist_matrix.get((seed_k, k), math.inf), k))

    needed = min(sub_size - 1, len(others))
    if needed <= 0:
        cand = frozenset([seed_k])
        return [seed_k] if cand not in explored_subsets else None

    for comb in combinations(others, needed):
        subset = [seed_k, *comb]
        key = frozenset(subset)
        if key not in explored_subsets:
            return sorted(subset)

    return None


def _active_objective(model: pyo.ConcreteModel) -> Optional[pyo.Objective]:
    """Returns the single active Pyomo Objective on the model."""
    for obj in model.component_data_objects(pyo.Objective, active=True):
        return obj
    return None


def _evaluate_solution_key(
    model: pyo.ConcreteModel,
    multiobj: bool = False,
    multiobj_mode: str = 'hierarchical',
    multiobj_specs: Optional[list[dict[str, Any]]] = None,
) -> tuple[float, ...]:
    """
    Evaluates the objective key of the current variable assignment on `model`.
    Returns a tuple of floats so both standard scalar objectives and hierarchical/lexicographic
    multi-objective models can be compared monotonically.
    """
    if multiobj:
        specs = multiobj_specs if multiobj_specs is not None else getattr(model, 'multiobj_specs', None)
        if specs:
            tiers: dict[int, float] = {}
            for i, spec in enumerate(specs):
                if multiobj_mode == 'hierarchical':
                    prio = int(spec.get('hierarchical_priority', 0))
                    weight = float(spec.get('hierarchical_weight', 1.0))
                elif multiobj_mode == 'blended':
                    prio = 0
                    weight = float(spec.get('default_weight', 1.0))
                elif multiobj_mode == 'lexicographic':
                    prio = int(spec.get('lexicographic_priority', len(specs) - 1 - i))
                    weight = 1.0
                else:
                    prio = int(spec.get('priority', 0))
                    weight = float(spec.get('weight', 1.0))
                val = float(pyo.value(spec['expr']))
                tiers[prio] = tiers.get(prio, 0.0) + weight * val
            return tuple(tiers[p] for p in sorted(tiers.keys(), reverse=True))

    obj = _active_objective(model)
    if obj is not None:
        return (float(pyo.value(obj)),)
    return (math.inf,)


def _evaluate_scalar_objective(model: pyo.ConcreteModel) -> float:
    """Evaluates the scalar objective (or model.obj) for reporting."""
    obj = _active_objective(model)
    if obj is not None:
        return float(pyo.value(obj))
    if hasattr(model, 'obj'):
        return float(pyo.value(cast(Any, model).obj))
    return math.nan


def _snapshot_variables(model: pyo.ConcreteModel) -> list[tuple[Any, Optional[float]]]:
    """Captures the current values of all active variables in the model."""
    return [
        (var, pyo.value(var, exception=False))
        for var in model.component_data_objects(pyo.Var, active=True)
    ]


def _restore_variables(snapshot: list[tuple[Any, Optional[float]]], baseline_fixed_ids: set[int]) -> None:
    """Restores all variables to their snapshot values and resets fixed status to baseline."""
    for var, val in snapshot:
        if id(var) in baseline_fixed_ids:
            var.fix(val)
        else:
            var.unfix()
            var.set_value(val, skip_validation=True)


def _unfix_to_baseline(model: pyo.ConcreteModel, baseline_fixed_ids: set[int]) -> None:
    """Unfixes all temporary POPMUSIC variable fixes while keeping baseline structural fixes."""
    for var in model.component_data_objects(pyo.Var, active=True):
        if id(var) not in baseline_fixed_ids and var.fixed:
            var.unfix()


def _fix_complement_for_subproblem(
    model: pyo.ConcreteModel,
    sub_brokers: set[int],
    frozen_props: set[int],
    baseline_fixed_ids: set[int],
) -> None:
    """
    Fixes all decision variables associated with brokers outside `sub_brokers`
    and properties in `frozen_props` to their current incumbent values, leaving only
    the sub-problem variables free for Gurobi to optimize.
    """
    model_any = cast(Any, model)
    _unfix_to_baseline(model, baseline_fixed_ids)

    broker_owners = _broker_route_owners(model)
    sub_owners = {owner for k in sub_brokers for owner in broker_owners.get(k, [])}
    owner_broker = _owner_to_broker(model)

    # 1. Fix edge traversal variables x
    if hasattr(model, 'ARCS'):
        for i, j, owner in model_any.ARCS:
            var = model_any.x[i, j, owner]
            if id(var) in baseline_fixed_ids:
                continue
            if owner not in sub_owners:
                var.fix(round(float(pyo.value(var))))
            elif i in frozen_props or j in frozen_props:
                var.fix(0)
    else:
        for k in model_any.K:
            for i in model_any.V:
                for j in model_any.V:
                    var = model_any.x[i, j, k]
                    if id(var) in baseline_fixed_ids:
                        continue
                    if k not in sub_brokers:
                        var.fix(round(float(pyo.value(var))))
                    elif i in frozen_props or j in frozen_props:
                        var.fix(0)

    # 2. Fix period-specific edge variables x_period (M0.5, M0.6)
    if hasattr(model, 'x_period') and hasattr(model, 'P'):
        for p in model_any.P:
            for i in model_any.V:
                for j in model_any.V:
                    for k in model_any.K:
                        var = model_any.x_period[p, i, j, k]
                        if id(var) in baseline_fixed_ids:
                            continue
                        if k not in sub_brokers:
                            var.fix(round(float(pyo.value(var))))
                        elif i in frozen_props or j in frozen_props:
                            var.fix(0)

    # 3. Fix lunch pair variables z (M3, M3.a)
    if hasattr(model, 'LUNCH_PAIRS') and hasattr(model, 'z'):
        for i, j, k in model_any.LUNCH_PAIRS:
            var = model_any.z[i, j, k]
            if id(var) in baseline_fixed_ids:
                continue
            if k not in sub_brokers:
                var.fix(round(float(pyo.value(var))))
            elif i in frozen_props or j in frozen_props:
                var.fix(0)

    # 4. Fix broker-indexed variables (y, overtime, w_departure, w_return, workload, outside)
    for attr in ('y', 'overtime', 'w_departure', 'w_return', 'workload'):
        if hasattr(model, attr):
            comp = getattr(model_any, attr)
            for k in model_any.K:
                if k not in sub_brokers and k in comp:
                    var = comp[k]
                    if id(var) not in baseline_fixed_ids:
                        val = float(pyo.value(var))
                        var.fix(round(val) if var.is_binary() else val)

    if hasattr(model, 'outside') and hasattr(model, 'K_on'):
        for k in model_any.K_on:
            if k not in sub_brokers:
                var = model_any.outside[k]
                if id(var) not in baseline_fixed_ids:
                    var.fix(float(pyo.value(var)))

    # 5. Fix shift-indexed variables (shift_span in M2/M2.a, overlap/reaches_shift/started_by_shift in M3/M3.a)
    if hasattr(model, 'shift_span') and hasattr(model, 'R'):
        for r in model_any.R:
            if r not in sub_owners:
                var = model_any.shift_span[r]
                if id(var) not in baseline_fixed_ids:
                    var.fix(float(pyo.value(var)))

    if hasattr(model, 'SHIFTS'):
        for attr in ('overlap', 'reaches_shift', 'started_by_shift'):
            if hasattr(model, attr):
                comp = getattr(model_any, attr)
                for k, s in model_any.SHIFTS:
                    if k not in sub_brokers:
                        var = comp[k, s]
                        if id(var) not in baseline_fixed_ids:
                            val = float(pyo.value(var))
                            var.fix(round(val) if var.is_binary() else val)

    # 6. Fix start-time w and delay variables for frozen properties and frozen broker nodes
    frozen_nodes = set(frozen_props)
    if hasattr(model, 'depot'):
        for owner, k in owner_broker.items():
            if k not in sub_brokers:
                frozen_nodes.add(int(round(pyo.value(model_any.depot[owner]))))
                if hasattr(model, 'end'):
                    frozen_nodes.add(int(round(pyo.value(model_any.end[owner]))))
                if hasattr(model, 'lunch'):
                    frozen_nodes.add(int(round(pyo.value(model_any.lunch[owner]))))

    if hasattr(model, 'w'):
        for node in frozen_nodes:
            if node in model_any.w:
                var = model_any.w[node]
                if id(var) not in baseline_fixed_ids:
                    var.fix(float(pyo.value(var)))

    if hasattr(model, 'delay'):
        for i in frozen_props:
            if i in model_any.delay:
                var = model_any.delay[i]
                if id(var) not in baseline_fixed_ids:
                    var.fix(float(pyo.value(var)))


def _find_initial_solution(
    model: pyo.ConcreteModel,
    solver_name: str = 'gurobi_direct',
    time_limit: Optional[float] = 60.0,
    raw: bool = False,
    tee: bool = False,
) -> tuple[bool, dict[str, Any]]:
    """
    Finds an initial feasible solution S_0 for POPMUSIC by running the solver with
    SolutionLimit=1 and MIPFocus=1 (feasibility focus) so it terminates immediately
    upon discovering the first valid integer routing plan.
    """
    start_time = time.time()
    solver = pyo.SolverFactory(solver_name)

    if 'gurobi' in solver_name:
        if time_limit is not None:
            solver.options['TimeLimit'] = time_limit
        solver.options['SolutionLimit'] = 1
        solver.options['MIPFocus'] = 1
        if raw:
            from src.solvers.engine import GUROBI_RAW_PARAMS
            for param_name, param_value in GUROBI_RAW_PARAMS.items():
                solver.options[param_name] = param_value

        results = solver.solve(model, tee=tee, load_solutions=False)
        grb = getattr(solver, '_solver_model', None)
        sol_count = getattr(grb, 'SolCount', 0) if grb is not None else 0
        if sol_count > 0:
            solver.load_vars()
            feasible = True
        else:
            feasible = False
    else:
        if time_limit is not None and solver_name == 'cbc':
            solver.options['sec'] = time_limit
            solver.options['maxSolutions'] = 1
        results = solver.solve(model, tee=tee)
        grb = None
        routes = _extract_model_routes(model)
        feasible = routes is not None and len(routes) > 0

    elapsed = round(time.time() - start_time, 4)
    info = {
        'cpu_time_seconds': elapsed,
        'solver_status': 'ok' if feasible else str(results.solver.status),
        'termination_condition': (
            'feasible' if feasible else str(results.solver.termination_condition)
        ),
        'iterations': getattr(grb, 'IterCount', 0) if grb is not None else 0,
        'node_count': getattr(grb, 'NodeCount', 0) if grb is not None else 0,
    }
    return feasible, info


def solve_popmusic(
    model: pyo.ConcreteModel,
    solver_name: str = 'gurobi_direct',
    sub_size: int = 2,
    sub_time_limit: Optional[float] = 30.0,
    initial_time_limit: Optional[float] = 60.0,
    time_limit: Optional[float] = None,
    mip_gap: float = 0.0,
    raw: bool = False,
    multiobj: Optional[bool] = None,
    multiobj_mode: str = 'hierarchical',
    multiobj_specs: Optional[list[dict[str, Any]]] = None,
    tee: bool = False,
) -> Tuple[pyo.ConcreteModel, dict[str, Any]]:
    """
    Executes the POPMUSIC matheuristic on an instantiated WSRP Pyomo model.

    1. Constructs an initial feasible solution S_0 (if the model does not already have one).
    2. Decomposes the solution into broker-level parts s_1, ..., s_{|K|}.
    3. Iteratively selects a seed part s_i from unexamined parts U, builds a sub-problem R_i
       with its r-1 nearest neighbor brokers, fixes all variables outside R_i, and optimizes
       R_i using the MILP solver.
    4. Updates the incumbent solution and re-queues modified parts into U whenever an
       improvement is found, stopping when U is empty or the global time limit is reached.

    Args:
        model (pyo.ConcreteModel): Instantiated Pyomo model.
        solver_name (str): Target MILP solver for sub-problems (default: 'gurobi_direct').
        sub_size (int): Number of brokers r per POPMUSIC sub-problem (default: 2).
        sub_time_limit (Optional[float]): Time limit in seconds for each sub-problem solve.
        initial_time_limit (Optional[float]): Time limit in seconds to find S_0.
        time_limit (Optional[float]): Total wall-clock time limit in seconds across all steps.
        mip_gap (float): Relative optimality gap for sub-problem MILPs.
        raw (bool): Whether to apply GUROBI_RAW_PARAMS.
        multiobj (Optional[bool]): Whether to solve sub-problems with Gurobi multi-objective.
        multiobj_mode (str): Multi-objective mode ('hierarchical', 'blended', 'lexicographic').
        multiobj_specs (Optional[list[dict]]): Custom multi-objective specifications.
        tee (bool): Stream sub-solver logs to the console.

    Returns:
        Tuple[pyo.ConcreteModel, dict[str, Any]]: Solved model and POPMUSIC benchmark metrics.
    """
    if sub_size < 1:
        raise ValueError(f"POPMUSIC sub_size (r) must be at least 1; got {sub_size}.")

    total_start = time.time()
    if multiobj is None:
        multiobj = getattr(model, 'is_multiobj', False)
    if multiobj and hasattr(model, 'multiobj_mode') and multiobj_mode == 'hierarchical':
        multiobj_mode = model.multiobj_mode

    # Single-broker models (M0.0, M0.1) have only 1 part; solve directly
    if not hasattr(model, 'K') or len(cast(Any, model).K) <= 1:
        solved_model, base_metrics = solve_model(
            model=model,
            solver_name=solver_name,
            time_limit=time_limit,
            mip_gap=mip_gap,
            raw=raw,
            multiobj=multiobj,
            multiobj_mode=multiobj_mode,
            multiobj_specs=multiobj_specs,
            tee=tee,
            popmusic=False,
        )
        obj_val = _evaluate_scalar_objective(solved_model)
        base_metrics.update({
            'popmusic': True,
            'popmusic_r': sub_size,
            'initial_objective': obj_val,
            'final_objective': obj_val,
            'popmusic_subproblems': 1,
            'popmusic_improvements': 0,
            'popmusic_history': [],
        })
        return solved_model, base_metrics

    model_any = cast(Any, model)
    brokers = list(model_any.K)
    all_properties = set(model_any.C)

    # Record structural fixes made by the model builder so we never unfix them
    baseline_fixed_ids = {
        id(var) for var in model.component_data_objects(pyo.Var, active=True) if var.fixed
    }

    # Check if the model already carries a valid initial solution
    existing_routes = _extract_model_routes(model)
    assigned_now = _broker_assigned_properties(model)
    covered_props = set().union(*assigned_now.values()) if assigned_now else set()
    has_initial = existing_routes is not None and covered_props == all_properties

    total_iterations = 0
    total_nodes = 0

    if not has_initial:
        init_limit = initial_time_limit
        if time_limit is not None:
            init_limit = min(init_limit, time_limit) if init_limit is not None else time_limit

        feasible, init_info = _find_initial_solution(
            model=model,
            solver_name=solver_name,
            time_limit=init_limit,
            raw=raw,
            tee=tee,
        )
        total_iterations += init_info.get('iterations') or 0
        total_nodes += init_info.get('node_count') or 0

        if not feasible:
            elapsed = round(time.time() - total_start, 4)
            return model, {
                'cpu_time_seconds': elapsed,
                'solver_status': init_info['solver_status'],
                'termination_condition': init_info['termination_condition'],
                'solver_mode': 'raw' if raw and 'gurobi' in solver_name else 'default',
                'multiobj': bool(multiobj),
                'multiobj_mode': multiobj_mode if multiobj else 'none',
                'iterations': total_iterations,
                'node_count': total_nodes,
                'popmusic': True,
                'popmusic_r': sub_size,
                'initial_objective': None,
                'final_objective': None,
                'popmusic_subproblems': 0,
                'popmusic_improvements': 0,
                'popmusic_history': [],
            }

    best_snapshot = _snapshot_variables(model)
    best_key = _evaluate_solution_key(model, multiobj=bool(multiobj), multiobj_mode=multiobj_mode,
                                      multiobj_specs=multiobj_specs)
    initial_scalar_obj = _evaluate_scalar_objective(model)
    best_scalar_obj = initial_scalar_obj

    # Order initial seed list U so active brokers with visits are examined first
    assigned_props = _broker_assigned_properties(model)
    unexamined: list[int] = sorted(
        brokers, key=lambda k: (0 if assigned_props.get(k) else 1, k)
    )
    explored_subsets: set[frozenset[int]] = set()
    history: list[dict[str, Any]] = []
    subproblems_solved = 0
    improvements = 0
    last_multiobj_results = None

    effective_r = min(sub_size, len(brokers))

    while unexamined:
        if time_limit is not None and (time.time() - total_start) >= time_limit:
            project_logger.info("POPMUSIC: Reached global time limit; stopping intensification.")
            break

        seed_k = unexamined.pop(0)
        assigned_props = _broker_assigned_properties(model)

        # Skip seeds that have no visits if other active brokers still exist
        if not assigned_props.get(seed_k) and any(assigned_props.values()):
            continue

        dist_matrix = _compute_broker_proximity_matrix(model, assigned_props)
        sub_brokers_list = _select_subproblem_brokers(
            seed_k=seed_k,
            brokers=brokers,
            sub_size=effective_r,
            dist_matrix=dist_matrix,
            explored_subsets=explored_subsets,
        )
        if sub_brokers_list is None:
            continue

        sub_brokers = set(sub_brokers_list)
        explored_subsets.add(frozenset(sub_brokers))

        frozen_brokers = set(brokers) - sub_brokers
        frozen_props = set()
        for fk in frozen_brokers:
            frozen_props.update(assigned_props.get(fk, set()))
        sub_props = all_properties - frozen_props

        # If none of the selected brokers currently serve any property, nothing to optimize
        if not sub_props:
            continue

        _fix_complement_for_subproblem(
            model=model,
            sub_brokers=sub_brokers,
            frozen_props=frozen_props,
            baseline_fixed_ids=baseline_fixed_ids,
        )

        # Compute remaining time budget for this sub-problem
        step_limit = sub_time_limit
        if time_limit is not None:
            remaining = max(0.1, time_limit - (time.time() - total_start))
            step_limit = min(step_limit, remaining) if step_limit is not None else remaining

        _, sub_metrics = solve_model(
            model=model,
            solver_name=solver_name,
            time_limit=step_limit,
            mip_gap=mip_gap,
            raw=raw,
            multiobj=multiobj,
            multiobj_mode=multiobj_mode,
            multiobj_specs=multiobj_specs,
            tee=tee,
            popmusic=False,
        )
        _unfix_to_baseline(model, baseline_fixed_ids)

        subproblems_solved += 1
        total_iterations += sub_metrics.get('iterations') or 0
        total_nodes += sub_metrics.get('node_count') or 0

        # Verify solution validity and check if objective strictly improved
        sub_ok = sub_metrics['solver_status'] == 'ok' and _extract_model_routes(model) is not None
        improved = False

        if sub_ok:
            cand_key = _evaluate_solution_key(
                model, multiobj=bool(multiobj), multiobj_mode=multiobj_mode, multiobj_specs=multiobj_specs
            )
            # Lexicographic tuple comparison with tolerance 1e-5
            for c_val, b_val in zip(cand_key, best_key):
                if c_val < b_val - 1e-5:
                    improved = True
                    break
                if c_val > b_val + 1e-5:
                    break

        if improved:
            new_assigned = _broker_assigned_properties(model)
            changed_brokers = [
                k for k in sub_brokers_list
                if new_assigned.get(k, set()) != assigned_props.get(k, set())
            ] or sub_brokers_list

            best_snapshot = _snapshot_variables(model)
            best_key = cand_key
            best_scalar_obj = _evaluate_scalar_objective(model)
            if sub_metrics.get('multiobj_results'):
                last_multiobj_results = sub_metrics['multiobj_results']
            improvements += 1

            # Since the solution changed, previously explored subsets involving other brokers
            # may now admit new improvements; keep only the just-optimized subset in explored_subsets
            explored_subsets = {frozenset(sub_brokers)}

            for k in changed_brokers:
                if k != seed_k and k not in unexamined:
                    unexamined.append(k)
            if seed_k not in unexamined and len(brokers) > effective_r:
                unexamined.append(seed_k)
        else:
            # Revert to best incumbent
            _restore_variables(best_snapshot, baseline_fixed_ids)

        history.append({
            'step': subproblems_solved,
            'seed_broker': seed_k,
            'sub_brokers': sub_brokers_list,
            'num_sub_properties': len(sub_props),
            'improved': improved,
            'objective': best_scalar_obj,
            'cpu_time_seconds': sub_metrics['cpu_time_seconds'],
        })

    # Ensure model holds the best incumbent with baseline structural fixes
    _restore_variables(best_snapshot, baseline_fixed_ids)

    # Populate multiobj_results if multiobj was requested and no sub-problem overwrote it
    if multiobj and last_multiobj_results is None:
        specs = multiobj_specs if multiobj_specs is not None else getattr(model, 'multiobj_specs', None)
        if specs:
            last_multiobj_results = []
            for i, spec in enumerate(specs):
                if multiobj_mode == 'hierarchical':
                    prio = spec.get('hierarchical_priority', 0)
                    weight = spec.get('hierarchical_weight', 1.0)
                elif multiobj_mode == 'blended':
                    prio = 0
                    weight = spec.get('default_weight', 1.0)
                elif multiobj_mode == 'lexicographic':
                    prio = spec.get('lexicographic_priority', len(specs) - 1 - i)
                    weight = 1.0
                else:
                    prio = spec.get('priority', 0)
                    weight = spec.get('weight', 1.0)
                last_multiobj_results.append({
                    'index': i,
                    'name': spec.get('name', f'obj_{i}'),
                    'value': float(pyo.value(spec['expr'])),
                    'priority': prio,
                    'weight': weight,
                    'abstol': spec.get('abstol', 0.0),
                    'reltol': spec.get('reltol', 0.0),
                    'unit': spec.get('unit', ''),
                })

    total_cpu = round(time.time() - total_start, 4)
    metrics: dict[str, Any] = {
        'cpu_time_seconds': total_cpu,
        'solver_status': 'ok',
        'termination_condition': 'optimal' if effective_r >= len(brokers) else 'locallyOptimal',
        'solver_mode': 'popmusic_raw' if raw and 'gurobi' in solver_name else 'popmusic',
        'multiobj': bool(multiobj),
        'multiobj_mode': multiobj_mode if multiobj else 'none',
        'iterations': total_iterations,
        'node_count': total_nodes,
        'popmusic': True,
        'popmusic_r': effective_r,
        'initial_objective': initial_scalar_obj,
        'final_objective': best_scalar_obj,
        'popmusic_subproblems': subproblems_solved,
        'popmusic_improvements': improvements,
        'popmusic_history': history,
    }
    if multiobj and last_multiobj_results is not None:
        metrics['multiobj_results'] = last_multiobj_results

    return model, metrics


def compare_popmusic(
    data_payload: dict[str, Any],
    model_version: str = 'm1.a',
    sub_size: int = 2,
    sub_time_limit: Optional[float] = 30.0,
    time_limit: Optional[float] = 1800.0,
    mip_gap: float = 0.0,
    raw: bool = False,
    multiobj: bool = False,
    multiobj_mode: str = 'hierarchical',
    print_table: bool = True,
) -> dict[str, Any]:
    """
    Runs a side-by-side benchmark comparing the standard exact MILP solve (without POPMUSIC)
    against the POPMUSIC matheuristic on the same WSRP instance and model version.
    """
    from src.models import BUILDERS

    builder = BUILDERS[model_version]

    # 1. Exact MILP Solve (without POPMUSIC)
    m_exact = builder(data_payload)
    _, metrics_exact = solve_model(
        m_exact,
        time_limit=time_limit,
        mip_gap=mip_gap,
        raw=raw,
        multiobj=multiobj if multiobj else None,
        multiobj_mode=multiobj_mode,
        tee=False,
        popmusic=False,
    )
    routes_exact = _extract_model_routes(m_exact)
    breakdown_exact = {item['name']: item['value'] for item in get_objective_breakdown(m_exact)}
    scalar_exact = _evaluate_scalar_objective(m_exact)

    # 2. POPMUSIC Matheuristic Solve
    m_pop = builder(data_payload)
    _, metrics_pop = solve_popmusic(
        m_pop,
        sub_size=sub_size,
        sub_time_limit=sub_time_limit,
        time_limit=time_limit,
        mip_gap=mip_gap,
        raw=raw,
        multiobj=multiobj if multiobj else None,
        multiobj_mode=multiobj_mode,
        tee=False,
    )
    routes_pop = _extract_model_routes(m_pop)
    breakdown_pop = {item['name']: item['value'] for item in get_objective_breakdown(m_pop)}
    scalar_pop = _evaluate_scalar_objective(m_pop)

    gap_pct = (
        100.0 * (scalar_pop - scalar_exact) / max(abs(scalar_exact), 1e-9)
        if not (math.isnan(scalar_exact) or math.isnan(scalar_pop))
        else None
    )

    results = {
        'model_version': model_version,
        'sub_size': sub_size,
        'runs': {
            'exact': {
                'model': m_exact,
                'metrics': metrics_exact,
                'routes': routes_exact,
                'breakdown': breakdown_exact,
                'scalar_objective': scalar_exact,
            },
            'popmusic': {
                'model': m_pop,
                'metrics': metrics_pop,
                'routes': routes_pop,
                'breakdown': breakdown_pop,
                'scalar_objective': scalar_pop,
                'route_match': routes_exact == routes_pop,
                'gap_pct': gap_pct,
            },
        },
    }

    if print_table:
        print_popmusic_comparison(results)

    return results


def print_popmusic_comparison(results: dict[str, Any]) -> None:
    """Prints a formatted side-by-side comparison table between Exact MILP and POPMUSIC."""
    model_version = results.get('model_version', 'm1.a')
    sub_size = results.get('sub_size', 2)
    exact = results['runs']['exact']
    pop = results['runs']['popmusic']

    headers = ["Metric / Component", "Exact MILP (No POPMUSIC)", f"POPMUSIC (r={sub_size})"]
    rows: list[tuple[str, list[str]]] = [
        ("Status", [exact['metrics']['solver_status'], pop['metrics']['solver_status']]),
        ("Termination", [exact['metrics']['termination_condition'], pop['metrics']['termination_condition']]),
        ("Solve Time (s)", [
            f"{exact['metrics']['cpu_time_seconds']:.4f}",
            f"{pop['metrics']['cpu_time_seconds']:.4f}",
        ]),
        ("Sub-problems Solved", ["1 (Full MILP)", str(pop['metrics'].get('popmusic_subproblems', 0))]),
        ("POPMUSIC Improvements", ["—", str(pop['metrics'].get('popmusic_improvements', 0))]),
        ("Simplex Iterations", [
            str(exact['metrics'].get('iterations', '—')),
            str(pop['metrics'].get('iterations', '—')),
        ]),
        ("Explored Nodes", [
            str(exact['metrics'].get('node_count', '—')),
            str(pop['metrics'].get('node_count', '—')),
        ]),
    ]

    comp_names = list(exact['breakdown'].keys())
    for comp in comp_names:
        label = comp.replace('_', ' ').title()
        rows.append((
            label,
            [
                f"{exact['breakdown'].get(comp, 0.0):.2f}",
                f"{pop['breakdown'].get(comp, 0.0):.2f}",
            ],
        ))

    init_obj = pop['metrics'].get('initial_objective')
    rows.append((
        "Initial Objective (S0)",
        ["—", f"{init_obj:.4f}" if init_obj is not None else "—"],
    ))
    rows.append((
        "Final Objective",
        [
            f"{exact['scalar_objective']:.4f}" if exact['scalar_objective'] is not None else "—",
            f"{pop['scalar_objective']:.4f}" if pop['scalar_objective'] is not None else "—",
        ],
    ))
    gap_pct = pop.get('gap_pct')
    rows.append((
        "Optimality Gap vs Exact",
        ["0.00%", f"{gap_pct:+.2f}%" if gap_pct is not None else "—"],
    ))
    rows.append((
        "Route Sequence Match",
        ["BASELINE", "IDENTICAL" if pop.get('route_match') else "HEURISTIC / ALT"],
    ))

    col_widths = [len(h) for h in headers]
    for label, vals in rows:
        col_widths[0] = max(col_widths[0], len(label))
        for j, val in enumerate(vals, start=1):
            col_widths[j] = max(col_widths[j], len(val))

    total_width = sum(col_widths) + 3 * (len(headers) - 1) + 4
    sep_line = "=" * total_width
    thin_sep = "-" * total_width

    print("\n" + sep_line)
    title = f"SOLVER BENCHMARK ({model_version.upper()}): Exact MILP vs POPMUSIC Matheuristic"
    print(f" {title.center(total_width - 2)}")
    print(sep_line)

    header_str = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    print(f"| {header_str} |")
    print(thin_sep)

    first_comp_label = comp_names[0].replace('_', ' ').title() if comp_names else None
    for label, vals in rows:
        if label in (first_comp_label, "Initial Objective (S0)"):
            print(thin_sep)
        val_str = " | ".join(v.rjust(col_widths[j + 1]) for j, v in enumerate(vals))
        print(f"| {label.ljust(col_widths[0])} | {val_str} |")

    print(sep_line + "\n")
