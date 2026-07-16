# Bell Sample Overtone Analyzer

A command-line tool that analyzes a single bell WAV sample and reports its spectral overtones as CSV or a formatted table. Phase 02 adds optional matplotlib visualization: a spectrogram of the decay segment and a spectrum plot with detected partials labeled.

## Features

- Loads mono or stereo WAV files (24-bit / 48 kHz tested)
- Reduces stereo input to the first channel
- Skips a configurable attack transient
- Averages the magnitude spectrum over the decay portion
- Detects spectral peaks with configurable prominence, distance, and smoothing
- Maps each peak to the nearest 12-TET note and reports cent deviation
- Optional spectrogram + spectrum visualization with PNG export
- Headless operation for CI/automation

## Installation

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## Usage

### Basic analysis

```bash
# Print CSV to stdout
python analyze_bell.py samples/bell.wav

# Write CSV file, skip first 150 ms
python analyze_bell.py samples/bell.wav --output peaks.csv --attack-skip-ms 150

# Formatted table with a narrower frequency range
python analyze_bell.py samples/bell.wav --min-freq 200 --max-freq 4000 --prominence 0.02 --format table
```

### Visualization

```bash
# Open an interactive matplotlib window (blocking)
python analyze_bell.py samples/bell.wav --visualize

# Save a PNG without blocking; CSV is still printed
python analyze_bell.py samples/bell.wav --plot-save bell_report.png --no-show

# Save a PNG with the default filename (<input_stem>_bell_analysis.png)
python analyze_bell.py samples/bell.wav --plot-save --no-show

# Save a PNG and suppress the text output
python analyze_bell.py samples/bell.wav --plot-save --no-show --quiet

# Limit the number of reported peaks
python analyze_bell.py samples/bell.wav --peak-count 12 --max-freq 6000
```

## Tests

```bash
venv\Scripts\python -m pytest tests/test_analyze_bell.py -v
```

## Project Structure

- `analyze_bell.py` — main analyzer CLI
- `tests/generate_test_sample.py` — synthetic bell fixture generator
- `tests/test_analyze_bell.py` — pytest test suite
- `plan/` — project plan, reviews, and implementation reports
