"""
Instrument Library Management for MetForce

Usage:
    library = InstrumentLibrary() # load default
    library = InstrumentLibrary("~/path/to/instruments.toml")  # default + custom
    specs = library.get("apogee_sp510")
"""

from typing import Any
from pathlib import Path
import toml

from metforce.logger_config import logger


class InstrumentSpec(dict[str, Any]):
    """
    Dictionary subclass for instrument specifications.

    Allows both dict-style and attribute-style access:
        spec["manufacturer"]  # dict style
        spec.get("model")     # dict method
    """
    pass


class InstrumentLibrary:
    """
    Manages instrument specifications from TOML files.

    Supports hierarchical organization:
        [pyranometers.apogee_sp510]
        [thermohygrometers.vaisala_hmp155]
        [barometers.vaisala_ptb330]

    Instruments can be referenced by short ID ("apogee_sp510") or
    full path ("pyranometers.apogee_sp510").
    """

    def __init__(self, custom_library: str | None = None):

        self._instruments: dict[str, InstrumentSpec] = {}
        self._load_default_library()

        if custom_library:
            self._load_custom_library(custom_library)

    def _load_default_library(self) -> None:
        """Load default instrument library shipped with metforce."""
        # Look for instruments.toml in same directory as this module
        default_path = Path(__file__).parent / "instruments.toml"

        if not default_path.exists():
            logger.warning(f"Default instrument library not found at {default_path}")
            return

        try:
            data = toml.load(default_path)
            self._add_instruments(data, source="default")
            logger.info(f"Loaded {len(self._instruments)} instruments from default library")
        except Exception as e:
            logger.error(f"Failed to load default instrument library: {e}")

    def _load_custom_library(self, path: str) -> None:

        custom_path = Path(path).expanduser()

        if not custom_path.exists():
            logger.warning(f"Custom instrument library not found at {custom_path}")
            return

        try:
            data = toml.load(custom_path)
            count_before = len(self._instruments)
            self._add_instruments(data, source="custom", override=True)
            count_after = len(self._instruments)
            new_count = count_after - count_before
            logger.info(f"Loaded custom library: {new_count} new, {count_after} total instruments")
        except Exception as e:
            logger.error(f"Failed to load custom instrument library: {e}")

    def _add_instruments(
            self,
            data: dict[str, Any],
            source: str = "unknown",
            override: bool = False
    ) -> None:
        """
        Add instruments from TOML data to library.

        Handles hierarchical structure like:
            [pyranometers.apogee_sp510]
            [thermohygrometers.vaisala_hmp155]

        Args:
            data: Parsed TOML data (nested dicts)
            source: Source identifier for logging
            override: If True, allow overriding existing specs
        """
        for category, instruments in data.items():
            if not isinstance(instruments, dict):
                continue

            for instrument_id, specs in instruments.items():
                if not isinstance(specs, dict):
                    continue

                # Create both short ID and full path ID
                short_id = instrument_id
                full_id = f"{category}.{instrument_id}"

                # Check for conflicts
                if short_id in self._instruments and not override:
                    logger.warning(
                        f"Duplicate instrument ID '{short_id}' from {source} "
                        f"(use full path '{full_id}' or custom library to override)"
                    )
                    continue

                # Store specs with metadata
                spec = InstrumentSpec(specs)
                spec["_category"] = category
                spec["_id"] = instrument_id
                spec["_full_id"] = full_id
                spec["_source"] = source

                # Store under both IDs
                self._instruments[short_id] = spec
                self._instruments[full_id] = spec

                logger.debug(f"Added instrument: {full_id} from {source}")

    def get(self, instrument_id: str) -> InstrumentSpec | None:
        """
        Get instrument specifications by ID.

        Example:
            >>> library = InstrumentLibrary()
            >>> spec = library.get("apogee_sp510")
            >>> print(spec["manufacturer"])
            Apogee Instruments Inc.
        """
        spec = self._instruments.get(instrument_id)

        if spec is None:
            logger.warning(f"Instrument '{instrument_id}' not found in library")

        return spec

    def list_instruments(self, category: str | None = None) -> list[str]:
        """
        List available instrument IDs.

        Args:
            category: Optional category filter (e.g., "pyranometers")

        Returns:
            List of instrument IDs (short form)
        """
        if category:
            # Return only instruments in this category
            return sorted([
                spec["_id"]
                for spec in self._instruments.values()
                if spec.get("_category") == category
            ])
        else:
            # Return all unique short IDs
            return sorted(set([
                spec["_id"]
                for spec in self._instruments.values()
            ]))

    def list_categories(self) -> list[str]:
        """List available instrument categories."""
        return sorted(set([
            spec["_category"]
            for spec in self._instruments.values()
            if "_category" in spec
        ]))

    def __contains__(self, instrument_id: str) -> bool:
        """Check if instrument exists: 'apogee_sp510' in library"""
        return instrument_id in self._instruments

    def __len__(self) -> int:
        """Count unique instruments (not counting duplicates from short/full IDs)."""
        return len(set(spec["_full_id"] for spec in self._instruments.values()))

    def __repr__(self) -> str:
        categories = self.list_categories()
        return f"InstrumentLibrary({len(self)} instruments, {len(categories)} categories)"


def merge_instrument_metadata(
        library: InstrumentLibrary | None,
        config_metadata: dict[str, Any]
) -> dict[str, Any]:
    """
    Merge instrument specs from library with deployment-specific config metadata.

    Priority order:
    1. Config metadata (deployment-specific) overrides library
    2. Library specs (model specifications) used as defaults
    3. Config metadata without instrument ID used as-is

    Args:
        library: InstrumentLibrary instance (or None)
        config_metadata: Metadata dict from parameter config

    Returns:
        Merged metadata dict

    Example:
        >>> library = InstrumentLibrary()
        >>> config = {
        ...     "instrument": "apogee_sp510",
        ...     "serial_number": "3847",
        ...     "installation_height": 2.0,
        ...     "comment": "Cleaned weekly"
        ... }
        >>> merged = merge_instrument_metadata(library, config)
        >>> # merged now has manufacturer, model, spectral_range (from library)
        >>> # plus serial_number, installation_height, comment (from config)
    """
    # Start with config metadata
    merged = dict(config_metadata)

    # If no library or no instrument ID, just return config
    instrument_id = config_metadata.get("instrument")
    if not library or not instrument_id:
        return merged

    # Get library specs
    specs = library.get(instrument_id)
    if not specs:
        logger.warning(
            f"Instrument '{instrument_id}' referenced but not found in library. "
            f"Using config metadata only."
        )
        return merged

    # Merge: library specs as defaults, config overrides
    # Don't include internal metadata fields (_category, _id, etc.)
    for key, value in specs.items():
        if key.startswith("_"):
            continue
        if key not in merged:
            merged[key] = value

    logger.debug(f"Merged library specs for '{instrument_id}' with config metadata")

    return merged


# Convenience function for common case
def load_instrument_library(custom_path: str | None = None) -> InstrumentLibrary:
    """
    Load instrument library (default + optional custom).
    """
    return InstrumentLibrary(custom_path)