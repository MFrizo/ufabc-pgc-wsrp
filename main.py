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
    python main.py --model m7 --dataset real --city "São Paulo" --neighborhood Moema
    python main.py --model m7 --dataset real --city "Rio de Janeiro" --neighborhood Copacabana --catalog-path data/raw_real.csv.gz
    python main.py --model m7 --properties 20 --brokers auto
"""

import argparse
from typing import Optional, Union

from src.utils.logger import project_logger
from src.core.data_generator import AUTO_BROKERS
from src.core.listings import DATASETS, load_instance
from src.models import BUILDERS
from src.solvers.engine import solve_model
from src.utils.parsers import print_results


def main(model_version: str, dataset: str = "synthetic", num_properties: int = 5, random_seed: int = 42,
         catalog_path: Optional[str] = None, city: Optional[str] = None, neighborhood: Optional[str] = None,
         num_brokers: Optional[Union[int, str]] = None):
    """
    Main execution pipeline for local development and benchmarking.

    Args:
        model_version (str): Model to execute, a key of src.models.BUILDERS (e.g. 'm0', 'm1', 'm2').
        dataset (str): "synthetic" for the generator, "real" for the rental catalog.
        num_properties (int): Number of properties in the instance.
        random_seed (int): Seed of the sample and of the hidden schedule.
        catalog_path (Optional[str]): Real-listings CSV. Defaults to data/real.csv.
        city (Optional[str]): City kept when dataset is "real".
        neighborhood (Optional[str]): Neighborhood kept when dataset is "real".
        num_brokers (Optional[Union[int, str]]): Brokers of the instance, or "auto" to size
            the fleet from the visits. None keeps the model's setting.
    """
    project_logger.info(f"Starting local WSRP optimization pipeline ({model_version}, {dataset})...")

    # ---------------------------------------------------------
    # PHASE 1: Data Ingestion
    # ---------------------------------------------------------
    project_logger.info(f"PHASE 1: Ingesting {dataset} dataset ({num_properties} properties + 1 Depot)...")
    data_payload = load_instance(dataset, model_version, num_properties=num_properties, random_seed=random_seed,
                                 catalog_path=catalog_path, city=city, neighborhood=neighborhood,
                                 num_brokers=num_brokers)
    if num_brokers == AUTO_BROKERS:
        project_logger.info(
            f"Fleet: {data_payload['num_brokers']} brokers "
            f"(the hidden schedule needs {data_payload['schedule_brokers']})."
        )
    for listing in data_payload.get("listings", []):
        project_logger.info(
            f"  node {listing['node']}: {listing['address']}, {listing['district']} "
            f"({listing['area']} m², {listing['type']})"
        )
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
    parser.add_argument('--dataset', choices=DATASETS, default='synthetic',
                        help="Instance source: synthetic generator, or real rental listings "
                             "(default: synthetic). The real catalog is a snapshot of a Brazilian "
                             "real estate company: "
                             "https://www.kaggle.com/datasets/maverickjpa/brazilian-real-estate-to-rent")
    parser.add_argument('--properties', type=int, default=5,
                        help="Number of properties in the instance (default: 5)")
    parser.add_argument('--seed', type=int, default=42,
                        help="Seed of the sample and of the hidden schedule (default: 42)")
    parser.add_argument('--catalog-path', default=None,
                        help="CSV of real listings when --dataset real. Defaults to data/real.csv, "
                             "the cleaned catalog. data/raw_real.csv.gz, the original export, is "
                             "accepted and cleaned the same way.")
    parser.add_argument('--city', default=None,
                        help="City kept when --dataset real. Required. A broker does not travel to another city.")
    parser.add_argument('--neighborhood', default=None,
                        help="Neighborhood kept when --dataset real. Required. "
                             "Only this neighborhood is sent to the solver.")
    parser.add_argument('--brokers', default=None,
                        help="Brokers of the instance, from m2 onwards: a positive integer, or "
                             f"'{AUTO_BROKERS}' to size the fleet from the visits (default: the model's setting)")
    args = parser.parse_args()
    if args.dataset == "real" and (not args.city or not args.neighborhood):
        parser.error("--dataset real requires --city and --neighborhood")
    brokers = args.brokers
    if brokers is not None and brokers != AUTO_BROKERS:
        if not brokers.isdigit() or int(brokers) < 1:
            parser.error(f"--brokers must be a positive integer or '{AUTO_BROKERS}'")
        brokers = int(brokers)
    if brokers is not None and args.model in ('m0', 'm1'):
        parser.error(f"--brokers applies from m2 onwards; {args.model} routes a single broker")
    main(args.model, dataset=args.dataset, num_properties=args.properties, random_seed=args.seed,
         catalog_path=args.catalog_path, city=args.city, neighborhood=args.neighborhood, num_brokers=brokers)
