"""
Package: solvers
Description: Solvers execution engine and benchmarking utilities.
"""

from src.solvers.engine import GUROBI_RAW_PARAMS, get_objective_breakdown, solve_model
from src.solvers.multiobj_benchmark import compare_objectives, print_comparison_table

__all__ = [
    'GUROBI_RAW_PARAMS',
    'get_objective_breakdown',
    'solve_model',
    'compare_objectives',
    'print_comparison_table',
]
