"""
Module: popmusic
Description: Implementation of the POPMUSIC (Partial OPtimization Metaheuristic Under Special
             Intensification Conditions) matheuristic for the WSRP, following Algorithm 1 of
             Queiroga, Sadykov, & Uchoa (2021), "A POPMUSIC matheuristic for the capacitated
             vehicle routing problem", Computers & Operations Research, 136, 105475.

             Algorithm 1 (POP) structure:
             - Maintains a target subproblem customer dimension `dim_sp` initialized to `alpha`
               and incremented by `delta` (`dim_sp <- dim_sp + delta`) up to |V_+| (|C|).
             - Maintains the memory set `Pi` of already-solved subproblems (V', S').
             - At each dimension `dim_sp`, generates a random permutation `L` of customer/property
               vertices `i in C`.
             - For each seed vertex `i = L[z]`, iteratively selects the closest route `r_hat` not
               yet in `R` according to `min_{j in C(r)} c_ij` (with symmetric c_ij and c_ii = 0)
               while `|V_sp| + |C(r_hat)| <= dim_sp`.
             - Checks the subset condition `V_sp not a subset of V' for all (V', S') in Pi`.
             - Solves `V_sp` with subproblem solver A using `cost(S_sp)` as the initial upper
               bound (via MIP warm start). If an improved subsolution `S'_sp` is found, updates
               `Pi` and `S` and restarts at line 7 (a new random permutation `L` at the same
               `dim_sp`).
"""

import math
import random
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


def _extract_route_customers(model: pyo.ConcreteModel) -> dict[int, set[int]]:
    """
    Extracts the customer/property set C(r) visited by each route r (broker k in K)
    in the current solution S.
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


def _symmetric_customer_costs(model: pyo.ConcreteModel) -> dict[tuple[int, int], float]:
    """
    Builds the symmetric edge cost matrix c_ij = c_ji for i, j in V_+ (C), with c_ii = 0,
    matching Section 2 of Queiroga, Sadykov, & Uchoa (2021).
    """
    model_any = cast(Any, model)
    customers = list(model_any.C)
    owners = list(_owner_to_broker(model).keys())
    costs: dict[tuple[int, int], float] = {}

    for i in customers:
        costs[i, i] = 0.0
        for j in customers:
            if i >= j:
                continue
            if hasattr(model, 'ARCS'):
                d_ij = next(
                    (float(pyo.value(model_any.distance[i, j, r])) for r in owners if (i, j, r) in model_any.ARCS),
                    0.0,
                )
                d_ji = next(
                    (float(pyo.value(model_any.distance[j, i, r])) for r in owners if (j, i, r) in model_any.ARCS),
                    d_ij,
                )
            else:
                d_ij = float(pyo.value(model_any.distance[i, j]))
                d_ji = float(pyo.value(model_any.distance[j, i]))
            c_sym = 0.5 * (d_ij + d_ji)
            costs[i, j] = c_sym
            costs[j, i] = c_sym

    return costs


def _build_subproblem_for_seed(
    seed_i: int,
    dim_sp: int,
    route_customers: dict[int, set[int]],
    sym_costs: dict[tuple[int, int], float],
) -> tuple[frozenset[int], list[int]]:
    """
    Implements lines 10-19 of Algorithm 1 in Queiroga, Sadykov, & Uchoa (2021):

        V_sp <- empty
        R <- empty
        while |V_sp| < dim_sp do
            r_hat <- argmin_{r in S, r not in R} { min_{j in C(r)} c_ij }
            if |V_sp| + |C(r_hat)| <= dim_sp then
                V_sp <- V_sp U C(r_hat)
                R <- R U {r_hat}
            else
                Go to line 21
    """
    active_routes = [r for r, custs in route_customers.items() if custs]
    v_sp: set[int] = set()
    r_set: list[int] = []
    r_included: set[int] = set()

    while len(v_sp) < dim_sp:
        candidates = [r for r in active_routes if r not in r_included]
        if not candidates:
            break

        # Line 14: r_hat <- argmin_{r in S, r not in R} { min_{j in C(r)} c_{seed_i, j} }
        r_hat = min(
            candidates,
            key=lambda r: (
                min(sym_costs.get((seed_i, j), math.inf) for j in route_customers[r]),
                r,
            ),
        )
        c_r_hat = route_customers[r_hat]

        # Lines 15-19: include C(r_hat) if it fits in dim_sp; otherwise stop construction
        if len(v_sp) + len(c_r_hat) <= dim_sp:
            v_sp.update(c_r_hat)
            r_set.append(r_hat)
            r_included.add(r_hat)
        else:
            break

    return frozenset(v_sp), sorted(r_set)


def _is_subset_of_pi(
    v_sp: frozenset[int],
    pi_memory: dict[frozenset[int], Any],
) -> bool:
    """
    Line 21 of Algorithm 1: checks whether V_sp is a subset of V' for any (V', S') in Pi.
    """
    if not v_sp:
        return True
    return any(v_sp.issubset(v_prime) for v_prime in pi_memory)


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
    Evaluates cost(S) as a lexicographic tuple so both standard scalar objectives
    and hierarchical/lexicographic multi-objective models can be compared monotonically.
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
    Restricts the model to the subproblem G[{0} U V_sp] (with V_sp = C \\ frozen_props
    and routes R = sub_brokers) by fixing all variables outside (V_sp, R) to their
    incumbent values in S.
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
    Finds an initial feasible solution S for POPMUSIC when one is not already loaded
    in `model` (running Gurobi with SolutionLimit=1 and MIPFocus=1).
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


def _default_alpha_delta(
    num_customers: int,
    num_brokers: int,
    alpha: Optional[int],
    delta: Optional[int],
    sub_size: Optional[int],
) -> tuple[int, int]:
    """
    Determines the initial subproblem customer dimension `alpha` and step size `delta`
    (lines 2, 4, and 31 of Algorithm 1 in Queiroga et al., 2021).

    - On large instances (n >= 100), defaults approach the paper's calibration (alpha=50, delta=40).
    - On smaller WSRP instances, scales `alpha` to the expected size of `sub_size` (default 2)
      routes so at least two routes fit inside the initial target dimension `dim_sp = alpha`.
    """
    avg_route_len = max(1, math.ceil(num_customers / max(1, num_brokers)))
    routes_per_sub = sub_size if sub_size is not None else 2

    if alpha is None:
        if num_customers >= 100 and sub_size is None:
            alpha_val = 50
        else:
            alpha_val = min(num_customers, max(2, routes_per_sub * avg_route_len))
    else:
        alpha_val = max(1, alpha)

    if delta is None:
        if num_customers >= 100 and sub_size is None:
            delta_val = 40
        else:
            delta_val = max(1, avg_route_len)
    else:
        delta_val = max(1, delta)

    return alpha_val, delta_val


def solve_popmusic(
    model: pyo.ConcreteModel,
    solver_name: str = 'gurobi_direct',
    alpha: Optional[int] = None,
    delta: Optional[int] = None,
    sub_size: Optional[int] = None,
    sub_time_limit: Optional[float] = 30.0,
    sub_node_limit: Optional[int] = None,
    initial_time_limit: Optional[float] = 60.0,
    time_limit: Optional[float] = None,
    mip_gap: float = 0.0,
    raw: bool = False,
    multiobj: Optional[bool] = None,
    multiobj_mode: str = 'hierarchical',
    multiobj_specs: Optional[list[dict[str, Any]]] = None,
    seed: int = 42,
    tee: bool = False,
) -> Tuple[pyo.ConcreteModel, dict[str, Any]]:
    """
    Executes the POPMUSIC matheuristic following Algorithm 1 of Queiroga, Sadykov, & Uchoa (2021):

        dim_sp <- alpha
        Pi <- empty
        while time limit is not exceeded and dim_sp <= |V_+| do
            L <- a vector of vertices in V_+ in random order
            for z = 1, 2, ..., n do
                i <- L[z]
                Build V_sp, R around seed vertex i while |V_sp| + |C(r_hat)| <= dim_sp
                if V_sp is not a subset of V' for all (V', S') in Pi then
                    Pi <- Pi U {(V_sp, S_sp)}
                    Solve V_sp with algorithm A using cost(S_sp) as upper bound
                    if cost(S'_sp) < cost(S_sp) then
                        Replace (V_sp, S_sp) by (V_sp, S'_sp) in Pi
                        Update S by replacing S_sp with S'_sp
                        Go to line 7 (restart with new random L at same dim_sp)
            dim_sp <- dim_sp + delta

    Args:
        model (pyo.ConcreteModel): Instantiated Pyomo model.
        solver_name (str): Target MILP solver for subproblems A (default: 'gurobi_direct').
        alpha (Optional[int]): Initial target customer dimension `alpha` for `dim_sp`.
        delta (Optional[int]): Step size `delta` to increase `dim_sp` when no seed improves S.
        sub_size (Optional[int]): Optional route-count hint used to scale default `alpha`
            when `alpha` is not explicitly specified.
        sub_time_limit (Optional[float]): Time limit in seconds per subproblem (GlobalTimeLimit).
        sub_node_limit (Optional[int]): Branch-and-bound node limit per subproblem
            (MaxNbOfBBtreeNodeTreated in Section 3 of Queiroga et al., 2021).
        initial_time_limit (Optional[float]): Time limit in seconds to obtain initial solution S.
        time_limit (Optional[float]): Overall wall-clock time limit in seconds.
        mip_gap (float): Relative optimality gap for subproblem MILPs.
        raw (bool): Whether to apply GUROBI_RAW_PARAMS.
        multiobj (Optional[bool]): Whether to solve subproblems with Gurobi multi-objective.
        multiobj_mode (str): Multi-objective mode ('hierarchical', 'blended', 'lexicographic').
        multiobj_specs (Optional[list[dict]]): Custom multi-objective specifications.
        seed (int): Random seed used to shuffle customer vector L at line 7.
        tee (bool): Stream sub-solver logs to the console.

    Returns:
        Tuple[pyo.ConcreteModel, dict[str, Any]]: Solved model and POPMUSIC benchmark metrics.
    """
    if sub_size is not None and sub_size < 1:
        raise ValueError(f"POPMUSIC sub_size must be at least 1; got {sub_size}.")
    if alpha is not None and alpha < 1:
        raise ValueError(f"POPMUSIC alpha must be at least 1; got {alpha}.")
    if delta is not None and delta < 1:
        raise ValueError(f"POPMUSIC delta must be at least 1; got {delta}.")

    total_start = time.time()
    if multiobj is None:
        multiobj = getattr(model, 'is_multiobj', False)
    if multiobj and hasattr(model, 'multiobj_mode') and multiobj_mode == 'hierarchical':
        multiobj_mode = model.multiobj_mode

    # Single-broker models (M0.0, M0.1) have only 1 route; solve directly
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
        n_cust = len(cast(Any, model).C) if hasattr(model, 'C') else 1
        base_metrics.update({
            'popmusic': True,
            'popmusic_alpha': n_cust,
            'popmusic_delta': n_cust,
            'popmusic_r': sub_size or 1,
            'initial_objective': obj_val,
            'final_objective': obj_val,
            'popmusic_subproblems': 1,
            'popmusic_improvements': 0,
            'popmusic_history': [],
        })
        return solved_model, base_metrics

    model_any = cast(Any, model)
    brokers = list(model_any.K)
    customers = list(model_any.C)
    all_properties = set(customers)
    num_customers = len(customers)

    alpha_val, delta_val = _default_alpha_delta(
        num_customers=num_customers,
        num_brokers=len(brokers),
        alpha=alpha,
        delta=delta,
        sub_size=sub_size,
    )

    # Record structural fixes made by the model builder so we never unfix them
    baseline_fixed_ids = {
        id(var) for var in model.component_data_objects(pyo.Var, active=True) if var.fixed
    }

    # Check if the model already carries a valid initial solution S
    existing_routes = _extract_model_routes(model)
    assigned_now = _extract_route_customers(model)
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
                'popmusic_alpha': alpha_val,
                'popmusic_delta': delta_val,
                'popmusic_r': sub_size or 2,
                'initial_objective': None,
                'final_objective': None,
                'popmusic_subproblems': 0,
                'popmusic_improvements': 0,
                'popmusic_history': [],
            }

    best_snapshot = _snapshot_variables(model)
    best_key = _evaluate_solution_key(
        model, multiobj=bool(multiobj), multiobj_mode=multiobj_mode, multiobj_specs=multiobj_specs
    )
    initial_scalar_obj = _evaluate_scalar_objective(model)
    best_scalar_obj = initial_scalar_obj

    sym_costs = _symmetric_customer_costs(model)
    rng = random.Random(seed)

    # Line 4: dim_sp <- alpha
    dim_sp = alpha_val

    # Line 5: Pi <- empty
    # Maps solved customer set V' -> subsolution signature (route assignment on V')
    pi_memory: dict[frozenset[int], dict[int, frozenset[int]]] = {}

    history: list[dict[str, Any]] = []
    subproblems_solved = 0
    improvements = 0
    last_multiobj_results = None
    max_dim_reached = dim_sp

    # Line 6: while time limit is not exceeded and dim_sp <= |V_+| do
    while dim_sp <= num_customers:
        if time_limit is not None and (time.time() - total_start) >= time_limit:
            project_logger.info("POPMUSIC: Reached global time limit; stopping.")
            break

        max_dim_reached = dim_sp
        restarted_at_line_7 = False

        # Line 7: L <- a vector of vertices in V_+ in random order
        l_seeds = list(customers)
        rng.shuffle(l_seeds)

        # Line 8: for z = 1, 2, ..., n do
        for seed_i in l_seeds:
            if time_limit is not None and (time.time() - total_start) >= time_limit:
                break

            route_customers = _extract_route_customers(model)

            # Lines 10-19: Build the subproblem (V_sp, R) for seed vertex i
            v_sp, r_brokers = _build_subproblem_for_seed(
                seed_i=seed_i,
                dim_sp=dim_sp,
                route_customers=route_customers,
                sym_costs=sym_costs,
            )

            # Line 21: if V_sp is not a subset of V' for all (V', S') in Pi then
            if _is_subset_of_pi(v_sp, pi_memory):
                continue

            # Lines 22-23: Let S_sp be the subsolution for V_sp in S; Pi <- Pi U {(V_sp, S_sp)}
            idle_brokers = [k for k, custs in route_customers.items() if not custs]
            sub_brokers = set(r_brokers) | set(idle_brokers)
            s_sp = {k: frozenset(route_customers[k]) for k in sorted(sub_brokers)}
            pi_memory[v_sp] = s_sp

            frozen_props = all_properties - set(v_sp)

            _fix_complement_for_subproblem(
                model=model,
                sub_brokers=sub_brokers,
                frozen_props=frozen_props,
                baseline_fixed_ids=baseline_fixed_ids,
            )

            step_limit = sub_time_limit
            if time_limit is not None:
                remaining = max(0.1, time_limit - (time.time() - total_start))
                step_limit = min(step_limit, remaining) if step_limit is not None else remaining

            extra_opts = {'NodeLimit': sub_node_limit} if sub_node_limit is not None else None

            # Line 24: Solve V_sp with algorithm A using cost(S_sp) as initial upper bound
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
                solver_options=extra_opts,
            )
            _unfix_to_baseline(model, baseline_fixed_ids)

            subproblems_solved += 1
            total_iterations += sub_metrics.get('iterations') or 0
            total_nodes += sub_metrics.get('node_count') or 0

            # Lines 25-26: Let S'_sp be the subsolution found by A; check if cost(S'_sp) < cost(S_sp)
            sub_ok = sub_metrics['solver_status'] == 'ok' and _extract_model_routes(model) is not None
            improved = False

            if sub_ok:
                cand_key = _evaluate_solution_key(
                    model, multiobj=bool(multiobj), multiobj_mode=multiobj_mode, multiobj_specs=multiobj_specs
                )
                for c_val, b_val in zip(cand_key, best_key):
                    if c_val < b_val - 1e-5:
                        improved = True
                        break
                    if c_val > b_val + 1e-5:
                        break

            if improved:
                # Line 27-28: Replace (V_sp, S_sp) by (V_sp, S'_sp) in Pi and update S.
                # Any cached (V', S') in Pi whose vertices overlap with modified routes no
                # longer matches the current global solution S and is invalidated.
                new_route_customers = _extract_route_customers(model)
                s_prime_sp = {k: frozenset(new_route_customers[k]) for k in sorted(sub_brokers)}

                changed_vertices: set[int] = set()
                for k in sorted(sub_brokers):
                    if new_route_customers[k] != route_customers[k]:
                        changed_vertices.update(new_route_customers[k] ^ route_customers[k])
                if not changed_vertices:
                    changed_vertices = set(v_sp)

                invalidated = [
                    v_prime for v_prime in pi_memory
                    if v_prime != v_sp and bool(v_prime & changed_vertices)
                ]
                for v_prime in invalidated:
                    del pi_memory[v_prime]
                pi_memory[v_sp] = s_prime_sp

                best_snapshot = _snapshot_variables(model)
                best_key = cand_key
                best_scalar_obj = _evaluate_scalar_objective(model)
                if sub_metrics.get('multiobj_results'):
                    last_multiobj_results = sub_metrics['multiobj_results']
                improvements += 1

                history.append({
                    'step': subproblems_solved,
                    'dim_sp': dim_sp,
                    'seed_vertex': seed_i,
                    'seed_broker': r_brokers[0] if r_brokers else None,
                    'sub_brokers': r_brokers,
                    'num_sub_properties': len(v_sp),
                    'improved': True,
                    'objective': best_scalar_obj,
                    'cpu_time_seconds': sub_metrics['cpu_time_seconds'],
                })

                # Line 29: Go to line 7 (restart with a new random permutation L at same dim_sp)
                restarted_at_line_7 = True
                break
            else:
                # Revert S to incumbent snapshot
                _restore_variables(best_snapshot, baseline_fixed_ids)
                history.append({
                    'step': subproblems_solved,
                    'dim_sp': dim_sp,
                    'seed_vertex': seed_i,
                    'seed_broker': r_brokers[0] if r_brokers else None,
                    'sub_brokers': r_brokers,
                    'num_sub_properties': len(v_sp),
                    'improved': False,
                    'objective': best_scalar_obj,
                    'cpu_time_seconds': sub_metrics['cpu_time_seconds'],
                })

        if restarted_at_line_7:
            continue

        # Line 31: Increase the current target dimension: dim_sp <- dim_sp + delta
        if dim_sp < num_customers and dim_sp + delta_val > num_customers:
            dim_sp = num_customers
        else:
            dim_sp += delta_val

    # Ensure model holds the best incumbent with baseline structural fixes
    _restore_variables(best_snapshot, baseline_fixed_ids)

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
        'termination_condition': (
            'optimal' if max_dim_reached >= num_customers and sub_node_limit is None else 'locallyOptimal'
        ),
        'solver_mode': 'popmusic_raw' if raw and 'gurobi' in solver_name else 'popmusic',
        'multiobj': bool(multiobj),
        'multiobj_mode': multiobj_mode if multiobj else 'none',
        'iterations': total_iterations,
        'node_count': total_nodes,
        'popmusic': True,
        'popmusic_alpha': alpha_val,
        'popmusic_delta': delta_val,
        'popmusic_r': sub_size if sub_size is not None else 2,
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
    alpha: Optional[int] = None,
    delta: Optional[int] = None,
    sub_size: Optional[int] = None,
    sub_time_limit: Optional[float] = 30.0,
    sub_node_limit: Optional[int] = None,
    time_limit: Optional[float] = 1800.0,
    mip_gap: float = 0.0,
    raw: bool = False,
    multiobj: bool = False,
    multiobj_mode: str = 'hierarchical',
    seed: int = 42,
    print_table: bool = True,
) -> dict[str, Any]:
    """
    Runs a side-by-side benchmark comparing the standard exact MILP solve (without POPMUSIC)
    against the POPMUSIC matheuristic (Algorithm 1 of Queiroga et al., 2021) on the same
    WSRP instance and model version.
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

    # 2. POPMUSIC Matheuristic Solve (Algorithm 1)
    m_pop = builder(data_payload)
    _, metrics_pop = solve_popmusic(
        m_pop,
        alpha=alpha,
        delta=delta,
        sub_size=sub_size,
        sub_time_limit=sub_time_limit,
        sub_node_limit=sub_node_limit,
        time_limit=time_limit,
        mip_gap=mip_gap,
        raw=raw,
        multiobj=multiobj if multiobj else None,
        multiobj_mode=multiobj_mode,
        seed=seed,
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
        'alpha': metrics_pop.get('popmusic_alpha'),
        'delta': metrics_pop.get('popmusic_delta'),
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
    alpha_val = results.get('alpha')
    delta_val = results.get('delta')
    exact = results['runs']['exact']
    pop = results['runs']['popmusic']

    pop_header = (
        f"POPMUSIC (alpha={alpha_val}, delta={delta_val})"
        if alpha_val is not None
        else "POPMUSIC"
    )
    headers = ["Metric / Component", "Exact MILP (No POPMUSIC)", pop_header]
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
