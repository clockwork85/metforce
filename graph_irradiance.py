#!/usr/bin/env python3
"""
Plot Direct / Diffuse short‑wave irradiance from multiple *.met files.

Usage
-----
python plot_met_irradiance.py file1.met file2.met ... [--start 2025-03-01] [--end 2025-03-31]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _read_met(path: Path) -> pd.DataFrame:
    """
    Parse a MET‑Force *.met* file into a DataFrame indexed by UTC datetime.

    The first five lines are header / units.  Line 3 contains the year.
    """
    with path.open("r", encoding="utf‑8") as f:
        header1 = f.readline().strip()          # descriptive string
        _ = f.readline()                        # Elevation / Lat / Lon / GMT / Year  header
        year_line = f.readline().strip()        # contains the numeric year
        units_line = f.readline()               # column names
        _ = f.readline()                        # units row we do not need

    year = int(year_line.split()[-1])
    col_names: list[str] = units_line.split()

    # Data start after five lines; read as whitespace‑delimited
    df = pd.read_table(
        path,
        delim_whitespace=True,
        skiprows=5,
        names=col_names,
        dtype=float,
    )

    # Build datetime index from DOY + Hr + Min + Year  (all integers)
    doy = df["Day"].astype(int)
    hr = df["Hr"].astype(int)
    minute = df["Min"].astype(int)

    # pandas to_datetime with a datetime origin is handy here
    dt = (
        pd.to_datetime(f"{year}-01-01", utc=True)
        + pd.to_timedelta(doy - 1, unit="D")
        + pd.to_timedelta(hr, unit="h")
        + pd.to_timedelta(minute, unit="m")
    )
    df.index = dt
    df.rename(columns={"Direct": "direct", "Diffuse": "diffuse"}, inplace=True)
    df.attrs["title"] = header1
    return df[["direct", "diffuse"]]


def _window(df: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    """Return a slice between *start* and *end* (inclusive) if given."""
    if start:
        df = df.loc[start:]  # type: ignore[arg-type]
    if end:
        df = df.loc[:end]    # type: ignore[arg-type]
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Main routine
# ──────────────────────────────────────────────────────────────────────────────
def _main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Overlay direct and diffuse irradiance from multiple *.met files."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="*.met files to plot")
    parser.add_argument("--start", type=str, default=None, help="YYYY‑MM‑DD[ HH:MM] UTC")
    parser.add_argument("--end", type=str, default=None, help="YYYY‑MM‑DD[ HH:MM] UTC")
    args = parser.parse_args(argv)

    # Read all files
    frames: dict[str, pd.DataFrame] = {
        p.stem: _window(_read_met(p), args.start, args.end) for p in args.paths
    }

    # ── Plot ────────────────────────────────────────────────────────────────
    fig, (ax_dir, ax_dif) = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
    ax_dir.set_ylabel("Direct Irradiance [W m⁻²]")
    ax_dif.set_ylabel("Diffuse Irradiance [W m⁻²]")
    ax_dif.set_xlabel("UTC time")

    for label, df in frames.items():
        ax_dir.plot(df.index, df["direct"], label=label)
        ax_dif.plot(df.index, df["diffuse"], label=label)

    ax_dir.set_title("Direct short‑wave irradiance")
    ax_dif.set_title("Diffuse short‑wave irradiance")
    ax_dir.legend(loc="upper right")
    ax_dif.legend(loc="upper right")

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":  # pragma: no cover
    _main()
