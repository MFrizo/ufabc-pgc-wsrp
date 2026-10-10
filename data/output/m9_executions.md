# M9 Executions: Fixed Ratio Benchmark

How the share of booked visits weighs on the solver. M9 is M7 (MO-DOMDVRPTW-SD) where only `fixed_ratio` of the visits are booked: a booked visit starts within ±10 minutes of its time, any other one at any time of the day. With `fixed_ratio` 1.0 the instance and the optimum are M7's.

## Setup

| Setting       | Value                                                                                   |
|---------------|-----------------------------------------------------------------------------------------|
| Dataset       | Synthetic                                                                               |
| Model         | m9                                                                                      |
| Solver        | Gurobi 13.0.3 (`gurobi_direct`) through Pyomo 6.10.1, raw mode, MIP gap 0               |
| Fixed ratios  | 0, 0.25, 0.5, 0.75, 1                                                                   |
| 5–7 properties| Seeds 1–5, 120 seconds limit                                                            |
| 8–10 properties| Seeds 1–3, 300 seconds limit                                                            |
| Machine       | AMD Ryzen 5 3600X (6 cores, 12 threads)                                                 |
| Execution Date| 2026-10-10                                                                              |

Time is the wall clock of `solve_model`, building the solver model included.

## Mean Time to Prove Optimality

| Properties | Ratio 0 | Ratio 0.25 | Ratio 0.5 | Ratio 0.75 | Ratio 1 (M7) |
|------------|---------|------------|-----------|------------|--------------|
| 5 | 0.08 s | 0.05 s | 0.03 s | 0.02 s | 0.02 s |
| 6 | 0.42 s | 0.08 s | 0.06 s | 0.04 s | 0.03 s |
| 7 | 0.79 s | 0.27 s | 0.07 s | 0.03 s | 0.04 s |
| 8 | 5.87 s | 0.64 s | 0.42 s | 0.06 s | 0.04 s |
| 9 | 26.05 s | 1.89 s | 0.81 s | 0.07 s | 0.05 s |
| 10 | 277.38 s (2 of 3 hit the limit) | 15.26 s | 0.90 s | 0.07 s | 0.05 s |

A run that hits the limit counts with the limit as its time, so that mean is a lower bound.

## Findings

- **Booked visits make the problem easy.** Every booked visit is pinned to a 20-minute slot, which rules out most visit orders. With every visit booked the time stays flat as the instance grows.
- **Flexible visits make it grow exponentially.** With none booked, each extra property multiplies the time by about 5 to 10; at 10 properties two of three runs did not prove optimality in 5 minutes.
- **The freedom pays off in the plan.** Fewer booked visits never needed more brokers on the same seed, and with none booked the route was shorter than with every visit booked in 23 of 24 instances.

## Runs

### Properties: 5

| Seed | Ratio | Booked | Status       | Total Time       | Brokers Used | Total Distance |
|------|-------|--------|--------------|------------------|--------------|----------------|
| 1 | 0 | 0 of 5 | optimal | 0.09 seconds | 2 | 118.7 units |
| 1 | 0.25 | 1 of 5 | optimal | 0.06 seconds | 2 | 118.7 units |
| 1 | 0.5 | 2 of 5 | optimal | 0.03 seconds | 2 | 118.7 units |
| 1 | 0.75 | 4 of 5 | optimal | 0.02 seconds | 2 | 156.7 units |
| 1 | 1 | 5 of 5 | optimal | 0.02 seconds | 2 | 156.9 units |
| 2 | 0 | 0 of 5 | optimal | 0.08 seconds | 2 | 66.7 units |
| 2 | 0.25 | 1 of 5 | optimal | 0.06 seconds | 2 | 66.7 units |
| 2 | 0.5 | 2 of 5 | optimal | 0.02 seconds | 2 | 131.6 units |
| 2 | 0.75 | 4 of 5 | optimal | 0.02 seconds | 2 | 179.8 units |
| 2 | 1 | 5 of 5 | optimal | 0.02 seconds | 3 | 151.8 units |
| 3 | 0 | 0 of 5 | optimal | 0.06 seconds | 2 | 79.7 units |
| 3 | 0.25 | 1 of 5 | optimal | 0.04 seconds | 2 | 79.7 units |
| 3 | 0.5 | 2 of 5 | optimal | 0.03 seconds | 2 | 117.1 units |
| 3 | 0.75 | 4 of 5 | optimal | 0.02 seconds | 3 | 227.9 units |
| 3 | 1 | 5 of 5 | optimal | 0.02 seconds | 3 | 227.9 units |
| 4 | 0 | 0 of 5 | optimal | 0.08 seconds | 2 | 55.2 units |
| 4 | 0.25 | 1 of 5 | optimal | 0.07 seconds | 2 | 81.0 units |
| 4 | 0.5 | 2 of 5 | optimal | 0.05 seconds | 2 | 81.0 units |
| 4 | 0.75 | 4 of 5 | optimal | 0.03 seconds | 2 | 201.8 units |
| 4 | 1 | 5 of 5 | optimal | 0.02 seconds | 2 | 201.8 units |
| 5 | 0 | 0 of 5 | optimal | 0.09 seconds | 2 | 75.7 units |
| 5 | 0.25 | 1 of 5 | optimal | 0.04 seconds | 2 | 107.6 units |
| 5 | 0.5 | 2 of 5 | optimal | 0.03 seconds | 2 | 110.1 units |
| 5 | 0.75 | 4 of 5 | optimal | 0.02 seconds | 2 | 143.1 units |
| 5 | 1 | 5 of 5 | optimal | 0.02 seconds | 3 | 151.2 units |

### Properties: 6

| Seed | Ratio | Booked | Status       | Total Time       | Brokers Used | Total Distance |
|------|-------|--------|--------------|------------------|--------------|----------------|
| 1 | 0 | 0 of 6 | optimal | 0.43 seconds | 2 | 122.1 units |
| 1 | 0.25 | 2 of 6 | optimal | 0.12 seconds | 2 | 140.7 units |
| 1 | 0.5 | 3 of 6 | optimal | 0.06 seconds | 2 | 165.4 units |
| 1 | 0.75 | 4 of 6 | optimal | 0.05 seconds | 2 | 199.8 units |
| 1 | 1 | 6 of 6 | optimal | 0.03 seconds | 2 | 224.4 units |
| 2 | 0 | 0 of 6 | optimal | 0.47 seconds | 2 | 69.6 units |
| 2 | 0.25 | 2 of 6 | optimal | 0.05 seconds | 2 | 94.8 units |
| 2 | 0.5 | 3 of 6 | optimal | 0.03 seconds | 2 | 141.3 units |
| 2 | 0.75 | 4 of 6 | optimal | 0.04 seconds | 2 | 144.5 units |
| 2 | 1 | 6 of 6 | optimal | 0.03 seconds | 2 | 224.9 units |
| 3 | 0 | 0 of 6 | optimal | 0.20 seconds | 1 | 135.0 units |
| 3 | 0.25 | 2 of 6 | optimal | 0.04 seconds | 1 | 169.9 units |
| 3 | 0.5 | 3 of 6 | optimal | 0.08 seconds | 2 | 104.2 units |
| 3 | 0.75 | 4 of 6 | optimal | 0.04 seconds | 2 | 115.5 units |
| 3 | 1 | 6 of 6 | optimal | 0.02 seconds | 3 | 178.8 units |
| 4 | 0 | 0 of 6 | optimal | 0.37 seconds | 2 | 71.9 units |
| 4 | 0.25 | 2 of 6 | optimal | 0.07 seconds | 2 | 84.0 units |
| 4 | 0.5 | 3 of 6 | optimal | 0.06 seconds | 2 | 89.7 units |
| 4 | 0.75 | 4 of 6 | optimal | 0.04 seconds | 2 | 111.9 units |
| 4 | 1 | 6 of 6 | optimal | 0.03 seconds | 2 | 150.6 units |
| 5 | 0 | 0 of 6 | optimal | 0.61 seconds | 1 | 176.0 units |
| 5 | 0.25 | 2 of 6 | optimal | 0.12 seconds | 2 | 173.1 units |
| 5 | 0.5 | 3 of 6 | optimal | 0.05 seconds | 2 | 173.1 units |
| 5 | 0.75 | 4 of 6 | optimal | 0.03 seconds | 2 | 173.1 units |
| 5 | 1 | 6 of 6 | optimal | 0.02 seconds | 3 | 158.4 units |

### Properties: 7

| Seed | Ratio | Booked | Status       | Total Time       | Brokers Used | Total Distance |
|------|-------|--------|--------------|------------------|--------------|----------------|
| 1 | 0 | 0 of 7 | optimal | 0.68 seconds | 3 | 51.5 units |
| 1 | 0.25 | 2 of 7 | optimal | 0.41 seconds | 3 | 83.3 units |
| 1 | 0.5 | 4 of 7 | optimal | 0.09 seconds | 3 | 117.0 units |
| 1 | 0.75 | 5 of 7 | optimal | 0.03 seconds | 3 | 83.3 units |
| 1 | 1 | 7 of 7 | optimal | 0.07 seconds | 3 | 126.7 units |
| 2 | 0 | 0 of 7 | optimal | 0.74 seconds | 2 | 73.2 units |
| 2 | 0.25 | 2 of 7 | optimal | 0.36 seconds | 2 | 94.8 units |
| 2 | 0.5 | 4 of 7 | optimal | 0.06 seconds | 2 | 118.0 units |
| 2 | 0.75 | 5 of 7 | optimal | 0.04 seconds | 2 | 118.7 units |
| 2 | 1 | 7 of 7 | optimal | 0.03 seconds | 3 | 114.3 units |
| 3 | 0 | 0 of 7 | optimal | 0.92 seconds | 3 | 98.2 units |
| 3 | 0.25 | 2 of 7 | optimal | 0.22 seconds | 3 | 108.9 units |
| 3 | 0.5 | 4 of 7 | optimal | 0.08 seconds | 3 | 100.4 units |
| 3 | 0.75 | 5 of 7 | optimal | 0.03 seconds | 3 | 154.2 units |
| 3 | 1 | 7 of 7 | optimal | 0.03 seconds | 3 | 192.5 units |
| 4 | 0 | 0 of 7 | optimal | 0.75 seconds | 2 | 85.5 units |
| 4 | 0.25 | 2 of 7 | optimal | 0.09 seconds | 2 | 130.3 units |
| 4 | 0.5 | 4 of 7 | optimal | 0.03 seconds | 2 | 193.7 units |
| 4 | 0.75 | 5 of 7 | optimal | 0.03 seconds | 2 | 193.7 units |
| 4 | 1 | 7 of 7 | optimal | 0.03 seconds | 3 | 172.9 units |
| 5 | 0 | 0 of 7 | optimal | 0.85 seconds | 2 | 154.3 units |
| 5 | 0.25 | 2 of 7 | optimal | 0.26 seconds | 2 | 195.8 units |
| 5 | 0.5 | 4 of 7 | optimal | 0.10 seconds | 2 | 200.7 units |
| 5 | 0.75 | 5 of 7 | optimal | 0.04 seconds | 2 | 257.6 units |
| 5 | 1 | 7 of 7 | optimal | 0.03 seconds | 2 | 287.0 units |

### Properties: 8

| Seed | Ratio | Booked | Status       | Total Time       | Brokers Used | Total Distance |
|------|-------|--------|--------------|------------------|--------------|----------------|
| 1 | 0 | 0 of 8 | optimal | 5.89 seconds | 3 | 66.1 units |
| 1 | 0.25 | 2 of 8 | optimal | 0.67 seconds | 3 | 112.9 units |
| 1 | 0.5 | 4 of 8 | optimal | 0.42 seconds | 3 | 164.3 units |
| 1 | 0.75 | 6 of 8 | optimal | 0.09 seconds | 3 | 164.3 units |
| 1 | 1 | 8 of 8 | optimal | 0.04 seconds | 3 | 197.0 units |
| 2 | 0 | 0 of 8 | optimal | 4.87 seconds | 2 | 121.9 units |
| 2 | 0.25 | 2 of 8 | optimal | 0.44 seconds | 2 | 123.5 units |
| 2 | 0.5 | 4 of 8 | optimal | 0.28 seconds | 2 | 217.2 units |
| 2 | 0.75 | 6 of 8 | optimal | 0.04 seconds | 3 | 131.6 units |
| 2 | 1 | 8 of 8 | optimal | 0.04 seconds | 3 | 144.3 units |
| 3 | 0 | 0 of 8 | optimal | 6.85 seconds | 2 | 177.5 units |
| 3 | 0.25 | 2 of 8 | optimal | 0.81 seconds | 2 | 184.3 units |
| 3 | 0.5 | 4 of 8 | optimal | 0.57 seconds | 2 | 220.6 units |
| 3 | 0.75 | 6 of 8 | optimal | 0.06 seconds | 2 | 262.9 units |
| 3 | 1 | 8 of 8 | optimal | 0.04 seconds | 2 | 296.0 units |

### Properties: 9

| Seed | Ratio | Booked | Status       | Total Time       | Brokers Used | Total Distance |
|------|-------|--------|--------------|------------------|--------------|----------------|
| 1 | 0 | 0 of 9 | optimal | 24.99 seconds | 3 | 115.7 units |
| 1 | 0.25 | 2 of 9 | optimal | 1.69 seconds | 3 | 169.3 units |
| 1 | 0.5 | 4 of 9 | optimal | 0.22 seconds | 3 | 169.3 units |
| 1 | 0.75 | 7 of 9 | optimal | 0.05 seconds | 3 | 174.2 units |
| 1 | 1 | 9 of 9 | optimal | 0.04 seconds | 3 | 174.2 units |
| 2 | 0 | 0 of 9 | optimal | 21.87 seconds | 2 | 120.8 units |
| 2 | 0.25 | 2 of 9 | optimal | 1.47 seconds | 2 | 126.5 units |
| 2 | 0.5 | 4 of 9 | optimal | 0.41 seconds | 2 | 163.3 units |
| 2 | 0.75 | 7 of 9 | optimal | 0.12 seconds | 2 | 308.9 units |
| 2 | 1 | 9 of 9 | optimal | 0.04 seconds | 2 | 258.1 units |
| 3 | 0 | 0 of 9 | optimal | 31.28 seconds | 3 | 149.0 units |
| 3 | 0.25 | 2 of 9 | optimal | 2.51 seconds | 3 | 154.9 units |
| 3 | 0.5 | 4 of 9 | optimal | 1.81 seconds | 3 | 169.2 units |
| 3 | 0.75 | 7 of 9 | optimal | 0.05 seconds | 3 | 203.0 units |
| 3 | 1 | 9 of 9 | optimal | 0.08 seconds | 3 | 275.2 units |

### Properties: 10

| Seed | Ratio | Booked | Status       | Total Time       | Brokers Used | Total Distance |
|------|-------|--------|--------------|------------------|--------------|----------------|
| 1 | 0 | 0 of 10 | maxTimeLimit | 300.07 seconds | 3 | 143.3 units |
| 1 | 0.25 | 2 of 10 | optimal | 9.64 seconds | 3 | 171.1 units |
| 1 | 0.5 | 5 of 10 | optimal | 1.04 seconds | 3 | 143.3 units |
| 1 | 0.75 | 8 of 10 | optimal | 0.08 seconds | 3 | 276.9 units |
| 1 | 1 | 10 of 10 | optimal | 0.05 seconds | 3 | 331.4 units |
| 2 | 0 | 0 of 10 | optimal | 232.03 seconds | 2 | 142.4 units |
| 2 | 0.25 | 2 of 10 | optimal | 6.69 seconds | 2 | 183.2 units |
| 2 | 0.5 | 5 of 10 | optimal | 0.60 seconds | 2 | 233.2 units |
| 2 | 0.75 | 8 of 10 | optimal | 0.07 seconds | 2 | 256.7 units |
| 2 | 1 | 10 of 10 | optimal | 0.05 seconds | 3 | 208.7 units |
| 3 | 0 | 0 of 10 | maxTimeLimit | 300.05 seconds | 2 | 193.9 units |
| 3 | 0.25 | 2 of 10 | optimal | 29.44 seconds | 2 | 244.1 units |
| 3 | 0.5 | 5 of 10 | optimal | 1.05 seconds | 3 | 252.8 units |
| 3 | 0.75 | 8 of 10 | optimal | 0.06 seconds | 3 | 276.1 units |
| 3 | 1 | 10 of 10 | optimal | 0.06 seconds | 3 | 297.3 units |
