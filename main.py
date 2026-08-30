import json
import numpy as np
import pandas as pd

from src.power_budget import (
    calculate_tx_power_for_target,
    calculate_route_power,
    mw_to_dbm,
    calculate_safe_launch_targets,
)

from src.gain_selection import (
    generate_initial_gains,
    refine_transit_endpoint_gains,
)

from src.ase_snr import (
    calculate_snr_db,
    calculate_route_ase,
)

from src.nonlinearity import (
    calculate_route_nonlinear_phase,
)

from src.dispersion import (
    calculate_route_dispersion,
    calculate_spectral_width_nm,
    calculate_bit_period_ps,
    calculate_dispersion_broadening,
    calculate_residual_route_dispersion,
)

from src.plotting import(
    plot_channel_power_profile,
    plot_edfa_input_by_site,
    plot_nonlinear_phase_by_channel,
    plot_optical_snr_by_channel
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

dispersion_compensation = load_json(
    "data/dispersion_compensation.json"
)

channels = pd.read_csv(
    "data/wavelength_allocation.csv"
)


# ============================================================
# Analysis configuration
# ============================================================

loss_case = "design"

# Baseline ASE integration bandwidth assumption
noise_bandwidth_by_rate_hz = {
    10: 10e9,
    40: 40e9,
}

mux_loss_db = components["wdm"][
    "mux_insertion_loss_db"
][loss_case]

demux_loss_db = components["wdm"][
    "demux_insertion_loss_db"
][loss_case]

demux_transmission = (
    10 ** (-demux_loss_db / 10)
)

tx_power_max_mw = constraints[
    "tx_power_max_mw_per_channel"
]

min_snr_db = constraints[
    "receiver_snr_min_db"
]

nonlinear_phase_limit_rad = constraints[
    "nonlinear_phase_max_rad"
]

dispersion_ps_per_nm_km = components[
    "fiber"
][
    "dispersion_ps_per_nm_km"
]

nominal_wavelength_nm = components[
    "system"
][
    "nominal_wavelength_nm"
]


# ============================================================
# 1. Generate initial EDFA gains
# ============================================================

initial_gains = generate_initial_gains(
    network=network,
    components=components,
    dispersion_compensation=(
        dispersion_compensation
    ),
)

print(
    "\n=== Initial EDFA Gains ==="
)

for link_name, gains in initial_gains.items():
    print(
        f"{link_name}: {gains}"
    )


# ============================================================
# 2. Calculate safe launch targets using initial gains
# ============================================================

# Current 10G and 40G modulators use the same baseline
# insertion loss. If this changes later, this part should
# become rate-dependent.
common_modulator_loss_db = (
    components["modulator"]["40g"][
        "insertion_loss_db"
    ]
)

target_input_by_link = (
    calculate_safe_launch_targets(
        network=network,
        gains_by_link=initial_gains,
        components=components,
        constraints=constraints,
        modulator_loss_db=(
            common_modulator_loss_db
        ),
        mux_loss_db=mux_loss_db,
        dispersion_compensation=(
            dispersion_compensation
        ),
    )
)


# ============================================================
# 3. Refine endpoint gains for transit traffic
# ============================================================

refined_gains, gain_adjustment_report = (
    refine_transit_endpoint_gains(
        initial_gains=initial_gains,
        channels=channels,
        target_input_by_link=(
            target_input_by_link
        ),
        network=network,
        components=components,
        dispersion_compensation=(
            dispersion_compensation
        ),
    )
)


# ============================================================
# 4. Recalculate safe launch targets using FINAL gains
# ============================================================

# Refinement may increase endpoint gain, so the safe launch
# targets are recalculated before the full-network simulation.
target_input_by_link = (
    calculate_safe_launch_targets(
        network=network,
        gains_by_link=refined_gains,
        components=components,
        constraints=constraints,
        modulator_loss_db=(
            common_modulator_loss_db
        ),
        mux_loss_db=mux_loss_db,
        dispersion_compensation=(
            dispersion_compensation
        ),
    )
)


print(
    "\n=== Final Safe Link Launch Targets ==="
)

for link_name, target_dbm in (
    target_input_by_link.items()
):
    print(
        f"{link_name}: {target_dbm:.2f} dBm"
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

    if item["status"] == "NO_ENDPOINT_EDFA":
        print(
            f"{item['link']}: NO_ENDPOINT_EDFA"
        )
        continue

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
# 5. Run full-network analysis
# ============================================================

print(
    "\n=== Full Network Analysis ==="
)

results = []

# Per-channel powers entering each physical EDFA are collected
# here. They will be summed AFTER all channels have been run
# to validate aggregate WDM input power.
edfa_input_records = []

# Keep the signal trace of each channel so that the
# worst-case channel power profile can be plotted later.
signal_traces = {}


for _, channel in channels.iterrows():

    channel_id = channel["channel_id"]
    rate_gbps = int(
        channel["rate_gbps"]
    )
    route = channel["route"]

    # ========================================================
    # 5.1 Transmitter
    # ========================================================

    modulator_loss_db = components[
        "modulator"
    ][f"{rate_gbps}g"][
        "insertion_loss_db"
    ]

    first_link = route.split("|")[0]

    source_target_dbm = (
        target_input_by_link[
            first_link
        ]
    )

    tx_power_mw = (
        calculate_tx_power_for_target(
            target_mux_output_dbm=(
                source_target_dbm
            ),
            modulator_loss_db=(
                modulator_loss_db
            ),
            mux_loss_db=mux_loss_db,
        )
    )

    tx_power_limit_status = (
        "PASS"
        if (
            tx_power_mw
            <= tx_power_max_mw + 1e-12
        )
        else "FAIL"
    )

    # Signal power entering the first fiber
    source_link_input_dbm = (
        mw_to_dbm(tx_power_mw)
        - modulator_loss_db
        - mux_loss_db
    )


    # ========================================================
    # 5.2 Signal propagation
    # ========================================================

    rx_power_dbm, signal_trace = (
        calculate_route_power(
            input_power_dbm=(
                source_link_input_dbm
            ),
            route=route,
            gains_by_link=refined_gains,
            components=components,
            network=network,
            constraints=constraints,
            loss_case=loss_case,
            target_input_by_link=(
                target_input_by_link
            ),
            dispersion_compensation=(
                dispersion_compensation
            ),
        )
    )

    rx_power_mw = (
        signal_trace[-1][
            "power_mw"
        ]
    )

    signal_traces[
        channel_id
    ] = signal_trace


    # ========================================================
    # 5.3 Collect EDFA input powers
    # ========================================================

    for point in signal_trace:

        if point["stage"] == "EDFA input":

            edfa_input_records.append({
                "channel_id": channel_id,
                "wavelength": (
                    channel["wavelength"]
                ),
                "rate_gbps": rate_gbps,
                "link": point["link"],
                "position_km": (
                    point["position_km"]
                ),
                "input_power_mw": (
                    point["power_mw"]
                ),
                "input_power_dbm": (
                    point["power_dbm"]
                ),
            })


    # ========================================================
    # 5.4 Nonlinear phase / SPM
    # ========================================================

    nonlinear_phase_rad, nonlinear_trace = (
        calculate_route_nonlinear_phase(
            signal_trace=signal_trace,
            components=components,
        )
    )

    nonlinear_status = (
        "PASS"
        if (
            nonlinear_phase_rad
            < nonlinear_phase_limit_rad
        )
        else "FAIL"
    )


    # ========================================================
    # 5.5 Chromatic dispersion
    # ========================================================

    (
        uncompensated_dispersion_ps_per_nm,
        uncompensated_dispersion_trace,
    ) = calculate_route_dispersion(
        route=route,
        network=network,
        dispersion_ps_per_nm_km=(
            dispersion_ps_per_nm_km
        ),
    )

    (
        residual_dispersion_ps_per_nm,
        residual_dispersion_trace,
    ) = calculate_residual_route_dispersion(
        route=route,
        network=network,
        dispersion_ps_per_nm_km=(
            dispersion_ps_per_nm_km
        ),
        dispersion_compensation=(
            dispersion_compensation
        ),
    )

    spectral_width_nm = (
        calculate_spectral_width_nm(
            wavelength_nm=(
                nominal_wavelength_nm
            ),
            bit_rate_gbps=rate_gbps,
        )
    )

    bit_period_ps = (
        calculate_bit_period_ps(
            bit_rate_gbps=rate_gbps
        )
    )

    uncompensated_broadening_ps = (
        calculate_dispersion_broadening(
            accumulated_dispersion_ps_per_nm=(
                uncompensated_dispersion_ps_per_nm
            ),
            spectral_width_nm=(
                spectral_width_nm
            ),
        )
    )

    residual_broadening_ps = (
        calculate_dispersion_broadening(
            accumulated_dispersion_ps_per_nm=(
                residual_dispersion_ps_per_nm
            ),
            spectral_width_nm=(
                spectral_width_nm
            ),
        )
    )

    residual_broadening_ratio = (
        residual_broadening_ps
        / bit_period_ps
    )


    # ========================================================
    # 5.6 Maximum per-channel EDFA output
    # ========================================================

    edfa_outputs = [
        point["power_mw"]
        for point in signal_trace
        if point["stage"].startswith(
            "EDFA output"
        )
    ]

    max_edfa_output_mw = (
        max(edfa_outputs)
        if edfa_outputs
        else 0.0
    )


    # ========================================================
    # 5.7 Per-channel power-limit status
    # ========================================================

    power_limit_status = (
        "PASS"
        if (
            tx_power_limit_status == "PASS"
            and all(
                point[
                    "power_limit_status"
                ] == "PASS"
                for point in signal_trace
            )
        )
        else "FAIL"
    )


    # ========================================================
    # 5.8 Extract intermediate-node leveling losses
    # ========================================================

    leveling_losses_db = {}

    for point in signal_trace:

        if (
            "leveling_attenuation_db"
            in point
        ):
            leveling_losses_db[
                point["link"]
            ] = float(
                point[
                    "leveling_attenuation_db"
                ]
            )


    # ========================================================
    # 5.9 Power-leveling status
    # ========================================================

    leveling_points = [
        point
        for point in signal_trace
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


    # ========================================================
    # 5.10 ASE bandwidth
    # ========================================================

    noise_bandwidth_hz = (
        noise_bandwidth_by_rate_hz[
            rate_gbps
        ]
    )


    # ========================================================
    # 5.11 Cascaded ASE propagation
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
            ),
            dispersion_compensation=(
                dispersion_compensation
            ),
        )
    )

    # calculate_route_ase() returns ASE before final DEMUX.
    rx_ase_w = (
        ase_output_w
        * demux_transmission
    )


    # ========================================================
    # 5.12 Optical SNR
    # ========================================================

    rx_signal_w = (
        rx_power_mw * 1e-3
    )

    optical_snr_db = (
        calculate_snr_db(
            signal_power_w=(
                rx_signal_w
            ),
            noise_power_w=(
                rx_ase_w
            ),
        )
    )

    optical_snr_status = (
        "PASS"
        if optical_snr_db >= min_snr_db
        else "FAIL"
    )


    # ========================================================
    # 5.13 Store per-channel result
    # ========================================================

    results.append({
        "channel_id": channel_id,
        "demand": channel["demand"],
        "wavelength": (
            channel["wavelength"]
        ),
        "rate_gbps": rate_gbps,
        "route": route,

        "tx_power_mw": (
            tx_power_mw
        ),

        "max_edfa_output_mw": (
            max_edfa_output_mw
        ),

        "rx_power_mw": (
            rx_power_mw
        ),

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

        "uncomp_dispersion_ps_per_nm": (
            uncompensated_dispersion_ps_per_nm
        ),

        "residual_dispersion_ps_per_nm": (
            residual_dispersion_ps_per_nm
        ),

        "spectral_width_nm": (
            spectral_width_nm
        ),

        "bit_period_ps": (
            bit_period_ps
        ),

        "uncomp_broadening_ps": (
            uncompensated_broadening_ps
        ),

        "residual_broadening_ps": (
            residual_broadening_ps
        ),

        "residual_broadening_ratio": (
            residual_broadening_ratio
        ),

        "nonlinear_phase_rad": (
            nonlinear_phase_rad
        ),

        "nonlinear_status": (
            nonlinear_status
        ),
    })


# ============================================================
# 6. Per-channel Results DataFrame
# ============================================================

results_df = pd.DataFrame(
    results
)

print(
    "\n========== Channel Results =========="
)

print(
    results_df.to_string(
        index=False
    )
)


# ============================================================
# 7. Aggregate WDM EDFA input validation
# ============================================================

edfa_input_df = pd.DataFrame(
    edfa_input_records
)

edfa_input_min_dbm = (
    components["edfa"][
        "input_power_min_dbm"
    ]
)

edfa_input_max_dbm = (
    components["edfa"][
        "input_power_max_dbm"
    ]
)

if not edfa_input_df.empty:

    aggregate_edfa_input_df = (
        edfa_input_df
        .groupby(
            [
                "link",
                "position_km",
            ],
            as_index=False,
        )
        .agg(
            total_input_power_mw=(
                "input_power_mw",
                "sum",
            ),
            channel_count=(
                "channel_id",
                "nunique",
            ),
        )
    )

    aggregate_edfa_input_df[
        "total_input_power_dbm"
    ] = (
        10
        * np.log10(
            aggregate_edfa_input_df[
                "total_input_power_mw"
            ]
        )
    )

    aggregate_edfa_input_df[
        "lower_margin_db"
    ] = (
        aggregate_edfa_input_df[
            "total_input_power_dbm"
        ]
        - edfa_input_min_dbm
    )

    aggregate_edfa_input_df[
        "upper_margin_db"
    ] = (
        edfa_input_max_dbm
        - aggregate_edfa_input_df[
            "total_input_power_dbm"
        ]
    )

    aggregate_edfa_input_df[
        "input_status"
    ] = np.where(
        (
            aggregate_edfa_input_df[
                "total_input_power_dbm"
            ]
            >= edfa_input_min_dbm
        )
        &
        (
            aggregate_edfa_input_df[
                "total_input_power_dbm"
            ]
            <= edfa_input_max_dbm
        ),
        "PASS",
        "FAIL",
    )

else:

    aggregate_edfa_input_df = (
        pd.DataFrame(
            columns=[
                "link",
                "position_km",
                "total_input_power_mw",
                "channel_count",
                "total_input_power_dbm",
                "lower_margin_db",
                "upper_margin_db",
                "input_status",
            ]
        )
    )


print(
    "\n========== Aggregate WDM EDFA Input =========="
)

print(
    aggregate_edfa_input_df.to_string(
        index=False
    )
)


# ============================================================
# 8. Channel Summary
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


# ============================================================
# 9. Aggregate EDFA Summary
# ============================================================

total_edfa_sites = len(
    aggregate_edfa_input_df
)

if total_edfa_sites > 0:

    edfa_input_pass = (
        aggregate_edfa_input_df[
            "input_status"
        ] == "PASS"
    ).sum()

    edfa_input_fail = (
        aggregate_edfa_input_df[
            "input_status"
        ] == "FAIL"
    ).sum()

else:

    edfa_input_pass = 0
    edfa_input_fail = 0


# ============================================================
# 10. Worst-case metrics
# ============================================================

worst_snr_row = (
    results_df.loc[
        results_df[
            "optical_snr_db"
        ].idxmin()
    ]
)

max_spm_row = (
    results_df.loc[
        results_df[
            "nonlinear_phase_rad"
        ].idxmax()
    ]
)

max_abs_residual_dispersion = (
    results_df[
        "residual_dispersion_ps_per_nm"
    ]
    .abs()
    .max()
)

max_residual_broadening_ps = (
    results_df[
        "residual_broadening_ps"
    ].max()
)

max_residual_broadening_ratio = (
    results_df[
        "residual_broadening_ratio"
    ].max()
)


# ============================================================
# 11. Generate figures
# ============================================================

plot_optical_snr_by_channel(
    results_df=results_df,
    snr_threshold_db=min_snr_db,
)

plot_edfa_input_by_site(
    aggregate_edfa_input_df=(
        aggregate_edfa_input_df
    ),
    input_min_dbm=edfa_input_min_dbm,
    input_max_dbm=edfa_input_max_dbm,
)

plot_nonlinear_phase_by_channel(
    results_df=results_df,
    nonlinear_phase_limit_rad=(
        nonlinear_phase_limit_rad
    ),
)

worst_channel_id = (
    worst_snr_row[
        "channel_id"
    ]
)

worst_channel_route = (
    worst_snr_row[
        "route"
    ]
)

plot_channel_power_profile(
    signal_trace=(
        signal_traces[
            worst_channel_id
        ]
    ),
    channel_id=worst_channel_id,
    route=worst_channel_route,
)

print(
    "\n=== Figures Saved ==="
)

print(
    "results/figures/"
    "optical_snr_by_channel.png"
)

print(
    "results/figures/"
    "edfa_input_by_site.png"
)

print(
    "results/figures/"
    "nonlinear_phase_by_channel.png"
)

print(
    "results/figures/"
    f"{worst_channel_id}_power_profile.png"
)


# ============================================================
# 12. Print final summary
# ============================================================

print(
    "\n=== Summary ==="
)

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

print(
    f"SPM PASS             : "
    f"{nonlinear_pass}"
)

print(
    f"SPM FAIL             : "
    f"{nonlinear_fail}"
)

print(
    f"EDFA sites checked   : "
    f"{total_edfa_sites}"
)

print(
    f"EDFA-input PASS      : "
    f"{edfa_input_pass}"
)

print(
    f"EDFA-input FAIL      : "
    f"{edfa_input_fail}"
)

print(
    f"Max |residual D|     : "
    f"{max_abs_residual_dispersion:.2f} ps/nm"
)

print(
    f"Max residual broad.  : "
    f"{max_residual_broadening_ps:.2f} ps"
)

print(
    f"Max broadening/Tb    : "
    f"{max_residual_broadening_ratio:.4f}"
)

print(
    "Dispersion status    : "
    "reported numerically (no explicit threshold)"
)


print(
    "\n=== Worst-Case Metrics ==="
)

print(
    f"Worst optical SNR    : "
    f"{worst_snr_row['channel_id']} "
    f"({worst_snr_row['route']}) "
    f"{worst_snr_row['optical_snr_db']:.2f} dB "
    f"| margin "
    f"{worst_snr_row['optical_snr_db'] - min_snr_db:.2f} dB"
)

print(
    f"Maximum SPM phase    : "
    f"{max_spm_row['channel_id']} "
    f"({max_spm_row['route']}) "
    f"{max_spm_row['nonlinear_phase_rad']:.3f} rad"
)

