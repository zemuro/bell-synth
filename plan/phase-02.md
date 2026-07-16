---
document_type: phase_spec
phase: 02
title: Bell Partial Analyzer Visualization
status: planning
created: 2026-07-16
author: plan_editor
dependencies:
  - soundfile
  - numpy
  - scipy
  - matplotlib
acceptance_criteria_summary:
  - `analyze_bell.py` gains a `--visualize` flag that opens an interactive matplotlib window with two subplots (spectrogram and spectrum with labeled peaks).
  - A `--plot-save` option writes a PNG without blocking, and `--no-show` enables fully headless use.
  - When visualizing, the CSV/table output is still emitted unless `--quiet` is used.
  - Plots remain readable for 24-bit/48 kHz mono or stereo WAV inputs using the first channel only.
---

# Phase 02 — Bell Partial Analyzer Visualization

## Summary

Extend the existing `analyze_bell.py` CLI from Phase 01 with optional visualization. When visualization is requested, the tool opens a matplotlib figure containing a time-frequency spectrogram of the analyzed decay segment and a spectrum plot showing detected partials annotated with frequency, note name, cent deviation, and relative amplitude.

## 1. Overview

### 1.1 Problem Statement

Phase 01 produces a numeric CSV/table of bell partials, but it is hard to validate whether the peak detector is correct without looking at the underlying spectrum and how it evolves over time. A visual summary helps users confirm that the attack skip, peak detection thresholds, and note mapping are behaving as expected.

### 1.2 Goal

Deliver a non-breaking CLI enhancement that:

1. Adds `--visualize` (primary flag) and an alias `--spectrogram` (identical behavior) to request plotting.
2. Adds `--plot-save PATH` to save a PNG, with a default filename derived from the input path when the flag is given without a value.
3. Adds `--no-show` to skip the interactive window, enabling headless/CI execution.
4. Adds `--quiet` to suppress the textual CSV/table output when only a plot is desired.
5. Displays two vertically stacked subplots:
   - Top: STFT spectrogram (dB magnitude) of the decay segment.
   - Bottom: averaged magnitude spectrum with detected peaks and labels.

### 1.3 Scope Boundaries

**In scope:**
- Single-file matplotlib visualization for the same WAV inputs supported by Phase 01.
- Reuse of Phase 01 windowing, decay segment selection, and averaged spectrum.
- Configurable STFT parameters for the spectrogram with sensible defaults for 48 kHz material.
- PNG export and headless (`--plot-save` + `--no-show`) operation.

**Out of scope:**
- A standalone GUI or real-time audio visualization.
- Batch plotting of multiple files in one command.
- Animated or 3-D plots.
- Publication-quality layout customization (fonts, colors, sizes are fixed to sensible defaults).

## 2. Architecture

The visualization is an optional post-processing step layered on top of the existing analysis pipeline. No existing peak-detection or output logic should change when visualization is disabled.

```text
WAV file
   │
   ▼
Load first channel (Phase 01)
   │
   ▼
Skip attack transient (Phase 01)
   │
   ├──► Windowed FFT frames ──► Averaged spectrum ──► Peak detection (Phase 01)
   │
   ▼
STFT frames for spectrogram (new)
   │
   ▼
Build matplotlib figure with 2 subplots
   │
   ├──► Subplot 1: STFT spectrogram (dB)
   └──► Subplot 2: averaged spectrum + peak markers/labels
   │
   ▼
Show window, save PNG, or both, then emit CSV/table unless --quiet
```

### 2.1 Dependencies

The following packages must be declared in `c:/Users/zemuro/Antigravity/bell synth/requirements.txt` (or equivalent):

| Package | Purpose | Recommended minimum |
|---------|---------|---------------------|
| `soundfile` | Read mono/stereo WAV files, including 24-bit PCM | `>=0.12.1` |
| `numpy` | Array operations, FFT, dB conversion | `>=1.24` |
| `scipy` | Windowing, smoothing, peak detection, STFT | `>=1.10` |
| `matplotlib` | Spectrogram and spectrum plots | `>=3.7` |

Install or update with:

```bash
pip install -r "c:/Users/zemuro/Antigravity/bell synth/requirements.txt"
```

## 3. Detailed Design

### Task 1: Add visualization entry point in `analyze_bell.py`

**Effort:** 2 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`

**Description:**
1. Import matplotlib lazily inside the visualization path so the CLI still starts quickly when plotting is not requested.
2. Add a top-level helper such as `plot_analysis(data, sr, peaks, spectrum, freqs, stft_result, args)` that constructs and renders the figure.
3. Call this helper only after the existing analysis completes and peaks have been computed.
4. Ensure the helper returns once rendering/saving is done so the script can proceed to CSV output.

### Task 2: Add CLI flags

**Effort:** 1 hour

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`

**Description:**
Add the following `argparse` entries:

| Argument | Action | Default | Description |
|----------|--------|---------|-------------|
| `--visualize` | `store_true` | `False` | Open an interactive matplotlib window with the spectrogram and spectrum plots. |
| `--spectrogram` | `store_true` | `False` | Alias for `--visualize`; if either flag is present, plotting is enabled. |
| `--plot-save` | `nargs='?'`, `const=''` | `None` | Save the figure to a PNG. If the flag is used without a path, derive the filename from the input file. |
| `--no-show` | `store_true` | `False` | Do not call `plt.show()`; use with `--plot-save` for headless operation. |
| `--quiet` | `store_true` | `False` | Suppress the textual CSV/table output. |
| `--spec-nperseg` | `int` | `4096` | STFT window length for the spectrogram (samples). |
| `--spec-noverlap` | `int` | `3072` | STFT hop overlap for the spectrogram (samples). |
| `--spec-nfft` | `int` | `4096` | FFT length used by the STFT. |

Notes:
- If both `--visualize` and `--plot-save` are omitted, the tool behaves exactly like Phase 01.
- `--plot-save` implies `--visualize`: when `--plot-save PATH` is provided, plotting is enabled and the interactive viewer is opened by default unless `--no-show` is also given.
- For headless environments, import `matplotlib` with a non-interactive backend (e.g., `Agg`) before importing `pyplot`. A robust approach is to call `matplotlib.use('Agg')` when `--no-show` is set.

### Task 3: Compute spectrogram data

**Effort:** 1 hour

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`

**Description:**
1. After skipping the attack transient, run `scipy.signal.stft` on the remaining decay segment using the parameters from `--spec-nperseg`, `--spec-noverlap`, and `--spec-nfft`.
2. Convert the complex STFT to magnitude and then to dB: `20 * np.log10(magnitude + epsilon)`, where `epsilon` is a small constant such as `1e-12`.
3. Pass the resulting matrix, time vector, and frequency vector to the plotting helper.

### Task 4: Render the figure

**Effort:** 3 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`

**Description:**
Create a figure with two subplots using `plt.subplots(2, 1, sharex=False)`.

**Top subplot — spectrogram:**
- Use `ax.pcolormesh` or `ax.imshow` with the STFT dB matrix.
- X-axis: time in seconds relative to the start of the analyzed segment.
- Y-axis: frequency in Hz, limited to a useful range (e.g., 0 Hz to `--max-freq`, or 0 Hz to 8 kHz if `--max-freq` is higher).
- Add colorbar labeled "Magnitude (dB)".
- Title: "STFT Spectrogram (decay segment)".

**Bottom subplot — averaged spectrum with peaks:**
- Plot the averaged magnitude spectrum as a line (reuse the data already computed for peak detection).
- Plot vertical markers (`ax.vlines`) at each detected peak frequency.
- Annotate each peak with text of the form:
  `440.0 Hz
A4 -0.8 c
100.0%`
  or a compact single-line equivalent such as `440.0 Hz · A4 -0.8 c · 100.0%`.
- To reduce overlap, alternate label positions above/below the marker or only label the top peaks by amplitude. At minimum, label all peaks whose relative amplitude is at least 5%.
- X-axis: frequency in Hz; Y-axis: magnitude (linear or dB, clearly labeled).
- Title: "Averaged Spectrum with Detected Partials".

**General:**
- Use `plt.tight_layout()` to prevent label clipping.
- Save at 150 DPI when writing PNG.

### Task 5: Default PNG filename derivation

**Effort:** 0.5 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`

**Description:**
If `--plot-save` is present but no path is supplied:
1. Take the input filename stem (e.g., `bell` from `c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav`).
2. Default to `<input_stem>_bell_analysis.png` in the current working directory.

Example:
- Input: `c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav`
- Default output: `c:/Users/zemuro/Antigravity/bell synth/bell_bell_analysis.png`

### Task 6: Add/update tests

**Effort:** 2 hours

**Files:**
- `c:/Users/zemuro/Antigravity/bell synth/tests/test_analyze_bell.py`
- `c:/Users/zemuro/Antigravity/bell synth/tests/generate_test_sample.py`

**Description:**
1. Add a test that runs `python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" "c:/Users/zemuro/Antigravity/bell synth/samples/synthetic_bell.wav" --plot-save --no-show` and asserts that the PNG file is created and non-empty.
2. Add a test that runs with `--visualize --no-show --plot-save out.png` and asserts no exception is raised.
3. Ensure existing Phase 01 tests still pass when no visualization flags are used.

## 4. Acceptance Criteria

- [ ] `python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" --visualize` opens an interactive matplotlib window with two clearly readable subplots.
- [ ] `python analyze_bell.py samples/bell.wav --visualize --peak-count 12 --max-freq 6000 --plot-save bell_report.png --no-show` produces `bell_report.png` without blocking. Verify that the PNG is created and is at least 480x360 pixels.
- [ ] When `--plot-save` is given without a path, the saved PNG filename is derived from the input filename stem.
- [ ] The spectrum subplot shows vertical markers at every detected peak frequency and labels containing frequency (Hz), note name + octave, cent deviation, and relative amplitude %.
- [ ] The spectrogram subplot shows frequency content evolving over the decay segment with time on the x-axis and frequency on the y-axis.
- [ ] Textual CSV/table output is still emitted by default when visualization is active; `--quiet` suppresses it.
- [ ] The tool runs successfully in a headless environment using only `--plot-save` and `--no-show` (e.g., in CI).
- [ ] Phase 01 behavior is unchanged when no visualization flags are provided.

## 5. Test Plan

### 5.1 Unit / integration tests

Run the existing test suite and new visualization tests with pytest:

```bash
pytest "c:/Users/zemuro/Antigravity/bell synth/tests/test_analyze_bell.py"
```

### 5.2 Interactive smoke test

1. Ensure a display is available and `matplotlib` can open a window.
2. Run:

```bash
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" --visualize
```

3. Verify:
   - Two subplots appear.
   - Spectrogram shows decaying frequency bands.
   - Spectrum plot contains vertical markers and labels at reported partials.
   - Closing the window returns control to the shell.

### 5.3 Headless PNG export test

```bash
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" \
  --plot-save "c:/Users/zemuro/Antigravity/bell synth/output.png" --no-show
```

Verify:
- `c:/Users/zemuro/Antigravity/bell synth/output.png` exists and is larger than 0 bytes.
- The command exits immediately (no blocking).
- The CSV table is still printed to stdout.

### 5.4 Quiet PNG export test

```bash
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" \
  --plot-save "c:/Users/zemuro/Antigravity/bell synth/output.png" --no-show --quiet
```

Verify:
- The PNG is created.
- No CSV/table is printed to stdout.

### 5.5 Default filename derivation test

```bash
cd "c:/Users/zemuro/Antigravity/bell synth"
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" --plot-save --no-show
```

Verify that `c:/Users/zemuro/Antigravity/bell synth/bell_bell_analysis.png` is created.

## 6. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `matplotlib` fails to load a GUI backend in some environments | Medium | High | Use `Agg` backend automatically when `--no-show` is set; document the `--plot-save --no-show` pattern for CI. |
| Peak labels overlap on bells with many partials | Medium | Medium | Alternate label positions and/or limit labels to peaks above a relative-amplitude threshold. |
| Spectrogram defaults are poorly matched to sample rate | Low | Medium | Defaults are tuned for 48 kHz; expose `--spec-nperseg`, `--spec-noverlap`, and `--spec-nfft` for override. |
| Visualization slows down script startup | Low | Low | Import matplotlib only inside the visualization path. |
| `--plot-save` without `--no-show` blocks unexpectedly in headless environments | Medium | Medium | Set `Agg` backend when no display is detected and `--no-show` is implied by absence of a display. |

## 7. Effort Estimate

| Sub-task | Hours | Notes |
|----------|-------|-------|
| Add CLI flags and argument validation | 1 | `--visualize`, `--spectrogram`, `--plot-save`, `--no-show`, `--quiet`, STFT params |
| Implement STFT and plotting helper | 3 | Two subplots, peak annotations, colorbars, layout |
| Default PNG filename derivation | 0.5 | Stem-based naming in CWD |
| Headless backend handling | 0.5 | `Agg` fallback and `--no-show` behavior |
| Add/update tests | 2 | PNG existence, no-exception, quiet mode |
| Manual verification | 1 | Interactive window and headless PNG smoke tests |
| **Total** | **8** | |

## 8. Deferred Items

| Item | Reason |
|------|--------|
| Batch plotting of multiple files | Out of scope; can be scripted externally once single-file plotting is stable. |
| Real-time or animated visualization | Phase 02 is focused on static summary plots for analyzed files. |
| Custom color maps / styling | Use matplotlib defaults; expose later if users request them. |
| Multi-channel visualization | Tool intentionally uses only the first channel; channel comparison is a future enhancement. |

## 9. Example Commands

```bash
# Open interactive plot window (blocking)
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" --visualize

# Save a PNG without blocking, still print CSV
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" \
  --plot-save "c:/Users/zemuro/Antigravity/bell synth/bell_analysis.png" --no-show

# Save PNG without blocking and suppress text output
python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
  "c:/Users/zemuro/Antigravity/bell synth/samples/bell.wav" \
  --plot-save --no-show --quiet
```

## 10. Example Output

When run without `--quiet`, the terminal output is identical to Phase 01:

```csv
peak_number,frequency_hz,amplitude_percent,note_name,deviation_cents
1,439.8,100.0,A4,-0.8
2,879.6,45.2,A5,-0.8
3,1319.4,18.6,E6,+1.2
4,1759.2,8.3,A6,-0.8
```

The PNG file contains the spectrogram and spectrum plots described above.
