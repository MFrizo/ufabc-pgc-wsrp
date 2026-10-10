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
    python main.py --model m9 --fixed-ratio 0.25    # Case 8.a with flexible visits: a quarter of them booked

    python main.py --model m7 --properties 12 --brokers 4    # Custom instance size
    python main.py --model m7 --properties 12 --brokers auto    # Fleet drawn from the instance
    python main.py --model m7 --seed 7    # Another reproducible instance
    python main.py --model m2 --fixed-ratio 0.5    # Half the visits at a strict time, half at any time

    python main.py --model m7 --dataset real --city "São Paulo" --neighborhood Moema    # Real listings
    python main.py --model m7 --dataset real --city "São Paulo"    # Real listings of the whole city
"""

import argparse
from typing import Optional, Union

from src.utils.logger import project_logger
from src.core.data_generator import AUTO_BROKERS
from src.core.listings import DATASETS, load_instance
from src.models import BUILDERS, DEFAULT_SEED, DEFAULT_SEEDS, INSTANCE_SETTINGS, SINGLE_BROKER_MODELS
from src.solvers.engine import solve_model
from src.utils.parsers import print_results


def main(model_version: str, num_properties: int = 5, num_brokers: Optional[Union[int, str]] = None,
         dataset: str = "synthetic", city: Optional[str] = None, neighborhood: Optional[str] = None,
         random_seed: Optional[int] = None, fixed_ratio: Optional[float] = None):
    """
    Main execution pipeline for local development and benchmarking.

    Args:
        model_version (str): Model to execute, a key of src.models.BUILDERS (e.g. 'm0', 'm1', 'm2').
        num_properties (int): Number of properties to visit.
        num_brokers (Optional[Union[int, str]]): Number of brokers |K|, read from M2 onwards;
            m0 and m1 warn and ignore it. "auto" draws it between the fewest brokers the visits
            need and the most the solver can take. None keeps the model's own setting in
            src.models.INSTANCE_SETTINGS.
        dataset (str): "synthetic" for the generator, "real" for the real rental catalog.
        city (Optional[str]): City of the real listings. Required when dataset is "real".
        neighborhood (Optional[str]): Neighborhood of the real listings, inside that city. None
            samples the whole city.
        random_seed (Optional[int]): Seed of the instance. None runs the model's default seed,
            src.models.DEFAULT_SEEDS or DEFAULT_SEED.
        fixed_ratio (Optional[float]): Share of the visits with a strict start time, from 0 to 1;
            the others may start at any time of the day. m7 and m8 warn and ignore it. None keeps
            the model's own setting.
    """
    project_logger.info(f"Starting local WSRP optimization pipeline ({model_version}, {dataset})...")

    # ---------------------------------------------------------
    # PHASE 1: Data Ingestion
    # ---------------------------------------------------------
    if random_seed is None:
        random_seed = DEFAULT_SEEDS.get(model_version, DEFAULT_SEED)
    if model_version in SINGLE_BROKER_MODELS or num_brokers is None:
        brokers = INSTANCE_SETTINGS[model_version].get('num_brokers', 1)
    else:
        brokers = num_brokers
    project_logger.info(f"PHASE 1: Ingesting {dataset} dataset ({num_properties} properties + 1 Depot, "
                        f"{brokers} brokers, seed {random_seed})...")
    data_payload = load_instance(dataset, model_version, num_properties=num_properties, random_seed=random_seed,
                                 num_brokers=num_brokers, city=city, neighborhood=neighborhood,
                                 fixed_ratio=fixed_ratio)
    num_fixed = len(data_payload['fixed_visits'])
    project_logger.info(f"Visits: {num_fixed} at a strict time, {num_properties - num_fixed} at any time.")
    if 'schedule_brokers' in data_payload:
        project_logger.info(f"Fleet drawn: {data_payload['num_brokers']} brokers, between "
                            f"{data_payload['schedule_brokers']} (fewest the visits need) and "
                            f"{data_payload['max_brokers']} (most the solver takes).")
    for listing in data_payload.get('listings', []):
        project_logger.info(f"  node {listing['node']}: {listing['address']}, {listing['district']} "
                            f"({listing['area']:.0f} m², {listing['type']})")
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


def _brokers(value: str) -> Union[int, str]:
    """--brokers value: a positive integer, or AUTO_BROKERS."""
    if value == AUTO_BROKERS:
        return value
    if not value.isdigit() or int(value) < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer or '{AUTO_BROKERS}'")
    return int(value)


def _ratio(value: str) -> float:
    """--fixed-ratio value: a share from 0 to 1."""
    try:
        ratio = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number from 0 to 1") from None
    if not 0 <= ratio <= 1:
        raise argparse.ArgumentTypeError("must be a number from 0 to 1")
    return ratio


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WSRP optimization pipeline")
    parser.add_argument('--model', choices=BUILDERS.keys(), default='m7',
                        help="Model to execute (default: m7, Case 8.a)")
    parser.add_argument('--properties', type=int, default=5,
                        help="Number of properties to visit (default: 5)")
    parser.add_argument('--brokers', type=_brokers, default=None,
                        help="Number of brokers, read from M2 onwards (m0 and m1 warn and ignore it), or 'auto' "
                             "to draw it between the fewest the visits need and the most the solver takes "
                             "(default: the model's own setting)")
    parser.add_argument('--seed', type=int, default=None,
                        help=f"Seed of the instance; each seed is another reproducible instance "
                             f"(default: the model's own, {DEFAULT_SEED}, or "
                             + ", ".join(f"{seed} for {model}" for model, seed in DEFAULT_SEEDS.items()) + ")")
    parser.add_argument('--fixed-ratio', type=_ratio, default=None,
                        help="Share of the visits with a strict start time, from 0 to 1, e.g. 0.3 for 30%%; the "
                             "others may start at any time of the day. Strict times follow a continuous uniform "
                             "distribution over each broker's free time. m7 and m8 book every visit, so they warn "
                             "and ignore it; m9 is m7 with this share of the visits booked (default: the model's "
                             "own setting)")
    parser.add_argument('--dataset', choices=DATASETS, default='synthetic',
                        help="Instance source: the synthetic generator, or the real rental catalog of a "
                             "Brazilian real estate company (default: synthetic)")
    parser.add_argument('--city', default=None,
                        help="City of the real listings. Required with --dataset real")
    parser.add_argument('--neighborhood', default=None,
                        help="Neighborhood of the real listings, inside --city (default: the whole city)")
    args = parser.parse_args()
    if args.dataset == 'real' and not args.city:
        parser.error("--dataset real requires --city")
    main(args.model, num_properties=args.properties, num_brokers=args.brokers, dataset=args.dataset,
         city=args.city, neighborhood=args.neighborhood, random_seed=args.seed, fixed_ratio=args.fixed_ratio)
