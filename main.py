# import packages & functions from moudlues
import json
import pandas as pd
import numpy as np

from src.power_budget import (
    calculate_tx_power_for_target,
    calculate_route_power,
    mw_to_dbm
)

from src.gain_selection import (
    generate_initial_gains,
    refine_transit_endpoint_gains
)
from src.ase_snr import (
    calculate_snr_db,
    calculate_route_ase
)   
from src.nonlinearity import(
    calculate_effective_length,
    calculate_nonlinear_phase,
    attenuation_db_to_linear,
    calculate_route_nonlinear_phase
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

noise_bandwidth_by_rate_hz = {
    10: 10e9,
    40: 40e9
}

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

reference_10g_modulator_loss = (
    components["modulator"]["10g"][
        "insertion_loss_db"
    ]
)

target_40g_input_dbm = (
    mw_to_dbm(tx_power_max_mw)
    - reference_40g_modulator_loss
    - mux_loss
)

target_10g_input_dbm = (
    mw_to_dbm(tx_power_max_mw)
    - reference_10g_modulator_loss
    - mux_loss
)

print(
    f"Target MUX output power: "
    f"{target_mux_output_dbm:.2f} dBm"
)

target_input_by_link = {
    "A-B": target_40g_input_dbm,
    "B-A": target_40g_input_dbm,
    "B-C": target_10g_input_dbm,
    "C-B": target_40g_input_dbm,
    "B-D": target_10g_input_dbm,
    "D-B": target_40g_input_dbm
}

# ============================================================
# Generate initial EDFA gains
# ============================================================

initial_gains = generate_initial_gains(
    network=network,
    components=components
)


# refine gains
refined_gains, gain_adjustment_report = (
    refine_transit_endpoint_gains(
        initial_gains=initial_gains,
        channels=channels,
        target_input_by_link=(
            target_input_by_link
        ),
        network=network,
        components=components
    )
)
print(
    "\n=== Refined EDFA Gains ==="
)

for link_name, gains in refined_gains.items():

    print(
        f"{link_name}: {gains}"
    )

print(
    "\n=== Gain Refinement Report ==="
)

for item in gain_adjustment_report:

    print(
        f"{item['link']}: "
        f"{item['old_endpoint_gain_db']} "
        f"-> "
        f"{item['new_endpoint_gain_db']} dB "
        f"| required "
        f"{item['required_output_dbm']:.2f} dBm "
        f"| before "
        f"{item['output_before_dbm']:.2f} dBm "
        f"| after "
        f"{item['output_after_dbm']:.2f} dBm "
        f"| {item['status']}"
    )
# ============================================================
# Run full-network power and optical-SNR analysis
# ============================================================

print("\n=== Full Network Analysis ===")

results = []

min_snr_db = constraints[
    "receiver_snr_min_db"
]

demux_loss_db = components["wdm"][
    "demux_insertion_loss_db"
][loss_case]

demux_transmission = (
    10 ** (-demux_loss_db / 10)
)


for _, channel in channels.iterrows():

    channel_id = channel["channel_id"]
    rate_gbps = int(channel["rate_gbps"])
    route = channel["route"]

    # ========================================================
    # 1. Transmitter
    # ========================================================

    modulator_loss = components[
        "modulator"
    ][f"{rate_gbps}g"][
        "insertion_loss_db"
    ]

    first_link = route.split("|")[0]

    source_target_dbm = target_input_by_link[
        first_link
    ]

    tx_power_mw = calculate_tx_power_for_target(
        target_mux_output_dbm=source_target_dbm,
        modulator_loss_db=modulator_loss,
        mux_loss_db=mux_loss
    )

    tx_power_limit_status = (
        "PASS"
        if tx_power_mw <= tx_power_max_mw + 1e-12
        else "FAIL"
    )

    # Signal power entering the first fiber
    source_link_input_dbm = (
        mw_to_dbm(tx_power_mw)
        - modulator_loss
        - mux_loss
    )

    # ========================================================
    # 2. Signal propagation
    # ========================================================

    rx_power_dbm, signal_trace = calculate_route_power(
        input_power_dbm=source_link_input_dbm,
        route=route,
        gains_by_link=refined_gains,
        components=components,
        network=network,
        constraints=constraints,
        loss_case=loss_case,
        target_input_by_link=target_input_by_link
    )

    rx_power_mw = signal_trace[-1][
        "power_mw"
    ]

    # ========================================================
    # 3. Nonlinear phase / SPM
    # ========================================================

    nonlinear_phase_rad, nonlinear_trace = (
        calculate_route_nonlinear_phase(
            signal_trace=signal_trace,
            components=components
        )
    )

    nonlinear_phase_limit_rad = constraints[
        "nonlinear_phase_max_rad"
    ]

    nonlinear_status = (
        "PASS"
        if nonlinear_phase_rad < nonlinear_phase_limit_rad
        else "FAIL"
    )
    # ========================================================
    # 4. Maximum EDFA output
    # ========================================================

    edfa_outputs = [
        point["power_mw"]
        for point in signal_trace
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

    # ========================================================
    # 4. Power-limit status
    # ========================================================

    power_limit_status = (
        "PASS"
        if (
            tx_power_limit_status == "PASS"
            and all(
                point["power_limit_status"] == "PASS"
                for point in signal_trace
            )
        )
        else "FAIL"
    )

    # ========================================================
    # 5. Extract node leveling losses
    # ========================================================

    leveling_losses_db = {}

    for point in signal_trace:

        if "leveling_attenuation_db" in point:

            leveling_losses_db[
                point["link"]
            ] = float(
                point[
                    "leveling_attenuation_db"
                ]
            )

    # ========================================================
    # 6. Power-leveling status
    # ========================================================

    leveling_points = [
        point
        for point in signal_trace
        if "leveling_status" in point
    ]

    leveling_status = (
        "PASS"
        if all(
            point["leveling_status"] == "PASS"
            for point in leveling_points
        )
        else "LOW"
    )

    # ========================================================
    # 7. ASE bandwidth for this channel
    # ========================================================

    noise_bandwidth_hz = (
        noise_bandwidth_by_rate_hz[
            rate_gbps
        ]
    )

    # ========================================================
    # 8. Cascaded ASE propagation
    # ========================================================

    ase_output_w, ase_trace = (
        calculate_route_ase(
            input_ase_w=0.0,
            route=route,
            gains_by_link=refined_gains,
            components=components,
            network=network,
            noise_bandwidth_hz=(
                noise_bandwidth_hz
            ),
            leveling_losses_db=(
                leveling_losses_db
            )
        )
    )

    # calculate_route_ase() returns ASE before final DEMUX
    rx_ase_w = (
        ase_output_w
        * demux_transmission
    )
    # ========================================================
    # 9. Optical SNR
    # ========================================================

    rx_signal_w = (
        rx_power_mw * 1e-3
    )

    optical_snr_db = (
        calculate_snr_db(
            signal_power_w=rx_signal_w,
            noise_power_w=rx_ase_w
        )
    )

    optical_snr_status = (
        "PASS"
        if optical_snr_db >= min_snr_db
        else "FAIL"
    )
    
    # ========================================================
    # 10. Store channel result
    # ========================================================

    results.append({
        "channel_id": channel_id,
        "demand": channel["demand"],
        "wavelength": channel["wavelength"],
        "rate_gbps": rate_gbps,
        "route": route,

        "tx_power_mw": tx_power_mw,

        "max_edfa_output_mw": (
            max_edfa_output_mw
        ),

        "rx_power_mw": rx_power_mw,

        "rx_ase_uw": (
            rx_ase_w * 1e6
        ),

        "optical_snr_db": (
            optical_snr_db
        ),

        "power_limit_status": (
            power_limit_status
        ),

        "leveling_status": (
            leveling_status
        ),

        "optical_snr_status": (
            optical_snr_status
        ),
        "nonlinear_phase_rad": (
            nonlinear_phase_rad
        ),

        "nonlinear_status": (
            nonlinear_status
        ),
        })


# ============================================================
# Results DataFrame
# ============================================================

results_df = pd.DataFrame(
    results
)

print("==========Result DataFrame=============")
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


power_pass = (
    results_df[
        "power_limit_status"
    ] == "PASS"
).sum()

power_fail = (
    results_df[
        "power_limit_status"
    ] == "FAIL"
).sum()


leveling_pass = (
    results_df[
        "leveling_status"
    ] == "PASS"
).sum()

leveling_low = (
    results_df[
        "leveling_status"
    ] == "LOW"
).sum()


snr_pass = (
    results_df[
        "optical_snr_status"
    ] == "PASS"
).sum()

snr_fail = (
    results_df[
        "optical_snr_status"
    ] == "FAIL"
).sum()
nonlinear_pass = (
    results_df[
        "nonlinear_status"
    ] == "PASS"
).sum()

nonlinear_fail = (
    results_df[
        "nonlinear_status"
    ] == "FAIL"
).sum()

print("\n=== Summary ===")

print(
    f"Total channels       : "
    f"{total_channels}"
)

print(
    f"Power-limit PASS     : "
    f"{power_pass}"
)

print(
    f"Power-limit FAIL     : "
    f"{power_fail}"
)

print(
    f"Power-leveling PASS  : "
    f"{leveling_pass}"
)

print(
    f"Power-leveling LOW   : "
    f"{leveling_low}"
)

print(
    f"Optical-SNR PASS     : "
    f"{snr_pass}"
)

print(
    f"Optical-SNR FAIL     : "
    f"{snr_fail}"
)
# SPM：nonlinearity
print(
    f"SPM PASS             : "
    f"{nonlinear_pass}"
)

print(
    f"SPM FAIL             : "
    f"{nonlinear_fail}"
)
