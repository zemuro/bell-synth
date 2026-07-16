#!/usr/bin/env python3
"""
Tests for the Bell Sample Overtone Analyzer CLI.

Generates a synthetic bell sample and verifies that analyze_bell.py recovers the
known partials within the tolerances specified in the phase plan.
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANALYZE_BELL = PROJECT_ROOT / "analyze_bell.py"
GENERATE_SAMPLE = PROJECT_ROOT / "tests" / "generate_test_sample.py"
SAMPLE_PATH = PROJECT_ROOT / "samples" / "synthetic_bell.wav"
OUTPUT_PATH = PROJECT_ROOT / "samples" / "synthetic_bell.csv"

EXPECTED_PARTIALS = [440.0, 880.0, 1320.0, 1760.0]
EXPECTED_AMPLITUDES = [100.0, 50.0, 30.0, 15.0]


def run_command(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a command with the current interpreter and return the result."""
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("UV_INTERNAL__PYTHONHOME", None)
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return result


def generate_fixture() -> None:
    """Create the synthetic bell WAV fixture if it does not exist."""
    result = run_command([
        sys.executable,
        str(GENERATE_SAMPLE),
        "--output",
        str(SAMPLE_PATH),
    ])
    assert result.returncode == 0, result.stderr


def analyze_fixture() -> list[dict[str, str]]:
    """Run the analyzer on the fixture and return parsed CSV rows."""
    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--output",
        str(OUTPUT_PATH),
        "--attack-skip-ms",
        "60",
        "--prominence",
        "0.005",
        "--distance",
        "30",
    ])
    assert result.returncode == 0, result.stderr

    with open(OUTPUT_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


@pytest.fixture(scope="module", autouse=True)
def fixture() -> None:
    generate_fixture()


def test_analyzer_runs_without_errors() -> None:
    rows = analyze_fixture()
    assert len(rows) >= len(EXPECTED_PARTIALS)


def test_fundamental_is_loudest() -> None:
    rows = analyze_fixture()
    assert float(rows[0]["frequency_hz"]) == pytest.approx(440.0, abs=5.0)
    assert float(rows[0]["amplitude_percent"]) == pytest.approx(100.0, abs=0.1)


def test_expected_partials_recovered() -> None:
    rows = analyze_fixture()
    detected_freqs = [float(row["frequency_hz"]) for row in rows]

    for expected_freq in EXPECTED_PARTIALS:
        matches = [f for f in detected_freqs if abs(f - expected_freq) <= 5.0]
        assert matches, f"Expected partial near {expected_freq} Hz not found"


def test_amplitude_ordering_and_values() -> None:
    rows = analyze_fixture()
    detected_freqs = [float(row["frequency_hz"]) for row in rows]
    detected_amps = [float(row["amplitude_percent"]) for row in rows]

    # Find the detected peaks closest to each expected partial.
    selected: list[tuple[float, float]] = []
    for expected_freq, expected_amp in zip(EXPECTED_PARTIALS, EXPECTED_AMPLITUDES):
        best_idx = min(
            range(len(detected_freqs)),
            key=lambda i: abs(detected_freqs[i] - expected_freq),
        )
        assert abs(detected_freqs[best_idx] - expected_freq) <= 5.0
        selected.append((expected_freq, detected_amps[best_idx]))

    # Verify rank order is preserved.
    sorted_by_freq = sorted(selected, key=lambda x: x[0])
    amplitudes = [amp for _, amp in sorted_by_freq]
    assert amplitudes == sorted(amplitudes, reverse=True)

    # Verify each amplitude is within ±5 percentage points of expected.
    for expected_freq, detected_amp in sorted_by_freq:
        expected_amp = EXPECTED_AMPLITUDES[EXPECTED_PARTIALS.index(expected_freq)]
        assert detected_amp == pytest.approx(expected_amp, abs=5.0)


def test_csv_header_and_columns() -> None:
    rows = analyze_fixture()
    assert len(rows) > 0
    expected_columns = {
        "peak_number",
        "frequency_hz",
        "amplitude_percent",
        "note_name",
        "deviation_cents",
    }
    assert set(rows[0].keys()) == expected_columns


def test_stereo_input_reduced_to_first_channel() -> None:
    stereo_path = PROJECT_ROOT / "samples" / "synthetic_bell_stereo.wav"
    result = run_command([
        sys.executable,
        str(GENERATE_SAMPLE),
        "--output",
        str(stereo_path),
        "--channels",
        "2",
    ])
    assert result.returncode == 0, result.stderr

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(stereo_path),
        "--attack-skip-ms",
        "60",
        "--prominence",
        "0.005",
        "--distance",
        "30",
    ])
    assert result.returncode == 0, result.stderr
    assert "440" in result.stdout or "A4" in result.stdout


def test_attack_skip_too_long_returns_error() -> None:
    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--attack-skip-ms",
        "10000",
    ])
    assert result.returncode == 2
    assert "attack skip" in result.stderr.lower()


def test_missing_input_file_returns_error() -> None:
    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(PROJECT_ROOT / "samples" / "nonexistent.wav"),
    ])
    assert result.returncode == 1
    assert "not found" in result.stderr.lower()


def test_plot_save_creates_png() -> None:
    png_path = PROJECT_ROOT / "samples" / "synthetic_bell_plot.png"
    if png_path.exists():
        png_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--plot-save",
        str(png_path),
        "--no-show",
        "--attack-skip-ms",
        "60",
        "--prominence",
        "0.005",
        "--distance",
        "30",
    ])
    assert result.returncode == 0, result.stderr
    assert png_path.exists()
    assert png_path.stat().st_size > 0


def test_visualize_no_show_plot_save() -> None:
    png_path = PROJECT_ROOT / "samples" / "visualize_test.png"
    if png_path.exists():
        png_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--visualize",
        "--no-show",
        "--plot-save",
        str(png_path),
        "--attack-skip-ms",
        "60",
    ])
    assert result.returncode == 0, result.stderr
    assert png_path.exists()
    assert png_path.stat().st_size > 0


def test_plot_save_default_filename() -> None:
    default_path = PROJECT_ROOT / "synthetic_bell_bell_analysis.png"
    if default_path.exists():
        default_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--plot-save",
        "--no-show",
        "--attack-skip-ms",
        "60",
    ])
    assert result.returncode == 0, result.stderr
    assert default_path.exists()
    assert default_path.stat().st_size > 0


def test_quiet_suppresses_text_output() -> None:
    png_path = PROJECT_ROOT / "samples" / "quiet_test.png"
    if png_path.exists():
        png_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--plot-save",
        str(png_path),
        "--no-show",
        "--quiet",
        "--attack-skip-ms",
        "60",
    ])
    assert result.returncode == 0, result.stderr
    assert png_path.exists()
    assert "peak_number" not in result.stdout
    assert "frequency_hz" not in result.stdout


def test_peak_count_limits_output() -> None:
    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--peak-count",
        "2",
        "--attack-skip-ms",
        "60",
        "--prominence",
        "0.005",
        "--distance",
        "30",
    ])
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    # Header + 2 data rows
    assert len(lines) == 3


def test_spectrogram_alias_enables_plotting() -> None:
    png_path = PROJECT_ROOT / "samples" / "alias_test.png"
    if png_path.exists():
        png_path.unlink()

    result = run_command([
        sys.executable,
        str(ANALYZE_BELL),
        str(SAMPLE_PATH),
        "--spectrogram",
        "--no-show",
        "--plot-save",
        str(png_path),
        "--attack-skip-ms",
        "60",
    ])
    assert result.returncode == 0, result.stderr
    assert png_path.exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
