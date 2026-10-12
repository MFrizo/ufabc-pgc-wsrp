# WSRP model definitions

M0.0 to M0.6 are sub-steps. Each one adds one feature, and together they lead to M1, the first complete model: brokers leave home, routes are open, and the day has a lunch break, soft time windows, overtime and a 12-hour limit.

M1.a is a subcase of M1 in which only a share of the visits are booked. M2 is the broker-focused model: each broker works his own morning and afternoon shift. M3 is the Pareto front between the agency's objective and the brokers' objective, on M1's feasible set.

Each page lists the sets, parameters, decision variables, objective function and constraints of the model as implemented in `src/models/`, and ends with the complete formulation.

| Model | Role | Problem class | Builds on | What it adds | Objective |
| --- | --- | --- | --- | --- | --- |
| [M0.0](m0.0.md) | sub-step | TSP (MTZ) | — | One broker, one closed tour from the agency | Distance |
| [M0.1](m0.1.md) | sub-step | TSPTW | M0.0 | Time windows, constant travel and service times; start times replace MTZ | Distance |
| [M0.2](m0.2.md) | sub-step | VRPTW | M0.1 | Several brokers sharing the agency | Distance |
| [M0.3](m0.3.md) | sub-step | SDVRPTW | M0.2 | Visits already assigned to a broker | Distance |
| [M0.4](m0.4.md) | sub-step | VRPTWWVST | M0.3 | A service time of its own for each visit | Distance |
| [M0.5](m0.5.md) | sub-step | TDVRPTW | M0.4 | Travel time by the period of the day the trip leaves in | Time out of the agency |
| [M0.6](m0.6.md) | sub-step | FSMVRPTW | M0.5 | Fleet minimization | Brokers, then time out of the agency |
| [M1](m1.md) | first complete model | MO-DOMDVRPTW-SD | M0.4–M0.6 | Brokers start at home, open routes, lunch break, soft windows, overtime, 12-hour days | Brokers, then travel time, delay and overtime |
| [M1.a](m1.a.md) | subcase of M1 | MO-DOMDVRPTW-SD with flexible visits | M1 | Only a share of the visits booked; the others may start at any time of the day | Brokers, then travel time, delay and overtime |
| [M2](m2.md) | broker-focused model | HC-DOMDVRPTW-SD | M1 | A morning and an afternoon shift per broker, lunch spot, days off, hard shift ends | Fuel, then delay and the longest day |
| [M3](m3.md) | Pareto front | — | M1 | M1's routes, with the brokers' shifts and days off scored instead of enforced | One plan per fleet size: brokers' cost subject to at most $m$ brokers |

## Conventions shared by every model

- **Time** is in minutes from the start of the day, so $0$ is 08:00, $540$ is 17:00 and $600$ is 18:00.
- **Distances** $c_{ij}$ are in the generator's map units, 4 per kilometer, on the same $100 \times 100$ map (about 25 km across). Synthetic nodes keep a straight-line distance, multiplied by a detour factor: the median of road distance over straight-line distance on a fixed sample of listing pairs in Moema, São Paulo (`data/travel/detour_factor.json`). That sample has its own seed, so an instance seed does not redraw it, and the factor is the one measured in Moema for every synthetic map. A São Paulo instance uses the street-network distance instead: `data/travel/sao_paulo.json` indexes every unique listing coordinate, computed once with OSMnx on the OpenStreetMap drive network, so any sample of the city is covered, with or without a neighborhood. That matrix may be asymmetric. A real instance in any other city still uses the straight-line distance.
- **Travel times** come from the generator (`src/core/data_generator.py`):
  - M0.1–M0.4 use one constant travel time $T$ (default 30 minutes) for every trip.
  - A synthetic trip, and any trip with no cached duration, takes $t^p_{ij} = \lceil c_{ij} / v_p \rceil$ at the speed of the period it leaves in. M0.5 and M0.6 use `RUSH_HOURS`: 1 unit/min from 08:00 to 10:00 and from 17:00, 2 units/min in between. M1, M1.a, M2 and M3 use the single period `NORMAL_SPEED` of 2 units/min (about 30 km/h).
  - A cached real instance carries a free-flow duration for every street trip. M0.5 and M0.6 multiply it by the congestion factor of the departure period; M1, M1.a, M2 and M3, which have a single period, multiply it by the midday factor. The result is rounded up to a whole minute. The factors are weekday means from the TomTom Traffic Index 2025 for the São Paulo city center: 1.859 from 08:00 to 10:00 (85.9% extra time), 1.796 from 10:00 to 17:00 (79.6%) and 2.005 from 17:00 (100.5%). There, congestion level is the extra travel time versus free flow. Source: <https://www.tomtom.com/traffic-index/city/sao-paulo/>.
- Broker homes and lunch spots are drawn points, not cached listings. On a synthetic instance their distance uses the same detour factor. On a real instance it stays the straight-line distance, and that trip's travel time stays $\lceil c / v \rceil$.
- Live traffic, GPS traces and random travel times are left for later. The cached durations are free-flow shortest paths, scaled by the fixed factors above, so the same seed always builds the same MILP. The measurement and the references are in [Distances and travel times](../decisions/travel.md).
- **Time windows** come from a hidden reference schedule that keeps every instance feasible. Within each broker's free time in that schedule, the start of each visit follows a continuous uniform distribution. A share `fixed_ratio` of the visits is booked at its reference start, so $e_i = l_i$. Every other visit is flexible and may start at any time that lets it end within the day: $e_i = 0$ and $l_i = \text{horizon} - s_i$. The agency's window is the whole day, $[0, \text{horizon}]$.
- **Booked visits:** M0.2 to M0.6, M1, M2 and M3 run with `fixed_ratio = 1.0`, so every visit is booked. M1, M2 and M3 read the booked time as the scheduled start $h_i`, and ignore a `--fixed-ratio` given in `main.py` (`STRICT_TIME_MODELS`). M1.a runs with `fixed_ratio = 0.5` and only gives the booked visits a scheduled start.
- **Subtours** are eliminated by MTZ order variables in M0.0 and by the start-time variables $w_i$ with Big-M time-flow constraints from M0.1 on.
- **Capacity:** no model has a vehicle capacity. What a route can serve is limited only by time (time windows, and the day length and shifts of M1, M1.a, M2 and M3). The decision and the references are in [Capacity](../decisions/capacity.md).
- **Constraint numbering** on these pages is per model, $(1), (2), \dots$. Each constraint also gives the name of its Pyomo component, which is the stable reference into the code. The `doc` labels in the code (`Constraint 4.1`, `Constraint 5.3`, …) follow an older numbering and differ between models.

## Instance settings

Each model runs on `generate_wsrp_instance` with its entry of `INSTANCE_SETTINGS` in `src/models/__init__.py` on top of the generator defaults: 5 properties, $T = 30$, $S = 60$, a 600-minute day, `fixed_ratio = 0.2` and 40% of the visits assigned to a broker. `--fixed-ratio` in `main.py` overrides the share of booked visits, except for M1, M2 and M3. The settings of each model are listed on its page.

## Experiments

Shared-input runs of M1, M1.a, M2 and M3 on the real catalog, and the tables where those runs are logged, are in [Complete models on the real catalog](../experiments/complete-models.md).
