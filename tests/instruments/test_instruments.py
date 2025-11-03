"""
Phase 2 Tests: Instrument Library

Tests instrument library loading, retrieval, and metadata merging.
Run with: pytest test_phase2_instruments.py -v
"""

import pytest
from pathlib import Path
import tempfile
import toml

from metforce.instruments import (
    InstrumentLibrary,
    merge_instrument_metadata,
    load_instrument_library
)


class TestInstrumentLibrary:
    """Test InstrumentLibrary loading and retrieval"""

    def test_load_default_library(self):
        """Test loading default library"""
        library = InstrumentLibrary()

        # Should have instruments
        assert len(library) > 0

        # Should have categories
        categories = library.list_categories()
        assert len(categories) > 0
        assert "pyranometers" in categories

    def test_get_by_short_id(self):
        """Test retrieving instrument by short ID"""
        library = InstrumentLibrary()

        # Get Apogee SP-510
        spec = library.get("apogee_sp510")
        assert spec is not None
        assert spec["manufacturer"] == "Apogee Instruments Inc."
        assert spec["model"] == "SP-510-SS"
        assert "spectral_range" in spec

    def test_get_by_full_id(self):
        """Test retrieving instrument by full path"""
        library = InstrumentLibrary()

        # Get by full ID
        spec = library.get("pyranometers.apogee_sp510")
        assert spec is not None
        assert spec["manufacturer"] == "Apogee Instruments Inc."

    def test_get_nonexistent(self):
        """Test retrieving non-existent instrument"""
        library = InstrumentLibrary()

        spec = library.get("nonexistent_instrument")
        assert spec is None

    def test_contains_check(self):
        """Test 'in' operator"""
        library = InstrumentLibrary()

        assert "apogee_sp510" in library
        assert "pyranometers.apogee_sp510" in library
        assert "nonexistent" not in library

    def test_list_instruments(self):
        """Test listing instruments"""
        library = InstrumentLibrary()

        # List all
        all_instruments = library.list_instruments()
        assert len(all_instruments) > 0
        assert "apogee_sp510" in all_instruments

        # List by category
        pyranometers = library.list_instruments(category="pyranometers")
        assert len(pyranometers) > 0
        assert "apogee_sp510" in pyranometers

        # Should not include instruments from other categories
        barometers = library.list_instruments(category="barometers")
        assert "apogee_sp510" not in barometers

    def test_list_categories(self):
        """Test listing categories"""
        library = InstrumentLibrary()

        categories = library.list_categories()
        assert "pyranometers" in categories
        assert "thermohygrometers" in categories
        assert "barometers" in categories

    def test_instrument_spec_metadata(self):
        """Test that specs include metadata fields"""
        library = InstrumentLibrary()

        spec = library.get("apogee_sp510")
        assert spec["_category"] == "pyranometers"
        assert spec["_id"] == "apogee_sp510"
        assert spec["_full_id"] == "pyranometers.apogee_sp510"
        assert spec["_source"] == "default"


class TestCustomLibrary:
    """Test custom library loading and overrides"""

    def test_load_custom_library(self):
        """Test loading custom library in addition to default"""
        # Create temporary custom library
        custom_data = {
            "custom_category": {
                "custom_instrument": {
                    "manufacturer": "Custom Manufacturer",
                    "model": "TEST-123",
                    "note": "This is a custom instrument"
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(custom_data, f)
            custom_path = f.name

        try:
            library = InstrumentLibrary(custom_path)

            # Should have both default and custom instruments
            assert "apogee_sp510" in library  # default
            assert "custom_instrument" in library  # custom

            # Should be able to retrieve custom instrument
            spec = library.get("custom_instrument")
            assert spec is not None
            assert spec["manufacturer"] == "Custom Manufacturer"
            assert spec["_source"] == "custom"
        finally:
            Path(custom_path).unlink()

    def test_custom_overrides_default(self):
        """Test that custom library can override default specs"""
        # Create custom library that overrides apogee_sp510
        custom_data = {
            "pyranometers": {
                "apogee_sp510": {
                    "manufacturer": "Apogee Instruments Inc.",
                    "model": "SP-510-SS",
                    "custom_note": "This is our lab-specific configuration",
                    "typical_sensitivity": "0.046 mV per W m⁻²"  # Override
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(custom_data, f)
            custom_path = f.name

        try:
            library = InstrumentLibrary(custom_path)

            spec = library.get("apogee_sp510")
            assert spec is not None
            assert spec["_source"] == "custom"
            assert "custom_note" in spec
            assert spec["typical_sensitivity"] == "0.046 mV per W m⁻²"
        finally:
            Path(custom_path).unlink()

    def test_missing_custom_library(self):
        """Test handling of missing custom library file"""
        # Should not crash, just log warning
        library = InstrumentLibrary("/nonexistent/path/instruments.toml")

        # Should still have default instruments
        assert "apogee_sp510" in library


class TestMetadataMerging:
    """Test merging library specs with config metadata"""

    def test_merge_with_library(self):
        """Test basic metadata merging"""
        library = InstrumentLibrary()

        config_metadata = {
            "instrument": "apogee_sp510",
            "serial_number": "3847",
            "installation_height": 2.0,
            "comment": "Cleaned weekly"
        }

        merged = merge_instrument_metadata(library, config_metadata)

        # Should have config fields
        assert merged["serial_number"] == "3847"
        assert merged["installation_height"] == 2.0
        assert merged["comment"] == "Cleaned weekly"

        # Should have library fields
        assert merged["manufacturer"] == "Apogee Instruments Inc."
        assert merged["model"] == "SP-510-SS"
        assert "spectral_range" in merged

    def test_config_overrides_library(self):
        """Test that config metadata overrides library specs"""
        library = InstrumentLibrary()

        config_metadata = {
            "instrument": "apogee_sp510",
            "typical_sensitivity": "0.048 mV per W m⁻²",  # Override library value
            "serial_number": "3847"
        }

        merged = merge_instrument_metadata(library, config_metadata)

        # Config value should override library
        assert merged["typical_sensitivity"] == "0.048 mV per W m⁻²"

        # Other library values should still be present
        assert merged["manufacturer"] == "Apogee Instruments Inc."

    def test_merge_without_instrument_id(self):
        """Test merging when no instrument ID specified"""
        library = InstrumentLibrary()

        config_metadata = {
            "comment": "Manual measurement",
            "accuracy": "±10%"
        }

        merged = merge_instrument_metadata(library, config_metadata)

        # Should just return config metadata unchanged
        assert merged == config_metadata

    def test_merge_with_missing_instrument(self):
        """Test merging with non-existent instrument ID"""
        library = InstrumentLibrary()

        config_metadata = {
            "instrument": "nonexistent_instrument",
            "serial_number": "123",
            "comment": "Test"
        }

        merged = merge_instrument_metadata(library, config_metadata)

        # Should return config metadata only (with warning logged)
        assert merged["instrument"] == "nonexistent_instrument"
        assert merged["serial_number"] == "123"
        assert "manufacturer" not in merged  # No library specs

    def test_merge_without_library(self):
        """Test merging when library is None"""
        config_metadata = {
            "instrument": "apogee_sp510",
            "serial_number": "3847"
        }

        merged = merge_instrument_metadata(None, config_metadata)

        # Should just return config metadata
        assert merged == config_metadata

    def test_internal_fields_not_merged(self):
        """Test that internal metadata fields (_category, _id, etc.) don't leak"""
        library = InstrumentLibrary()

        config_metadata = {
            "instrument": "apogee_sp510",
            "serial_number": "3847"
        }

        merged = merge_instrument_metadata(library, config_metadata)

        # Internal fields should not appear in merged metadata
        assert "_category" not in merged
        assert "_id" not in merged
        assert "_full_id" not in merged
        assert "_source" not in merged


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_load_instrument_library_default(self):
        """Test convenience loader without custom library"""
        library = load_instrument_library()

        assert isinstance(library, InstrumentLibrary)
        assert "apogee_sp510" in library

    def test_load_instrument_library_custom(self):
        """Test convenience loader with custom library"""
        custom_data = {
            "test_category": {
                "test_instrument": {
                    "manufacturer": "Test Inc.",
                    "model": "TEST"
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(custom_data, f)
            custom_path = f.name

        try:
            library = load_instrument_library(custom_path)

            assert "test_instrument" in library
            assert "apogee_sp510" in library  # Still has defaults
        finally:
            Path(custom_path).unlink()


class TestRealWorldScenarios:
    """Test realistic usage scenarios"""

    def test_research_grade_deployment(self):
        """Test full research-grade metadata scenario"""
        library = InstrumentLibrary()

        # Config has deployment-specific details
        config_metadata = {
            "instrument": "apogee_sp510",
            "serial_number": "3847",
            "installation_date": "2023-06-15",
            "installation_height": 2.0,
            "calibration_date": "2024-11-01",
            "comment": "Cleaned weekly. No drift observed in latest cal check."
        }

        merged = merge_instrument_metadata(library, config_metadata)

        # Should have complete metadata for NetCDF
        assert merged["manufacturer"] == "Apogee Instruments Inc."
        assert merged["model"] == "SP-510-SS"
        assert merged["spectral_range"] == "385 to 2105 nm (50% points)"
        assert merged["serial_number"] == "3847"
        assert merged["installation_date"] == "2023-06-15"
        assert merged["installation_height"] == 2.0
        assert "Cleaned weekly" in merged["comment"]

    def test_minimal_deployment(self):
        """Test minimal metadata scenario"""
        library = InstrumentLibrary()

        # Just instrument ID and basic note
        config_metadata = {
            "instrument": "vaisala_hmp155",
            "comment": "Station temperature sensor"
        }

        merged = merge_instrument_metadata(library, config_metadata)

        # Should still get rich library specs
        assert merged["manufacturer"] == "Vaisala Oyj"
        assert merged["model"] == "HMP155"
        assert "temperature_accuracy" in merged
        assert merged["comment"] == "Station temperature sensor"

    def test_multiple_instruments_same_model(self):
        """Test deploying multiple instruments of same model"""
        library = InstrumentLibrary()

        # Two pyranometers, same model, different deployments
        config1 = {
            "instrument": "apogee_sp510",
            "serial_number": "3847",
            "installation_height": 2.0,
            "comment": "Primary upward-facing"
        }

        config2 = {
            "instrument": "apogee_sp510",
            "serial_number": "3901",
            "installation_height": 2.0,
            "comment": "Backup sensor"
        }

        merged1 = merge_instrument_metadata(library, config1)
        merged2 = merge_instrument_metadata(library, config2)

        # Both should have same library specs
        assert merged1["manufacturer"] == merged2["manufacturer"]
        assert merged1["model"] == merged2["model"]

        # But different deployment details
        assert merged1["serial_number"] != merged2["serial_number"]
        assert merged1["comment"] != merged2["comment"]


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])