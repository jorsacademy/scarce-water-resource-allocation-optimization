# Scarce Water Resource Allocation Optimization

A reproducible Operations Research case study on allocating scarce water resources across agricultural zones under economic, hydrological, and equity constraints.

This repository is designed as a graduate/PhD-level teaching example for linear programming, scarce-resource allocation, and policy-oriented optimization.

## Problem Context

The fictional region of **Agraria** must allocate limited annual water resources among five agricultural zones. Water can be supplied from two physically distinct sources:

- **Surface water** from regulated rivers and reservoirs.
- **Groundwater** from regional aquifers.

The planner seeks to maximize annual net agricultural value while preserving environmental flows, respecting groundwater sustainability, accounting for conveyance losses, satisfying minimum service levels, and avoiding allocation beyond economically useful demand.

The model is deliberately richer than a single aggregate capacity constraint. Surface-water withdrawals and groundwater abstractions are modeled separately because they have different physical limits, losses, and environmental consequences.

## Data

All data are synthetic and internally consistent. Monetary values are expressed in **thousand USD per MCM of water delivered to the farm gate**. One MCM is one million cubic meters.

| Zone | Demand (MCM delivered) | Minimum service (MCM delivered) | Net value (thousand USD/MCM delivered) | Surface conveyance efficiency | Groundwater conveyance efficiency |
|---|---:|---:|---:|---:|---:|
| North Plains | 32 | 12 | 6,100 | 0.90 | 0.97 |
| Central Valley | 27 | 10 | 6,800 | 0.92 | 0.96 |
| East Terraces | 22 | 8 | 5,900 | 0.88 | 0.95 |
| South Orchards | 18 | 7 | 7,400 | 0.94 | 0.98 |
| West Greenhouses | 14 | 6 | 8,600 | 0.96 | 0.99 |

Regional source data:

- Gross annual surface-water availability: **74 MCM**.
- Mandatory environmental-flow reservation: **14 MCM**.
- Therefore, at most **60 MCM** of surface water may be withdrawn for agriculture.
- Aquifer annual recharge: **42 MCM**.
- Sustainable groundwater abstraction fraction: **0.75** of recharge.
- Therefore, annual groundwater abstraction may not exceed **31.5 MCM**.
- Surface-water withdrawal cost: **250 thousand USD per MCM withdrawn**.
- Groundwater abstraction cost: **1,050 thousand USD per MCM abstracted**.

The distinction between withdrawn water and delivered water is essential. If a source-zone conveyance efficiency is `eta`, withdrawing 1 MCM supplies only `eta` MCM to the zone.

## Decision Variables

For each agricultural zone `i`:

- `s_i >= 0`: gross surface-water withdrawal allocated to zone `i` (MCM).
- `g_i >= 0`: gross groundwater abstraction allocated to zone `i` (MCM).

Delivered water to zone `i` is

`d_i = eta_surface_i * s_i + eta_ground_i * g_i`.

## Mathematical Formulation

Let:

- `I` be the set of agricultural zones.
- `v_i` be the economic value of one MCM delivered to zone `i`.
- `c_s` be the unit cost of surface-water withdrawal.
- `c_g` be the unit cost of groundwater abstraction.
- `eta^s_i` and `eta^g_i` be source-specific conveyance efficiencies.
- `D_i` be maximum useful delivered-water demand.
- `M_i` be minimum delivered-water service requirement.
- `S` be agricultural surface-water withdrawal capacity after environmental reservation.
- `G` be the sustainable groundwater abstraction limit.

The linear program is:

### Objective

Maximize annual net economic value:

`max Z = sum_i v_i(eta^s_i s_i + eta^g_i g_i) - c_s sum_i s_i - c_g sum_i g_i`

### Constraints

Surface-water capacity:

`sum_i s_i <= S`

Groundwater sustainability:

`sum_i g_i <= G`

Zone demand ceilings:

`eta^s_i s_i + eta^g_i g_i <= D_i   for all i`

Equity / minimum service constraints:

`eta^s_i s_i + eta^g_i g_i >= M_i   for all i`

Non-negativity:

`s_i, g_i >= 0   for all i`

## Why This Formulation Is More Realistic

A common introductory formulation places a single constraint on total water use. That approach hides the fact that surface water and groundwater have different ecological limits, costs, and delivery losses.

This formulation improves the logic in five ways:

1. Environmental protection is represented explicitly through a reserved surface-water volume.
2. Groundwater sustainability is tied to recharge rather than to an arbitrary percentage of total regional water.
3. Conveyance losses distinguish gross withdrawals from useful delivered water.
4. Economic returns are measured on delivered water, while extraction costs are charged on gross withdrawals.
5. Equity is modeled through mandatory minimum delivered-water service by zone.

## Repository Structure

```text
.
├── README.md
├── LICENSE.md
├── requirements.txt
├── .gitignore
├── data
│   └── agraria_water_data.csv
└── src
    └── water_allocation.py
```

## Installation

```bash
python -m venv .venv
```

Activate the environment, then install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python src/water_allocation.py
```

The script validates the dataset, builds the linear program, solves it with PuLP's CBC solver, prints the optimal allocation, reports source utilization and constraint slack, and exports a detailed solution table to `solution.csv` in the project root.

## Teaching Extensions

The deterministic LP can be extended to stochastic programming, robust optimization, multi-period reservoir-aquifer planning, piecewise-linear crop response functions, multi-objective equity-efficiency tradeoffs, or endogenous crop selection.

## License

This repository is provided for educational, academic, and other non-commercial use only. Commercial use is not permitted without prior written authorization. See `LICENSE.md` for the complete terms.
