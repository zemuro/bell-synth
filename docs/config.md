# Configuration Reference

The analyzer can be configured through an INI file. CLI flags always override config values, and config values override hardcoded defaults.

## Config file location

The tool searches for configuration in this order:

1. File passed with `--config /path/to/file.ini`
2. `analyze_bell.ini` in the current working directory
3. `analyze_bell.ini` next to the script (the bundled defaults)
4. Hardcoded defaults

If no config file is found, the analyzer uses hardcoded defaults and runs normally.

## Sections overview

### `[analysis]`

Parameters controlling the spectral analysis.

### `[visualization]`

Parameters controlling the spectrogram and spectrum plot.

### `[output]`

Parameters controlling textual output format.

## Key reference

| Key | Section | Type | Default | Units | Description |
|-----|---------|------|---------|-------|-------------|
| `attack_skip_ms` | analysis | float | `100.0` | ms | Duration to skip at the start |
| `min_freq` | analysis | float | `50.0` | Hz | Minimum reported peak frequency |
| `max_freq` | analysis | float | `8000.0` | Hz | Maximum reported peak frequency |
| `prominence` | analysis | float | `0.005` | magnitude | Minimum peak prominence |
| `distance` | analysis | int | `20` | bins | Minimum bins between peaks |
| `smoothing_window` | analysis | int | `11` | samples | Savitzky-Golay window length |
| `fft_size` | analysis | int | `16384` | samples | FFT size per frame |
| `hop_size` | analysis | int | `2048` | samples | Hop between frames |
| `peak_count` | analysis | int | blank | count | Maximum peaks to report; blank = no limit |
| `spec_nperseg` | visualization | int | `4096` | samples | STFT window length |
| `spec_noverlap` | visualization | int | `3072` | samples | STFT overlap |
| `spec_nfft` | visualization | int | `4096` | samples | STFT FFT length |
| `spectrum_floor` | visualization | float | `-50.0` | dB | Floor for averaged spectrum plot |
| `spec_floor` | visualization | float | `-144.0` | dB | Floor for spectrogram color scale |
| `n_labels` | visualization | int | `7` | count | Number of strongest peaks to label |
| `format` | output | string | `csv` | — | Output format: `csv` or `table` |

## Example config

```ini
[analysis]
attack_skip_ms = 100.0
min_freq = 50.0
max_freq = 8000.0
prominence = 0.005
distance = 20
smoothing_window = 11
fft_size = 16384
hop_size = 2048
peak_count =

[visualization]
spec_nperseg = 4096
spec_noverlap = 3072
spec_nfft = 4096
spectrum_floor = -50.0
spec_floor = -144.0
n_labels = 7

[output]
format = csv
```

## Precedence rules

```text
CLI flag > config file value > hardcoded default
```

For example, if `analyze_bell.ini` sets `min_freq = 500.0` but you run:

```bash
python analyze_bell.py samples/bell.wav --config analyze_bell.ini --min-freq 100.0
```

the effective `min_freq` will be `100.0`.

## Saving a config

Use `--save-config` to write the current effective configuration to a file:

```bash
# Write to analyze_bell.ini in the current directory
python analyze_bell.py --save-config

# Write to a specific path
python analyze_bell.py --save-config my_bell.ini
```

The generated file is valid input for a later `--config` run. It includes all configurable keys, with empty `peak_count` meaning no limit.

## Boolean/action flags

CLI-only action flags such as `--visualize`, `--quiet`, and `--no-show` are not configurable through the INI file. They must be passed on the command line when needed.
