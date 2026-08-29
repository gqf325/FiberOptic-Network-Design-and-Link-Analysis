import numpy as np


# ============================================================
# Basic unit conversions
# ============================================================

def mw_to_dbm(power_mw):
    """Convert optical power from mW to dBm."""
    return 10 * np.log10(power_mw)


def dbm_to_mw(power_dbm):
    """Convert optical power from dBm to mW."""
    return 10 ** (power_dbm / 10)


def calculate_fiber_loss(length_km, attenuation_db_per_km):
    """Calculate fiber attenuation in dB."""
    return length_km * attenuation_db_per_km


# ============================================================
# Transmitter power equalization
# ============================================================

def calculate_tx_power_for_target(
    target_mux_output_dbm,
    modulator_loss_db,
    mux_loss_db
):
    """
    Calculate the transmitter power required to obtain a target
    optical power after the modulator and MUX.
    """

    tx_power_dbm = (
        target_mux_output_dbm
        + modulator_loss_db
        + mux_loss_db
    )

    return dbm_to_mw(tx_power_dbm)


# ============================================================
# Channel power equalization
# ============================================================

def equalize_channel_power(
    input_power_dbm,
    target_power_dbm
):
    """
    Equalize a pass-through optical channel to the target
    launch power of the next fiber.

    Only attenuation is applied.

    If the incoming channel is already weaker than the target,
    passive attenuation cannot increase its power.

    Returns
    -------
    output_power_dbm : float
        Equalized optical power.

    attenuation_db : float
        Applied attenuation.

    leveling_status : str
        "PASS" if the target can be reached by attenuation.
        "LOW" if the incoming signal is already below target.
    """

    if input_power_dbm >= target_power_dbm:

        attenuation_db = (
            input_power_dbm - target_power_dbm
        )

        output_power_dbm = target_power_dbm
        leveling_status = "PASS"

    else:

        attenuation_db = 0.0
        output_power_dbm = input_power_dbm
        leveling_status = "LOW"

    return (
        output_power_dbm,
        attenuation_db,
        leveling_status
    )


# ============================================================
# Original single-link power-budget model
# ============================================================

def calculate_link_power(
    link_name,
    rate_gbps,
    tx_power_mw,
    gains_db,
    components,
    network,
    constraints,
    loss_case="typical"
):
    """
    Calculate per-channel optical power along one directed fiber.

    Includes:
    - transmitter
    - modulator
    - MUX
    - fiber attenuation
    - EDFA gain
    - DEMUX
    - receiver

    This function is retained mainly for single-link validation.
    Multi-link routes should use calculate_route_power().
    """

    link = network[link_name]

    attenuation = components["fiber"][
        "attenuation_db_per_km"
    ]

    modulator_loss = components["modulator"][
        f"{rate_gbps}g"
    ]["insertion_loss_db"]

    mux_loss = components["wdm"][
        "mux_insertion_loss_db"
    ][loss_case]

    demux_loss = components["wdm"][
        "demux_insertion_loss_db"
    ][loss_case]

    max_edfa_output_mw = constraints[
        "edfa_output_max_mw_per_channel"
    ]

    max_rx_power_mw = constraints[
        "rx_power_max_mw_per_channel"
    ]

    trace = []

    # --------------------------------------------------------
    # Transmitter
    # --------------------------------------------------------

    power_dbm = mw_to_dbm(tx_power_mw)

    trace.append({
        "stage": "Tx",
        "position_km": 0,
        "power_dbm": power_dbm,
        "power_mw": dbm_to_mw(power_dbm),
        "power_limit_status": "PASS"
    })

    # --------------------------------------------------------
    # Modulator
    # --------------------------------------------------------

    power_dbm -= modulator_loss

    trace.append({
        "stage": f"{rate_gbps}G MZM output",
        "position_km": 0,
        "power_dbm": power_dbm,
        "power_mw": dbm_to_mw(power_dbm),
        "power_limit_status": "PASS"
    })

    # --------------------------------------------------------
    # MUX
    # --------------------------------------------------------

    power_dbm -= mux_loss

    trace.append({
        "stage": "MUX output",
        "position_km": 0,
        "power_dbm": power_dbm,
        "power_mw": dbm_to_mw(power_dbm),
        "power_limit_status": "PASS"
    })

    current_position = 0

    amplifiers = link["amplifiers"]

    if len(amplifiers) != len(gains_db):
        raise ValueError(
            f"{link_name}: number of gains does not match "
            f"number of amplifiers"
        )

    # --------------------------------------------------------
    # Fiber spans and EDFAs
    # --------------------------------------------------------

    for amplifier, gain_db in zip(
        amplifiers,
        gains_db
    ):

        position = amplifier["position_km"]

        span_length = (
            position - current_position
        )

        # Fiber before amplifier
        if span_length > 0:

            fiber_loss_db = calculate_fiber_loss(
                span_length,
                attenuation
            )

            power_dbm -= fiber_loss_db

            trace.append({
                "stage": f"Fiber ({span_length} km)",
                "position_km": position,
                "power_dbm": power_dbm,
                "power_mw": dbm_to_mw(power_dbm),
                "power_limit_status": "PASS"
            })

        # EDFA input
        trace.append({
            "stage": "EDFA input",
            "position_km": position,
            "power_dbm": power_dbm,
            "power_mw": dbm_to_mw(power_dbm),
            "power_limit_status": "PASS"
        })

        # EDFA output
        power_dbm += gain_db

        power_mw = dbm_to_mw(power_dbm)

        power_limit_status = (
            "PASS"
            if power_mw <= max_edfa_output_mw
            else "FAIL"
        )

        trace.append({
            "stage": f"EDFA output ({gain_db} dB)",
            "position_km": position,
            "power_dbm": power_dbm,
            "power_mw": power_mw,
            "power_limit_status": (
                power_limit_status
            )
        })

        current_position = position

    # --------------------------------------------------------
    # Fiber after final amplifier
    # --------------------------------------------------------

    remaining_length = (
        link["length_km"]
        - current_position
    )

    if remaining_length > 0:

        fiber_loss_db = calculate_fiber_loss(
            remaining_length,
            attenuation
        )

        power_dbm -= fiber_loss_db

        trace.append({
            "stage": f"Fiber ({remaining_length} km)",
            "position_km": link["length_km"],
            "power_dbm": power_dbm,
            "power_mw": dbm_to_mw(power_dbm),
            "power_limit_status": "PASS"
        })

    # --------------------------------------------------------
    # DEMUX and receiver
    # --------------------------------------------------------

    power_dbm -= demux_loss

    rx_power_mw = dbm_to_mw(power_dbm)

    rx_power_limit_status = (
        "PASS"
        if rx_power_mw <= max_rx_power_mw
        else "FAIL"
    )

    trace.append({
        "stage": "Receiver input",
        "position_km": link["length_km"],
        "power_dbm": power_dbm,
        "power_mw": rx_power_mw,
        "power_limit_status": (
            rx_power_limit_status
        )
    })

    return trace


# ============================================================
# Propagation through one directed fiber
# ============================================================

def propagate_link(
    input_power_dbm,
    link_name,
    gains_db,
    components,
    network,
    constraints,
    include_endpoint_amplifier=True
):
    """
    Propagate one wavelength channel through one directed fiber.

    Includes:
    - fiber attenuation
    - EDFA gain

    Does NOT include:
    - transmitter
    - modulator
    - MUX
    - DEMUX
    - receiver

    Parameters
    ----------
    include_endpoint_amplifier : bool
        If False, an amplifier located exactly at the destination
        node is bypassed.

        This is used when a channel terminates at that node
        and is dropped to the receiver.
    """

    link = network[link_name]

    attenuation = components["fiber"][
        "attenuation_db_per_km"
    ]

    max_edfa_output_mw = constraints[
        "edfa_output_max_mw_per_channel"
    ]

    amplifiers = link["amplifiers"]

    if len(amplifiers) != len(gains_db):
        raise ValueError(
            f"{link_name}: number of gains does not match "
            f"number of amplifiers"
        )

    trace = []

    power_dbm = input_power_dbm
    current_position = 0

    # --------------------------------------------------------
    # Link input
    # --------------------------------------------------------

    trace.append({
        "stage": f"{link_name} input",
        "position_km": 0,
        "power_dbm": power_dbm,
        "power_mw": dbm_to_mw(power_dbm),
        "power_limit_status": "PASS"
    })

    # --------------------------------------------------------
    # Fiber spans and EDFAs
    # --------------------------------------------------------

    for amplifier, gain_db in zip(
        amplifiers,
        gains_db
    ):

        position = amplifier["position_km"]

        span_length = (
            position - current_position
        )

        # ----------------------------------------------------
        # Fiber before amplifier
        # ----------------------------------------------------

        if span_length > 0:

            fiber_loss_db = calculate_fiber_loss(
                span_length,
                attenuation
            )

            power_dbm -= fiber_loss_db

            trace.append({
                "stage": f"Fiber ({span_length} km)",
                "position_km": position,
                "span_length_km": span_length,
                "power_dbm": power_dbm,
                "power_mw": dbm_to_mw(power_dbm),
                "power_limit_status": "PASS"
            })

        current_position = position

        # ----------------------------------------------------
        # Endpoint amplifier check
        # ----------------------------------------------------

        is_endpoint_amplifier = (
            position == link["length_km"]
        )

        if (
            is_endpoint_amplifier
            and not include_endpoint_amplifier
        ):

            trace.append({
                "stage": (
                    "Endpoint EDFA bypassed (DROP)"
                ),
                "position_km": position,
                "power_dbm": power_dbm,
                "power_mw": dbm_to_mw(power_dbm),
                "power_limit_status": "PASS"
            })

            continue

        # ----------------------------------------------------
        # EDFA input
        # ----------------------------------------------------

        trace.append({
            "stage": "EDFA input",
            "position_km": position,
            "power_dbm": power_dbm,
            "power_mw": dbm_to_mw(power_dbm),
            "power_limit_status": "PASS"
        })

        # ----------------------------------------------------
        # EDFA output
        # ----------------------------------------------------

        power_dbm += gain_db

        power_mw = dbm_to_mw(power_dbm)

        power_limit_status = (
            "PASS"
            if power_mw <= max_edfa_output_mw
            else "FAIL"
        )

        trace.append({
            "stage": f"EDFA output ({gain_db} dB)",
            "position_km": position,
            "power_dbm": power_dbm,
            "power_mw": power_mw,
            "power_limit_status": (
                power_limit_status
            )
        })

    # --------------------------------------------------------
    # Fiber after last amplifier site
    # --------------------------------------------------------

    remaining_length = (
        link["length_km"]
        - current_position
    )

    if remaining_length > 0:

        fiber_loss_db = calculate_fiber_loss(
            remaining_length,
            attenuation
        )

        power_dbm -= fiber_loss_db

        trace.append({
            "stage": f"Fiber ({remaining_length} km)",
            "position_km": link["length_km"],
            "span_length_km": remaining_length,
            "power_dbm": power_dbm,
            "power_mw": dbm_to_mw(power_dbm),
            "power_limit_status": "PASS"
        })

    # --------------------------------------------------------
    # Link output
    # --------------------------------------------------------

    trace.append({
        "stage": f"{link_name} output",
        "position_km": link["length_km"],
        "power_dbm": power_dbm,
        "power_mw": dbm_to_mw(power_dbm),
        "power_limit_status": "PASS"
    })

    return power_dbm, trace


# ============================================================
# Complete route propagation
# ============================================================

def calculate_route_power(
    input_power_dbm,
    route,
    gains_by_link,
    components,
    network,
    constraints,
    loss_case="typical",
    target_input_by_link=None
):
    """
    Propagate one wavelength channel through a complete route.

    Example
    -------
    A-B|B-C

    The transmitter is used only at the source.

    At intermediate nodes, the channel remains optical and
    is passed to the next directed fiber.
    """

    links = route.split("|")

    power_dbm = input_power_dbm

    trace = []

    for i, link_name in enumerate(links):

        # ----------------------------------------------------
        # Check gain configuration
        # ----------------------------------------------------

        if link_name not in gains_by_link:

            raise ValueError(
                f"No EDFA gain configuration found "
                f"for {link_name}"
            )

        # ----------------------------------------------------
        # Determine whether this is the last physical link
        # ----------------------------------------------------

        is_last_link = (
            i == len(links) - 1
        )

        # ----------------------------------------------------
        # Propagate through directed fiber
        # ----------------------------------------------------

        power_dbm, link_trace = propagate_link(
            input_power_dbm=power_dbm,
            link_name=link_name,
            gains_db=gains_by_link[link_name],
            components=components,
            network=network,
            constraints=constraints,
            include_endpoint_amplifier=(
                not is_last_link
            )
        )

        # Add link name to trace
        for point in link_trace:

            point_with_link = point.copy()

            point_with_link["link"] = (
                link_name
            )

            trace.append(
                point_with_link
            )

        # ----------------------------------------------------
        # Intermediate optical node
        # ----------------------------------------------------

        if not is_last_link:

            current_destination = (
                link_name.split("-")[1]
            )

            next_source = (
                links[i + 1].split("-")[0]
            )

            # Check route continuity
            if current_destination != next_source:

                raise ValueError(
                    f"Invalid route: {link_name} "
                    f"does not connect to "
                    f"{links[i + 1]}"
                )

            transit_node = (
                current_destination
            )

            # ------------------------------------------------
            # Channel power leveling
            # ------------------------------------------------

            if target_input_by_link is not None:
                next_link = links[i+1]

                target_power_dbm = (
                    target_input_by_link[next_link]
                )

                (
                    power_dbm,
                    attenuation_db,
                    leveling_status
                ) = equalize_channel_power(
                    input_power_dbm=power_dbm,
                    target_power_dbm=target_power_dbm
                )

            else:

                attenuation_db = 0.0
                leveling_status = "PASS"

            trace.append({
                "link": (
                    f"{link_name} -> "
                    f"{links[i + 1]}"
                ),
                "stage": (
                    f"Node {transit_node} PASS "
                    f"(leveling "
                    f"{attenuation_db:.2f} dB)"
                ),
                "position_km": None,
                "power_dbm": power_dbm,
                "power_mw": dbm_to_mw(
                    power_dbm
                ),

                # Power upper-limit check
                "power_limit_status": "PASS",

                # Separate leveling check
                "leveling_status": (
                    leveling_status
                ),
                "leveling_attenuation_db": attenuation_db,
            })

    # ========================================================
    # Final DEMUX and receiver
    # ========================================================

    demux_loss = components["wdm"][
        "demux_insertion_loss_db"
    ][loss_case]

    power_dbm -= demux_loss

    rx_power_mw = dbm_to_mw(
        power_dbm
    )

    max_rx_power_mw = constraints[
        "rx_power_max_mw_per_channel"
    ]

    rx_power_limit_status = (
        "PASS"
        if rx_power_mw <= max_rx_power_mw
        else "FAIL"
    )

    trace.append({
        "link": "Receiver",
        "stage": "Receiver input",
        "position_km": None,
        "power_dbm": power_dbm,
        "power_mw": rx_power_mw,
        "power_limit_status": (
            rx_power_limit_status
        )
    })

    return power_dbm, trace