# 我们事先规定了一切EDFA的gain 在16-20dB之间，这段脚本用于自动选择合适的gain大小
def generate_initial_gains(
    network,
    components
):
    """
    Generate an initial EDFA gain configuration for all
    directed fiber links.

    The initial gain of each EDFA is based on the loss of
    the preceding fiber span, limited by the EDFA gain range.

    Returns
    -------
    gains_by_link : dict

        Example:
        {
            "A-B": [16, 20, 18, 20],
            "B-C": [16, 20, 20, 17]
        }
    """

    attenuation = components["fiber"][
        "attenuation_db_per_km"
    ]

    min_gain_db = components["edfa"][
        "gain_min_db"
    ]

    max_gain_db = components["edfa"][
        "gain_max_db"
    ]

    gains_by_link = {}

    # Go through every directed fiber
    for link_name, link_data in network.items():

        amplifiers = link_data["amplifiers"]

        link_gains = []

        previous_position = 0

        for amplifier in amplifiers:

            position = amplifier["position_km"]

            # Length of fiber before this amplifier
            span_length_km = position - previous_position

            # Corresponding fiber loss
            span_loss_db = (
                span_length_km * attenuation
            )

            # Use span loss as initial gain,
            # but keep it within the EDFA gain range.
            gain_db = max(
                min_gain_db,
                min(span_loss_db, max_gain_db)
            )

            link_gains.append(gain_db)

            previous_position = position

        gains_by_link[link_name] = link_gains

    return gains_by_link

# gain refinement 校正gain
def refine_transit_endpoint_gains(
    initial_gains,
    channels,
    target_input_by_link,
    network,
    components
):
    """
    Refine endpoint EDFA gains for transit channels.

    The initial gains are based on span-loss compensation.

    For a link carrying transit traffic, its endpoint EDFA
    must provide enough output power to reach the launch-power
    target of the next directed fiber.

    Only endpoint EDFA gains are increased.
    Gains are limited by the EDFA maximum gain.

    Returns
    -------
    refined_gains : dict
        Updated EDFA gain configuration.

    adjustment_report : list
        Information about every transit-link gain check.
    """

    # Copy the gain dictionary so that initial_gains
    # itself is not modified.
    refined_gains = {
        link_name: list(gains)
        for link_name, gains
        in initial_gains.items()
    }

    attenuation_db_per_km = (
        components["fiber"][
            "attenuation_db_per_km"
        ]
    )

    gain_max_db = (
        components["edfa"][
            "gain_max_db"
        ]
    )

    # ========================================================
    # Find all physical-link transitions used by transit traffic
    # ========================================================

    transitions = {}

    for route in channels["route"]:

        links = route.split("|")

        for i in range(len(links) - 1):

            current_link = links[i]
            next_link = links[i + 1]

            if current_link not in transitions:
                transitions[current_link] = set()

            transitions[current_link].add(
                next_link
            )

    adjustment_report = []

    # ========================================================
    # Check each upstream link
    # ========================================================

    for current_link, next_links in transitions.items():

        link = network[current_link]

        amplifiers = link["amplifiers"]

        # ----------------------------------------------------
        # Make sure there really is an endpoint EDFA
        # ----------------------------------------------------

        has_endpoint_edfa = (
            len(amplifiers) > 0
            and amplifiers[-1]["position_km"]
            == link["length_km"]
        )

        if not has_endpoint_edfa:

            adjustment_report.append({
                "link": current_link,
                "old_endpoint_gain_db": None,
                "new_endpoint_gain_db": None,
                "required_output_dbm": None,
                "output_before_dbm": None,
                "output_after_dbm": None,
                "status": "NO_ENDPOINT_EDFA"
            })

            continue

        # ----------------------------------------------------
        # Calculate current link output power
        # ----------------------------------------------------

        input_power_dbm = (
            target_input_by_link[
                current_link
            ]
        )

        total_fiber_loss_db = (
            link["length_km"]
            * attenuation_db_per_km
        )

        total_gain_db = sum(
            refined_gains[current_link]
        )

        output_before_dbm = (
            input_power_dbm
            - total_fiber_loss_db
            + total_gain_db
        )

        # ----------------------------------------------------
        # Find strongest target required by downstream links
        # ----------------------------------------------------

        required_output_dbm = max(
            target_input_by_link[next_link]
            for next_link in next_links
        )

        # ----------------------------------------------------
        # Determine whether more endpoint gain is needed
        # ----------------------------------------------------

        gain_deficit_db = max(
            0.0,
            required_output_dbm
            - output_before_dbm
        )

        old_endpoint_gain_db = (
            refined_gains[
                current_link
            ][-1]
        )

        new_endpoint_gain_db = min(
            old_endpoint_gain_db
            + gain_deficit_db,
            gain_max_db
        )

        refined_gains[
            current_link
        ][-1] = new_endpoint_gain_db

        actual_gain_increase_db = (
            new_endpoint_gain_db
            - old_endpoint_gain_db
        )

        output_after_dbm = (
            output_before_dbm
            + actual_gain_increase_db
        )

        status = (
            "PASS"
            if output_after_dbm
            >= required_output_dbm - 1e-12
            else "GAIN_LIMIT"
        )

        adjustment_report.append({
            "link": current_link,
            "next_links": sorted(
                next_links
            ),
            "old_endpoint_gain_db": (
                old_endpoint_gain_db
            ),
            "new_endpoint_gain_db": (
                new_endpoint_gain_db
            ),
            "required_output_dbm": (
                required_output_dbm
            ),
            "output_before_dbm": (
                output_before_dbm
            ),
            "output_after_dbm": (
                output_after_dbm
            ),
            "status": status
        })

    return (
        refined_gains,
        adjustment_report
    )