---
document_type: review
phase: 02
title: Bell Partial Analyzer Visualization — Review
reviewer: plan_editor
review_date: 2026-07-16
verdict: 🟢
---

# Bell Partial Analyzer Visualization — Review

## Verdict

🟢 **Ready to implement, with minor notes.**

Phase 02 is a clear, non-breaking extension of Phase 01. The visualization layer is well-scoped, the CLI flags cover interactive, headless, and quiet use cases, and the proposed architecture keeps plotting optional so existing behavior is preserved.

## Strengths

- **Non-breaking design.** Plotting is triggered only by explicit flags, so Phase 01 paths remain untouched.
- **CLI coverage.** `--visualize`, `--plot-save`, `--no-show`, and `--quiet` handle interactive, headless, and silent workflows cleanly.
- **Lazy matplotlib import.** Keeping the import inside the visualization path avoids slowing down non-plotting invocations.
- **Overlap mitigation.** Alternating peak-label positions with a 5% relative-amplitude threshold is a pragmatic first pass.

## Issues, Ambiguities, and Recommendations

1. **Default PNG filename is awkward.** The plan specifies `<input_stem>_bell_analysis.png`, which would produce names like `bell_bell_analysis.png` for an input called `bell.wav`. Recommend changing the default to `<input_stem>_analysis.png` in `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`.

2. **Make headless backend handling explicit.** The current text says a non-interactive backend "may" be used. The implementer should **always** call `matplotlib.use('Agg')` whenever `--no-show` is set, before importing `pyplot`, to guarantee headless/CI operation.

3. **Pin the spectrogram y-axis range.** The description says "limited to a useful range" but is vague. Recommend documenting it as `[0, min(max_freq, sr/2)]` or a hard cap such as 8 kHz, and applying that limit consistently in `c:/Users/zemuro/Antigravity/bell synth/analyze_bell.py`.

4. **Update user-facing documentation.** The plan should mention updating `c:/Users/zemuro/Antigravity/bell synth/README.md` with the new flags and examples so users discover `--plot-save --no-show` and `--quiet`.

5. **`--spectrogram` alias is fine but redundant.** It is acceptable to keep for discoverability, but ensure it is documented as an exact alias of `--visualize`.

## Action Items

- [ ] Change default PNG filename pattern from `<input_stem>_bell_analysis.png` to `<input_stem>_analysis.png`.
- [ ] Add a note to the phase spec (or implement directly) that `matplotlib.use('Agg')` is called before any `pyplot` import when `--no-show` is present.
- [ ] Clarify spectrogram y-axis limits in the design.
- [ ] Add a task or acceptance criterion for updating `c:/Users/zemuro/Antigravity/bell synth/README.md`.

## Summary

The specification is solid and ready for implementation. Address the filename default, enforce the `Agg` backend for `--no-show`, and clarify the spectrogram axis range before coding begins. Documentation updates should be included as part of the implementation.
