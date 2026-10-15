# Distances and travel times

This note records how $c_{ij}$ and $t_{ij}$ are built. The matrices are fixed before the MILP is written, so a seed still rebuilds the same model with no network call. M1 and M1.a minimize travel time, with distance only as a tie-break. M2 minimizes the fuel on that distance, as on its model page.

The code is `src/core/travel.py` and the generator in `src/core/data_generator.py`. The numbers that the solver reads are `data/travel/detour_factor.json` and `data/travel/sao_paulo.json` (the matrix is `data/travel/sao_paulo.npz`). The shared conventions are on the [model pages](../models/README.md).

## Decision

A São Paulo instance uses a street-network distance and a free-flow duration, both shortest paths on the OpenStreetMap drive network. The duration is then scaled by a congestion factor for the period the trip leaves in. A synthetic instance keeps the straight-line distance and multiplies it by one detour factor, measured on real listings. Models that have no speed profile keep one constant travel time.

## Why the matrices are fixed

The MILP has to be the same model every time a seed is run. A live routes API, a GPS trace, or a draw of the travel time would change $c_{ij}$ or $t_{ij}$ between runs, and the solver would be solving a different instance. OpenStreetMap itself changes, so the committed index is the snapshot. Rebuilding the cache can change the numbers. The instance seed does not.

## Real instances

The network is the OpenStreetMap drive graph, downloaded with OSMnx 2.1.1 on 10 October 2026 (Boeing, 2017). The map data are © OpenStreetMap contributors. Each listing and the agency are snapped to the nearest graph node. A snap farther than 400 m is refused. The distance is the shortest-path length in meters. The duration is the shortest path under free-flow travel time in seconds. The two weights can pick different paths.

The graph is directed, and the models already solve it that way. The arc from $i$ to $j$ is a different variable from the arc back. The objective and the clock read $c_{ij}$ and $t_{ij}$ of the direction that is travelled. A one-way street makes those two numbers differ, and both directions are stored. If no drive path runs from $i$ to $j$, only that crossing is fixed at zero. The return remains an arc when a path exists. A synthetic map still has equal directions, because its distance is the straight line times the detour factor. Broker homes and lunch spots are drawn points, so those legs stay straight-line in both directions.

Meters become the generator's map units, 4 per kilometer, rounded to two decimals, so a street distance sits on the same $100 \times 100$ map as a synthetic one. Seconds become minutes, rounded to four decimals, and the MILP then sees a whole number of minutes.

The index holds every unique São Paulo listing coordinate, rounded to six decimals. There are 6,874 listings and 3,354 distinct coordinates. A sample uses the index when each of its houses is one of those coordinates, whether or not a neighborhood was set. House-to-house values are the stored shortest paths. The agency is the centroid of the sampled houses, so it is not a listing: its trips are shortest paths on the same drive graph, from the centroid's nearest node, computed when the instance is built. The graph is the bounding box of every São Paulo listing, padded by 0.03°.

13,406 directed pairs have no drive path. They are not arcs: the model fixes that crossing at zero, and it is not given a substitute distance. A listing in any other city is not in the index. That instance keeps the straight-line distance, and its travel time stays $\lceil c_{ij} / v \rceil$.

Those 13,406 pairs are the trips out of four listings. The drive graph is directed, so one-way streets split it into strongly connected pieces even though the city is one continuous street network. The largest piece holds 191,489 of 191,955 intersections. Three of the listings snap to a 15-intersection pocket in the west of the city (about −23.62, −46.72) whose one-way streets do not lead back out. The fourth snaps to a single intersection with no outgoing drive edge (about −23.56, −46.60). The rest of the city can still drive in. Nothing drives out, including through another listing, because no mapped drive edge leaves the pocket. An open route can end at that house. A route that has to leave it has no feasible arc.

Broker homes and lunch spots are random points inside the city hull, not catalog listings, so they are not in the matrix. On a real instance their distance stays the straight line.

## Free-flow duration and the congestion factors

OSMnx sets each edge speed from the posted `maxspeed` tag. Where that tag is missing it uses its default for the highway type. Travel time is length divided by that speed. It is a free-flow time, not a measured one.

Congestion is taken from the TomTom Traffic Index 2025 page for São Paulo, the city-center hourly series (`weekHourData.center`), not the metropolitan series. TomTom's congestion level is the extra travel time versus free flow, so the multiplier is $1 + c/100$. The figure used for a model period is the Monday–Friday mean of the hours inside that period, rounded to one decimal before the multiplier is formed:

| Departure | Hours averaged | Mean congestion | Factor |
| --- | --- | --- | --- |
| 08:00–10:00 | 8 and 9 | 85.91% → 85.9% | 1.859 |
| 10:00–17:00 | 10 through 16 | 79.59% → 79.6% | 1.796 |
| from 17:00 | 17 and 18 | 100.52% → 100.5% | 2.005 |

The evening factor is the mean of 17:00–19:00, and it applies to the whole period that starts at 17:00. The same page publishes a morning peak of 88.2% at 09:00, an evening peak of 102.6% at 18:00, and a city average of 58.5%. Those are single hours or a year that includes the night. The factors are the means of the hours the model periods cover. The profile is São Paulo only. Source: <https://www.tomtom.com/traffic-index/city/sao-paulo/>.

M0.5 and M0.6 multiply the free-flow minutes by the factor of the departure period and round up. A zero duration stays zero. M1, M1.a and M2 have one period, `NORMAL_SPEED` at 2 units per minute, which is the middle speed of `RUSH_HOURS`. They use the midday factor, 1.796, for the same reason.

M0.1 through M0.4 have no speed profile. They keep the constant $T$ of 30 minutes on every trip, including a cached real instance.

## Synthetic instances

A point on the $100 \times 100$ map is not a street address, so there is no path to compute. The distance is the straight line times one detour factor, rounded to two decimals.

The factor is the median of directed road meters over straight-line meters. The sample is 24 unordered pairs of distinct Moema coordinates, both directions, so 48 ratios. The draw uses seed `20261010`, which is not an instance seed, so it does not move the coordinate stream. The straight line is the equirectangular distance in meters at the pair's midpoint latitude, with the catalog constants of 110.574 km per degree of latitude and 111.320 km per degree of longitude, rounded to 0.1 m. A pair whose straight line is under 30 m, or whose route fails, is dropped. None of the 48 were dropped. The median, rounded to four decimals, is **1.3671**.

That number is the generator's factor on every synthetic map, including homes and lunch spots. It is data in `detour_factor.json`, not a constant typed into the generator and not a draw from the instance RNG. The same seed still places the nodes in the same coordinates. Distances change, and the time windows change with them, because travel time is $\lceil c_{ij} / v \rceil$ on the new distance.

Two published ratios are the check, not the value that was coded. Ballou, Rahardja and Sakai (2002) report an average circuity of 1.23 for Brazil, from 120 sampled points, with a standard deviation of 0.11. That sample is a national road network, not trips inside one neighborhood. Boscoe, Henry and Zdeb (2012) regress driving distance on straight-line distance, through the origin, for trips to community hospitals across the United States. The slope, which they call the detour index, is 1.417, with $r^2 = 0.94$. The measured Moema median sits between those two.

## FIFO

M0.5 and M0.6 store one travel time per departure period. The time is a step function of the minute the trip leaves, which is the model of Malandraki and Daskin (1992). A step down at a period boundary can make a later departure arrive earlier. That breaks first-in, first-out.

Ichoua, Gendreau and Potvin (2003) keep the speed constant inside a period and integrate it along the trip, so the travel time is affine in the exact departure minute and FIFO holds. Using that form changes the coefficient of the departure time in the three time-flow inequalities, which M0.6 inherits. It does not fit the current formulation without a rewrite, so it is not implemented.

With these São Paulo factors the step that can break FIFO is the morning period into midday, 1.859 down to 1.796. The evening factor, 2.005, is higher than midday, so that boundary does not.

## What was left out

Live traffic, GPS traces and a random travel time are future work. A stochastic travel time of the kind in Taş, Dellaert, van Woensel and de Kok (2013) is the reference for that paragraph. The cached durations stay free-flow shortest paths times the three factors above.

M0.0 through M0.4 minimize distance. M0.5 minimizes time out of the agency, and M0.6 the fleet and then that time. M1 and M1.a minimize travel time, with a distance weight too small to outweigh one minute of driving. M2 minimizes fuel, priced from the distance.

## What the thesis can claim

A São Paulo instance is routed on the OpenStreetMap drive network of the city's listings, with free-flow times scaled by weekday congestion for São Paulo. Any sample of those listings is covered. A synthetic instance uses a detour factor measured on the same network, checked against the published circuity ratios, and the factor is fixed for a seed. The models do not query a map, and they do not draw the travel time.

## Options that were set aside

- **Self-hosted OSRM** (Luxen and Vetter, 2011) on an OpenStreetMap extract. It returns the same kind of shortest path. It also needs a routing server and a PBF extract for a matrix the MILP only reads as numbers. OSMnx computes those numbers in Python, and the solver never imports it.
- **The public OSRM demo server.** It is not a fixed snapshot, and it is not meant for repeated matrix builds.
- **A one-off calibration against a commercial routes API.** The congestion factors come from a published index instead, so the multiplier can be recomputed from the page.
- **Copying 1.23 or 1.417 into the generator.** Both describe other networks. The factor in the cache is the median measured on the Moema pairs.
- **The FIFO travel-time function of Ichoua, Gendreau and Potvin (2003).** It changes the time-flow constraints. The step function stays, and the thesis should say where FIFO can fail.

## References

Ballou, R. H., Rahardja, H., & Sakai, N. (2002). Selected country circuity factors for road travel distance estimation. *Transportation Research Part A: Policy and Practice*, 36(9), 843–848. https://doi.org/10.1016/S0965-8564(01)00044-1

Boeing, G. (2017). OSMnx: New methods for acquiring, constructing, analyzing, and visualizing complex street networks. *Computers, Environment and Urban Systems*, 65, 126–139. https://doi.org/10.1016/j.compenvurbsys.2017.05.004

Boscoe, F. P., Henry, K. A., & Zdeb, M. S. (2012). A nationwide comparison of driving distance versus straight-line distance to hospitals. *The Professional Geographer*, 64(2), 188–196. https://doi.org/10.1080/00330124.2011.583586

Ichoua, S., Gendreau, M., & Potvin, J.-Y. (2003). Vehicle dispatching with time-dependent travel times. *European Journal of Operational Research*, 144(2), 379–396. https://doi.org/10.1016/S0377-2217(02)00147-9

Luxen, D., & Vetter, C. (2011). Real-time routing with OpenStreetMap data. In *Proceedings of the 19th ACM SIGSPATIAL International Conference on Advances in Geographic Information Systems* (pp. 513–516). https://doi.org/10.1145/2093973.2094062

Malandraki, C., & Daskin, M. S. (1992). Time dependent vehicle routing problems: Formulations, properties and heuristic algorithms. *Transportation Science*, 26(3), 185–200. https://doi.org/10.1287/trsc.26.3.185

OpenStreetMap contributors. (2026). *OpenStreetMap*. Retrieved 10 October 2026, from https://www.openstreetmap.org/copyright

Taş, D., Dellaert, N., van Woensel, T., & de Kok, T. (2013). Vehicle routing problem with stochastic travel times including soft time windows and service costs. *Computers & Operations Research*, 40(1), 214–224. https://doi.org/10.1016/j.cor.2012.06.008

TomTom. (2025). *São Paulo traffic report*. TomTom Traffic Index. https://www.tomtom.com/traffic-index/city/sao-paulo/
