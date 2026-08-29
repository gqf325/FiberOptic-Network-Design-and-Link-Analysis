import numpy as np


# ============================================================
# Fiber attenuation conversion
# ============================================================

def attenuation_db_to_linear(
    attenuation_db_per_km
):
    """
    Convert fiber power attenuation from dB/km
    to linear attenuation coefficient in 1/km.
    """

    return (
        attenuation_db_per_km
        * np.log(10)
        / 10
    )


# ============================================================
# Effective fiber length
# ============================================================

def calculate_effective_length(
    length_km,
    attenuation_db_per_km
):
    """
    Calculate nonlinear effective length of a fiber span.

    Leff = (1 - exp(-alpha * L)) / alpha
    """

    alpha = attenuation_db_to_linear(
        attenuation_db_per_km
    )

    return (
        1 - np.exp(-alpha * length_km)
    ) / alpha


# ============================================================
# SPM nonlinear phase shift
# ============================================================

def calculate_nonlinear_phase(
    input_power_w,
    length_km,
    attenuation_db_per_km,
    gamma_per_w_km
):
    """
    Calculate SPM nonlinear phase shift for one fiber span.

    phi_NL = gamma * P_in * Leff
    """

    effective_length_km = (
        calculate_effective_length(
            length_km=length_km,
            attenuation_db_per_km=(
                attenuation_db_per_km
            )
        )
    )

    nonlinear_phase_rad = (
        gamma_per_w_km
        * input_power_w
        * effective_length_km
    )

    return nonlinear_phase_rad

def calculate_route_nonlinear_phase(
    signal_trace,
    components
):
    """
    Calculate accumulated SPM nonlinear phase shift
    over all fiber spans in a complete optical route.

    The input power of each fiber span is taken from
    the signal power immediately before that span.

    Returns
    -------
    total_phase_rad : float
        Total accumulated nonlinear phase shift.

    phase_trace : list
        Per-span nonlinear phase information.
    """

    attenuation_db_per_km = (
        components["fiber"][
            "attenuation_db_per_km"
        ]
    )

    gamma_per_w_km = (
        components["fiber"][
            "gamma_per_w_km"
        ]
    )

    total_phase_rad = 0.0
    phase_trace = []

    for i, point in enumerate(signal_trace):

        # Only process actual fiber spans
        if "span_length_km" not in point:
            continue

        span_length_km = (
            point["span_length_km"]
        )

        # The trace point immediately before the fiber
        # contains the fiber-span input power.
        previous_point = signal_trace[i - 1]

        input_power_mw = (
            previous_point["power_mw"]
        )

        input_power_w = (
            input_power_mw * 1e-3
        )

        effective_length_km = (
            calculate_effective_length(
                length_km=span_length_km,
                attenuation_db_per_km=(
                    attenuation_db_per_km
                )
            )
        )

        span_phase_rad = (
            calculate_nonlinear_phase(
                input_power_w=input_power_w,
                length_km=span_length_km,
                attenuation_db_per_km=(
                    attenuation_db_per_km
                ),
                gamma_per_w_km=(
                    gamma_per_w_km
                )
            )
        )

        total_phase_rad += (
            span_phase_rad
        )

        phase_trace.append({
            "link": point["link"],
            "span_length_km": span_length_km,
            "input_power_mw": input_power_mw,
            "effective_length_km": (
                effective_length_km
            ),
            "span_phase_rad": (
                span_phase_rad
            )
        })

    return (
        total_phase_rad,
        phase_trace
    )