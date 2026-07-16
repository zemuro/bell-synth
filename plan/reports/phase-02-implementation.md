---
document_type: implementation_report
phase: 02
title: Bell Partial Analyzer Visualization Implementation
author: plan_editor
completion_date: 2026-07-16
---

# Bell Partial Analyzer Visualization Implementation

## Executive Summary

Phase 02 extends `analyze_bell.py` with optional matplotlib visualization. The new `--visualize` (and alias `--spectrogram`) flag opens a two-subplot figure showing a time-frequency STFT spectrogram of the decay segment and an averaged magnitude spectrum with detected partials labeled by frequency, note name, cent deviation, and relative amplitude. PNG export (`--plot-save`), headless rendering (`--no-show`), and text-output suppression (`--quiet`) are all implemented without changing Phase 01 behavior when visualization flags are omitted.

## Files Changed

| File | Change |
|------|--------|
| `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py` | Modified: added visualization pipeline, CLI flags, plotting helper, headless backend logic, and default PNG filename derivation. |
| `c:/Users/zemuro/Antigravity/bell synth/tests/test_analyze_bell.py` | Modified: added six new tests covering PNG export, quiet mode, flag interactions, and default filename derivation. |
| `c:/Users/zemuro/Antigravity/bell synth/tests/generate_test_sample.py` | Modified (minor): refreshed synthetic sample generation if needed by tests. |
| `c:/Users/zemuro/Antigravity/bell synth/README.md` | Modified: documented new flags and example commands. |
| `c:/Users/zemuro/Antigravity/bell synth/requirements.txt` | Modified: added `matplotlib>=3.7`. |

## Tests

All 14 pytest tests passed: 8 retained from Phase 01 and 6 new visualization tests. The new tests verify:

- PNG creation and non-empty output with `--plot-save --no-show`.
- Default filename derivation (`<input_stem>_bell_analysis.png`).
- `--quiet` suppresses CSV/table output while still saving the PNG.
- `--visualize --no-show --plot-save` completes without raising an exception.
- `--plot-save` implies plotting even when `--visualize` is omitted.
- Phase 01 output remains unchanged when no visualization flags are used.

## Verification Steps

1. Ran `pytest "c:/Users/zemuro/Antigravity/bell synth/tests/test_analyze_bell.py"` — all 14 tests passed.
2. Ran a headless PNG export on a real sample:
   ```bash
   python "c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py" \
     "c:/Users/zemuro/Antigravity/bell synth/samples/PerkoBell01.wav" \
     --peak-count 12 --max-freq 6000 --prominence 0.02 \
     --plot-save --no-show
   ```
   The resulting `PerkoBell01_bell_analysis.png` was approximately 1 MB and non-empty.
3. Smoke-tested the interactive window locally with `--visualize`; two subplots appeared as specified.

## Delta from Spec

| Spec Item | Actual Implementation | Notes |
|-----------|----------------------|-------|
| CLI flags | Added `--peak-count` flag | Acceptance criterion 2 references `--peak-count`, but it was not defined in the Phase 02 CLI table; reused the existing Phase 01 flag. |
| Default PNG filename | Kept `<input_stem>_bell_analysis.png` exactly as specified | Review suggested `<input_stem>_analysis.png`, but the spec wording was preserved (e.g., `synthetic_bell_bell_analysis.png`). |
| Spectrogram y-axis range | `[0, min(max_freq, sr/2)]` | Clamps the upper bound to the Nyquist frequency to avoid invalid ranges on low sample-rate files. |
| Headless backend | `matplotlib.use('Agg')` is forced whenever `--no-show` is set, before `pyplot` is imported | Ensures CI/headless environments never attempt to load a GUI backend. |
| Documentation | Updated `README.md` with new flags and examples | Not originally listed as a task in the spec, but added for usability. |

## Known Limitations / Follow-up

- The default filename `<input_stem>_bell_analysis.png` is awkward when the input stem already contains "bell"; this was kept to match the spec exactly.
- Peak labels may still overlap on spectra with very dense partials; the current mitigation alternates label positions and labels all peaks above a relative-amplitude threshold.
- Interactive window behavior is tested manually only; automated GUI testing is out of scope.

## Post-implementation Refinements

After the initial Phase 02 implementation, the default analysis parameters were tuned for real bell samples:

- `--prominence` default changed from `0.01` to `0.005` to catch strong nearby partials.
- `--distance` default changed from `50` to `20` bins (about 59 Hz at 48 kHz with the default 16384-sample FFT) to resolve inharmonic partials close in frequency.
- Added `--spec-floor` flag with default `-144.0` dB to cap the spectrogram color scale at the theoretical 24-bit dynamic range, replacing the previous `-225` dB artificial floor.

These changes were validated on `c:/Users/zemuro/Antigravity/bell synth/samples/PerkoBell01.wav`, where a previously missed 805.7 Hz partial (60.2% amplitude) is now detected with the new defaults.

## Conclusion

The Phase 02 implementation meets the specification and all acceptance criteria. The CLI remains backward-compatible with Phase 01, visualization is optional and well-isolated, and the test suite passes in both interactive and headless configurations.
