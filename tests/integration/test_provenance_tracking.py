"""
Phase 3 Integration Test: Provenance Tracking

Tests the complete Phase 3 implementation including:
- Auto-generated methodology descriptions
- Dataframe introspection
- Instrument library integration
- Streamlined global attributes
- Quality assessment
"""

import pytest
import pandas as pd
import numpy as np

from metforce.output import build_netcdf_dataset


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_met_df():
    """Create sample meteorological DataFrame."""
    dates = pd.date_range("2024-01-01", periods=24, freq="h")
    return pd.DataFrame({
        "pressure": np.linspace(1013, 1015, 24),
        "temperature": np.linspace(20, 25, 24),
        "relative_humidity": np.linspace(60, 70, 24),
        "wind_speed": np.linspace(2, 5, 24),
        "wind_direction": np.linspace(180, 220, 24),
        "global_shortwave": np.linspace(0, 800, 24),
        "direct_shortwave": np.linspace(0, 600, 24),
    }, index=dates)


@pytest.fixture
def minimal_meta():
    """Minimal metadata for testing."""
    return {
        "title": "Test Dataset",
        "latitude": 35.0,
        "longitude": -97.0,
        "elevation_m": 300.0,
    }


@pytest.fixture
def complete_meta():
    """Complete metadata for testing."""
    return {
        "title": "Research Grade Dataset",
        "institution": "Test Lab",
        "comment": "Experimental dataset for validation",
        "latitude": 35.0,
        "longitude": -97.0,
        "elevation_m": 300.0,
    }


# =============================================================================
# TEST: MINIMAL CONFIGURATION (NO METADATA)
# =============================================================================

def test_minimal_config_works(sample_met_df, minimal_meta):
    """Test that minimal config (no metadata) produces valid NetCDF."""
    parameters = {
        "temperature": {"source": "met"},
        "pressure": {"source": "met"},
        "global_shortwave": {"source": "met"},
    }

    ds = build_netcdf_dataset(
        sample_met_df,
        meta=minimal_meta,
        parameters=parameters,
    )

    # Check required global attributes
    assert ds.attrs["Conventions"] == "CF-1.10"
    assert ds.attrs["title"] == "Test Dataset"
    assert ds.attrs["processing_level"] == "2"
    assert "history" in ds.attrs

    # Check geospatial attributes
    assert ds.attrs["geospatial_latitude"] == 35.0
    assert ds.attrs["geospatial_longitude"] == -97.0

    # Check variables have basic provenance
    assert "air_temperature" in ds
    assert ds["air_temperature"].attrs["source"] == "station"
    assert ds["air_temperature"].attrs["measurement_type"] == "in_situ"
    assert "quality_assessment" in ds["air_temperature"].attrs


# =============================================================================
# TEST: STATION PROVENANCE
# =============================================================================

def test_station_provenance_basic(sample_met_df, minimal_meta):
    """Test basic station provenance without instrument library."""
    parameters = {
        "temperature": {
            "source": "met",
            "metadata": {
                "comment": "Calibrated annually",
            }
        }
    }

    ds = build_netcdf_dataset(
        sample_met_df,
        meta=minimal_meta,
        parameters=parameters,
    )

    attrs = ds["air_temperature"].attrs

    # Check auto-generated comment is present
    assert "Direct measurement from weather station" in attrs["comment"]

    # Check user comment was appended
    assert "Calibrated annually" in attrs["comment"]

    # Check quality assessment
    assert attrs["quality_assessment"] == "All values consistent quality"


def test_station_provenance_with_instrument_library(sample_met_df, minimal_meta, tmp_path):
    """Test station provenance with instrument library."""
    # Create temp instrument library
    lib_file = tmp_path / "instruments.toml"
    lib_file.write_text("""
[thermohygrometers.test_sensor]
manufacturer = "Test Manufacturer"
model = "TH-100"
accuracy = "±0.2°C"
temperature_range = "-40 to 60°C"
response_time = "< 10 seconds"
""")

    parameters = {
        "temperature": {
            "source": "met",
            "metadata": {
                "instrument": "test_sensor",
                "serial_number": "T12345",
                "installation_height": 2.0,
                "comment": "Cleaned weekly",
            }
        }
    }

    ds = build_netcdf_dataset(
        sample_met_df,
        meta=minimal_meta,
        parameters=parameters,
        instrument_library_path=str(lib_file),
    )

    attrs = ds["air_temperature"].attrs

    # Check library specs merged
    assert attrs["instrument_manufacturer"] == "Test Manufacturer"
    assert attrs["instrument_model"] == "TH-100"
    assert attrs["accuracy"] == "±0.2°C"
    assert attrs["temperature_range"] == "-40 to 60°C"

    # Check deployment details
    assert attrs["serial_number"] == "T12345"
    assert attrs["sensor_height"] == "2.0 m"

    # Check comment merging
    assert "Test Manufacturer TH-100" in attrs["comment"]
    assert "Cleaned weekly" in attrs["comment"]


# =============================================================================
# TEST: NLDAS2 PROVENANCE
# =============================================================================

def test_nldas2_provenance(sample_met_df, minimal_meta):
    """Test NLDAS2 provenance metadata."""
    parameters = {
        "temperature": {
            "source": "nldas2",
            "metadata": {
                "comment": "Used for gap-filling",
            }
        }
    }

    ds = build_netcdf_dataset(
        sample_met_df,
        meta=minimal_meta,
        parameters=parameters,
    )

    attrs = ds["air_temperature"].attrs

    # Check NLDAS2-specific attributes
    assert attrs["source"] == "nldas2"
    assert attrs["data_type"] == "reanalysis"
    assert "NLDAS-2" in attrs["model"]
    assert attrs["spatial_resolution"] == "0.125 degree (~12.5 km)"

    # Check comment merging
    assert "NLDAS-2 reanalysis" in attrs["comment"]
    assert "Used for gap-filling" in attrs["comment"]

    # Check references
    assert "doi:10.1175/JCLI-D-20-0982.1" in attrs["references"]


# =============================================================================
# TEST: PVLIB PROVENANCE WITH INTROSPECTION
# =============================================================================

def test_pvlib_provenance_with_introspection(sample_met_df, minimal_meta):
    """Test pvlib provenance with dataframe introspection."""
    # Create source dataframe with pressure and T/RH
    source_df = sample_met_df.copy()
    source_df["BP_mbar"] = 1013.0
    source_df["AirT_2M"] = 20.0
    source_df["RH"] = 65.0

    dataframes = {"met": source_df}

    parameters = {
        "direct_shortwave": {
            "source": "pvlib_dirindex",
            "metadata": {
                "comment": "Validated against ARM pyrheliometer",
            }
        }
    }

    ds = build_netcdf_dataset(
        sample_met_df,
        meta=minimal_meta,
        parameters=parameters,
        dataframes=dataframes,
    )

    # Direct shortwave becomes BHI when we have solar zenith
    # Since we don't have zenith in sample data, it stays as direct
    cf_var = "surface_direct_along_beam_shortwave_flux_in_air"
    attrs = ds[cf_var].attrs

    # Check pvlib-specific attributes
    assert attrs["source"] == "pvlib"
    assert attrs["data_type"] == "derived"
    assert "dirindex" in attrs["method"]

    # Check introspected atmospheric corrections
    assert "atmospheric_corrections" in attrs
    assert "surface_pressure" in attrs["atmospheric_corrections"]
    assert "dew_point_temperature" in attrs["atmospheric_corrections"]

    # Check sources documented
    assert attrs["pressure_source"] == "station barometer"
    assert "air temperature and relative humidity" in attrs["dew_point_method"]

    # Check comment merging
    assert "Perez-Ineichen" in attrs["comment"]
    assert "Validated against ARM" in attrs["comment"]

    # Check references
    assert "Perez" in attrs["references"]


def test_pvlib_provenance_without_corrections(sample_met_df, minimal_meta):
    """Test pvlib provenance when no atmospheric data available."""
    parameters = {
        "direct_shortwave": {
            "source": "pvlib_dirindex",
        }
    }

    ds = build_netcdf_dataset(
        sample_met_df,
        meta=minimal_meta,
        parameters=parameters,
        dataframes={},  # Empty - no source data
    )

    cf_var = "surface_direct_along_beam_shortwave_flux_in_air"
    attrs = ds[cf_var].attrs

    # Should not have atmospheric corrections attributes
    assert "atmospheric_corrections" not in attrs
    assert "pressure_source" not in attrs
    assert "dew_point_method" not in attrs

    # But should still have basic provenance
    assert attrs["source"] == "pvlib"
    assert "dirindex" in attrs["method"]


# =============================================================================
# TEST: DERIVED VARIABLES
# =============================================================================

def test_derived_provenance(sample_met_df, minimal_meta):
    """Test provenance for derived variables."""
    parameters = {
        "diffuse_shortwave": {
            "source": "global_fraction",
            "metadata": {
                "comment": "Fixed 20% diffuse fraction",
            }
        }
    }

    # Add the variable to DataFrame
    sample_met_df["diffuse_shortwave"] = sample_met_df["global_shortwave"] * 0.2

    ds = build_netcdf_dataset(
        sample_met_df,
        meta=minimal_meta,
        parameters=parameters,
    )

    cf_var = "surface_diffuse_downwelling_shortwave_flux_in_air"
    attrs = ds[cf_var].attrs

    # Check derived provenance
    assert attrs["source"] == "global_fraction"
    assert attrs["data_type"] == "derived"
    assert "global shortwave" in attrs["comment"].lower()
    assert "Fixed 20% diffuse fraction" in attrs["comment"]


# =============================================================================
# TEST: GLOBAL ATTRIBUTES
# =============================================================================

def test_streamlined_global_attrs(sample_met_df, complete_meta):
    """Test streamlined global attributes."""
    parameters = {
        "temperature": {"source": "met"},
        "pressure": {"source": "nldas2"},
        "direct_shortwave": {"source": "pvlib_dirindex"},
    }

    ds = build_netcdf_dataset(
        sample_met_df,
        meta=complete_meta,
        parameters=parameters,
    )

    # Check CF compliance
    assert ds.attrs["Conventions"] == "CF-1.10"
    assert ds.attrs["featureType"] == "timeSeries"

    # Check user-specified
    assert ds.attrs["title"] == "Research Grade Dataset"
    assert ds.attrs["institution"] == "Test Lab"
    assert ds.attrs["comment"] == "Experimental dataset for validation"

    # Check auto-generated
    assert ds.attrs["processing_level"] == "2"
    assert "Generated by metforce" in ds.attrs["history"]

    # Check auto-detected sources
    sources = ds.attrs["source"].split()
    assert "nldas2" in sources
    assert "pvlib_model" in sources
    assert "weather_station" in sources

    # Check geospatial
    assert ds.attrs["geospatial_latitude"] == 35.0
    assert ds.attrs["geospatial_longitude"] == -97.0
    assert ds.attrs["geospatial_vertical_min"] == 300.0


# =============================================================================
# TEST: QUALITY ASSESSMENT
# =============================================================================

def test_quality_assessment_complete_data(sample_met_df, minimal_meta):
    """Test quality assessment for complete data."""
    parameters = {"temperature": {"source": "met"}}

    ds = build_netcdf_dataset(
        sample_met_df,
        meta=minimal_meta,
        parameters=parameters,
    )

    # Complete data should have homogeneous quality
    attrs = ds["air_temperature"].attrs
    assert attrs["quality_assessment"] == "All values consistent quality"


def test_quality_assessment_with_missing(sample_met_df, minimal_meta):
    """Test quality assessment for data with gaps."""
    # Introduce some NaN values
    sample_met_df.loc[sample_met_df.index[5:10], "temperature"] = np.nan

    parameters = {"temperature": {"source": "met"}}

    ds = build_netcdf_dataset(
        sample_met_df,
        meta=minimal_meta,
        parameters=parameters,
    )

    # Should document coverage percentage
    attrs = ds["air_temperature"].attrs
    assert "Data coverage" in attrs["quality_assessment"]
    # Should be around 79% (19/24 valid)
    assert "79" in attrs["quality_assessment"]


# =============================================================================
# TEST: COMMENT OVERRIDE
# =============================================================================

def test_comment_replace(sample_met_df, minimal_meta):
    """Test full comment override with comment_replace."""
    parameters = {
        "temperature": {
            "source": "met",
            "metadata": {
                "comment_replace": "Custom methodology description",
            }
        }
    }

    ds = build_netcdf_dataset(
        sample_met_df,
        meta=minimal_meta,
        parameters=parameters,
    )

    # Should use only the replacement comment
    attrs = ds["air_temperature"].attrs
    assert attrs["comment"] == "Custom methodology description"
    assert "Direct measurement" not in attrs["comment"]


# =============================================================================
# TEST: BACKWARD COMPATIBILITY
# =============================================================================

def test_backward_compatibility_no_metadata(sample_met_df, minimal_meta):
    """Test that old configs without metadata still work."""
    # Old-style config: just source, no metadata
    parameters = {
        "temperature": {"source": "met"},
        "pressure": {"source": "nldas2"},
    }

    ds = build_netcdf_dataset(
        sample_met_df,
        meta=minimal_meta,
        parameters=parameters,
    )

    # Should create valid NetCDF with auto-generated provenance
    assert "air_temperature" in ds
    assert "air_pressure" in ds

    # Variables should have basic provenance
    assert ds["air_temperature"].attrs["source"] == "station"
    assert ds["air_pressure"].attrs["source"] == "nldas2"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])