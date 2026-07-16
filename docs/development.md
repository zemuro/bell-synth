# Development Guide

This guide explains how the analyzer works and how to contribute.

## Project structure

```text
c:/Users/zemuro/Antigravity/bell synth/
├── analyze_bell.py              # Main CLI and analysis pipeline
├── analyze_bell.ini             # Default configuration file
├── requirements.txt             # Python dependencies
├── README.md / README.ru.md     # Project overviews
├── docs/                        # Bilingual documentation
│   ├── usage.md / usage.ru.md
│   ├── config.md / config.ru.md
│   └── development.md / development.ru.md
├── samples/                     # WAV samples (not tracked by Git)
├── tests/
│   ├── generate_test_sample.py  # Synthetic bell fixture generator
│   └── test_analyze_bell.py     # pytest test suite
└── plan/                        # Project plans, reviews, reports
```

## Theory of operation

### Decay-window selection

Bell recordings begin with a short, noisy attack transient caused by the clapper strike. The analyzer skips the first `--attack-skip-ms` milliseconds before analysis. The remaining signal is assumed to contain the sustained, decaying partials.

If the requested skip is longer than the input, the tool exits with a clear error rather than silently producing an empty spectrum.

### Spectrum averaging

After the attack skip, the decay signal is divided into overlapping Hann-windowed frames. The magnitude spectrum is computed for each frame using `numpy.fft.rfft`, and the mean of all frames is taken. This averaging reduces random noise while preserving stable spectral features.

The FFT size and hop size are configurable via `--fft-size` and `--hop-size`. Larger FFT sizes give finer frequency resolution but require sufficient signal length.

### Smoothing

The averaged magnitude spectrum is smoothed with a Savitzky-Golay filter. Smoothing reduces high-frequency bin-to-bin variation without shifting peak locations, making subsequent peak detection more reliable.

### Peak detection

Peaks are detected with `scipy.signal.find_peaks`, restricted to the frequency range `[min_freq, max_freq]`. Two parameters control sensitivity:

- **prominence** — how much a peak must stand out above its surroundings.
- **distance** — minimum number of bins between adjacent peaks.

For inharmonic bell spectra, `distance` should be small enough to resolve closely spaced partials.

### Note and cent conversion

Each peak frequency `f` is mapped independently to the nearest 12-TET pitch:

```text
semitones = 12 * log2(f / 440)
note_index = round(semitones)
deviation_cents = 1200 * log2(f / (440 * 2^(note_index / 12)))
```

The note name is derived from `note_index` with A4 = 440 Hz as the reference. The octave changes at C.

### Inharmonic bell overtones

Unlike strings or woodwinds, bell partials are not integer multiples of a single fundamental. Each partial is therefore mapped to 12-TET independently rather than assumed to be a harmonic. This is why the analyzer reports note names and cent deviations for every detected peak.

## Running tests

Install dependencies and run pytest:

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -m pytest tests/test_analyze_bell.py -v
```

Synthetic fixtures are generated automatically during tests.

## How to add a feature

1. Update `analyze_bell.py` with the new behavior.
2. If the feature is configurable, add the key to `CONFIG_SECTIONS` and `config_defaults()`.
3. Add tests to `tests/test_analyze_bell.py`.
4. Update the example config and `config/default.ini` if needed.
5. Update both English and Russian user-facing docs.
6. Run the full test suite before committing.

## Architecture notes

- **First-channel extraction:** Stereo files are reduced to channel 0. Multi-channel analysis is deferred.
- **Lazy matplotlib import:** `matplotlib` and `pyplot` are imported only when visualization is requested, keeping startup fast for CSV-only runs.
- **Headless backend:** When `--no-show` is set, `matplotlib.use("Agg")` is called before importing `pyplot`, ensuring the tool runs without a display.
- **Config precedence:** CLI > config file > hardcoded defaults. The `--config` path is extracted in a first pass so argparse defaults can be set from the config.

## Contribution guidelines

- Keep changes focused and well-tested.
- Maintain bilingual documentation parity: any change to `docs/*.md` should be reflected in `docs/*.ru.md`.
- Follow the existing Google-style docstring format.
- Run `pytest` before submitting a pull request.

## Troubleshooting for developers

**Installing `soundfile` on Windows**
- Ensure you have a working C compiler or use a pre-built wheel. The package is backed by libsndfile.

**24-bit PCM handling**
- `soundfile.read(..., dtype="float64")` reads 24-bit WAV files correctly and returns normalized floats in `[-1.0, 1.0]`.

**Matplotlib backend issues**
- If you see backend errors in a headless environment, verify `--no-show` is set before `--plot-save`.
- The `Agg` backend is forced automatically when `--no-show` is present.
