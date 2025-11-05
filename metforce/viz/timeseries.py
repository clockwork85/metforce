"""Time series visualization for NetCDF meteorological data."""
from __future__ import annotations

from typing import Optional

import altair as alt
import pandas as pd
import xarray as xr

alt.data_transformers.enable('vegafusion')

def filter_time_range(
        ds: xr.Dataset,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
) -> xr.Dataset:
    """
    Pre-filter dataset to time range before visualization.

    This is useful for loading only a subset of data (e.g., "only show January").
    Separate from interactive scrubbing which happens in the browser.

    Args:
        ds: Input dataset
        start_time: ISO format start time (e.g., "2025-01-15T00:00:00")
        end_time: ISO format end time

    Returns:
        Filtered dataset
    """
    if start_time is None and end_time is None:
        return ds

    if start_time is not None:
        time_start = pd.to_datetime(start_time)
        ds = ds.sel(time=slice(time_start, None))

    if end_time is not None:
        time_end = pd.to_datetime(end_time)
        ds = ds.sel(time=slice(None, time_end))

    return ds


def plot_variable(
        nc_path: str,
        variable: str,
        *,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        title: Optional[str] = None,
        width: int = 800,
        height: int = 400,
        interactive: str = "scrub"
) -> alt.Chart:
    """
    Plot single variable time series with interactive scrubbing.

    Args:
        nc_path: Path to NetCDF file
        variable: CF variable name (e.g., "air_temperature")
        start_time: Optional ISO format start (pre-filter data)
        end_time: Optional ISO format end (pre-filter data)
        title: Optional plot title
        width: Plot width in pixels
        height: Plot height in pixels
        interactive: "scrub" (default), "zoom", or "none"
            - "scrub": Adds timeline scrubber below chart
            - "zoom": Simple zoom/pan with mouse
            - "none": Static chart

    Returns:
        Altair chart (with scrubber by default)

    Example:
        >>> # Interactive scrubber (default)
        >>> chart = plot_variable("data.nc", "air_temperature")
        >>> chart.save("temp.html")
        >>>
        >>> # Pre-filter to January, then scrub within January
        >>> chart = plot_variable(
        ...     "data.nc",
        ...     "air_temperature",
        ...     start_time="2025-01-01",
        ...     end_time="2025-01-31"
        ... )
    """
    ds = xr.open_dataset(nc_path)
    ds = filter_time_range(ds, start_time, end_time)

    if variable not in ds:
        available = [v for v in ds.data_vars if not v.startswith("qc_")]
        raise ValueError(f"Variable '{variable}' not found. Available: {available}")

    # Convert to pandas
    df = ds[variable].to_dataframe().reset_index()

    # Get metadata
    attrs = ds[variable].attrs
    long_name = attrs.get("long_name", variable)
    units = attrs.get("units", "")

    if title is None:
        title = long_name

    y_label = f"{long_name} ({units})" if units else long_name

    # --- Define base chart (reused for main and context) ---
    base = alt.Chart(df).mark_line().encode(
        x=alt.X("time:T", title="Time"),
        y=alt.Y(f"{variable}:Q", title=y_label),
        tooltip=[
            alt.Tooltip("time:T", title="Time", format="%Y-%m-%d %H:%M"),
            alt.Tooltip(f"{variable}:Q", title=long_name, format=".2f")
        ]
    )

    # --- Handle interactivity modes ---
    if interactive == 'scrub':
        # Create brush for time scrubbing
        brush = alt.selection_interval(encodings=['x'])

        # Main chart - x-axis linked to brush
        main = base.encode(
            x=alt.X("time:T", title="Time", scale=alt.Scale(domain=brush))
        ).properties(
            title=title,
            width=width,
            height=height
        )

        # Context chart (scrubber) - attach brush here
        context = base.encode(
            y=alt.Y(f"{variable}:Q", title="")  # Hide y-label
        ).properties(
            title="← Drag on timeline to zoom main chart →",
            width=width,
            height=60
        ).add_params(brush)

        # Stack vertically
        return alt.vconcat(main, context)

    # --- Other modes ---
    chart = base.properties(
        title=title,
        width=width,
        height=height
    )

    if interactive == 'zoom':
        return chart.interactive()

    return chart  # 'none' mode


def plot_multiple(
        nc_path: str,
        variables: list[str],
        *,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        title: Optional[str] = None,
        width: int = 700,
        height_per_var: int = 200,
        interactive: str = "scrub"
) -> alt.Chart:
    """
    Plot multiple variables with shared time scrubber.

    Args:
        nc_path: Path to NetCDF file
        variables: List of CF variable names
        start_time: Optional ISO format start (pre-filter data)
        end_time: Optional ISO format end (pre-filter data)
        title: Optional overall title
        width: Plot width in pixels
        height_per_var: Height per variable panel
        interactive: "scrub" (default), "zoom", or "none"

    Returns:
        Concatenated Altair chart with shared scrubber

    Example:
        >>> chart = plot_multiple(
        ...     "data.nc",
        ...     ["air_temperature", "relative_humidity", "wind_speed"]
        ... )
        >>> chart.save("multi.html")
        >>> # All variables zoom together when you scrub the timeline
    """
    ds = xr.open_dataset(nc_path)
    ds = filter_time_range(ds, start_time, end_time)

    # --- Create shared brush for all charts ---
    brush = None
    if interactive == 'scrub':
        brush = alt.selection_interval(encodings=['x'])

    # --- Build main charts for each variable ---
    charts = []
    context_df = None
    first_var_name = None

    for var in variables:
        if var not in ds:
            print(f"Warning: Variable '{var}' not found, skipping")
            continue

        attrs = ds[var].attrs
        long_name = attrs.get("long_name", var)
        units = attrs.get("units", "")
        y_label = f"{long_name} ({units})" if units else long_name

        df = ds[var].to_dataframe().reset_index()

        # Save first variable for context chart
        if context_df is None:
            context_df = df
            first_var_name = var

        # Base chart for this variable
        chart = alt.Chart(df).mark_line().encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y(f"{var}:Q", title=y_label),
            tooltip=[
                alt.Tooltip("time:T", format="%Y-%m-%d %H:%M"),
                alt.Tooltip(f"{var}:Q", format=".2f")
            ]
        ).properties(
            width=width,
            height=height_per_var
        )

        # Link to brush or make interactive
        if interactive == 'scrub':
            chart = chart.encode(
                x=alt.X("time:T", title="Time", scale=alt.Scale(domain=brush))
            )
        elif interactive == 'zoom':
            chart = chart.interactive()

        charts.append(chart)

    if not charts:
        return alt.Chart().mark_text(text="No valid variables found.")

    # Combine main charts
    combined = alt.vconcat(*charts)
    if title:
        combined = combined.properties(title=title)

    # --- Add shared scrubber at bottom ---
    if interactive == 'scrub' and context_df is not None:
        context = alt.Chart(context_df).mark_line().encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y(f"{first_var_name}:Q", title="")
        ).properties(
            title="← Drag on timeline to zoom all charts →",
            width=width,
            height=60
        ).add_params(brush)

        return alt.vconcat(combined, context)

    return combined