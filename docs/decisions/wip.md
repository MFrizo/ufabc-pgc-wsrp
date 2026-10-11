# Work in progress

Open decisions from the same discussion as [Capacity](capacity.md). That note covers whether the models need a load capacity and whether they may be called capacitated. This note covers the rest. The street distances and travel times are implemented, in [Distances and travel times](travel.md). The rest of this note is not.

Names follow the renumbering. m1 was M7, m1.a was M9, m2 was M8, m0.5 was M5, and m0.6 was M6.

Two items from that discussion are already in the repository, so they are only recorded at the end:

- The formulations, one page per model, are in [docs/models](../models/README.md) (pull request #40).
- The renumbering is on `main` (pull request #41).

## Distance in the objective

The code stays as it is. The objective of m1, m1.a and m2 minimizes distance $c_{ij}$. On a synthetic instance that distance is the straight line times the detour factor. On a cached real instance it is the street-network distance. Travel time $t_{ij}$ is a separate parameter, used in the time-flow, window, shift and day-length constraints.

On a synthetic instance, and on a real instance with no cached duration, the generator sets $t_{ij} = \lceil c_{ij} / v \rceil$. Those three models run at one speed, `NORMAL_SPEED = [(0, 2.0)]`, about 30 km/h, so minimizing distance then gives the same routes as minimizing driving time, except for near-ties that the rounding can break differently. On a cached real instance the duration is a free-flow shortest path scaled by the midday congestion factor, and that path can differ from the shortest-distance path, so the two objectives already differ. The equivalence also fails as soon as speed depends on the time of day, which is why m0.5 and m0.6 minimize time out of the base directly.

The weak spot is units. The m1 and m1.a objectives add distance units to minutes of delay and overtime. m2 adds distance units to minutes of delay. A weight such as "a minute of delay costs 10" then means 10 distance units, which is hard to defend. Switching the travel term to $t_{ij}$ would put every term in minutes. That change was left for later. It is [What the objective should minimize](#what-the-objective-should-minimize), and it is not part of the street-network task.

## Realistic distances and times

This is implemented. The measurement, the congestion factors and the references are in [Distances and travel times](travel.md).

Live traffic, GPS traces and random travel times stay out of scope (Taş, Dellaert, van Woensel and de Kok, 2013). The street-network task does not switch the objective from distance to travel time.

## What the objective should minimize

Once the matrices can differ from a constant speed, shortest and fastest are different routes. The recommendation, not yet applied, is to minimize **travel time**.

Time-dependent routing minimizes travel time or route duration (Ichoua, Gendreau and Potvin, 2003; Gendreau, Ghiani and Guerriero, 2015). The constraints are already in minutes, and so are delay and overtime, so the weights become ratios. A minute of driving is a minute not spent on a showing, which holds for the agency's objective and for the broker's.

Distance comes back only as a **generalized cost**, as in the pollution-routing problem (Bektaş and Laporte, 2011):

$$
\text{travel cost}_{ij} = \alpha \, c_{ij} + \beta \, t_{ij}
$$

$\alpha$ is a real R$/km figure (fuel, or the mileage the agency reimburses) and $\beta$ is a real R$/min figure (an hourly cost for the broker). Kilometres are easier to justify on m2, where the broker drives his own car. If those two numbers cannot be taken from real data, do not put both terms in the objective with arbitrary weights. That would be a second trade-off, and it would need its own front. A small weight on distance, used only to break ties between routes of equal time, is acceptable.

In the code this is a small change on m1, m1.a and m2: the objective reads `travel_time` instead of `distance`, and the fleet weight of m1 and m1.a is computed from travel times. Making those three models time-dependent is the larger change. They currently read only the first period. Congestion factors would bring in the period-selection variables of m0.5, and with them the FIFO issue. Keeping one period, filled with free-flow or day-average street times, already improves on Euclidean distance at 30 km/h and leaves the models the same size. m0.5 and m0.6 remain the place where rush hours are shown.

Do this before the Pareto model below. Otherwise one axis mixes distance units with minutes.

## One solution for the agency and the brokers

A Pareto front is the right picture of a solution that serves both sides. It cannot be built from m1 and m2 as they stand, because the constraints differ, not only the objectives.

- **m1:** one open route from home, a virtual lunch node, a 12-hour cap, overtime charged as a penalty.
- **m2:** two shifts, lunch at a chosen spot, hard shift ends, days off.

A route that is feasible in one model can be infeasible in the other. The front needs one model whose feasible set is shared. The rules nobody negotiates stay as constraints: each visit served once, an already-assigned visit done by its broker, the time windows and their tolerance, the 12-hour day, and a lunch break. Each side's preferences become an objective.

- **Agency, $f_1$:** brokers used, travel time, and delay for the clients. This is the m1 objective, once the travel term is in minutes.
- **Brokers, $f_2$:** minutes outside the broker's own shifts, work on a day off, and distance from the lunch spot the broker picked. These are the m2 rules, made soft. m2 already charges the longest time a working broker is out, the min-max measure of Matl, Hartl and Vidal (2018). That term stays inside m2. It is not a substitute for this front, because m1 and m2 still do not share a feasible set.

Compute the front with the $\varepsilon$-constraint method. A weighted sum $\lambda f_1 + (1-\lambda) f_2$ only finds points on the convex hull of an integer front (Mavrotas, 2009). AUGMECON is the usual version of $\varepsilon$-constraint. The balanced box method is an exact alternative for two objectives (Boland, Charkhgard and Savelsbergh, 2015). Surveys of multi-objective routing and the closest applied front are Jozefowiez, Semet and Talbi (2008) and Braekers, Hartl, Parragh and Tricoire (2016). The home-care paper is the model for the chapter: a front between operating cost and the inconvenience of the people being served.

If $f_1$ leads with the number of brokers, that number takes few integer values, so one MILP per fleet size is enough:

$$
\min f_2 \quad \text{subject to} \quad \sum_k y_k \le m, \qquad m = 1, \dots, |K|
$$

That is at most $|K|$ solves, each about as hard as m1, with a small tie-breaking term on travel time. The smallest $m$ is close to m1's answer. The largest $m$ is close to m2's. Gurobi's `setObjectiveN` does not draw the front. It returns one lexicographic or blended point per run.

The front is a set of trade-offs. Picking one point is a separate decision. Three usual choices are the compromise point (closest to the ideal point, after normalizing), the knee (where a small loss on one side stops buying much on the other), and Nash bargaining (the product of each side's gain over its worst outcome). The front can also collapse to a single point when the instance is too loose to force a trade-off. That is a valid result, and it should be reported as such. Each point is a full MILP, so the instances stay small.

## Already written down

Writing the formulations showed two facts about the code that the thesis should not smooth over. Both are described on the model pages.

- In m1 and m1.a the arcs into and out of the virtual lunch node have zero distance and zero travel time. The trip across lunch is free, and if lunch is the first stop the trip from home is free.
- In m2 the morning arrival at the lunch spot and the afternoon departure are not linked by a time constraint. The shift end limits the last visit, not the trip to the shift's destination.

## References

Bektaş, T., & Laporte, G. (2011). The pollution-routing problem. *Transportation Research Part B: Methodological*, 45(8), 1232–1250. https://doi.org/10.1016/j.trb.2011.02.004

Boland, N., Charkhgard, H., & Savelsbergh, M. (2015). A criterion space search algorithm for biobjective integer programming: The balanced box method. *INFORMS Journal on Computing*, 27(4), 735–754. https://doi.org/10.1287/ijoc.2015.0657

Braekers, K., Hartl, R. F., Parragh, S. N., & Tricoire, F. (2016). A bi-objective home care scheduling problem: Analyzing the trade-off between costs and client inconvenience. *European Journal of Operational Research*, 248(2), 428–443. https://doi.org/10.1016/j.ejor.2015.07.028

Gendreau, M., Ghiani, G., & Guerriero, E. (2015). Time-dependent routing problems: A review. *Computers & Operations Research*, 64, 189–197. https://doi.org/10.1016/j.cor.2015.06.001

Ichoua, S., Gendreau, M., & Potvin, J.-Y. (2003). Vehicle dispatching with time-dependent travel times. *European Journal of Operational Research*, 144(2), 379–396. https://doi.org/10.1016/S0377-2217(02)00147-9

Jozefowiez, N., Semet, F., & Talbi, E.-G. (2008). Multi-objective vehicle routing problems. *European Journal of Operational Research*, 189(2), 293–309. https://doi.org/10.1016/j.ejor.2007.05.055

Matl, P., Hartl, R. F., & Vidal, T. (2018). Workload equity in vehicle routing problems: A survey and analysis. *Transportation Science*, 52(2), 239–260. https://doi.org/10.1287/trsc.2017.0744

Mavrotas, G. (2009). Effective implementation of the ε-constraint method in multi-objective mathematical programming problems. *Applied Mathematics and Computation*, 213(2), 455–465. https://doi.org/10.1016/j.amc.2009.03.037

Taş, D., Dellaert, N., van Woensel, T., & de Kok, T. (2013). Vehicle routing problem with stochastic travel times including soft time windows and service costs. *Computers & Operations Research*, 40(1), 214–224. https://doi.org/10.1016/j.cor.2012.06.008
