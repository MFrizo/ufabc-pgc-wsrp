"""
Module: multiobj_benchmark
Description: Benchmarking and comparison tool between default scalarized objectives
             and Gurobi native multi-objective optimization (hierarchical, blended,
             lexicographic).
"""

from typing import Any, Optional, Sequence
import pyomo.environ as pyo

from src.solvers.engine import get_objective_breakdown, solve_model
from src.utils.parsers import extract_broker_routes, extract_open_routes, extract_route


def _extract_model_routes(model: pyo.ConcreteModel) -> Optional[Any]:
    """Extracts routes regardless of model family (open routes, closed routes, single broker)."""
    if hasattr(model, 'end'):
        return extract_open_routes(model)
    elif hasattr(model, 'K'):
        return extract_broker_routes(model)
    return extract_route(model)


def compare_objectives(data_payload: dict[str, Any], model_version: str = 'm1.b',
                       modes: Sequence[str] = ('hierarchical', 'blended'),
                       time_limit: Optional[float] = None, mip_gap: float = 0.0,
                       raw: bool = False, print_table: bool = True) -> dict[str, Any]:
    """
    Solves an instance using the default scalarized objective and Gurobi's built-in
    multi-objective optimization in one or more modes, comparing performance,
    component values, and route equivalence.

    Args:
        data_payload (dict): Instance data loaded via load_instance.
        model_version (str): Model key in BUILDERS (e.g. 'm1', 'm1.a', 'm2', 'm2.a').
        modes (Sequence[str]): Multi-objective modes to benchmark (e.g. ('hierarchical', 'blended')).
        time_limit (Optional[float]): Time limit in seconds.
        mip_gap (float): Optimality MIP gap tolerance.
        raw (bool): Whether to use GUROBI_RAW_PARAMS.
        print_table (bool): Whether to print the formatted comparison table.

    Returns:
        dict[str, Any]: Detailed comparison dictionary containing runs, differences, and match status.
    """
    from src.models import BUILDERS

    builder = BUILDERS[model_version]
    results: dict[str, Any] = {'runs': {}}

    # 1. Default Scalarized Solve
    m_default = builder(data_payload)
    _, metrics_default = solve_model(
        m_default, time_limit=time_limit, mip_gap=mip_gap, raw=raw, multiobj=False, tee=False
    )
    routes_default = _extract_model_routes(m_default)
    breakdown_default = {item['name']: item['value'] for item in get_objective_breakdown(m_default)}
    scalar_default = pyo.value(m_default.obj) if hasattr(m_default, 'obj') else None

    results['runs']['default'] = {
        'model': m_default,
        'metrics': metrics_default,
        'routes': routes_default,
        'breakdown': breakdown_default,
        'scalar_objective': scalar_default,
    }

    # 2. Gurobi Multi-Objective Solves
    for mode in modes:
        m_mo = builder(data_payload)
        _, metrics_mo = solve_model(
            m_mo, time_limit=time_limit, mip_gap=mip_gap, raw=raw,
            multiobj=True, multiobj_mode=mode, tee=False
        )
        routes_mo = _extract_model_routes(m_mo)
        breakdown_mo = {item['name']: item['value'] for item in get_objective_breakdown(m_mo)}
        scalar_mo = pyo.value(m_mo.obj) if hasattr(m_mo, 'obj') else None

        # Compare with default
        route_match = (routes_default == routes_mo)
        component_diffs = {
            k: abs(breakdown_mo.get(k, 0.0) - breakdown_default.get(k, 0.0))
            for k in breakdown_default
        }
        scalar_diff = abs(scalar_mo - scalar_default) if scalar_mo is not None and scalar_default is not None else None

        results['runs'][f'gurobi_{mode}'] = {
            'model': m_mo,
            'metrics': metrics_mo,
            'routes': routes_mo,
            'breakdown': breakdown_mo,
            'scalar_objective': scalar_mo,
            'route_match': route_match,
            'component_diffs': component_diffs,
            'scalar_diff': scalar_diff,
        }

    if print_table:
        print_comparison_table(results, model_version=model_version)

    return results


def print_comparison_table(results: dict[str, Any], model_version: str = 'm1.b') -> None:
    """
    Renders a formatted side-by-side terminal comparison table.
    """
    runs = results['runs']
    col_names = list(runs.keys())
    headers = ["Metric / Component"] + [col.replace('_', ' ').title() for col in col_names]

    # Collect component names from default
    default_breakdown = runs['default']['breakdown']
    comp_names = list(default_breakdown.keys())

    rows: list[tuple[str, list[str]]] = []

    # Solver metrics
    rows.append(("Status", [runs[c]['metrics']['solver_status'] for c in col_names]))
    rows.append(("Termination", [runs[c]['metrics']['termination_condition'] for c in col_names]))
    rows.append(("Solve Time (s)", [f"{runs[c]['metrics']['cpu_time_seconds']:.4f}" for c in col_names]))
    rows.append(("Simplex Iterations", [str(runs[c]['metrics'].get('iterations', '—')) for c in col_names]))
    rows.append(("Explored Nodes", [str(runs[c]['metrics'].get('node_count', '—')) for c in col_names]))

    # Individual objective components
    for comp in comp_names:
        label = comp.replace('_', ' ').title()
        vals = [f"{runs[c]['breakdown'].get(comp, 0.0):.2f}" for c in col_names]
        rows.append((label, vals))

    # Overall scalar objective evaluation
    scalar_vals = [
        f"{runs[c]['scalar_objective']:.4f}" if runs[c]['scalar_objective'] is not None else "—"
        for c in col_names
    ]
    rows.append(("Default Objective Eval", scalar_vals))

    # Route comparison
    route_status = []
    for c in col_names:
        if c == 'default':
            route_status.append("BASELINE")
        else:
            match = runs[c].get('route_match')
            route_status.append("IDENTICAL" if match else "ALT OPTIMAL")
    rows.append(("Route Sequence Match", route_status))

    # Determine column widths
    col_widths = [len(h) for h in headers]
    for label, vals in rows:
        col_widths[0] = max(col_widths[0], len(label))
        for j, val in enumerate(vals, start=1):
            col_widths[j] = max(col_widths[j], len(val))

    total_width = sum(col_widths) + 3 * (len(headers) - 1) + 4
    sep_line = "=" * total_width
    thin_sep = "-" * total_width

    print("\n" + sep_line)
    title = f"OBJECTIVE FORMULATION BENCHMARK ({model_version.upper()}): Default vs Gurobi Multi-Objective"
    print(f" {title.center(total_width - 2)}")
    print(sep_line)

    header_str = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    print(f"| {header_str} |")
    print(thin_sep)

    for i, (label, vals) in enumerate(rows):
        # Add separator before components and before summary
        if label == comp_names[0].replace('_', ' ').title() or label == "Default Objective Eval":
            print(thin_sep)
        val_str = " | ".join(v.rjust(col_widths[j + 1]) for j, v in enumerate(vals))
        print(f"| {label.ljust(col_widths[0])} | {val_str} |")

    print(sep_line + "\n")
