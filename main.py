import json
import pandas as pd

from src.power_budget import (
    calculate_tx_power_for_target,
    calculate_route_power,
    mw_to_dbm
)

from src.gain_selection import (
    generate_initial_gains
)


# ============================================================
# Load JSON
# ============================================================

def load_json(path):
    """Load a JSON file."""

    with open(path, "r") as f:
        return json.load(f)


# ============================================================
# Load input data
# ============================================================

components = load_json(
    "data/Components.json"
)

network = load_json(
    "data/Network.json"
)

constraints = load_json(
    "data/design_constraint.json"
)

channels = pd.read_csv(
    "data/wavelength_allocation.csv"
)


# ============================================================
# Analysis configuration
# ============================================================

loss_case = "typical"

mux_loss = components["wdm"][
    "mux_insertion_loss_db"
][loss_case]


# ============================================================
# Determine target MUX output power
# ============================================================

# Use the 40G channel transmitting at the maximum allowed
# Tx power as the reference channel.

tx_power_max_mw = constraints[
    "tx_power_max_mw_per_channel"
]

reference_40g_modulator_loss = (
    components["modulator"]["40g"][
        "insertion_loss_db"
    ]
)

target_mux_output_dbm = (
    mw_to_dbm(tx_power_max_mw)
    - reference_40g_modulator_loss
    - mux_loss
)

print(
    f"Target MUX output power: "
    f"{target_mux_output_dbm:.2f} dBm"
)


# ============================================================
# Generate initial EDFA gains
# ============================================================

initial_gains = generate_initial_gains(
    network=network,
    components=components
)

print("\n=== Initial EDFA Gains ===")

for link_name, gains in initial_gains.items():

    print(
        f"{link_name}: {gains}"
    )


# ============================================================
# Run power-budget analysis for all channels
# ============================================================

print(
    "\n=== Full Network Power Budget ==="
)

results = []


for _, channel in channels.iterrows():

    channel_id = channel["channel_id"]

    rate_gbps = int(
        channel["rate_gbps"]
    )

    route = channel["route"]

    # --------------------------------------------------------
    # Get modulator loss
    # --------------------------------------------------------

    modulator_loss = components[
        "modulator"
    ][f"{rate_gbps}g"][
        "insertion_loss_db"
    ]

    # --------------------------------------------------------
    # Calculate transmitter power
    # --------------------------------------------------------

    tx_power_mw = (
        calculate_tx_power_for_target(
            target_mux_output_dbm=(
                target_mux_output_dbm
            ),
            modulator_loss_db=(
                modulator_loss
            ),
            mux_loss_db=mux_loss
        )
    )

    # --------------------------------------------------------
    # Tx power limit
    # --------------------------------------------------------

    tx_power_limit_status = (
        "PASS"
        if (
            tx_power_mw
            <= tx_power_max_mw + 1e-12
        )
        else "FAIL"
    )

    # --------------------------------------------------------
    # Optical power entering first fiber
    # --------------------------------------------------------

    source_link_input_dbm = (
        mw_to_dbm(tx_power_mw)
        - modulator_loss
        - mux_loss
    )

    # --------------------------------------------------------
    # Propagate through complete route
    # --------------------------------------------------------

    rx_power_dbm, trace = (
        calculate_route_power(
            input_power_dbm=(
                source_link_input_dbm
            ),
            route=route,
            gains_by_link=initial_gains,
            components=components,
            network=network,
            constraints=constraints,
            loss_case=loss_case,
            target_link_input_dbm=(
                target_mux_output_dbm
            )
        )
    )

    # --------------------------------------------------------
    # Maximum EDFA output power
    # --------------------------------------------------------

    edfa_outputs = [
        point["power_mw"]
        for point in trace
        if point["stage"].startswith(
            "EDFA output"
        )
    ]

    if edfa_outputs:
        max_edfa_output_mw = max(
            edfa_outputs
        )
    else:
        max_edfa_output_mw = 0.0

    # --------------------------------------------------------
    # Receiver power
    # --------------------------------------------------------

    rx_power_mw = trace[-1][
        "power_mw"
    ]

    # --------------------------------------------------------
    # Power-limit status
    # --------------------------------------------------------

    power_limit_status = (
        "PASS"
        if (
            tx_power_limit_status == "PASS"
            and all(
                point[
                    "power_limit_status"
                ] == "PASS"
                for point in trace
            )
        )
        else "FAIL"
    )

    # --------------------------------------------------------
    # Power-leveling status
    # --------------------------------------------------------

    leveling_points = [
        point
        for point in trace
        if "leveling_status" in point
    ]

    leveling_status = (
        "PASS"
        if all(
            point["leveling_status"]
            == "PASS"
            for point in leveling_points
        )
        else "LOW"
    )

    # --------------------------------------------------------
    # Store result
    # --------------------------------------------------------

    results.append({
        "channel_id": channel_id,
        "demand": channel["demand"],
        "wavelength": channel[
            "wavelength"
        ],
        "rate_gbps": rate_gbps,
        "route": route,
        "tx_power_mw": tx_power_mw,
        "max_edfa_output_mw": (
            max_edfa_output_mw
        ),
        "rx_power_mw": rx_power_mw,
        "power_limit_status": (
            power_limit_status
        ),
        "leveling_status": (
            leveling_status
        )
    })


# ============================================================
# Convert results to DataFrame
# ============================================================

results_df = pd.DataFrame(
    results
)


# ============================================================
# Display full results
# ============================================================

print()

print(
    results_df.to_string(
        index=False
    )
)


# ============================================================
# Summary
# ============================================================

total_channels = len(
    results_df
)

power_passed_channels = (
    results_df[
        "power_limit_status"
    ] == "PASS"
).sum()

power_failed_channels = (
    results_df[
        "power_limit_status"
    ] == "FAIL"
).sum()

leveling_passed_channels = (
    results_df[
        "leveling_status"
    ] == "PASS"
).sum()

leveling_low_channels = (
    results_df[
        "leveling_status"
    ] == "LOW"
).sum()


print("\n=== Summary ===")

print(
    f"Total channels       : "
    f"{total_channels}"
)

print(
    f"Power-limit PASS     : "
    f"{power_passed_channels}"
)

print(
    f"Power-limit FAIL     : "
    f"{power_failed_channels}"
)

print(
    f"Power-leveling PASS  : "
    f"{leveling_passed_channels}"
)

print(
    f"Power-leveling LOW   : "
    f"{leveling_low_channels}"
)


# ============================================================
# D-B DROP test
# ============================================================

db_output_dbm, db_trace = (
    calculate_route_power(
        input_power_dbm=(
            target_mux_output_dbm
        ),
        route="D-B",
        gains_by_link=initial_gains,
        components=components,
        network=network,
        constraints=constraints,
        loss_case=loss_case,
        target_link_input_dbm=(
            target_mux_output_dbm
        )
    )
)


print(
    "\n=== D-B DROP Test ==="
)


for point in db_trace:

    print(
        f"{str(point['position_km']):>8} | "
        f"{point['stage']:<34} | "
        f"{point['power_dbm']:>8.2f} dBm | "
        f"{point['power_mw']:>9.4f} mW | "
        f"{point['power_limit_status']}"
    )

#----------------------------------------------------------
# save results
#----------------------------------------------------------
results_df.to_csv(
    "results/power_budget_results.csv",
    index=False
)