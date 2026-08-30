SPEED_OF_LIGHT = 299792458


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
    over a complete optical route before compensation.

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


# ============================================================
# NRZ-OOK pulse broadening helpers
# ============================================================

def calculate_spectral_width_nm(
    wavelength_nm,
    bit_rate_gbps
):
    """
    Estimate the optical spectral width of an NRZ-OOK
    channel from its bit rate.

    Baseline approximation:
        delta_f ~= bit rate
    """

    wavelength_m = (
        wavelength_nm * 1e-9
    )

    bandwidth_hz = (
        bit_rate_gbps * 1e9
    )

    spectral_width_m = (
        wavelength_m ** 2
        / SPEED_OF_LIGHT
        * bandwidth_hz
    )

    return spectral_width_m * 1e9


def calculate_bit_period_ps(
    bit_rate_gbps
):
    """
    Calculate one bit period in ps.
    """

    return (
        1000.0 / bit_rate_gbps
    )


def calculate_dispersion_broadening(
    accumulated_dispersion_ps_per_nm,
    spectral_width_nm
):
    """
    Estimate pulse broadening due to chromatic dispersion.

    delta_T = |D_total| * delta_lambda
    """

    return (
        abs(accumulated_dispersion_ps_per_nm)
        * spectral_width_nm
    )


# ============================================================
# Ideal compensation helper
# ============================================================

def generate_ideal_compensation_plan(
    network,
    dispersion_ps_per_nm_km
):
    """
    Generate the theoretical ideal chromatic-dispersion
    compensation value for every directed physical link.

    This helper is retained for comparison only.

    The actual network validation should use the commercial
    DCM configuration from dispersion_compensation.json.

    Returns
    -------
    compensation_by_link : dict
        Ideal compensation in ps/nm for every directed link.
    """

    compensation_by_link = {}

    for link_name, link in network.items():

        fiber_dispersion = (
            calculate_link_dispersion(
                length_km=link["length_km"],
                dispersion_ps_per_nm_km=(
                    dispersion_ps_per_nm_km
                )
            )
        )

        compensation_by_link[
            link_name
        ] = -fiber_dispersion

    return compensation_by_link


# ============================================================
# Residual dispersion using configured commercial DCMs
# ============================================================

def calculate_residual_route_dispersion(
    route,
    network,
    dispersion_ps_per_nm_km,
    dispersion_compensation
):
    """
    Calculate residual chromatic dispersion after applying
    the configured DCM compensation on every directed link.

    Parameters
    ----------
    route : str
        Example: "A-B|B-C"

    network : dict
        Directed-link network configuration.

    dispersion_ps_per_nm_km : float
        Fiber dispersion coefficient.

    dispersion_compensation : dict
        DCM configuration loaded directly from
        data/dispersion_compensation.json.

        Example:
        {
            "A-B": {
                "model": "DCM-HDC",
                "position_km": 190,
                "modules": 1,
                "compensation_ps_per_nm": -5760,
                "total_insertion_loss_db": 3.7
            }
        }

    Returns
    -------
    total_residual_ps_per_nm : float
        Residual dispersion over the complete route.

    trace : list
        Per-link fiber dispersion, configured compensation,
        and residual dispersion.
    """

    links = route.split("|")

    total_fiber_dispersion = 0.0
    total_compensation = 0.0

    trace = []

    for link_name in links:

        if link_name not in dispersion_compensation:
            raise ValueError(
                f"No DCM configuration found for {link_name}"
            )

        length_km = network[
            link_name
        ]["length_km"]

        fiber_dispersion = (
            calculate_link_dispersion(
                length_km=length_km,
                dispersion_ps_per_nm_km=(
                    dispersion_ps_per_nm_km
                )
            )
        )

        dcm_config = (
            dispersion_compensation[
                link_name
            ]
        )

        compensation = (
            dcm_config[
                "compensation_ps_per_nm"
            ]
        )

        residual = (
            fiber_dispersion
            + compensation
        )

        total_fiber_dispersion += (
            fiber_dispersion
        )

        total_compensation += (
            compensation
        )

        trace.append({
            "link": link_name,
            "fiber_dispersion_ps_per_nm": (
                fiber_dispersion
            ),
            "dcm_model": (
                dcm_config.get(
                    "model"
                )
            ),
            "dcm_modules": (
                dcm_config.get(
                    "modules"
                )
            ),
            "dcm_position_km": (
                dcm_config.get(
                    "position_km"
                )
            ),
            "compensation_ps_per_nm": (
                compensation
            ),
            "residual_ps_per_nm": (
                residual
            )
        })

    total_residual_ps_per_nm = (
        total_fiber_dispersion
        + total_compensation
    )

    return (
        total_residual_ps_per_nm,
        trace
    )
