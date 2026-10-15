"""
Module: main
Description: Entrypoint script for local execution of the WSRP optimization pipeline
             on the Ubuntu environment. Orchestrates ingestion, modeling,
             solving, and parsing.

Usage:
    python main.py --model m0.0    # Sub-step: TSP
    python main.py --model m0.1    # Sub-step: TSPTW
    python main.py --model m0.2    # Sub-step: VRPTW
    python main.py --model m0.3    # Sub-step: SDVRPTW
    python main.py --model m0.4    # Sub-step: VRPTWWVST
    python main.py --model m0.5    # Sub-step: TDVRPTW
    python main.py --model m0.6    # Sub-step: FSMVRPTW
    python main.py --model m1      # Moema, 5 houses, 3 brokers, seed 8, gap 0, 30 min
    python main.py --model m1.a    # Same instance; the booked share stays the model's own
    python main.py --model m2      # Broker-focused model: HC-DOMDVRPTW-SD
    python main.py --model m3      # Pareto front of the agency and the brokers

    python main.py --properties 12 --brokers 4    # Custom instance size
    python main.py --brokers auto    # Fleet drawn from the instance
    python main.py --seed 7    # Another reproducible instance
    python main.py --neighborhood ""    # The whole city of São Paulo
    python main.py --dataset synthetic    # The generator instead of the catalog
    python main.py --no-hidden-schedule    # Booked starts drawn on their own; the instance may be infeasible
"""

import argparse
from typing import Optional, Union

from src.utils.logger import project_logger
from src.core.data_generator import AUTO_BROKERS
from src.core.listings import DATASETS, load_instance
from src.models import BUILDERS, DEFAULT_SEED, DEFAULT_SEEDS, INSTANCE_SETTINGS, SINGLE_BROKER_MODELS
from src.solvers.engine import solve_model
from src.utils.parsers import print_results


def main(model_version: str, num_properties: int = 5, num_brokers: Optional[Union[int, str]] = 3,
         dataset: str = "real", city: Optional[str] = "São Paulo", neighborhood: Optional[str] = "Moema",
         random_seed: Optional[int] = 8, fixed_ratio: Optional[float] = None,
         hidden_schedule: Optional[bool] = None):
    """
    Main execution pipeline for local development and benchmarking.

    Args:
        model_version (str): Model to execute, a key of src.models.BUILDERS (e.g. 'm0.0', 'm1', 'm1.a', 'm2', 'm3').
        num_properties (int): Number of properties to visit.
        num_brokers (Optional[Union[int, str]]): Number of brokers |K|, read from M0.2 onwards;
            m0.0 and m0.1 warn and ignore it. "auto" draws it between the fewest brokers the visits
            need and the most the solver can take. None keeps the model's own setting in
            src.models.INSTANCE_SETTINGS. The complete-model series uses 3.
        dataset (str): "real" for the rental catalog, "synthetic" for the generator.
        city (Optional[str]): City of the real listings. Required when dataset is "real".
        neighborhood (Optional[str]): Neighborhood of the real listings, inside that city. None
            samples the whole city. The series starts in Moema.
        random_seed (Optional[int]): Seed of the instance. None runs the model's default seed,
            src.models.DEFAULT_SEEDS or DEFAULT_SEED. The series uses 8.
        fixed_ratio (Optional[float]): Share of the visits with a strict start time, from 0 to 1;
            the others may start at any time of the day. m1, m2 and m3 warn and ignore it. None keeps
            the model's own setting.
        hidden_schedule (Optional[bool]): Whether the time windows come from a hidden reference day
            that keeps the instance feasible. False draws each booked start on its own and lets the
            solver receive an instance that may be infeasible. None keeps the generator default, on.
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
                                 fixed_ratio=fixed_ratio, hidden_schedule=hidden_schedule)
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
    if model_version == 'm3':
        from src.models.model_3 import pareto_front

        project_logger.info("PHASE 2: Pareto front, one MILP per fleet size...")
        front = pareto_front(data_payload)
        if not front:
            project_logger.error("No feasible fleet size.")
            return
        for point in front:
            project_logger.info(
                f"  {point['brokers']} broker(s): broker cost {point['broker_cost']:.1f} min, "
                f"travel {point['travel_time']:.0f} min, delay {point['delay']:.1f} min, "
                f"overtime {point['overtime']:.1f} min")
        return

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
        time_limit=1800,
        mip_gap=0.0,
        raw=False
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
    parser.add_argument('--model', choices=BUILDERS.keys(), default='m1',
                        help="Model to execute (default: m1, the first complete model)")
    parser.add_argument('--properties', type=int, default=5,
                        help="Number of properties to visit (default: 5)")
    parser.add_argument('--brokers', type=_brokers, default=3,
                        help="Number of brokers, read from M0.2 onwards (m0.0 and m0.1 warn and ignore it), or 'auto' "
                             "to draw it between the fewest the visits need and the most the solver takes "
                             "(default: 3)")
    parser.add_argument('--seed', type=int, default=8,
                        help="Seed of the instance; each seed is another reproducible instance (default: 8)")
    parser.add_argument('--fixed-ratio', type=_ratio, default=None,
                        help="Share of the visits with a strict start time, from 0 to 1, e.g. 0.3 for 30%%; the "
                             "others may start at any time of the day. Strict times follow a continuous uniform "
                             "distribution over each broker's free time. m1, m2 and m3 book every visit, so they warn "
                             "and ignore it; m1.a is m1 with this share of the visits booked (default: the model's "
                             "own setting)")
    parser.add_argument('--no-hidden-schedule', action='store_true',
                        help="Draw each booked start on its own, without the feasible reference day, "
                             "so the solver may receive an infeasible instance (default: the hidden schedule is on)")
    parser.add_argument('--dataset', choices=DATASETS, default='real',
                        help="Instance source: the real rental catalog of a Brazilian real estate company, "
                             "or the synthetic generator (default: real)")
    parser.add_argument('--city', default='São Paulo',
                        help="City of the real listings. Required with --dataset real (default: São Paulo)")
    parser.add_argument('--neighborhood', default='Moema',
                        help="Neighborhood of the real listings, inside --city. An empty string samples the "
                             "whole city (default: Moema)")
    args = parser.parse_args()
    if args.dataset == 'real' and not args.city:
        parser.error("--dataset real requires --city")
    main(args.model, num_properties=args.properties, num_brokers=args.brokers, dataset=args.dataset,
         city=args.city, neighborhood=args.neighborhood, random_seed=args.seed, fixed_ratio=args.fixed_ratio,
         hidden_schedule=False if args.no_hidden_schedule else None)
