"""Visualization tools for meteorological NetCDF data."""

from .timeseries import plot_variable, plot_multiple, filter_time_range
from .radiation import plot_radiation_components, plot_clearness_index

try:
    from .interactive import create_time_slider
except ImportError:
    # ipywidgets not available
    pass

__all__ = [
    "plot_variable",
    "plot_multiple",
    "plot_radiation_components",
    "plot_clearness_index",
    "filter_time_range",
]