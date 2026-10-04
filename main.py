"""
Module: main
Description: Entrypoint script for local execution of the WSRP optimization pipeline
             on the Ubuntu environment. Orchestrates ingestion, modeling,
             solving, and parsing.

Usage:
    python main.py --model m0    # Case 1: TSP
    python main.py --model m1    # Case 2: TSPTW
    python main.py --model m2    # Case 3: VRPTW
    python main.py --model m3    # Case 4: SDVRPTW
    python main.py --model m4    # Case 5: VRPTWWVST
    python main.py --model m5    # Case 6: TDVRPTW
    python main.py --model m6    # Case 7: FSMVRPTW
    python main.py --model m7    # Case 8.a: MO-DOMDVRPTW-SD
    python main.py --model m8    # Case 8.b: HC-DOMDVRPTW-SD

    python main.py --model m7 --properties 12 --brokers 4    # Custom instance size
"""

import argparse
from typing import Optional

from src.utils.logger import project_logger
from src.core.data_generator import generate_wsrp_instance
from src.models import BUILDERS, DEFAULT_SEED, DEFAULT_SEEDS, INSTANCE_SETTINGS
from src.solvers.engine import solve_model
from src.utils.parsers import print_results


def main(model_version: str, num_properties: int = 5, num_brokers: Optional[int] = None):
    """
    Main execution pipeline for local development and benchmarking.

    Args:
        model_version (str): Model to execute, a key of src.models.BUILDERS (e.g. 'm0', 'm1', 'm2').
        num_properties (int): Number of properties to visit.
        num_brokers (Optional[int]): Number of brokers |K|, read from M2 onwards. None keeps
            the model's own setting in src.models.INSTANCE_SETTINGS.
    """
    project_logger.info(f"Starting local WSRP optimization pipeline ({model_version})...")

    # ---------------------------------------------------------
    # PHASE 1: Data Ingestion (Mock generation)
    # ---------------------------------------------------------
    instance_settings = dict(INSTANCE_SETTINGS[model_version])
    if num_brokers is not None:
        instance_settings['num_brokers'] = num_brokers

    project_logger.info(f"PHASE 1: Ingesting dataset ({num_properties} properties + 1 Depot, "
                        f"{instance_settings.get('num_brokers', 1)} brokers)...")
    random_seed = DEFAULT_SEEDS.get(model_version, DEFAULT_SEED)
    data_payload = generate_wsrp_instance(num_properties=num_properties, random_seed=random_seed, **instance_settings)
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
    parser.add_argument('--model', choices=BUILDERS.keys(), default='m7',
                        help="Model to execute (default: m7, Case 8.a)")
    parser.add_argument('--properties', type=int, default=5,
                        help="Number of properties to visit (default: 5)")
    parser.add_argument('--brokers', type=int, default=None,
                        help="Number of brokers, read from M2 onwards (default: the model's own setting)")
    args = parser.parse_args()
    main(args.model, num_properties=args.properties, num_brokers=args.brokers)
