# WSRP model definitions

Mathematical definition of every model in `src/models/`, as implemented on `main`. Each page lists the model's sets, parameters, decision variables, objective function and constraints, and ends with the complete formulation.

| Model | Case | Problem class | Builds on | What it adds | Objective |
| --- | --- | --- | --- | --- | --- |
| [M0](m0.md) | 1 | TSP (MTZ) | — | One broker, one closed tour from the agency | Distance |
| [M1](m1.md) | 2 | TSPTW | M0 | Time windows, constant travel and service times; start times replace MTZ | Distance |
| [M2](m2.md) | 3 | VRPTW | M1 | Several brokers sharing the agency | Distance |
| [M3](m3.md) | 4 | SDVRPTW | M2 | Visits already assigned to a broker | Distance |
| [M4](m4.md) | 5 | VRPTWWVST | M3 | A service time of its own for each visit | Distance |
| [M5](m5.md) | 6 | TDVRPTW | M4 | Travel time by the period of the day the trip leaves in | Time out of the agency |
| [M6](m6.md) | 7 | FSMVRPTW | M5 | Fleet minimization | Brokers, then time out of the agency |
| [M7](m7.md) | 8.a | MO-DOMDVRPTW-SD | M4–M6 | Brokers start at home, open routes, lunch break, soft windows, overtime, 12-hour days | Brokers, then distance, delay and overtime |
| [M8](m8.md) | 8.b | HC-DOMDVRPTW-SD | M7 | A morning and an afternoon shift per broker, lunch spot, days off, hard shift ends | Distance and delay |
| [M9](m9.md) | 8.a | MO-DOMDVRPTW-SD with flexible visits | M7 | Only a share of the visits booked; the others may start at any time of the day | Brokers, then distance, delay and overtime |

## Conventions shared by every model

- **Time** is in minutes from the start of the day, so $0$ is 08:00, $540$ is 17:00 and $600$ is 18:00.
- **Distances** $c_{ij}$ are Euclidean. The synthetic generator places the nodes on a $100 \times 100$ map, about 25 km across (4 units per km); real instances from `data/real.csv` are projected to the same scale (`src/core/listings.py`).
- **Travel times** come from the generator (`src/core/data_generator.py`):
  - M1–M4 use one constant travel time $T$ (default 30 minutes) for every trip.
  - M5 and M6 use the speed profile `RUSH_HOURS`: 1 unit/min from 08:00 to 10:00 and from 17:00, 2 units/min in between, so $t^p_{ij} = \lceil c_{ij} / v_p \rceil$.
  - M7, M8 and M9 use the single period `NORMAL_SPEED` of 2 units/min (about 30 km/h), so $t_{ij} = \lceil c_{ij} / 2 \rceil$.
- **Time windows** come from a hidden reference schedule that keeps every instance feasible. Within each broker's free time in that schedule, the start of each visit follows a continuous uniform distribution. A share `fixed_ratio` of the visits is booked at its reference start, so $e_i = l_i$. Every other visit is flexible and may start at any time that lets it end within the day: $e_i = 0$ and $l_i = \text{horizon} - s_i$. The agency's window is the whole day, $[0, \text{horizon}]$.
- **Booked visits:** M2 to M8 run with `fixed_ratio = 1.0`, so every visit is booked. M7 and M8 read the booked time as the scheduled start $h_i$, and ignore a `--fixed-ratio` given in `main.py` (`STRICT_TIME_MODELS`). M9 runs with `fixed_ratio = 0.5` and only gives the booked visits a scheduled start.
- **Subtours** are eliminated by MTZ order variables in M0 and by the start-time variables $w_i$ with Big-M time-flow constraints from M1 on.
- **Capacity:** no model has a vehicle capacity. What a route can serve is limited only by time (time windows, and the day length and shifts of M7, M8 and M9).
- **Constraint numbering** on these pages is per model, $(1), (2), \dots$. Each constraint also gives the name of its Pyomo component, which is the stable reference into the code. The `doc` labels in the code (`Constraint 4.1`, `Constraint 5.3`, …) follow an older numbering and differ between models.

## Instance settings

Each model runs on `generate_wsrp_instance` with its entry of `INSTANCE_SETTINGS` in `src/models/__init__.py` on top of the generator defaults: 5 properties, $T = 30$, $S = 60$, a 600-minute day, `fixed_ratio = 0.2` and 40% of the visits assigned to a broker. `--fixed-ratio` in `main.py` overrides the share of booked visits, except for M7 and M8. The settings of each model are listed on its page.
