# Bell Sample Overtone Analyzer

A command-line tool that analyzes a single bell WAV sample and reports its spectral overtones as CSV or a formatted table. It also provides optional matplotlib visualization: a spectrogram of the decay segment and a spectrum plot with detected partials labeled.

## Features

- Loads mono or stereo WAV files (24-bit / 48 kHz tested)
- Reduces stereo input to the first channel
- Skips a configurable attack transient
- Averages the magnitude spectrum over the decay portion
- Detects spectral peaks with configurable prominence, distance, and smoothing
- Maps each peak to the nearest 12-TET note and reports cent deviation
- Optional spectrogram + spectrum visualization with PNG export
- Headless operation for CI/automation
- INI configuration file support with CLI overrides
- Bilingual documentation (English / Russian)

## Quick start

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt

# Basic analysis
python analyze_bell.py samples/bell.wav

# Save a visualization PNG
python analyze_bell.py samples/bell.wav --plot-save --no-show --peak-count 12
```

## Example output

```csv
peak_number,frequency_hz,amplitude_percent,note_name,deviation_cents
1,366.2,100.0,F#4,-17.8
2,890.6,81.6,A5,+20.8
3,805.7,60.2,G5,+47.2
4,1517.6,44.6,F#6,+43.4
```

## Configuration

Edit `analyze_bell.ini` to change defaults. CLI flags always override config values, and config values override hardcoded defaults. You can also use `--save-config` to dump the effective configuration for editing.

```bash
# Save the current effective configuration for editing
python analyze_bell.py --save-config my_config.ini

# Use a custom config file
python analyze_bell.py samples/bell.wav --config my_config.ini
```

See [`docs/config.md`](docs/config.md) for the full configuration reference.

## Documentation

- [`docs/usage.md`](docs/usage.md) — CLI flag reference and examples
- [`docs/config.md`](docs/config.md) — configuration file reference
- [`docs/development.md`](docs/development.md) — theory of operation and contribution guidelines
- [`README.ru.md`](README.ru.md) — русская версия

## Contributing

1. Open an issue to discuss large changes.
2. Fork the repository and create a feature branch.
3. Add tests for new behavior and ensure `pytest` passes.
4. Update both English and Russian user-facing documentation.
5. Submit a pull request.

## Troubleshooting

**No peaks reported**
- Lower `--prominence` or reduce `--distance` to detect quieter or closer partials.
- Make sure `--min-freq` and `--max-freq` include the range of interest.

**Attack skip too long**
- Reduce `--attack-skip-ms` or use a longer input file.

**PNG is blank / labels overlap**
- Use `--n-labels` to limit the number of annotated peaks.
- Adjust `--spectrum-floor` or `--spec-floor`.

**Matplotlib backend error in headless environment**
- Always use `--no-show` with `--plot-save`.

## License

This project is provided as-is for analysis and research. See the repository for license details.
