# Complete models on the real catalog

Shared-input runs of [M1](../models/m1.md), [M1.a](../models/m1.a.md), [M2](../models/m2.md) and [M3](../models/m3.md) on the real rental catalog, executed on Google Colab from `notebooks/ufabc-pgc-wsrp.ipynb`.

The result tables are grouped by house count, so the four models on one sample sit together. On Colab, one model was finished across every size and both places, then `MODEL_VERSION` was changed. M3 used the same cell 3 as the others: one solve, with every broker allowed to work.

## Setup

| Input | Value |
| --- | --- |
| Dataset | `real` |
| City | São Paulo |
| Places | Moema, then the whole city (`NEIGHBORHOOD = None`) |
| Seed | 8 |
| Fleet | `NUM_BROKERS = 3` |
| Solver | `gurobi_direct`, `mip_gap = 0`, `raw = False`, `time_limit = 300` |
| M1.a booked visits | `FIXED_RATIO = 0`, so no visit has a set time |

Cell 2 settings that stay put while one model is running:

```python
DATASET = "real"
CITY = "São Paulo"
NUM_BROKERS = 3
RANDOM_SEED = 8
```

For M1.a set `MODEL_VERSION = "m1.a"` and `FIXED_RATIO = 0`. M1, M2 and M3 ignore `FIXED_RATIO`.

Sizes, in order, for each model: 5, 10, 15, 20, 25, 30, 40, 50. Moema first. A model stops at the first size where generation raises or the solve hits 300 seconds, and its larger sizes in that place are left blank.

Every logged solve uses `raw=False`. The notebook prints that as solver mode `default`. M3's rows are that same solve: `build_model_m3` once, with all 3 brokers allowed. They do not call `pareto_front`. That helper, in `src/models/model_3.py`, hardcodes `raw=True`, so calling it would have broken this setting. The front, one solve per fleet size, was not run.

The objective cell is what the notebook prints. Routes stay out of this page.

## Results

Colab, 2026-10-11, solver mode `default` (`raw=False`).

### Moema, 3 brokers, seed 8

| Houses | Model | Status | Time (s) | Brokers used | Objective |
| --- | --- | --- | --- | --- | --- |
| 5 | m1 | optimal | 0.0830 | 2 of 3 | delay 0.00 min, overtime 40.00 min, distance 84.45 units |
| 5 | m1.a | optimal | 0.2264 | 2 of 3 | delay 0.00 min, overtime 0.00 min, distance 4.24 units |
| 5 | m2 | optimal | 0.1279 | 2 of 3 | delay 0.00 min, distance 312.95 units |
| 5 | m3 | one solve, all 3 brokers allowed | 0.1005 | 3 of 3 | delay 50.00 min, overtime 60.00 min, distance 70.72 units |
| 10 | m1 | optimal | 0.3673 | 3 of 3 | delay 0.00 min, overtime 10.00 min, distance 151.60 units |
| 10 | m1.a | time_limit | | | |
| 10 | m2 | optimal | 0.1449 | 2 of 3 | delay 5.00 min, distance 455.22 units |
| 10 | m3 | one solve, all 3 brokers allowed | 0.1850 | 3 of 3 | delay 100.00 min, overtime 60.00 min, distance 160.23 units |
| 15 | m1 | optimal | 0.2622 | 3 of 3 | delay 0.00 min, overtime 42.00 min, distance 184.02 units |
| 15 | m1.a | | | | |
| 15 | m2 | optimal | 0.2445 | 2 of 3 | delay 12.00 min, distance 466.18 units |
| 15 | m3 | one solve, all 3 brokers allowed | 0.2446 | 3 of 3 | delay 150.00 min, overtime 73.00 min, distance 196.95 units |
| 20 | m1 | optimal | 0.2952 | 3 of 3 | delay 0.00 min, overtime 25.00 min, distance 191.55 units |
| 20 | m1.a | | | | |
| 20 | m2 | does not fit in the shifts | | | |
| 20 | m3 | one solve, all 3 brokers allowed | 0.2473 | 3 of 3 | delay 200.00 min, overtime 93.00 min, distance 208.32 units |
| 25 | m1 | optimal | 0.4169 | 3 of 3 | delay 0.00 min, overtime 57.00 min, distance 211.81 units |
| 25 | m1.a | | | | |
| 25 | m2 | | | | |
| 25 | m3 | one solve, all 3 brokers allowed | 0.3551 | 3 of 3 | delay 250.00 min, overtime 137.00 min, distance 224.79 units |
| 30 | m1 | optimal | 0.7027 | 3 of 3 | delay 8.00 min, overtime 169.00 min, distance 247.67 units |
| 30 | m1.a | | | | |
| 30 | m2 | | | | |
| 30 | m3 | one solve, all 3 brokers allowed | 0.4233 | 3 of 3 | delay 300.00 min, overtime 171.00 min, distance 255.43 units |
| 40 | m1 | optimal | 0.9929 | 3 of 3 | delay 0.00 min, overtime 452.00 min, distance 293.27 units |
| 40 | m1.a | | | | |
| 40 | m2 | | | | |
| 40 | m3 | one solve, all 3 brokers allowed | 0.9598 | 3 of 3 | delay 400.00 min, overtime 476.00 min, distance 284.52 units |
| 50 | m1 | does not fit in 3 brokers | | | |
| 50 | m1.a | | | | |
| 50 | m2 | | | | |
| 50 | m3 | does not fit in 3 brokers | | | |

### São Paulo, 3 brokers, seed 8

| Houses | Model | Status | Time (s) | Brokers used | Objective |
| --- | --- | --- | --- | --- | --- |
| 5 | m1 | optimal | 0.0548 | 2 of 3 | delay 0.00 min, overtime 50.00 min, distance 144.91 units |
| 5 | m1.a | optimal | 0.2191 | 2 of 3 | delay 0.00 min, overtime 0.00 min, distance 85.04 units |
| 5 | m2 | optimal | 0.0979 | 2 of 3 | delay 0.00 min, distance 513.15 units |
| 5 | m3 | one solve, all 3 brokers allowed | 0.1159 | 2 of 3 | delay 50.00 min, overtime 72.00 min, distance 144.91 units |
| 10 | m1 | optimal | 0.0956 | 3 of 3 | delay 0.00 min, overtime 33.00 min, distance 242.04 units |
| 10 | m1.a | optimal | 243.0094 | 2 of 3 | delay 0.00 min, overtime 0.00 min, distance 146.09 units |
| 10 | m2 | optimal | 0.1239 | 2 of 3 | delay 4.00 min, distance 756.97 units |
| 10 | m3 | one solve, all 3 brokers allowed | 0.1282 | 3 of 3 | delay 100.00 min, overtime 101.00 min, distance 258.25 units |
| 15 | m1 | optimal | 0.1814 | 3 of 3 | delay 0.00 min, overtime 45.00 min, distance 356.76 units |
| 15 | m1.a | time_limit | | | |
| 15 | m2 | does not fit in the shifts | | | |
| 15 | m3 | one solve, all 3 brokers allowed | 0.2131 | 3 of 3 | delay 150.00 min, overtime 75.00 min, distance 407.13 units |
| 20 | m1 | optimal | 0.1740 | 3 of 3 | delay 0.00 min, overtime 63.00 min, distance 697.40 units |
| 20 | m1.a | | | | |
| 20 | m2 | | | | |
| 20 | m3 | one solve, all 3 brokers allowed | 0.3193 | 3 of 3 | delay 200.00 min, overtime 107.00 min, distance 701.27 units |
| 25 | m1 | optimal | 0.2682 | 3 of 3 | delay 0.00 min, overtime 247.00 min, distance 690.63 units |
| 25 | m1.a | | | | |
| 25 | m2 | | | | |
| 25 | m3 | one solve, all 3 brokers allowed | 0.5187 | 3 of 3 | delay 250.00 min, overtime 276.00 min, distance 739.78 units |
| 30 | m1 | does not fit in 3 brokers | | | |
| 30 | m1.a | | | | |
| 30 | m2 | | | | |
| 30 | m3 | does not fit in 3 brokers | | | |
| 40 | m1 | | | | |
| 40 | m1.a | | | | |
| 40 | m2 | | | | |
| 40 | m3 | | | | |
| 50 | m1 | | | | |
| 50 | m1.a | | | | |
| 50 | m2 | | | | |
| 50 | m3 | | | | |

### Stress test, seed 8, `raw=False`

The fleet grows with the houses. A fit error means the hidden schedule is longer than 12 hours, so the next try is the same houses with more brokers.

| Place | Houses | Model | Brokers | Status |
| --- | --- | --- | --- | --- |
| | 200 | m3 | 16 | does not fit in the longest working day |
