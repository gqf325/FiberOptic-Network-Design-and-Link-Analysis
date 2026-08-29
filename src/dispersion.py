# ============================================================
# Chromatic dispersion
# ============================================================

def calculate_link_dispersion(
    length_km,
    dispersion_ps_per_nm_km
):
    """
    Calculate accumulated chromatic dispersion
    over one fiber link.

    Returns
    -------
    dispersion_ps_per_nm : float
        Accumulated dispersion in ps/nm.
    """

    return (
        dispersion_ps_per_nm_km
        * length_km
    )


def calculate_route_dispersion(
    route,
    network,
    dispersion_ps_per_nm_km
):
    """
    Calculate accumulated chromatic dispersion
    over a complete optical route.

    Example
    -------
    A-B|B-C
    """

    links = route.split("|")

    total_dispersion_ps_per_nm = 0.0

    trace = []

    for link_name in links:

        length_km = network[
            link_name
        ]["length_km"]

        link_dispersion = (
            calculate_link_dispersion(
                length_km=length_km,
                dispersion_ps_per_nm_km=(
                    dispersion_ps_per_nm_km
                )
            )
        )

        total_dispersion_ps_per_nm += (
            link_dispersion
        )

        trace.append({
            "link": link_name,
            "length_km": length_km,
            "dispersion_ps_per_nm": (
                link_dispersion
            )
        })

    return (
        total_dispersion_ps_per_nm,
        trace
    )