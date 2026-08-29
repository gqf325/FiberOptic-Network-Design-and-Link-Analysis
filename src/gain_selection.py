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