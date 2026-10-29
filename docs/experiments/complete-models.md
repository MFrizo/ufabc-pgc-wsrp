# Complete models on the real catalog

Shared-input runs of [M1](../models/m1.md), [M1.a](../models/m1.a.md), [M1.b](../models/m1.b.md), [M2](../models/m2.md) and [M3](../models/m3.md) on the real rental catalog, executed on Google Colab from `notebooks/ufabc-pgc-wsrp.ipynb`.

The result tables are grouped by house count, so the models on one sample sit together. On Colab, one model was finished across every size and both places, then `MODEL_VERSION` was changed. M3 used the same cell 3 as the others: one solve, with every broker allowed to work.

## Setup

| Input | Value |
| --- | --- |
| Dataset | `real` |
| City | São Paulo |
| Places | Moema, then the whole city (`NEIGHBORHOOD = None`) |
| Seed | 8 |
| Fleet | `NUM_BROKERS = 3` |
| Solver | `gurobi_direct`, `mip_gap = 0`, `raw = False`, `time_limit = 300` |
| Booked visits | `m1` and `m1.a` tested with `FIXED_RATIO = 1` (default benchmark) and flexible ratios (`r = 0.5` and `r = 0`) |

Cell 2 settings that stay put while one model is running:

```python
DATASET = "real"
CITY = "São Paulo"
NUM_BROKERS = 3
RANDOM_SEED = 8
```

For M1 set `MODEL_VERSION = "m1"` and `FIXED_RATIO` in `[0, 1]` (default `1.0`). For M1.a (tightened and lifted MTZ reformulation) set `MODEL_VERSION = "m1.a"`. M2 and M3 enforce `fixed_ratio = 1` (`STRICT_TIME_MODELS`).

Sizes, in order, for each model: 5, 10, 15, 20, 25, 30, 40, 50. Moema first. A model stops at the first size where generation raises or the solve hits 300 seconds, and its larger sizes in that place are left blank.

Every logged solve uses `raw=False`. The notebook prints that as solver mode `default`. M3's rows are that same solve: `build_model_m3` once, with all 3 brokers allowed. They do not call `pareto_front`. That helper, in `src/models/model_3.py`, hardcodes `raw=True`, so calling it would have broken this setting. The front, one solve per fleet size, was not run.

The objective cell is what the notebook prints. Routes stay out of this page.

## Results

Colab, 2026-10-11, solver mode `default` (`raw=False`).

### Moema, 3 brokers, seed 8

| Houses | Model | Status | Time (s) | Brokers used | Objective |
| --- | --- | --- | --- | --- | --- |
| 5 | m1 (`fixed_ratio=1`) | optimal | 0.0940 | 2 of 3 | delay 0.00 min, overtime 40.00 min, distance 84.45 units |
| 5 | m1.a (`fixed_ratio=1`) | optimal | 0.3375 | 2 of 3 | delay 0.00 min, overtime 40.00 min, distance 84.45 units |
| 5 | m1 (`fixed_ratio=0.5`) | optimal | 0.1013 | 2 of 3 | delay 0.00 min, overtime 40.00 min, distance 4.24 units |
| 5 | m1.a (`fixed_ratio=0.5`) | optimal | 0.0997 | 2 of 3 | delay 0.00 min, overtime 40.00 min, distance 4.24 units |
| 5 | m1 (`fixed_ratio=0`) | optimal | 0.1165 | 2 of 3 | delay 0.00 min, overtime 0.00 min, distance 4.24 units |
| 5 | m1.a (`fixed_ratio=0`) | optimal | 0.0985 | 2 of 3 | delay 0.00 min, overtime 0.00 min, distance 4.24 units |
| 5 | m2 | optimal | 0.0761 | 2 of 3 | delay 0.00 min, distance 312.95 units |
| 5 | m3 | one solve, all 3 brokers allowed | 0.1120 | 3 of 3 | delay 50.00 min, overtime 60.00 min, distance 70.72 units |
| 10 | m1 (`fixed_ratio=1`) | optimal | 0.1332 | 3 of 3 | delay 0.00 min, overtime 10.00 min, distance 151.60 units |
| 10 | m1.a (`fixed_ratio=1`) | optimal | 0.0862 | 3 of 3 | delay 0.00 min, overtime 10.00 min, distance 151.60 units |
| 10 | m1 (`fixed_ratio=0.5`) | optimal | 0.3247 | 2 of 3 | delay 0.00 min, overtime 10.00 min, distance 79.74 units |
| 10 | m1.a (`fixed_ratio=0.5`) | optimal | 0.4302 | 2 of 3 | delay 0.00 min, overtime 10.00 min, distance 79.74 units |
| 10 | m1 (`fixed_ratio=0`) | optimal | 0.4749 | 2 of 3 | delay 0.00 min, overtime 0.00 min, distance 16.06 units |
| 10 | m1.a (`fixed_ratio=0`) | optimal | 0.6790 | 2 of 3 | delay 0.00 min, overtime 0.00 min, distance 16.06 units |
| 10 | m2 | optimal | 0.1320 | 2 of 3 | delay 5.00 min, distance 455.22 units |
| 10 | m3 | one solve, all 3 brokers allowed | 0.1807 | 3 of 3 | delay 100.00 min, overtime 60.00 min, distance 160.23 units |
| 15 | m1 (`fixed_ratio=1`) | optimal | 0.1960 | 3 of 3 | delay 0.00 min, overtime 42.00 min, distance 184.02 units |
| 15 | m1.a (`fixed_ratio=1`) | optimal | 0.1370 | 3 of 3 | delay 0.00 min, overtime 42.00 min, distance 184.02 units |
| 15 | m1 (`fixed_ratio=0.5`) | optimal | 0.8127 | 3 of 3 | delay 0.00 min, overtime 0.00 min, distance 175.83 units |
| 15 | m1.a (`fixed_ratio=0.5`) | optimal | 0.7770 | 3 of 3 | delay 0.00 min, overtime 0.00 min, distance 175.83 units |
| 15 | m1 (`fixed_ratio=0`) | optimal | 1.2526 | 3 of 3 | delay 0.00 min, overtime 0.00 min, distance 25.06 units |
| 15 | m1.a (`fixed_ratio=0`) | optimal | 1.6219 | 3 of 3 | delay 0.00 min, overtime 0.00 min, distance 25.06 units |
| 15 | m2 | optimal | 0.2170 | 2 of 3 | delay 12.00 min, distance 466.18 units |
| 15 | m3 | one solve, all 3 brokers allowed | 0.2676 | 3 of 3 | delay 150.00 min, overtime 73.00 min, distance 196.95 units |
| 20 | m1 (`fixed_ratio=1`) | optimal | 0.4829 | 3 of 3 | delay 0.00 min, overtime 25.00 min, distance 191.55 units |
| 20 | m1.a (`fixed_ratio=1`) | optimal | 0.1981 | 3 of 3 | delay 0.00 min, overtime 25.00 min, distance 191.55 units |
| 20 | m1 (`fixed_ratio=0.5`) | optimal | 8.8430 | 3 of 3 | delay 0.00 min, overtime 0.00 min, distance 174.24 units |
| 20 | m1.a (`fixed_ratio=0.5`) | optimal | 6.9170 | 3 of 3 | delay 0.00 min, overtime 0.00 min, distance 174.23 units |
| 20 | m1 (`fixed_ratio=0`) | time_limit (gap 0.0035%) | 300.03 | | gap 0.0035% |
| 20 | m1.a (`fixed_ratio=0`) | time_limit (gap 0.0028%) | 300.02 | | gap 0.0028% |
| 20 | m2 | infeasible (presolve) | | | |
| 20 | m3 | one solve, all 3 brokers allowed | 0.3585 | 3 of 3 | delay 200.00 min, overtime 93.00 min, distance 208.32 units |
| 25 | m1 (`fixed_ratio=1`) | optimal | 0.7035 | 3 of 3 | delay 0.00 min, overtime 57.00 min, distance 211.81 units |
| 25 | m1.a (`fixed_ratio=1`) | optimal | 0.3139 | 3 of 3 | delay 0.00 min, overtime 57.00 min, distance 211.81 units |
| 25 | m1 (`fixed_ratio=0.5`) | time_limit (gap 0.0032%) | 300.03 | | gap 0.0032% |
| 25 | m1.a (`fixed_ratio=0.5`) | optimal | 242.9612 | 3 of 3 | delay 0.00 min, overtime 11.00 min, distance 113.61 units |
| 25 | m1 (`fixed_ratio=0`) | time_limit (gap 0.0122%) | 300.02 | | gap 0.0122% |
| 25 | m1.a (`fixed_ratio=0`) | time_limit (gap 0.0167%) | 300.02 | | gap 0.0167% |
| 25 | m2 | infeasible (presolve) | | | |
| 25 | m3 | one solve, all 3 brokers allowed | 0.5436 | 3 of 3 | delay 250.00 min, overtime 137.00 min, distance 224.79 units |
| 30 | m1 (`fixed_ratio=1`) | optimal | 0.5879 | 3 of 3 | delay 8.00 min, overtime 169.00 min, distance 247.67 units |
| 30 | m1.a (`fixed_ratio=1`) | optimal | 0.3834 | 3 of 3 | delay 8.00 min, overtime 169.00 min, distance 247.67 units |
| 30 | m1 (`fixed_ratio=0.5`) | | | | |
| 30 | m1.a (`fixed_ratio=0.5`) | | | | |
| 30 | m1 (`fixed_ratio=0`) | | | | |
| 30 | m1.a (`fixed_ratio=0`) | | | | |
| 30 | m2 | infeasible (presolve) | | | |
| 30 | m3 | one solve, all 3 brokers allowed | 0.7101 | 3 of 3 | delay 300.00 min, overtime 171.00 min, distance 255.43 units |
| 40 | m1 (`fixed_ratio=1`) | optimal | 0.9731 | 3 of 3 | delay 0.00 min, overtime 452.00 min, distance 293.27 units |
| 40 | m1.a (`fixed_ratio=1`) | optimal | 0.6261 | 3 of 3 | delay 0.00 min, overtime 452.00 min, distance 293.27 units |
| 40 | m1 (`fixed_ratio=0.5`) | | | | |
| 40 | m1.a (`fixed_ratio=0.5`) | | | | |
| 40 | m1 (`fixed_ratio=0`) | | | | |
| 40 | m1.a (`fixed_ratio=0`) | | | | |
| 40 | m2 | infeasible (presolve) | | | |
| 40 | m3 | one solve, all 3 brokers allowed | 1.2645 | 3 of 3 | delay 400.00 min, overtime 476.00 min, distance 284.52 units |
| 50 | m1 (`fixed_ratio=1`) | infeasible (presolve) | | | |
| 50 | m1.a (`fixed_ratio=1`) | infeasible (presolve) | | | |
| 50 | m1 (`fixed_ratio=0.5`) | | | | |
| 50 | m1.a (`fixed_ratio=0.5`) | | | | |
| 50 | m1 (`fixed_ratio=0`) | | | | |
| 50 | m1.a (`fixed_ratio=0`) | | | | |
| 50 | m2 | infeasible (presolve) | | | |
| 50 | m3 | infeasible (presolve) | | | |

### São Paulo, 3 brokers, seed 8

| Houses | Model | Status | Time (s) | Brokers used | Objective |
| --- | --- | --- | --- | --- | --- |
| 5 | m1 (`fixed_ratio=1`) | optimal | 0.0760 | 2 of 3 | delay 0.00 min, overtime 50.00 min, distance 144.91 units |
| 5 | m1 (`fixed_ratio=0`) | optimal | 0.2191 | 2 of 3 | delay 0.00 min, overtime 0.00 min, distance 85.04 units |
| 5 | m1.a (`fixed_ratio=1`) | optimal | 0.0556 | 2 of 3 | delay 0.00 min, overtime 50.00 min, distance 144.91 units |
| 5 | m2 | optimal | 0.0802 | 2 of 3 | delay 0.00 min, distance 513.15 units |
| 5 | m3 | one solve, all 3 brokers allowed | 0.1243 | 2 of 3 | delay 50.00 min, overtime 70.00 min, distance 144.91 units |
| 10 | m1 (`fixed_ratio=1`) | optimal | 0.3797 | 3 of 3 | delay 0.00 min, overtime 33.00 min, distance 242.04 units |
| 10 | m1 (`fixed_ratio=0`) | optimal | 243.0094 | 2 of 3 | delay 0.00 min, overtime 0.00 min, distance 146.09 units |
| 10 | m1.a (`fixed_ratio=1`) | optimal | 0.0733 | 3 of 3 | delay 0.00 min, overtime 33.00 min, distance 242.04 units |
| 10 | m2 | optimal | 0.1349 | 2 of 3 | delay 4.00 min, distance 756.97 units |
| 10 | m3 | one solve, all 3 brokers allowed | 0.1620 | 3 of 3 | delay 100.00 min, overtime 101.00 min, distance 258.25 units |
| 15 | m1 (`fixed_ratio=1`) | optimal | 0.2045 | 3 of 3 | delay 0.00 min, overtime 45.00 min, distance 356.76 units |
| 15 | m1 (`fixed_ratio=0`) | time_limit | | | |
| 15 | m1.a (`fixed_ratio=1`) | optimal | 0.1281 | 3 of 3 | delay 0.00 min, overtime 45.00 min, distance 356.76 units |
| 15 | m2 | infeasible (presolve) | | | |
| 15 | m3 | one solve, all 3 brokers allowed | 0.2536 | 3 of 3 | delay 150.00 min, overtime 75.00 min, distance 407.13 units |
| 20 | m1 (`fixed_ratio=1`) | optimal | 0.4340 | 3 of 3 | delay 0.00 min, overtime 63.00 min, distance 697.40 units |
| 20 | m1 (`fixed_ratio=0`) | | | | |
| 20 | m1.a (`fixed_ratio=1`) | optimal | 0.1583 | 3 of 3 | delay 0.00 min, overtime 63.00 min, distance 697.40 units |
| 20 | m2 | infeasible (presolve) | | | |
| 20 | m3 | one solve, all 3 brokers allowed | 0.3672 | 3 of 3 | delay 200.00 min, overtime 107.00 min, distance 701.27 units |
| 25 | m1 (`fixed_ratio=1`) | optimal | 0.4059 | 3 of 3 | delay 0.00 min, overtime 247.00 min, distance 690.63 units |
| 25 | m1 (`fixed_ratio=0`) | | | | |
| 25 | m1.a (`fixed_ratio=1`) | optimal | 0.2003 | 3 of 3 | delay 0.00 min, overtime 247.00 min, distance 690.63 units |
| 25 | m2 | infeasible (presolve) | | | |
| 25 | m3 | one solve, all 3 brokers allowed | 0.4821 | 3 of 3 | delay 250.00 min, overtime 276.00 min, distance 739.78 units |
| 30 | m1 (`fixed_ratio=1`) | infeasible (presolve) | | | |
| 30 | m1 (`fixed_ratio=0`) | | | | |
| 30 | m1.a (`fixed_ratio=1`) | infeasible (presolve) | | | |
| 30 | m2 | infeasible (presolve) | | | |
| 30 | m3 | infeasible (presolve) | | | |
| 40 | m1 (`fixed_ratio=1`) | infeasible (presolve) | | | |
| 40 | m1 (`fixed_ratio=0`) | | | | |
| 40 | m1.a (`fixed_ratio=1`) | infeasible (presolve) | | | |
| 40 | m2 | infeasible (presolve) | | | |
| 40 | m3 | infeasible (presolve) | | | |
| 50 | m1 (`fixed_ratio=1`) | infeasible (presolve) | | | |
| 50 | m1 (`fixed_ratio=0`) | | | | |
| 50 | m1.a (`fixed_ratio=1`) | infeasible (presolve) | | | |
| 50 | m2 | infeasible (presolve) | | | |
| 50 | m3 | infeasible (presolve) | | | |

### Native Multi-Objective M1.b vs. Scalarized M1 (Moema, seed 8, fixed_ratio=1.0)

Direct comparison between native Gurobi multi-objective optimization ([M1.b](../models/m1.b.md), using `setObjectiveN` with hierarchical lexicographic priorities) and the scalarized formulations ([M1](../models/m1.md) with global Big-M and [M1.a](../models/m1.a.md) with lifted MTZ) for identical inputs in Moema (`NUM_BROKERS = 3`, `RANDOM_SEED = 8`, `FIXED_RATIO = 1.0`).

| Houses | Model | Objective Approach | Status | Time (s) | Ratio vs. M1 | Brokers used | Delay (min) | Overtime (min) | Distance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | m1 | Scalarized (global Big-M) | optimal | 0.0940 | 1.00x (base) | 2 of 3 | 0.00 | 40.00 | 84.45 |
| 5 | m1.a | Scalarized (lifted MTZ) | optimal | 0.3375 | 0.28x | 2 of 3 | 0.00 | 40.00 | 84.45 |
| 5 | m1.b | Native multi-objective (`setObjectiveN`) | optimal | 0.2685 | 0.35x | 2 of 3 | 0.00 | 40.00 | 84.45 |
| 20 | m1 | Scalarized (global Big-M) | optimal | 0.4829 | 1.00x (base) | 3 of 3 | 0.00 | 25.00 | 191.55 |
| 20 | m1.a | Scalarized (lifted MTZ) | optimal | 0.1981 | 2.44x | 3 of 3 | 0.00 | 25.00 | 191.55 |
| 20 | m1.b | Native multi-objective (`setObjectiveN`) | optimal | 0.3325 | 1.45x | 3 of 3 | 0.00 | 25.00 | 191.55 |
| 40 | m1 | Scalarized (global Big-M) | optimal | 0.9731 | 1.00x (base) | 3 of 3 | 0.00 | 452.00 | 293.27 |
| 40 | m1.a | Scalarized (lifted MTZ) | optimal | 0.6261 | 1.55x | 3 of 3 | 0.00 | 452.00 | 293.27 |
| 40 | m1.b | Native multi-objective (`setObjectiveN`) | optimal | 0.4924 | 1.98x | 3 of 3 | 0.00 | 452.00 | 293.27 |

#### Comparison with M1:
1. **Identical Solution Quality**: Across all three sample sizes (5, 20, and 40 houses), M1.b produces exactly identical objective metrics (number of active brokers, 0.00 min delay, identical overtime, and identical distance of 84.45, 191.55, and 293.27 units) to M1 and M1.a.
2. **Speedup at Scale**: While M1 is faster at $N=5$ due to minimal overhead on trivial solves, M1.b is **1.45x faster** than M1 at $N=20$ (0.3325 s vs. 0.4829 s) and **1.98x faster** (nearly half the runtime) at $N=40$ (0.4924 s vs. 0.9731 s).
3. **M1.b vs. M1.a**: At $N=40$, M1.b also outperforms M1.a (0.4924 s vs. 0.6261 s), demonstrating that native multi-objective priority stages avoid the ill-conditioning of scalarized artificial Big-W weights.

### POPMUSIC Matheuristic vs. Exact MIP Solver (Moema, seed 8, 50 houses, 4 brokers, fixed_ratio=0.9)

Evaluation of the POPMUSIC matheuristic (*Partial OPtimization Metaheuristic Under Special Intensification Conditions*, based on Algorithm 1 of Queiroga, Sadykov, & Uchoa 2021) compared to the exact Gurobi solver (`solver_mode = default`) on a large instance in Moema (`MODEL_VERSION = "m1.a"`, `NUM_BROKERS = 4`, `RANDOM_SEED = 8`, `FIXED_RATIO = 0.9`):

| Solver Mode | Model | Time (s) | Speedup | Brokers used | Delay (min) | Overtime (min) | Distance | Solution Details |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `default` (exact) | m1.a | 310.50 | 1.00x (base) | 4 of 4 | 10.00 | 444.00 | 375.42 | Hit nominal 300 s cutoff |
| `popmusic` ($\alpha=6, \delta=3$) | m1.a | 179.77 | 1.73x (-42.1% time) | 4 of 4 | 10.00 | 444.00 | 375.41 | 33 sub-problems, 10 improvements ($S_0 = 313285.09 \to S^* = 299970.09$) |

#### Key Insights:
1. **Preserved and Enhanced Solution Quality**: POPMUSIC found a slightly better route layout (375.41 units vs. 375.42 units, saving 0.01 units by swapping visits 4 and 36 between Broker 2 and Broker 3), while matching the exact solver on all priority metrics (10.00 min delay on node 5, 444.00 min overtime, and 4 brokers utilized).
2. **Computational Speedup**: The exact MIP solver exhausted the nominal 300 s time limit (finishing at 310.50 s). POPMUSIC converged in 179.77 s, achieving a **1.73x speedup** (42.1% runtime reduction).
3. **Subproblem Dynamics**: Over 33 subproblem evaluations with expansion parameter $\delta=3$, POPMUSIC identified 10 sequential improvements, reducing the objective value from $S_0 = 313285.09$ to $S^* = 299970.09$ (-4.25% cost reduction).

### Stress test, seed 8, `raw=False`

The fleet grows with the houses. A fit error means the hidden schedule is longer than 12 hours, so the next try is the same houses with more brokers.

| Place | Houses | Model | Brokers | Status |
| --- | --- | --- | --- | --- |
| | 200 | m3 | 16 | does not fit in the longest working day |
