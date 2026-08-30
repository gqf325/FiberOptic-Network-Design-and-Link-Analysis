from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


# ============================================================
# Helpers
# ============================================================

def _prepare_output_path(output_path):
    """Create the parent directory for a figure if needed."""

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    return output_path


# ============================================================
# 1. Optical SNR by channel
# ============================================================

def plot_optical_snr_by_channel(
    results_df,
    snr_threshold_db,
    output_path=(
        "results/figures/"
        "optical_snr_by_channel.png"
    )
):
    """
    Plot optical SNR for all WDM channels.

    Bars are used instead of connecting lines because channel
    IDs are categorical rather than a continuous x variable.
    """

    output_path = _prepare_output_path(output_path)

    df = results_df.copy().reset_index(drop=True)

    x = np.arange(len(df))
    snr_values = df["optical_snr_db"].to_numpy()
    rates = df["rate_gbps"].to_numpy()
    labels = df["channel_id"].astype(str).tolist()

    fig, ax = plt.subplots(figsize=(13, 6))

    mask_10g = rates == 10
    mask_40g = rates == 40

    ax.bar(
        x[mask_10g],
        snr_values[mask_10g],
        label="10G",
        color="tab:blue"
    )

    ax.bar(
        x[mask_40g],
        snr_values[mask_40g],
        label="40G",
        color="tab:orange"
    )

    ax.axhline(
        y=snr_threshold_db,
        color="tab:red",
        linestyle="--",
        linewidth=2,
        label=(
            f"SNR requirement "
            f"({snr_threshold_db:.1f} dB)"
        )
    )

    ax.set_xticks(x)
    ax.set_xticklabels(
        labels,
        rotation=60,
        ha="right"
    )

    ax.set_xlabel("Channel")
    ax.set_ylabel("Optical SNR (dB)")
    ax.set_title("Optical SNR by WDM Channel")

    ax.grid(
        True,
        axis="y",
        alpha=0.3
    )

    ax.legend()
    fig.tight_layout()

    fig.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight"
    )

    plt.close(fig)

    return output_path


# ============================================================
# 2. Aggregate WDM EDFA input power
# ============================================================

def plot_edfa_input_by_site(
    aggregate_edfa_input_df,
    input_min_dbm,
    input_max_dbm,
    output_path=(
        "results/figures/"
        "edfa_input_by_site.png"
    )
):
    """
    Plot aggregate WDM input power at every active EDFA site.

    EDFA sites are discrete categories, so bars are used rather
    than connecting them with a line.
    """

    output_path = _prepare_output_path(output_path)

    df = (
        aggregate_edfa_input_df
        .copy()
        .reset_index(drop=True)
    )

    labels = [
        f"{row['link']} @ {row['position_km']:.0f} km"
        for _, row in df.iterrows()
    ]

    x = np.arange(len(df))

    input_powers = (
        df["total_input_power_dbm"]
        .to_numpy()
    )

    fig, ax = plt.subplots(figsize=(13, 6))

    ax.bar(
        x,
        input_powers,
        color="tab:blue",
        label="Aggregate WDM input"
    )

    ax.axhline(
        y=input_min_dbm,
        color="tab:red",
        linestyle="--",
        linewidth=2,
        label=(
            f"Minimum input "
            f"({input_min_dbm:.0f} dBm)"
        )
    )

    ax.axhline(
        y=input_max_dbm,
        color="tab:green",
        linestyle="-.",
        linewidth=2,
        label=(
            f"Maximum input "
            f"({input_max_dbm:.0f} dBm)"
        )
    )

    ax.set_xticks(x)

    ax.set_xticklabels(
        labels,
        rotation=60,
        ha="right"
    )

    ax.set_xlabel("Active EDFA site")
    ax.set_ylabel("Aggregate input power (dBm)")
    ax.set_title(
        "Aggregate WDM Input Power at Active EDFA Sites"
    )

    ax.grid(
        True,
        axis="y",
        alpha=0.3
    )

    ax.legend()
    fig.tight_layout()

    fig.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight"
    )

    plt.close(fig)

    return output_path


# ============================================================
# 3. Nonlinear phase by channel
# ============================================================

def plot_nonlinear_phase_by_channel(
    results_df,
    nonlinear_phase_limit_rad,
    output_path=(
        "results/figures/"
        "nonlinear_phase_by_channel.png"
    )
):
    """
    Plot accumulated SPM nonlinear phase for all channels.

    Bars are used because channel IDs are categorical.
    """

    output_path = _prepare_output_path(output_path)

    df = results_df.copy().reset_index(drop=True)

    x = np.arange(len(df))
    phase_values = df["nonlinear_phase_rad"].to_numpy()
    rates = df["rate_gbps"].to_numpy()
    labels = df["channel_id"].astype(str).tolist()

    fig, ax = plt.subplots(figsize=(13, 6))

    mask_10g = rates == 10
    mask_40g = rates == 40

    ax.bar(
        x[mask_10g],
        phase_values[mask_10g],
        label="10G",
        color="tab:blue"
    )

    ax.bar(
        x[mask_40g],
        phase_values[mask_40g],
        label="40G",
        color="tab:orange"
    )

    ax.axhline(
        y=nonlinear_phase_limit_rad,
        color="tab:red",
        linestyle="--",
        linewidth=2,
        label=(
            f"Phase limit "
            f"({nonlinear_phase_limit_rad:.2f} rad)"
        )
    )

    ax.set_xticks(x)

    ax.set_xticklabels(
        labels,
        rotation=60,
        ha="right"
    )

    ax.set_xlabel("Channel")
    ax.set_ylabel(
        "Accumulated nonlinear phase (rad)"
    )
    ax.set_title(
        "SPM Nonlinear Phase by WDM Channel"
    )

    ax.grid(
        True,
        axis="y",
        alpha=0.3
    )

    ax.legend()
    fig.tight_layout()

    fig.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight"
    )

    plt.close(fig)

    return output_path


# ============================================================
# 4. Power profile for one selected channel
# ============================================================

def plot_channel_power_profile(
    signal_trace,
    channel_id,
    route,
    output_path=None
):
    """
    Plot signal power through the ordered propagation stages
    of one wavelength channel.

    The x-axis is stage order, not physical distance. Straight
    segments simply connect successive calculated states.

    Fiber attenuation is continuous in the physical system,
    while EDFA gain and DCM loss are discrete jumps. Therefore,
    markers and vertical guide lines are emphasized instead of
    implying that every stage is equally spaced in distance.
    """

    if output_path is None:
        output_path = (
            "results/figures/"
            f"{channel_id}_power_profile.png"
        )

    output_path = _prepare_output_path(output_path)

    plot_points = [
        point
        for point in signal_trace
        if point.get("power_dbm") is not None
    ]

    stage_labels = [
        point["stage"]
        for point in plot_points
    ]

    power_values = np.array([
        point["power_dbm"]
        for point in plot_points
    ])

    x = np.arange(len(plot_points))

    fig, ax = plt.subplots(figsize=(14, 6))

    ax.plot(
        x,
        power_values,
        marker="o",
        linewidth=1.5,
        color="tab:blue"
    )

    # Highlight discrete gain/loss elements.
    for i, point in enumerate(plot_points):

        stage = point["stage"]

        if (
            stage.startswith("EDFA output")
            or stage.startswith("DCM loss")
            or "leveling" in stage
        ):
            ax.axvline(
                x=i,
                color="0.75",
                linestyle=":",
                linewidth=1
            )

    ax.set_xticks(x)

    ax.set_xticklabels(
        stage_labels,
        rotation=65,
        ha="right"
    )

    ax.set_xlabel(
        "Propagation stage"
    )

    ax.set_ylabel(
        "Signal power (dBm)"
    )

    ax.set_title(
        f"Signal Power Profile: "
        f"{channel_id} ({route})"
    )

    ax.grid(
        True,
        axis="y",
        alpha=0.3
    )

    fig.tight_layout()

    fig.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight"
    )

    plt.close(fig)

    return output_path
