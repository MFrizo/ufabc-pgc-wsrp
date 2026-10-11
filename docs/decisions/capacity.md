# Capacity

Decision on whether the complete models need a vehicle capacity, in the sense of the Capacitated Vehicle Routing Problem (CVRP). This note covers m1 and m2. m1 was M7 and m2 was M8 before the renumbering. m1.a copies m1's working-day limit, so the same wording covers it. No capacity constraint was added to the code. The other open decisions from the same discussion are in [Work in progress](wip.md).

## Decision

m1 and m2 do not get a load capacity. A broker showing a property carries nothing, so a demand $q_i$ has no meaning here. What a route can serve is already limited by time, and that is the scarce resource in the workforce scheduling and routing literature.

The models are described as **resource-constrained, with time as the resource**. They are not described as capacitated. In vehicle routing, "capacitated" means a load limit $\sum q_i \le Q$, and an examiner who reads that word will look for $Q$.

A cap on the number of visits per broker stays optional. It is added only if $Q_k$ comes from real data, such as how many showings a broker does in a day. With the $\pm 10$ minute windows around each booked visit, the clock already limits how many visits fit. A cap set above that limit never binds and changes nothing in the results.

## What already limits a route

Two jobs of the CVRP capacity constraint are already done by time.

1. **How much one route can serve.** Without some limit, a vehicle routing problem collapses into a multiple traveling salesman problem. m1 caps each broker's day at $J_{\max} = 720$ minutes, from leaving home to the end of the last visit (`day_length_rule` in `src/models/model_1.py`). That is a duration-constrained VRP (Laporte, Desrochers and Nobert, 1984). The regular end of the day $L_k$ is soft: time past it is overtime, penalized in the objective. Only $J_{\max}$ is hard. m2 limits each shift by its hard end $L_r$ (`shift_end_rule` in `src/models/model_2.py`): the last visit of the shift ends by $L_r$. Booked visits also sit in a window of $\pm 10$ minutes.
2. **Subtours.** In the load formulation of Miller–Tucker–Zemlin (Kulkarni and Bhave, 1985; Desrochers and Laporte, 1991), the load carried along the route is the ordering variable. Here the start times $w_i$ with the Big-M time-flow constraints do that job, as they have since m0.1.

## Why the literature does not ask for a load

Surveys of workforce scheduling and routing treat the worker's time as the scarce resource: working-time rules, breaks, shifts, skills and time windows (Castillo-Salazar, Landa-Silva and Qu, 2016; Paraskevopoulos, Laporte, Repoussis and Tarantilis, 2017). The same holds for home health care routing (Fikar and Hirsch, 2017; Cissé et al., 2017).

A physical load appears when the worker carries something. The usual example is a technician who must bring tools and spare parts (Kovacs, Parragh, Doerner and Hartl, 2012; Pillac, Gendreau, Guéret and Medaglia, 2013). That is a different problem from a broker opening a property.

## Why the names still raise the question

The canonical definitions behind several of the names used in this project include a capacity. An examiner can fairly ask where $Q$ is.

| Name in the project | What the literature includes | Reference |
| --- | --- | --- |
| VRPTW (m0.2 and later) | The CVRP plus time windows. The version without a capacity is an m-TSPTW | Solomon (1987); Toth and Vigo (2014) |
| Open routes (m1, m2) | The open VRP benchmarks have a capacity, and usually a maximum route length | Sariklis and Powell (2000); Li, Golden and Wasil (2007) |
| Multi-depot and site-dependent VRPTW | The standard benchmarks are capacitated | Cordeau and Laporte (2001); Cordeau, Laporte and Mercier (2001); Vidal, Crainic, Gendreau and Prins (2013) |
| FSMVRPTW (m0.6) | The "mix" is a choice of vehicle types that differ in capacity and cost | Golden, Assad, Levy and Gheysens (1984) |

m0.6 has identical brokers and no capacity, so it is a VRPTW with hierarchical fleet minimization: fewest brokers first, then the secondary criterion. That is Solomon's objective, not a fleet-size-and-mix problem. m1 has the same hierarchical shape, with travel time, delay and overtime in place of the secondary criterion.

## Options that were set aside

**State the omission in the text.** This is the option the thesis uses. Every model is the uncapacitated case, $Q_k \ge n$, and the 12-hour day in m1 and the hard shifts in m2 are the route-resource constraints.

**Add an optional visit cap.** Unit demand $q_i = 1$, so $Q_k$ is the most showings broker $k$ does in the day. The arcs are already indexed by broker (m1) or by shift (m2), so this is one knapsack inequality per route. No load-flow variables are needed, because $w_i$ already eliminates subtours. Setting $Q_k$ to infinity returns the models as they are.

- m1, for each broker $k$: $\sum_{i \in C} \sum_{j} x_{ijk} \le Q_k \, y_k$.
- m2, for each broker $k$, summed over both of his shifts $R_k$: $\sum_{r \in R_k} \sum_{i \in C} \sum_{j} x_{ijr} \le Q_k$.

On m1 the fleet term pushes the solver to load as many visits as possible onto each broker, so a cap is the realistic counterweight and gives the bin-packing bound $\lceil n / Q \rceil$ on the number of brokers. The factor $Q_k y_k$ also tightens the linear relaxation, which is weak because of the Big-M constraints. On m2 the same inequality would cap the number of visits. It is not implemented. m2 records the longest time a working broker is out and, unless a weight is given, uses it only to break a fuel tie. That is a different workload measure from a visit cap (Matl, Hartl and Vidal, 2018).

**Service time as the demand.** Setting $q_i = s_i$ repeats the duration constraints that are already in the model.

**Seats in the broker's car.** Driving the client between properties is a pickup-and-delivery problem (a dial-a-ride problem). It is outside the scope of these models.

## Wording for the thesis

> The models are not capacitated in the classical CVRP sense. How much each route can serve is limited by time constraints (working-day length and shift limits), so they belong to the duration-constrained / resource-constrained VRP family, in which time plays the role that load capacity plays in the CVRP.

## Where the analogy stops

In column generation for vehicle routing problems, the pricing subproblem is a shortest path problem with resource constraints (Irnich and Desaulniers, 2005). There, vehicle load and elapsed time are the same kind of object: a quantity that builds up along the route and stops at an upper bound.

- **Load in a CVRP.** Customer $i$ adds $q_i$, and the route total stays at most $Q$.
- **Time in m1.** Each visit adds service plus travel, $s_i + t_{ij}$. The day, from leaving home to the end of the last visit, stays at most $J_{\max}$.
- **Time in m2.** The same build-up, and the last visit of shift $r$ ends by $L_r$.

Time is a less tidy resource than load, and the thesis should say so.

- **It is not a plain sum.** Waiting for a time window makes the clock jump to the window opening. Load only adds up.
- **m1 limits a span, not a sum of demands.** The hard limit is the time from leaving home to the end of the last visit. The regular end $L_k$ is soft.
- **m2 has two limits per broker**, one for the morning shift and one for the afternoon shift, rather than a single daily capacity.

## What this claim does not cover

The reading behind this note is m1 and m2. m0.2 to m0.6 limit visits by time windows, and m0.5 and m0.6 also measure time out of the agency, but they have no $J_{\max}$ and no shift end. The sentence above is for m1, m1.a and m2.

## References

Castillo-Salazar, J. A., Landa-Silva, D., & Qu, R. (2016). Workforce scheduling and routing problems: Literature survey and computational study. *Annals of Operations Research*, 239(1), 39–67. https://doi.org/10.1007/s10479-014-1687-2

Cissé, M., Yalçındağ, S., Kergosien, Y., Şahin, E., Lenté, C., & Matta, A. (2017). OR problems related to home health care: A review of relevant routing and scheduling problems. *Operations Research for Health Care*, 13–14, 1–22. https://doi.org/10.1016/j.orhc.2017.06.001

Cordeau, J.-F., & Laporte, G. (2001). A tabu search algorithm for the site dependent vehicle routing problem with time windows. *INFOR: Information Systems and Operational Research*, 39(3), 292–298. https://doi.org/10.1080/03155986.2001.11732443

Cordeau, J.-F., Laporte, G., & Mercier, A. (2001). A unified tabu search heuristic for vehicle routing problems with time windows. *Journal of the Operational Research Society*, 52(8), 928–936. https://doi.org/10.1057/palgrave.jors.2601163

Desrochers, M., & Laporte, G. (1991). Improvements and extensions to the Miller-Tucker-Zemlin subtour elimination constraints. *Operations Research Letters*, 10(1), 27–36. https://doi.org/10.1016/0167-6377(91)90083-2

Fikar, C., & Hirsch, P. (2017). Home health care routing and scheduling: A review. *Computers & Operations Research*, 77, 86–95. https://doi.org/10.1016/j.cor.2016.07.019

Golden, B., Assad, A., Levy, L., & Gheysens, F. (1984). The fleet size and mix vehicle routing problem. *Computers & Operations Research*, 11(1), 49–66. https://doi.org/10.1016/0305-0548(84)90007-8

Irnich, S., & Desaulniers, G. (2005). Shortest path problems with resource constraints. In G. Desaulniers, J. Desrosiers, & M. M. Solomon (Eds.), *Column Generation* (pp. 33–65). Springer. https://doi.org/10.1007/0-387-25486-2_2

Kovacs, A. A., Parragh, S. N., Doerner, K. F., & Hartl, R. F. (2012). Adaptive large neighborhood search for service technician routing and scheduling problems. *Journal of Scheduling*, 15(5), 579–600. https://doi.org/10.1007/s10951-011-0246-9

Kulkarni, R. V., & Bhave, P. R. (1985). Integer programming formulations of vehicle routing problems. *European Journal of Operational Research*, 20(1), 58–67. https://doi.org/10.1016/0377-2217(85)90284-X

Laporte, G., Desrochers, M., & Nobert, Y. (1984). Two exact algorithms for the distance-constrained vehicle routing problem. *Networks*, 14(1), 161–172. https://doi.org/10.1002/net.3230140113

Li, F., Golden, B., & Wasil, E. (2007). The open vehicle routing problem: Algorithms, large-scale test problems, and computational results. *Computers & Operations Research*, 34(10), 2918–2930. https://doi.org/10.1016/j.cor.2005.11.018

Matl, P., Hartl, R. F., & Vidal, T. (2018). Workload equity in vehicle routing problems: A survey and analysis. *Transportation Science*, 52(2), 239–260. https://doi.org/10.1287/trsc.2017.0744

Paraskevopoulos, D. C., Laporte, G., Repoussis, P. P., & Tarantilis, C. D. (2017). Resource constrained routing and scheduling: Review and research prospects. *European Journal of Operational Research*, 263(3), 737–754. https://doi.org/10.1016/j.ejor.2017.05.035

Pillac, V., Gendreau, M., Guéret, C., & Medaglia, A. L. (2013). A review of dynamic vehicle routing problems. *European Journal of Operational Research*, 225(1), 1–11. https://doi.org/10.1016/j.ejor.2012.08.015

Sariklis, D., & Powell, S. (2000). A heuristic method for the open vehicle routing problem. *Journal of the Operational Research Society*, 51(5), 564–573. https://doi.org/10.1057/palgrave.jors.2600924

Solomon, M. M. (1987). Algorithms for the vehicle routing and scheduling problems with time window constraints. *Operations Research*, 35(2), 254–265. https://doi.org/10.1287/opre.35.2.254

Toth, P., & Vigo, D. (Eds.). (2014). *Vehicle routing: Problems, methods, and applications* (2nd ed.). SIAM. https://doi.org/10.1137/1.9781611973594

Vidal, T., Crainic, T. G., Gendreau, M., & Prins, C. (2013). A hybrid genetic algorithm for multidepot and periodic vehicle routing problems. *Operations Research*, 61(3), 745–758. https://doi.org/10.1287/opre.1120.1142
