from __future__ import annotations

import os
import re
import sys
import time
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import pytest
import tomllib

# Opt-in guard: these tests may rely on local data or live fetches.
pytestmark = pytest.mark.skipif(
    os.getenv("MF_REGRESSION") != "1",
    reason="Set MF_REGRESSION=1 to run regression tests."
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "tests" / "data" / "regression_index.toml"

# ----- Utilities ----------------------------------------------------------------

def _set_env_for_determinism() -> None:
    os.environ["TZ"] = "UTC"
    os.environ["LC_ALL"] = "C"
    # tzset is posix-only; best-effort
    if hasattr(time, "tzset"):
        time.tzset()

def _load_manifest() -> list[dict[str, Any]]:
    with MANIFEST.open("rb") as f:
        data = tomllib.load(f)
    return data.get("case", [])

def _patch_config_text(text: str, *, start_range: str | None,
                       patch_source_map: list | None = None, outfile: Path) -> str:
    """
    Idempotently set start_range (if provided) and force outfile into [optional].
    The outfile injection removes any existing 'outfile =' lines to avoid duplicate-key TOML errors.
    """
    new = text

    # 1) start_range at top-level (or under [required]); replace if present, else insert under [required] if found
    if start_range is not None:
        if re.search(r'(?m)^\s*start_range\s*=', new):
            new = re.sub(
                r'(?m)^\s*start_range\s*=\s*".*?"\s*$',
                f'start_range = "{start_range}"',
                new,
            )
        else:
            # Insert under [required] if that table exists; else prepend at top
            if re.search(r'(?m)^\[\s*required\s*\]\s*$', new):
                new = re.sub(
                    r'(?m)^(\[\s*required\s*\]\s*\n)',
                    r'\1' + f'start_range = "{start_range}"\n',
                    new,
                    count=1,
                )
            else:
                new = f'start_range = "{start_range}"\n' + new

    # 2) Remove ANY existing outfile lines (any table)
    new = re.sub(r'(?m)^\s*outfile\s*=.*\n?', '', new)

    # 3) Ensure [optional] exists and inject outfile immediately after it
    m = re.search(r'(?m)^\[\s*optional\s*\]\s*$', new)
    if m:
        insert_at = m.end()
        new = new[:insert_at] + f'\noutfile = "{outfile.as_posix()}"\n' + new[insert_at:]
    else:
        new += f'\n\n[optional]\noutfile = "{outfile.as_posix()}"\n'

    if patch_source_map:
        for replacement in patch_source_map:
            from_str = replacement.get("from")
            to_str = replacement.get("to")
            if from_str and to_str:
                from_quoted = f'"{from_str}"'
                to_quoted = f'"{to_str}"'
                new = new.replace(from_quoted, to_quoted)

    return new


def _write_temp_config(orig_cfg: Path, tmp_dir: Path, *, patch_start: str | None,
                       patch_source_map: list | None = None, out_path: Path) -> Path:
    text = orig_cfg.read_text(encoding="utf-8")
    patched = _patch_config_text(text, start_range=patch_start, patch_source_map=patch_source_map, outfile=out_path)
    tmp_cfg = tmp_dir / orig_cfg.name
    tmp_cfg.write_text(patched, encoding="utf-8")
    return tmp_cfg

# --- add these helpers somewhere above the parametrized test ---

def _parse_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)

def _preflight_or_skip_on_path(cfg_path: Path) -> None:
    """
    Skip cases that require live NLDAS-2 or missing local files,
    by reading the *original* config (no patch side-effects).
    """
    cfg = _parse_toml(cfg_path)
    opt = (cfg.get("optional") or {})

    # Live NLDAS-2 fetch?
    pull_nldas2 = bool(opt.get("pull_nldas2", False))
    if pull_nldas2 and os.getenv("MF_NLDAS2") != "1":
        pytest.skip("Requires NLDAS-2 fetch. Set MF_NLDAS2=1 to enable this regression case.")

    # Local met-station file?
    metfile = opt.get("metfile")
    if isinstance(metfile, str):
        mf_path = Path(os.path.expanduser(metfile))
        if not mf_path.exists():
            pytest.skip(f"Local metfile not found: {mf_path}. Provide it or adjust the config to run this case.")


# --- replace the old runner with this ---
def _run_metforce_with_config(config_path: Path) -> None:
    """
    Prefer the top-level metforce.py script. Fall back to -m only if a package __main__ exists.
    No production changes required.
    """
    candidates: list[list[str]] = []

    pkg_main = REPO_ROOT / "metforce" / "__main__.py"
    top_script = REPO_ROOT / "metforce.py"

    if top_script.exists():
        candidates.append([sys.executable, str(top_script), str(config_path)])
    if pkg_main.exists():
        candidates.append([sys.executable, "-m", "metforce", str(config_path)])

    if not candidates:
        raise RuntimeError("Cannot find a CLI entrypoint: expected metforce.py or metforce/__main__.py")

    last_err: subprocess.CalledProcessError | None = None
    for cmd in candidates:
        try:
            subprocess.run(cmd, check=True, cwd=REPO_ROOT)
            return
        except subprocess.CalledProcessError as e:
            last_err = e
    assert last_err is not None
    raise last_err

def _read_met(path: Path, *, expected_cols: list[str]) -> pl.DataFrame:
    """
    Read legacy .met robustly:
    - Find the explicit column header line ("Day Hr Min ...").
    - Skip one or more units/legend lines after the header (first token not integer).
    - Parse subsequent numeric rows, mapping by column names (ignore extra columns like 'Sec').
    - Return only the expected_cols, in that order.
    """
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()

    # 1) locate header: the line that starts with "Day Hr Min"
    header_idx = None
    header_tokens: list[str] | None = None
    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s or s.lstrip().startswith("#"):
            continue
        toks = s.split()
        if len(toks) >= 3 and toks[0] == "Day" and toks[1] == "Hr" and toks[2] == "Min":
            header_idx = i
            header_tokens = toks
            break
    if header_idx is None or header_tokens is None:
        raise AssertionError(f"Did not find 'Day Hr Min' header in {path}")

    # 2) build a column index map from header tokens
    #    We allow extra columns in the file; we only keep expected ones.
    idx_map: dict[str, int] = {}
    name_to_pos = {name: pos for pos, name in enumerate(header_tokens)}
    for name in expected_cols:
        if name not in name_to_pos:
            raise AssertionError(
                f"Expected column '{name}' not present in header of {path}. "
                f"Header columns: {header_tokens}"
            )
        idx_map[name] = name_to_pos[name]

    # 3) find the first data row: skip units/legend lines after header
    i = header_idx + 1
    n = len(lines)
    def _is_data_line(toks: list[str]) -> bool:
        if len(toks) <= max(idx_map.values()):
            return False
        try:
            d = int(toks[idx_map["Day"]]); h = int(toks[idx_map["Hr"]]); m = int(toks[idx_map["Min"]])
        except Exception:
            return False
        return 1 <= d <= 366 and 0 <= h <= 23 and 0 <= m <= 59

    # skip non-numeric/unit lines until we hit a data line
    while i < n:
        s = lines[i].strip()
        if s and not s.lstrip().startswith("#"):
            toks = s.split()
            if _is_data_line(toks):
                break
        i += 1

    if i >= n:
        # optional debug dump on failure
        if os.getenv("MF_REG_DEBUG") == "1":
            print("---- DEBUG: first 40 non-comment lines ----", file=sys.stderr)
            cnt = 0
            for raw in lines:
                if not raw.strip() or raw.lstrip().startswith("#"):
                    continue
                print(raw.rstrip(), file=sys.stderr)
                cnt += 1
                if cnt >= 40:
                    break
        raise AssertionError(f"No data rows recognized in {path}")

    # 4) collect rows
    rows: list[list[float]] = []
    for j in range(i, n):
        s = lines[j].strip()
        if not s or s.lstrip().startswith("#"):
            continue
        toks = s.split()
        if not _is_data_line(toks):
            # ignore stray lines after the table
            continue
        # assemble the row in expected_cols order; missing values → nan (shouldn't happen if header matched)
        vals: list[float] = []
        for name in expected_cols:
            pos = idx_map[name]
            try:
                vals.append(float(toks[pos]))
            except ValueError:
                vals.append(np.nan)
        rows.append(vals)

    if not rows:
        raise AssertionError(f"No data values parsed in {path}")

    # 5) DataFrame construction
    df = pl.DataFrame(rows, orient="row", schema=expected_cols)
    # fix types for discrete fields
    df = df.with_columns(
        pl.col("Day").cast(pl.Int64, strict=False),
        pl.col("Hr").cast(pl.Int64, strict=False),
        pl.col("Min").cast(pl.Int64, strict=False),
    )
    return df


def _angular_diff_deg(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Minimal signed angular difference in degrees, wrapped into [-180, 180].
    """
    d = (a - b + 180.0) % 360.0 - 180.0
    return d

def _assert_frames_close(
    got: pl.DataFrame,
    exp: pl.DataFrame,
    *,
    discrete_cols: list[str],
    float_cols: list[str],
    rtol: float,
    atol: float,
) -> None:
    # Basic shape check
    assert got.shape == exp.shape, f"Row/col mismatch: got {got.shape}, expected {exp.shape}"

    # Check discrete time fields exactly
    for col in discrete_cols:
        assert (got[col] == exp[col]).all(), f"Mismatch in discrete column {col}"

    # Continuous columns with tolerances, special handling for wind direction
    for col in float_cols:
        g = got[col].to_numpy()
        e = exp[col].to_numpy()
        if col.lower() in {"wnddir", "winddir", "wind_dir"}:
            both_nan = np.isnan(g) & np.isnan(e)
            one_nan  = np.isnan(g) ^ np.isnan(e)
            if np.any(one_nan):
                k = int(np.where(one_nan)[0][0])
                raise AssertionError(f"{col} NaN mismatch at row {k}: got={g[k]!r}, exp={e[k]!r}")

            gi = g[~both_nan]; ei = e[~both_nan]
            d = np.abs(_angular_diff_deg(gi, ei))
            thresh = np.maximum(atol, rtol * np.maximum(1.0, np.abs(ei)))
            bad = d > thresh
            if np.any(bad):
                j_local = int(np.argmax(d - thresh))
                j = int(np.where(~both_nan)[0][j_local])
                raise AssertionError(
                    f"{col} exceeded angular tolerance at row {j}: "
                    f"Δ={d[j_local]:.6g} deg (tol {thresh[j_local]:.6g})"
                )
        else:
            if not np.allclose(g, e, rtol=rtol, atol=atol, equal_nan=True):
                idx = int(np.where(~np.isclose(g, e, rtol=rtol, atol=atol, equal_nan=True))[0][0])
                raise AssertionError(
                    f"{col} mismatch at row {idx}: got={g[idx]!r}, exp={e[idx]!r}"
                )

# ----- Parametrized test --------------------------------------------------------

@pytest.mark.parametrize("case", _load_manifest(), ids=lambda c: c["name"])
def test_legacy_met_regression(tmp_path: Path, case: dict[str, Any]) -> None:
    _set_env_for_determinism()

    # Resolve paths
    cfg_path = REPO_ROOT / case["config"]
    exp_path = REPO_ROOT / case["expected_met"]
    assert cfg_path.exists(), f"Missing config: {cfg_path}"
    assert exp_path.exists(), f"Missing expected .met: {exp_path}"

    _preflight_or_skip_on_path(cfg_path)

    # Build a temporary config with patched start_range (if provided) and an isolated outfile
    out_path = tmp_path / "out.met"
    patch_start: str | None = case.get("patch_start_range")
    patch_source_map: list | None = case.get("patch_source_map")
    tmp_cfg = _write_temp_config(
        cfg_path,
        tmp_path,
        patch_start=patch_start,
        patch_source_map=patch_source_map,
        out_path=out_path
    )

    _run_metforce_with_config(tmp_cfg)

    # Read expected and produced .met files
    expected_cols: list[str] = case["discrete_columns"] + case["float_columns"]
    got_df = _read_met(out_path, expected_cols=expected_cols)
    exp_df = _read_met(exp_path, expected_cols=expected_cols)

    # Compare
    _assert_frames_close(
        got_df, exp_df,
        discrete_cols=case["discrete_columns"],
        float_cols=case["float_columns"],
        rtol=float(case["rtol"]),
        atol=float(case["atol"]),
    )
