from __future__ import annotations

from typing import Optional

import altair as alt
import numpy as np
import pandas as pd
import xarray as xr

from .timeseries import filter_time_range

alt.data_transformers.enable('vegafusion')

def plot_radiation_components(
        nc_path: str,
        *,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        width: int = 800,
        height: int = 400,
        interactive: str = "scrub"
) -> alt.Chart:
    """
    Plot global, direct (DNI), and diffuse radiation with scrubber.

    Args:
        nc_path: Path to NetCDF file
        start_time: Optional ISO format start (pre-filter data)
        end_time: Optional ISO format end (pre-filter data)
        width: Plot width in pixels
        height: Plot height in pixels
        interactive: "scrub" (default), "zoom", or "none"

    Returns:
        Layered Altair chart with legend and scrubber

    Example:
        >>> chart = plot_radiation_components("data.nc")
        >>> chart.save("radiation.html")
    """
    ds = xr.open_dataset(nc_path)
    ds = filter_time_range(ds, start_time, end_time)

    rad_vars = {
        "surface_downwelling_shortwave_flux_in_air": "Global (GHI)",
        "surface_direct_along_beam_shortwave_flux_in_air": "Direct (DNI)",
        "surface_diffuse_downwelling_shortwave_flux_in_air": "Diffuse (DHI)"
    }

    # Build long-form dataframe
    data = []
    for cf_name, label in rad_vars.items():
        if cf_name in ds:
            var_df = ds[cf_name].to_dataframe().reset_index()
            var_df["component"] = label
            var_df = var_df.rename(columns={cf_name: "value"})
            data.append(var_df[["time", "component", "value"]])

    if not data:
        raise ValueError("No radiation variables found in dataset")

    df = pd.concat(data, ignore_index=True)

    # Base chart
    base = alt.Chart(df).mark_line().encode(
        x=alt.X("time:T", title="Time"),
        y=alt.Y("value:Q", title="Irradiance (W/m²)"),
        color=alt.Color("component:N", title="Component"),
        tooltip=[
            alt.Tooltip("time:T", format="%Y-%m-%d %H:%M"),
            "component:N",
            alt.Tooltip("value:Q", title="W/m²", format=".1f")
        ]
    )

    # Handle interactivity
    if interactive == 'scrub':
        brush = alt.selection_interval(encodings=['x'])

        # Main chart
        main = base.encode(
            x=alt.X("time:T", title="Time", scale=alt.Scale(domain=brush))
        ).properties(
            title="Solar Radiation Components",
            width=width,
            height=height
        )

        # Context chart (show just one component for simplicity)
        context_df = df[df["component"] == "Global (GHI)"].copy()
        context = alt.Chart(context_df).mark_line().encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y("value:Q", title="")
        ).properties(
            title="← Drag to zoom →",
            width=width,
            height=60
        ).add_params(brush)

        return alt.vconcat(main, context)

    # Other modes
    chart = base.properties(
        title="Solar Radiation Components",
        width=width,
        height=height
    )

    if interactive == 'zoom':
        return chart.interactive()

    return chart

def plot_clearness_index(
        nc_path: str,
        *,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        width: int = 800,
        height: int = 300,
        interactive: str = "scrub"
) -> alt.Chart:
    """
    Plot clearness index (GHI / extraterrestrial radiation).

    Args:
        nc_path: Path to NetCDF file
        start_time: Optional ISO format start (pre-filter data)
        end_time: Optional ISO format end (pre-filter data)
        width: Plot width in pixels
        height: Plot height in pixels
        interactive: "scrub" (default), "zoom", or "none"

    Returns:
        Altair chart of clearness index with scrubber
    """
    ds = xr.open_dataset(nc_path)
    ds = filter_time_range(ds, start_time, end_time)

    ghi_var = "surface_downwelling_shortwave_flux_in_air"
    zenith_var = "solar_zenith_angle"

    if ghi_var not in ds:
        raise ValueError(f"GHI variable '{ghi_var}' not found")

    if zenith_var not in ds:
        raise ValueError(f"Zenith variable '{zenith_var}' not found - needed for clearness index")

    # Compute clearness index
    ghi = ds[ghi_var].values
    zenith = ds[zenith_var].values

    # Daytime only (zenith < 85°)
    daytime = zenith < 85

    # Solar constant and TOA calculation
    solar_constant = 1367  # W/m²
    cos_zenith = np.cos(np.deg2rad(zenith))
    toa = solar_constant * cos_zenith

    kt = np.where((daytime) & (toa > 0), ghi / toa, np.nan)

    df = pd.DataFrame({
        "time": ds["time"].values,
        "clearness_index": kt
    })

    # Base chart
    base = alt.Chart(df).mark_line().encode(
        x=alt.X("time:T", title="Time"),
        y=alt.Y("clearness_index:Q",
                title="Clearness Index (kt)",
                scale=alt.Scale(domain=[0, 1])),
        tooltip=[
            alt.Tooltip("time:T", format="%Y-%m-%d %H:%M"),
            alt.Tooltip("clearness_index:Q", format=".3f")
        ]
    )

    # Handle interactivity
    if interactive == 'scrub':
        brush = alt.selection_interval(encodings=['x'])

        # Main chart
        main = base.encode(
            x=alt.X("time:T", title="Time", scale=alt.Scale(domain=brush))
        ).properties(
            title="Atmospheric Clearness Index (GHI / TOA)",
            width=width,
            height=height
        )

        # Context chart
        context = base.encode(
            y=alt.Y("clearness_index:Q", title="")
        ).properties(
            title="← Drag to zoom →",
            width=width,
            height=60
        ).add_params(brush)

        return alt.vconcat(main, context)

    # Other modes
    chart = base.properties(
        title="Atmospheric Clearness Index (GHI / TOA)",
        width=width,
        height=height
    )

    if interactive == 'zoom':
        return chart.interactive()

    return chart