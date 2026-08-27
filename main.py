"""
Module: main
Description: Entrypoint script for local execution of the WSRP optimization pipeline
             on the Ubuntu environment. Orchestrates ingestion, modeling,
             solving, and parsing.
"""

from src.utils.logger import project_logger
from src.core.data_generator import generate_wsrp_m0_instance
from src.models.model_0 import build_model_m0
from src.solvers.engine import solve_model
from src.utils.parsers import print_routes


def main():
    """
    Main execution pipeline for local development and benchmarking.
    """
    project_logger.info("Starting local WSRP optimization pipeline (M0 - TSP)...")

    # ---------------------------------------------------------
    # PHASE 1: Data Ingestion (Mock generation)
    # ---------------------------------------------------------
    project_logger.info("PHASE 1: Ingesting dataset (5 properties + 1 Depot)...")
    data_payload = generate_wsrp_m0_instance(num_properties=5, random_seed=42)
    project_logger.info(f"Dataset loaded. Total nodes: {data_payload['num_nodes']}")

    # ---------------------------------------------------------
    # PHASE 2: Mathematical Modeling (Pyomo Polyhedron)
    # ---------------------------------------------------------
    project_logger.info("PHASE 2: Building abstract MILP model using MTZ constraints...")
    abstract_model = build_model_m0(data_payload)

    # ---------------------------------------------------------
    # PHASE 3: Optimization Engine (Strategy Pattern)
    # ---------------------------------------------------------
    project_logger.info("PHASE 3: Dispatching model to Gurobi engine (Absolute Optimality)...")

    # Using gurobi_direct for in-memory high performance communication
    solved_model, metrics = solve_model(
        model=abstract_model,
        solver_name='gurobi_direct',
        time_limit=300,
        mip_gap=0.0
    )

    # ---------------------------------------------------------
    # PHASE 4: Output and Results Parsing
    # ---------------------------------------------------------
    if metrics['solver_status'] == 'ok':
        project_logger.info(f"Optimization successfully completed in {metrics['cpu_time_seconds']}s.")
        print_routes(solved_model)
    else:
        project_logger.error(f"Optimization failed. Termination: {metrics['termination_condition']}")


if __name__ == "__main__":
    main()
