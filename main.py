"""
Module: main
Description: Entrypoint script for local execution of the WSRP optimization pipeline
             on the Ubuntu environment. Orchestrates ingestion, modeling,
             solving, and parsing.

Usage:
    python main.py --model m0    # Base Model (TSP)
    python main.py --model m1    # Time Windows (TSPTW)
"""

import argparse

from src.utils.logger import project_logger
from src.core.data_generator import generate_wsrp_instance
from src.models.model_0 import build_model_m0
from src.models.model_1 import build_model_m1
from src.solvers.engine import solve_model
from src.utils.parsers import print_routes, print_schedule

BUILDERS = {'m0': build_model_m0, 'm1': build_model_m1}


def main(model_version: str):
    """
    Main execution pipeline for local development and benchmarking.

    Args:
        model_version (str): Model to execute: 'm0' (TSP) or 'm1' (TSPTW).
    """
    project_logger.info(f"Starting local WSRP optimization pipeline ({model_version})...")

    # ---------------------------------------------------------
    # PHASE 1: Data Ingestion (Mock generation)
    # ---------------------------------------------------------
    project_logger.info("PHASE 1: Ingesting dataset (5 properties + 1 Depot)...")
    data_payload = generate_wsrp_instance(num_properties=5, random_seed=42)
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
        print_routes(solved_model, elapsed_time=metrics['cpu_time_seconds'], solver_mode=metrics['solver_mode'])
        if model_version == 'm1':
            print_schedule(solved_model)
    else:
        project_logger.error(f"Optimization failed. Termination: {metrics['termination_condition']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WSRP optimization pipeline")
    parser.add_argument('--model', choices=BUILDERS.keys(), default='m1',
                        help="Model to execute (default: m1)")
    main(parser.parse_args().model)
