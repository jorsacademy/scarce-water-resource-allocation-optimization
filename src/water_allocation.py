from __future__ import annotations

from pathlib import Path

import pandas as pd
import pulp as pl


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "agraria_water_data.csv"
OUTPUT_PATH = PROJECT_ROOT / "solution.csv"

# Regional hydrological and economic parameters.
SURFACE_WATER_AVAILABILITY_MCM = 74.0
ENVIRONMENTAL_FLOW_RESERVE_MCM = 14.0
SURFACE_WITHDRAWAL_CAPACITY_MCM = (
    SURFACE_WATER_AVAILABILITY_MCM - ENVIRONMENTAL_FLOW_RESERVE_MCM
)

AQUIFER_RECHARGE_MCM = 42.0
SUSTAINABLE_GROUNDWATER_FRACTION = 0.75
GROUNDWATER_CAPACITY_MCM = AQUIFER_RECHARGE_MCM * SUSTAINABLE_GROUNDWATER_FRACTION

SURFACE_COST_KUSD_PER_MCM = 250.0
GROUNDWATER_COST_KUSD_PER_MCM = 1050.0

REQUIRED_COLUMNS = {
    "zone",
    "demand_mcm",
    "min_service_mcm",
    "value_kusd_per_delivered_mcm",
    "surface_efficiency",
    "ground_efficiency",
}


def load_and_validate_data(path: Path) -> pd.DataFrame:
    """Load the synthetic Agraria dataset and perform structural validation."""
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    df = pd.read_csv(path)

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if df.empty:
        raise ValueError("The dataset must contain at least one agricultural zone.")

    if df["zone"].duplicated().any():
        duplicates = df.loc[df["zone"].duplicated(), "zone"].tolist()
        raise ValueError(f"Duplicate zone names found: {duplicates}")

    numeric_columns = [
        "demand_mcm",
        "min_service_mcm",
        "value_kusd_per_delivered_mcm",
        "surface_efficiency",
        "ground_efficiency",
    ]

    for column in numeric_columns:
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise TypeError(f"Column '{column}' must be numeric.")
        if df[column].isna().any():
            raise ValueError(f"Column '{column}' contains missing values.")

    if (df["demand_mcm"] <= 0).any():
        raise ValueError("All demand values must be strictly positive.")

    if (df["min_service_mcm"] < 0).any():
        raise ValueError("Minimum service values cannot be negative.")

    if (df["min_service_mcm"] > df["demand_mcm"]).any():
        bad_zones = df.loc[
            df["min_service_mcm"] > df["demand_mcm"], "zone"
        ].tolist()
        raise ValueError(
            "Minimum service cannot exceed demand. Violating zones: "
            f"{bad_zones}"
        )

    for efficiency_column in ["surface_efficiency", "ground_efficiency"]:
        invalid = (df[efficiency_column] <= 0) | (df[efficiency_column] > 1)
        if invalid.any():
            bad_zones = df.loc[invalid, "zone"].tolist()
            raise ValueError(
                f"Efficiencies in '{efficiency_column}' must lie in (0, 1]. "
                f"Violating zones: {bad_zones}"
            )

    if (df["value_kusd_per_delivered_mcm"] <= 0).any():
        raise ValueError("Economic value coefficients must be strictly positive.")

    return df.reset_index(drop=True)


def perform_feasibility_screen(df: pd.DataFrame) -> None:
    """Check whether minimum-service requirements are plausibly supportable."""
    total_minimum_delivered = float(df["min_service_mcm"].sum())

    max_surface_delivered = float(
        SURFACE_WITHDRAWAL_CAPACITY_MCM * df["surface_efficiency"].max()
    )
    max_ground_delivered = float(
        GROUNDWATER_CAPACITY_MCM * df["ground_efficiency"].max()
    )

    optimistic_total_delivered = max_surface_delivered + max_ground_delivered

    if total_minimum_delivered > optimistic_total_delivered + 1e-9:
        raise ValueError(
            "Minimum-service requirements are infeasible even under an optimistic "
            "delivery-efficiency bound."
        )


def build_model(df: pd.DataFrame) -> tuple[pl.LpProblem, dict[str, pl.LpVariable], dict[str, pl.LpVariable]]:
    """Construct the linear programming model."""
    model = pl.LpProblem("Agraria_Scarce_Water_Allocation", pl.LpMaximize)

    zones = df["zone"].tolist()

    surface = {
        zone: pl.LpVariable(f"surface_{idx}", lowBound=0)
        for idx, zone in enumerate(zones)
    }
    groundwater = {
        zone: pl.LpVariable(f"groundwater_{idx}", lowBound=0)
        for idx, zone in enumerate(zones)
    }

    row_by_zone = df.set_index("zone").to_dict(orient="index")

    delivered = {
        zone: (
            row_by_zone[zone]["surface_efficiency"] * surface[zone]
            + row_by_zone[zone]["ground_efficiency"] * groundwater[zone]
        )
        for zone in zones
    }

    total_benefit = pl.lpSum(
        row_by_zone[zone]["value_kusd_per_delivered_mcm"] * delivered[zone]
        for zone in zones
    )
    total_surface_cost = SURFACE_COST_KUSD_PER_MCM * pl.lpSum(
        surface[zone] for zone in zones
    )
    total_ground_cost = GROUNDWATER_COST_KUSD_PER_MCM * pl.lpSum(
        groundwater[zone] for zone in zones
    )

    model += (
        total_benefit - total_surface_cost - total_ground_cost,
        "Annual_Net_Economic_Value_kUSD",
    )

    model += (
        pl.lpSum(surface[zone] for zone in zones)
        <= SURFACE_WITHDRAWAL_CAPACITY_MCM,
        "Surface_Water_Capacity",
    )

    model += (
        pl.lpSum(groundwater[zone] for zone in zones)
        <= GROUNDWATER_CAPACITY_MCM,
        "Groundwater_Sustainability",
    )

    for zone in zones:
        model += (
            delivered[zone] <= row_by_zone[zone]["demand_mcm"],
            f"Demand_Ceiling_{zone.replace(' ', '_')}",
        )
        model += (
            delivered[zone] >= row_by_zone[zone]["min_service_mcm"],
            f"Minimum_Service_{zone.replace(' ', '_')}",
        )

    return model, surface, groundwater


def solve_model(model: pl.LpProblem) -> None:
    """Solve the LP with CBC and fail explicitly if no optimum is found."""
    solver = pl.PULP_CBC_CMD(msg=False)
    model.solve(solver)

    status = pl.LpStatus[model.status]
    if status != "Optimal":
        raise RuntimeError(f"Optimization terminated with status: {status}")


def build_solution_table(
    df: pd.DataFrame,
    surface: dict[str, pl.LpVariable],
    groundwater: dict[str, pl.LpVariable],
) -> pd.DataFrame:
    """Create a detailed zone-level solution table."""
    records: list[dict[str, float | str]] = []

    for row in df.itertuples(index=False):
        surface_withdrawal = float(pl.value(surface[row.zone]))
        groundwater_withdrawal = float(pl.value(groundwater[row.zone]))

        surface_delivered = row.surface_efficiency * surface_withdrawal
        groundwater_delivered = row.ground_efficiency * groundwater_withdrawal
        total_delivered = surface_delivered + groundwater_delivered

        gross_benefit = row.value_kusd_per_delivered_mcm * total_delivered
        withdrawal_cost = (
            SURFACE_COST_KUSD_PER_MCM * surface_withdrawal
            + GROUNDWATER_COST_KUSD_PER_MCM * groundwater_withdrawal
        )
        net_value = gross_benefit - withdrawal_cost

        records.append(
            {
                "zone": row.zone,
                "surface_withdrawal_mcm": surface_withdrawal,
                "groundwater_withdrawal_mcm": groundwater_withdrawal,
                "surface_delivered_mcm": surface_delivered,
                "groundwater_delivered_mcm": groundwater_delivered,
                "total_delivered_mcm": total_delivered,
                "demand_mcm": row.demand_mcm,
                "minimum_service_mcm": row.min_service_mcm,
                "demand_satisfaction_pct": 100.0 * total_delivered / row.demand_mcm,
                "gross_benefit_kusd": gross_benefit,
                "withdrawal_cost_kusd": withdrawal_cost,
                "net_value_kusd": net_value,
            }
        )

    return pd.DataFrame.from_records(records)


def print_constraint_report(model: pl.LpProblem) -> None:
    """Print constraint slacks to help identify binding restrictions."""
    print("\nConstraint report")
    print("-" * 72)

    for name, constraint in model.constraints.items():
        slack = float(constraint.slack)
        binding = abs(slack) <= 1e-7
        label = "BINDING" if binding else "non-binding"
        print(f"{name:45s} slack = {slack:10.4f}   {label}")


def print_summary(model: pl.LpProblem, solution: pd.DataFrame) -> None:
    """Print a concise but complete optimization summary."""
    total_surface = solution["surface_withdrawal_mcm"].sum()
    total_ground = solution["groundwater_withdrawal_mcm"].sum()
    total_delivered = solution["total_delivered_mcm"].sum()
    total_demand = solution["demand_mcm"].sum()
    net_value_kusd = float(pl.value(model.objective))

    print(f"Status: {pl.LpStatus[model.status]}")
    print(f"Optimal annual net economic value: {net_value_kusd:,.2f} thousand USD")
    print(f"Equivalent value: {net_value_kusd / 1000:,.3f} million USD")
    print()
    print(
        solution[
            [
                "zone",
                "surface_withdrawal_mcm",
                "groundwater_withdrawal_mcm",
                "total_delivered_mcm",
                "demand_mcm",
                "minimum_service_mcm",
                "demand_satisfaction_pct",
                "net_value_kusd",
            ]
        ].to_string(index=False, float_format=lambda x: f"{x:,.3f}")
    )

    print("\nRegional resource utilization")
    print("-" * 72)
    print(
        f"Surface water: {total_surface:.3f} / "
        f"{SURFACE_WITHDRAWAL_CAPACITY_MCM:.3f} MCM"
    )
    print(
        f"Groundwater:   {total_ground:.3f} / "
        f"{GROUNDWATER_CAPACITY_MCM:.3f} MCM"
    )
    print(f"Delivered:     {total_delivered:.3f} / {total_demand:.3f} MCM total demand")


def main() -> None:
    df = load_and_validate_data(DATA_PATH)
    perform_feasibility_screen(df)

    model, surface, groundwater = build_model(df)
    solve_model(model)

    solution = build_solution_table(df, surface, groundwater)
    solution.to_csv(OUTPUT_PATH, index=False)

    print_summary(model, solution)
    print_constraint_report(model)
    print(f"\nDetailed solution exported to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
