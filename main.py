"""
Module: main
Description: Entrypoint script for local execution of the WSRP optimization pipeline
             on the Ubuntu environment. Orchestrates ingestion, modeling,
             solving, and parsing.

Usage:
    python main.py --model m0    # Case 1: TSP
    python main.py --model m1    # Case 2: TSPTW
    python main.py --model m2    # Case 3: VRPTW
"""

import argparse

from src.utils.logger import project_logger
from src.core.data_generator import generate_wsrp_instance
from src.models import BUILDERS, INSTANCE_SETTINGS
from src.solvers.engine import solve_model
from src.utils.parsers import print_results


def main(model_version: str):
    """
    Main execution pipeline for local development and benchmarking.

    Args:
        model_version (str): Model to execute, a key of src.models.BUILDERS (e.g. 'm0', 'm1', 'm2').
    """
    project_logger.info(f"Starting local WSRP optimization pipeline ({model_version})...")

    # ---------------------------------------------------------
    # PHASE 1: Data Ingestion (Mock generation)
    # ---------------------------------------------------------
    project_logger.info("PHASE 1: Ingesting dataset (5 properties + 1 Depot)...")
    data_payload = generate_wsrp_instance(num_properties=5, random_seed=42, **INSTANCE_SETTINGS[model_version])
    project_logger.info(f"Dataset loaded. Total nodes: {data_payload['num_nodes']}")

    # ---------------------------------------------------------
    # PHASE 2: Mathematical Modeling (Pyomo Polyhedron)
    # ---------------------------------------------------------
    project_logger.info("PHASE 2: Building abstract MILP model...")
    abstract_model = BUILDERS[model_version](data_payload)

    # ---------------------------------------------------------
    # PHASE 3: Optimization Engine (Strategy Pattern)
    # ---------------------------------------------------------
    project_logger.info("PHASE 3: Dispatching model to Gurobi engine (Absolute Optimality)...")

    # Using gurobi_direct for in-memory high performance communication
    solved_model, metrics = solve_model(
        model=abstract_model,
        solver_name='gurobi_direct',
        mip_gap=0.0,
        raw=True
    )

    # ---------------------------------------------------------
    # PHASE 4: Output and Results Parsing
    # ---------------------------------------------------------
    if metrics['solver_status'] == 'ok':
        project_logger.info(f"Optimization successfully completed in {metrics['cpu_time_seconds']}s.")
        print_results(solved_model, elapsed_time=metrics['cpu_time_seconds'], solver_mode=metrics['solver_mode'])
    else:
        project_logger.error(f"Optimization failed. Termination: {metrics['termination_condition']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WSRP optimization pipeline")
    parser.add_argument('--model', choices=BUILDERS.keys(), default='m1',
                        help="Model to execute (default: m1)")
    main(parser.parse_args().model)
