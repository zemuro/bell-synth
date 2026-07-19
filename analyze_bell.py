#!/usr/bin/env python3
"""
Bell Sample Overtone Analyzer CLI.

Reads a single WAV bell sample, skips the noisy attack, averages the magnitude
spectrum over the remaining signal, and emits a ranked list of overtone peaks
with frequency, relative amplitude, nearest 12-TET note, and cent deviation.
Optional matplotlib visualization includes an STFT spectrogram and an averaged
spectrum plot with detected partials annotated.

Configuration is loaded from an INI file if present; CLI flags always override
config values, and config values override hardcoded defaults.
"""

from __future__ import annotations

import argparse
import configparser
import csv
import io
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import find_peaks, savgol_filter, stft

try:
    import mido
except ImportError:
    mido = None


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Config sections and keys that can be set in an INI file.
CONFIG_SECTIONS = {
    "analysis": [
        "attack_skip_ms",
        "min_freq",
        "max_freq",
        "prominence",
        "distance",
        "smoothing_window",
        "fft_size",
        "hop_size",
        "peak_count",
    ],
    "visualization": [
        "spec_nperseg",
        "spec_noverlap",
        "spec_nfft",
        "spectrum_floor",
        "spec_floor",
        "n_labels",
    ],
    "output": [
        "format",
    ],
}


def config_defaults() -> dict[str, object]:
    """Return the hardcoded fallback configuration dictionary.

    Returns:
        Dictionary mapping config keys to their hardcoded default values.
    """
    return {
        "attack_skip_ms": 100.0,
        "min_freq": 50.0,
        "max_freq": 8000.0,
        "prominence": 0.005,
        "distance": 20,
        "smoothing_window": 11,
        "fft_size": 16384,
        "hop_size": 2048,
        "peak_count": None,
        "spec_nperseg": 4096,
        "spec_noverlap": 3072,
        "spec_nfft": 4096,
        "spectrum_floor": -50.0,
        "spec_floor": -144.0,
        "n_labels": 7,
        "format": "csv",
    }


def _convert_value(raw: str) -> object:
    """Convert a raw INI string to int, float, or None where possible.

    Args:
        raw: Raw string value from the config file.

    Returns:
        int, float, or the original string. Empty strings become None.
    """
    raw = raw.strip()
    if raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def load_config(path: Path | None) -> dict[str, object]:
    """Load an INI configuration file into a flat dictionary.

    If ``path`` is provided and exists, it is parsed directly. If ``path`` is
    provided and missing, a RuntimeError is raised. If ``path`` is ``None``,
    the function searches for ``analyze_bell.ini`` in the current working
    directory and then falls back to ``analyze_bell.ini`` next to the script.

    Args:
        path: Explicit path to a config file, or ``None`` to search defaults.

    Returns:
        Flat dictionary of config key/value pairs.

    Raises:
        RuntimeError: If an explicitly requested config file does not exist.
    """
    if path is not None:
        if not path.exists():
            raise RuntimeError(f"Error: config file not found: {path}")
        files_to_read = [path]
    else:
        script_dir = Path(__file__).resolve().parent
        cwd_ini = Path.cwd() / "analyze_bell.ini"
        bundled_ini = script_dir / "analyze_bell.ini"
        files_to_read = []
        if cwd_ini.exists():
            files_to_read.append(cwd_ini)
        elif bundled_ini.exists():
            files_to_read.append(bundled_ini)

    result: dict[str, object] = {}
    if not files_to_read:
        return result

    parser = configparser.ConfigParser()
    parser.read(files_to_read, encoding="utf-8")

    for section, keys in CONFIG_SECTIONS.items():
        if not parser.has_section(section):
            continue
        for key in keys:
            if parser.has_option(section, key):
                result[key] = _convert_value(parser.get(section, key))

    return result


def _extract_config_path(argv: list[str] | None) -> Path | None:
    """Scan argv for ``--config`` or ``-c`` and return its value.

    Args:
        argv: Argument list to scan. Uses ``sys.argv[1:]`` if ``None``.

    Returns:
        The config path if found, otherwise ``None``.
    """
    if argv is None:
        argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--config", "-c"):
            if i + 1 < len(argv):
                return Path(argv[i + 1])
        elif arg.startswith("--config="):
            return Path(arg.split("=", 1)[1])
        i += 1
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Config precedence is: CLI > config file > hardcoded defaults. The function
    first scans for ``--config`` to know which config file to load, merges
    defaults with config values, and then lets argparse apply CLI overrides.

    Args:
        argv: Argument list. Uses ``sys.argv[1:]`` if ``None``.

    Returns:
        Parsed argument namespace.
    """
    project_root = Path(__file__).resolve().parent
    default_input = project_root / "samples" / "bell.wav"

    defaults = config_defaults()
    config_path = _extract_config_path(argv)
    try:
        config_values = load_config(config_path)
    except RuntimeError:
        # Defer the error until after argparse so --help still works.
        config_values = {}
    defaults.update(config_values)

    parser = argparse.ArgumentParser(
        description="Analyze a bell WAV sample and report its overtone peaks."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=default_input,
        help="Path to input WAV file (default: samples\\bell.wav).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path; prints to stdout if omitted.",
    )
    parser.add_argument(
        "--attack-skip-ms",
        type=float,
        default=defaults.get("attack_skip_ms"),
        help="Duration to skip at the start, in milliseconds (default: %(default)s).",
    )
    parser.add_argument(
        "--min-freq",
        type=float,
        default=defaults.get("min_freq"),
        help="Minimum peak frequency to report, in Hz (default: %(default)s).",
    )
    parser.add_argument(
        "--max-freq",
        type=float,
        default=defaults.get("max_freq"),
        help="Maximum peak frequency to report, in Hz (default: %(default)s).",
    )
    parser.add_argument(
        "--prominence",
        type=float,
        default=defaults.get("prominence"),
        help="Minimum peak prominence in normalized magnitude units (default: %(default)s).",
    )
    parser.add_argument(
        "--distance",
        type=int,
        default=defaults.get("distance"),
        help="Minimum number of bins between peaks (default: %(default)s).",
    )
    parser.add_argument(
        "--smoothing-window",
        type=int,
        default=defaults.get("smoothing_window"),
        help="Window length for spectrum smoothing, odd integer (default: %(default)s).",
    )
    parser.add_argument(
        "--fft-size",
        type=int,
        default=defaults.get("fft_size"),
        help="FFT size per frame (default: %(default)s).",
    )
    parser.add_argument(
        "--hop-size",
        type=int,
        default=defaults.get("hop_size"),
        help="Hop size between successive frames (default: %(default)s).",
    )
    parser.add_argument(
        "--peak-count",
        type=int,
        default=defaults.get("peak_count"),
        help="Maximum number of peaks to report (default: no limit).",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "table"],
        default=defaults.get("format"),
        help="Output format: csv or table (default: %(default)s).",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Open an interactive matplotlib window with the analysis plots.",
    )
    parser.add_argument(
        "--spectrogram",
        action="store_true",
        help="Alias for --visualize.",
    )
    parser.add_argument(
        "--plot-save",
        nargs="?",
        const="",
        default=None,
        help="Save the figure to a PNG. If used without a path, a default "
             "filename is derived from the input file.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open the interactive plot window; use with --plot-save "
             "for headless operation.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the textual CSV/table output.",
    )
    parser.add_argument(
        "--spec-nperseg",
        type=int,
        default=defaults.get("spec_nperseg"),
        help="STFT window length for the spectrogram (default: %(default)s).",
    )
    parser.add_argument(
        "--spec-noverlap",
        type=int,
        default=defaults.get("spec_noverlap"),
        help="STFT overlap for the spectrogram (default: %(default)s).",
    )
    parser.add_argument(
        "--spec-nfft",
        type=int,
        default=defaults.get("spec_nfft"),
        help="FFT length used by the STFT (default: %(default)s).",
    )
    parser.add_argument(
        "--spectrum-floor",
        type=float,
        default=defaults.get("spectrum_floor"),
        help="Minimum dB value shown on the averaged spectrum plot "
             "(default: %(default)s).",
    )
    parser.add_argument(
        "--spec-floor",
        type=float,
        default=defaults.get("spec_floor"),
        help="Minimum dB value used for the spectrogram color scale "
             "(default: %(default)s).",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=None,
        help="Path to a custom INI configuration file.",
    )
    parser.add_argument(
        "--save-config",
        nargs="?",
        const="",
        default=None,
        help="Write the effective configuration to a file and exit. "
             "If used without a path, writes analyze_bell.ini in the current "
             "working directory.",
    )
    parser.add_argument(
        "--n-labels",
        "-n",
        type=int,
        default=defaults.get("n_labels"),
        help="Maximum number of peaks to label on the spectrum plot "
             "(default: %(default)s).",
    )

    args = parser.parse_args(argv)

    # Re-raise the missing-config error now that argparse has finished.
    if config_path is not None and not config_path.exists():
        raise RuntimeError(f"Error: config file not found: {config_path}")

    return args


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    """Load a WAV file and reduce multi-channel input to the first channel.

    Args:
        path: Path to the input WAV file.

    Returns:
        Tuple of the mono audio signal (float64) and the sample rate.

    Raises:
        RuntimeError: If the file does not exist or cannot be read.
    """
    if not path.exists():
        raise RuntimeError(f"Error: input file not found: {path}")

    try:
        data, sr = sf.read(str(path), dtype="float64")
    except Exception as exc:
        raise RuntimeError(f"Error: failed to read input file {path}: {exc}")

    if data.ndim > 1:
        data = data[:, 0]
    return data, sr


def find_transient_ms(data: np.ndarray, sr: int, window_ms: float = 5.0, threshold_ratio: float = 0.05) -> float:
    """Finds the start of the first transient using RMS energy.
    
    Args:
        data: Input audio signal.
        sr: Sample rate.
        window_ms: RMS window length.
        threshold_ratio: Threshold relative to maximum RMS.
        
    Returns:
        Milliseconds until the first transient.
    """
    window_samples = int(round((window_ms / 1000.0) * sr))
    if window_samples < 1:
        window_samples = 1

    if len(data) < window_samples:
        return 0.0

    # Remove DC offset to prevent silence from triggering the threshold
    centered_data = data - np.mean(data)
    squared = centered_data ** 2
    window = np.ones(window_samples) / window_samples
    mean_squared = np.convolve(squared, window, mode='valid')
    rms = np.sqrt(mean_squared)

    # Use the derivative of the RMS to find the sharpest volume increase
    rms_diff = np.diff(rms)
    if len(rms_diff) == 0:
        return 0.0
        
    max_diff = np.max(rms_diff)
    if max_diff <= 0:
        return 0.0
    
    # Find where the slope first exceeds 20% of the maximum attack slope
    threshold = max_diff * 0.2
    above_threshold = np.where(rms_diff > threshold)[0]
    
    if len(above_threshold) > 0:
        return float((above_threshold[0] / sr) * 1000.0)
    return 0.0


def skip_attack(data: np.ndarray, sr: int, attack_skip_ms: float, start_offset_ms: float = 0.0) -> np.ndarray:
    """Return the portion of the signal after the attack transient.

    Args:
        data: Input audio signal.
        sr: Sample rate in Hz.
        attack_skip_ms: Duration to skip after the start offset.
        start_offset_ms: Initial offset to trim leading silence.

    Returns:
        Audio signal starting after the offset and attack window.

    Raises:
        RuntimeError: If the total skip is longer than the input signal.
    """
    total_skip_ms = start_offset_ms + attack_skip_ms
    skip_samples = int(round((total_skip_ms / 1000.0) * sr))
    if skip_samples >= len(data):
        duration_ms = len(data) / sr * 1000.0
        raise RuntimeError(
            f"Error: attack skip ({attack_skip_ms:.1f} ms) is longer than "
            f"the input ({duration_ms:.1f} ms)"
        )
    if skip_samples < 0:
        skip_samples = 0
    return data[skip_samples:]


def compute_mean_spectrum(
    data: np.ndarray, sr: int, fft_size: int, hop_size: int
) -> tuple[np.ndarray, np.ndarray]:
    """Compute the mean magnitude spectrum over windowed frames.

    Args:
        data: Audio signal (1-D).
        sr: Sample rate in Hz.
        fft_size: Number of samples per FFT frame.
        hop_size: Number of samples between consecutive frames.

    Returns:
        Tuple of the mean magnitude spectrum and its corresponding frequency
        axis.
    """
    if fft_size > len(data):
        data = np.pad(data, (0, fft_size - len(data)))

    window = np.hanning(fft_size)
    frames = []
    start = 0
    while start < len(data):
        frame = data[start : start + fft_size]
        if len(frame) < fft_size:
            frame = np.pad(frame, (0, fft_size - len(frame)))
        frames.append(frame * window)
        start += hop_size

    frames_array = np.array(frames)
    magnitude_spectra = np.abs(np.fft.rfft(frames_array, n=fft_size, axis=1))
    mean_spectrum = np.mean(magnitude_spectra, axis=0)
    freqs = np.fft.rfftfreq(fft_size, 1.0 / sr)
    return mean_spectrum, freqs


def compute_stft(
    data: np.ndarray,
    sr: int,
    nperseg: int,
    noverlap: int,
    nfft: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute the STFT magnitude (dB) of the decay segment.

    Args:
        data: Audio signal (1-D).
        sr: Sample rate in Hz.
        nperseg: STFT window length in samples.
        noverlap: STFT overlap in samples.
        nfft: FFT length used by the STFT.

    Returns:
        Tuple of the STFT magnitude in dB, time vector, and frequency vector.
    """
    freqs, times, zxx = stft(
        data,
        fs=sr,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        nfft=nfft,
        boundary="zeros",
    )
    magnitude = np.abs(zxx)
    db = 20.0 * np.log10(magnitude + 1e-12)
    return db, times, freqs


def smooth_spectrum(spectrum: np.ndarray, smoothing_window: int) -> np.ndarray:
    """Smooth a magnitude spectrum while preserving peak locations.

    Args:
        spectrum: Magnitude spectrum (1-D).
        smoothing_window: Window length for Savitzky-Golay smoothing. Should
            be an odd integer >= 3; values < 3 disable smoothing.

    Returns:
        Smoothed magnitude spectrum.
    """
    window = int(smoothing_window)
    if window < 3:
        return spectrum
    if window % 2 == 0:
        window += 1
    if window > len(spectrum):
        window = len(spectrum) if len(spectrum) % 2 == 1 else len(spectrum) - 1
    if window < 3:
        return spectrum
    return savgol_filter(spectrum, window_length=window, polyorder=3)


def detect_peaks(
    spectrum: np.ndarray,
    freqs: np.ndarray,
    min_freq: float,
    max_freq: float,
    prominence: float,
    distance: float,
    mode: str = "linear",
) -> tuple[np.ndarray, np.ndarray]:
    """Detect spectral peaks within a frequency range.

    Args:
        spectrum: Magnitude or smoothed magnitude spectrum.
        freqs: Frequency axis corresponding to ``spectrum``.
        min_freq: Minimum peak frequency to report (Hz).
        max_freq: Maximum peak frequency to report (Hz).
        prominence: Minimum peak prominence in magnitude units or dB (if log mode).
        distance: Minimum number of bins (linear) or semitones (logarithmic) between peaks.
        mode: "linear" or "logarithmic".

    Returns:
        Tuple of peak indices and their frequencies.
    """
    valid_idx = np.where((freqs >= min_freq) & (freqs <= max_freq))[0]
    if len(valid_idx) == 0:
        return np.array([], dtype=int), freqs[np.array([], dtype=int)]

    min_idx = valid_idx[0]
    max_idx = valid_idx[-1]

    if mode == "logarithmic":
        # Logarithmic (Musical) Peak Detection
        # Clamp to 1e-12 to prevent NaNs from Savitzky-Golay filter overshoots
        safe_spectrum = np.maximum(spectrum, 1e-12)
        db_spectrum = 20.0 * np.log10(safe_spectrum)
        peaks, _ = find_peaks(db_spectrum, prominence=prominence)
        
        # Filter by frequency range
        peaks = peaks[(peaks >= min_idx) & (peaks <= max_idx)]
        
        # Filter by semitone distance using greedy amplitude sorting
        if len(peaks) > 0 and distance > 0:
            # Sort by dB amplitude descending
            sorted_peaks = peaks[np.argsort(db_spectrum[peaks])][::-1]
            kept_peaks = []
            
            for p in sorted_peaks:
                f_p = freqs[p]
                conflict = False
                for k in kept_peaks:
                    f_k = freqs[k]
                    # Avoid division by zero
                    if f_k > 0 and f_p > 0:
                        semitone_diff = abs(12.0 * np.log2(f_p / f_k))
                        if semitone_diff < distance:
                            conflict = True
                            break
                if not conflict:
                    kept_peaks.append(p)
            peaks = np.sort(np.array(kept_peaks, dtype=int))
            
    else:
        # Linear (Mathematical) Peak Detection
        peaks, _ = find_peaks(
            spectrum,
            prominence=prominence,
            distance=int(distance),
        )
        peaks = peaks[(peaks >= min_idx) & (peaks <= max_idx)]

    return peaks, freqs[peaks]


def frequency_to_note(frequency: float) -> tuple[str, float]:
    """Map a frequency to the nearest 12-TET note name and cent deviation.

    Args:
        frequency: Frequency in Hz. Must be positive.

    Returns:
        Tuple of note name (e.g., "A4") and cent deviation from that note.

    Raises:
        ValueError: If ``frequency`` is not positive.
    """
    if frequency <= 0:
        raise ValueError("Frequency must be positive")

    semitones = 12.0 * np.log2(frequency / 440.0)
    note_index = int(round(semitones))
    deviation_cents = 1200.0 * np.log2(
        frequency / (440.0 * 2.0 ** (note_index / 12.0))
    )

    note_name = NOTE_NAMES[(note_index + 9) % 12]
    octave = 4 + (note_index + 9) // 12
    return f"{note_name}{octave}", float(deviation_cents)


def format_peaks(
    peaks: np.ndarray,
    freqs: np.ndarray,
    spectrum: np.ndarray,
    peak_count: int | None = None,
    spec_db: np.ndarray | None = None,
    spec_freqs: np.ndarray | None = None,
    spec_times: np.ndarray | None = None,
    spec_floor: float = -144.0,
) -> list[dict[str, object]]:
    """Build a list of peak records sorted by descending amplitude.

    Args:
        peaks: Array of peak indices in the spectrum.
        freqs: Frequency axis.
        spectrum: Magnitude spectrum used for amplitude ranking.
        peak_count: Optional maximum number of peaks to return.
        spec_db: STFT spectrogram magnitude in dB.
        spec_freqs: STFT frequency axis.
        spec_times: STFT time axis.
        spec_floor: Spectrogram noise floor.

    Returns:
        List of peak dictionaries with keys ``peak_number``,
        ``frequency_hz``, ``amplitude_db``, ``duration_percent``, 
        ``note_name``, and ``deviation_cents``.
    """
    if len(peaks) == 0:
        return []

    peak_mags = spectrum[peaks]
    sorted_order = np.argsort(peak_mags)[::-1]
    sorted_peaks = peaks[sorted_order]
    sorted_mags = peak_mags[sorted_order]
    max_mag = sorted_mags[0]

    durations_sec = []
    
    # Calculate durations if STFT data is available
    if spec_db is not None and spec_freqs is not None and spec_times is not None:
        for peak_idx in sorted_peaks:
            peak_hz = freqs[peak_idx]
            # Find closest freq bin in STFT
            bin_idx = np.argmin(np.abs(spec_freqs - peak_hz))
            time_series = spec_db[bin_idx, :]
            
            # Find the last time index where magnitude > spec_floor + margin
            threshold = spec_floor + 5.0  # 5dB above floor
            above_thresh = np.where(time_series > threshold)[0]
            if len(above_thresh) > 0:
                durations_sec.append(spec_times[above_thresh[-1]])
            else:
                durations_sec.append(0.0)
    else:
        durations_sec = [0.0] * len(sorted_peaks)

    max_duration = max(durations_sec) if durations_sec and max(durations_sec) > 0 else 1.0

    rows: list[dict[str, object]] = []
    for rank, peak_idx in enumerate(sorted_peaks, start=1):
        if peak_count is not None and rank > peak_count:
            break
        frequency = float(freqs[peak_idx])
        # Calculate amplitude in dB relative to loudest peak
        amplitude_db = 20.0 * np.log10(sorted_mags[rank - 1] / max_mag)
        
        duration_percent = 100.0 * (durations_sec[rank - 1] / max_duration)
        
        note_name, deviation_cents = frequency_to_note(frequency)
        rows.append(
            {
                "peak_number": rank,
                "frequency_hz": frequency,
                "amplitude_db": round(amplitude_db, 1),
                "duration_percent": round(duration_percent, 1),
                "note_name": note_name,
                "deviation_cents": round(deviation_cents, 1),
            }
        )
    return rows


def derive_plot_save_path(input_path: Path, plot_save_arg: str | None) -> Path:
    """Returns the default plot save path based on the input audio file.
    
    Args:
        input_path: Path to the input audio file.
        plot_save_arg: Value passed to `--plot-save`.
        
    Returns:
        Resolved PNG output path.
    """
    if plot_save_arg:
        return Path(plot_save_arg)
    return input_path.parent / f"{input_path.stem}_bell_analysis.png"


def write_csv(rows: list[dict[str, object]], output: Path | None, input_path: Path | None = None) -> None:
    """Write peak records as CSV to a file or stdout.

    Args:
        rows: List of peak dictionaries.
        output: Output file path, or ``None`` to write to stdout/default path.
        input_path: Input file path to derive default output path.
    """
    if output is None and input_path is not None:
        output = input_path.parent / f"{input_path.stem}_bell_analysis.csv"

    fieldnames = [
        "peak_number",
        "frequency_hz",
        "amplitude_db",
        "duration_percent",
        "note_name",
        "deviation_cents",
    ]

    def write_to_fileobj(fobj: object) -> None:
        writer = csv.DictWriter(fobj, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            formatted = {
                "peak_number": row["peak_number"],
                "frequency_hz": f"{row['frequency_hz']:.1f}",
                "amplitude_db": f"{row['amplitude_db']:.1f}",
                "duration_percent": f"{row['duration_percent']:.1f}",
                "note_name": row["note_name"],
                "deviation_cents": f"{row['deviation_cents']:+.1f}",
            }
            writer.writerow(formatted)

    if output is None:
        write_to_fileobj(sys.stdout)
    else:
        with open(output, "w", newline="", encoding="utf-8") as f:
            write_to_fileobj(f)


def write_table(rows: list[dict[str, object]], output: Path | None, input_path: Path | None = None) -> None:
    """Write peak records as an aligned table to a file or stdout.

    Args:
        rows: List of peak dictionaries.
        output: Output file path, or ``None`` to write to stdout/default path.
        input_path: Input file path to derive default output path.
    """
    if output is None and input_path is not None:
        output = input_path.parent / f"{input_path.stem}_bell_analysis.txt"
        
    headers = [
        "peak_number",
        "frequency_hz",
        "amplitude_db",
        "duration_percent",
        "note_name",
        "deviation_cents",
    ]
    formatted_rows: list[list[str]] = []
    for row in rows:
        formatted_rows.append(
            [
                str(row["peak_number"]),
                f"{row['frequency_hz']:.1f}",
                f"{row['amplitude_db']:.1f}",
                f"{row['duration_percent']:.1f}",
                str(row["note_name"]),
                f"{row['deviation_cents']:+.1f}",
            ]
        )

    widths = [len(h) for h in headers]
    for formatted in formatted_rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, formatted)]

    def write_to_fileobj(fobj: object) -> None:
        header_line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
        fobj.write(header_line + "\n")
        for formatted in formatted_rows:
            line = "  ".join(
                cell.ljust(w) for cell, w in zip(formatted, widths)
            )
            fobj.write(line + "\n")

    if output is None:
        write_to_fileobj(sys.stdout)
    else:
        with open(output, "w", encoding="utf-8") as f:
            write_to_fileobj(f)


def plot_analysis(
    data: np.ndarray,
    sr: int,
    peaks: np.ndarray,
    spectrum: np.ndarray,
    freqs: np.ndarray,
    rows: list[dict[str, object]],
    args: argparse.Namespace,
) -> Path | None:
    """Render and optionally display/save the analysis figure.

    Args:
        data: Decay-segment audio signal (1-D).
        sr: Sample rate in Hz.
        peaks: Indices of detected spectral peaks.
        spectrum: Smoothed magnitude spectrum.
        freqs: Frequency axis.
        rows: Peak records sorted by descending amplitude.
        args: Parsed CLI/config argument namespace.

    Returns:
        Path to the saved PNG if ``--plot-save`` was used, otherwise ``None``.
    """
    # Lazy matplotlib import; set a non-interactive backend when headless.
    import matplotlib

    if args.no_show:
        matplotlib.use("Agg")

    import matplotlib.pyplot as plt

    # Compute spectrogram data.
    spec_db, spec_times, spec_freqs = compute_stft(
        data,
        sr,
        args.spec_nperseg,
        args.spec_noverlap,
        args.spec_nfft,
    )

    fig, axes = plt.subplots(2, 1, figsize=(10, 8))

    # --- Top subplot: spectrogram ---
    ax_spec = axes[0]
    y_max = min(args.max_freq, sr / 2.0)
    freq_mask = spec_freqs <= y_max
    spec_floor_db = float(args.spec_floor)
    spec_db_plot = np.maximum(spec_db, spec_floor_db)
    im = ax_spec.pcolormesh(
        spec_times,
        spec_freqs[freq_mask],
        spec_db_plot[freq_mask, :],
        shading="gouraud",
        cmap="magma",
        vmin=spec_floor_db,
        vmax=np.max(spec_db_plot),
    )
    ax_spec.set_ylim(0, y_max)
    ax_spec.set_xlabel("Time (s)")
    ax_spec.set_ylabel("Frequency (Hz)")
    ax_spec.set_title("STFT Spectrogram (decay segment)")
    fig.colorbar(im, ax=ax_spec, label="Magnitude (dB)")

    # --- Bottom subplot: averaged spectrum with peaks ---
    ax_mag = axes[1]
    floor_db = float(args.spectrum_floor)
    spectrum_db = 20.0 * np.log10(np.maximum(spectrum, 0.0) + 1e-12)
    spectrum_db_plot = np.maximum(spectrum_db, floor_db)
    ax_mag.plot(freqs, spectrum_db_plot, color="steelblue", linewidth=0.8)

    if len(peaks) > 0:
        peak_freqs = freqs[peaks]
        peak_mags = np.maximum(spectrum_db[peaks], floor_db)
        ax_mag.vlines(
            peak_freqs,
            ymin=floor_db,
            ymax=peak_mags,
            color="red",
            linewidth=1.5,
            alpha=0.7,
        )

        # Select top N peaks by amplitude, then display in frequency order.
        n_labels = max(0, int(args.n_labels))
        labeled_rows = rows[:n_labels]
        labeled_rows = sorted(labeled_rows, key=lambda r: r["frequency_hz"])

        for idx, row in enumerate(labeled_rows):
            x = row["frequency_hz"]
            y = max(float(np.interp(x, freqs, spectrum_db)), floor_db)
            label = (
                f"{row['frequency_hz']:.1f} Hz\n"
                f"{row['note_name']} {row['deviation_cents']:+.1f} c\n"
                f"{row['amplitude_db']:.1f} dB"
            )
            # Stagger labels vertically and horizontally to reduce overlap.
            offsets = [(0, 14), (0, 24), (0, -14), (0, -24)]
            ox, oy = offsets[idx % len(offsets)]
            va = "bottom" if oy > 0 else "top"
            ax_mag.annotate(
                label,
                xy=(x, y),
                xytext=(ox, oy),
                textcoords="offset points",
                fontsize=7,
                ha="center",
                va=va,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="gray", alpha=0.8),
                arrowprops=dict(arrowstyle="-", color="gray", lw=0.5),
            )

    ax_mag.set_xlim(args.min_freq, min(args.max_freq, sr / 2.0))
    ax_mag.set_ylim(bottom=floor_db)
    ax_mag.set_xlabel("Frequency (Hz)")
    ax_mag.set_ylabel("Magnitude (dB)")
    ax_mag.set_title("Averaged Spectrum with Detected Partials")

    plt.tight_layout()

    saved_path: Path | None = None
    if args.plot_save is not None:
        saved_path = derive_plot_save_path(args.input, args.plot_save)
        plt.savefig(saved_path, dpi=150)

    if not args.no_show:
        plt.show()

    plt.close(fig)
    return saved_path


def save_config(args: argparse.Namespace) -> Path:
    """Write the effective configuration to an INI file.

    Args:
        args: Parsed CLI/config argument namespace containing the effective
            values for all configurable keys.

    Returns:
        Path to the written configuration file.
    """
    if args.save_config:
        path = Path(args.save_config)
    else:
        path = Path.cwd() / "analyze_bell.ini"

    parser = configparser.ConfigParser()
    parser.add_section("analysis")
    parser.add_section("visualization")
    parser.add_section("output")

    parser.set("analysis", "attack_skip_ms", str(args.attack_skip_ms))
    parser.set("analysis", "min_freq", str(args.min_freq))
    parser.set("analysis", "max_freq", str(args.max_freq))
    parser.set("analysis", "prominence", str(args.prominence))
    parser.set("analysis", "distance", str(args.distance))
    parser.set("analysis", "smoothing_window", str(args.smoothing_window))
    parser.set("analysis", "fft_size", str(args.fft_size))
    parser.set("analysis", "hop_size", str(args.hop_size))
    parser.set(
        "analysis",
        "peak_count",
        "" if args.peak_count is None else str(args.peak_count),
    )

    parser.set("visualization", "spec_nperseg", str(args.spec_nperseg))
    parser.set("visualization", "spec_noverlap", str(args.spec_noverlap))
    parser.set("visualization", "spec_nfft", str(args.spec_nfft))
    parser.set("visualization", "spectrum_floor", str(args.spectrum_floor))
    parser.set("visualization", "spec_floor", str(args.spec_floor))
    parser.set("visualization", "n_labels", str(args.n_labels))

    parser.set("output", "format", str(args.format))

    with open(path, "w", encoding="utf-8") as f:
        f.write("# Effective configuration generated by analyze_bell.py\n")
        f.write("# Units are documented in analyze_bell.ini.example.\n\n")
        parser.write(f)

    return path


def generate_midi_bytes(rows: list[dict[str, object]], max_duration_sec: float = 4.0) -> bytes | None:
    """
    Generates a standard MIDI file (as bytes) from the analyzed peaks.
    Frequencies are mapped to 12-TET notes.
    Amplitudes (in dB) are mapped to velocities (0 dB = 127).
    Durations (%) are mapped to seconds relative to max_duration_sec.
    """
    if mido is None:
        return None
        
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)
    
    events = []
    
    for row in rows:
        freq = float(row["frequency_hz"])
        note = int(round(69 + 12 * np.log2(freq / 440.0)))
        note = max(0, min(127, note))
        
        amp_db = float(row["amplitude_db"])
        vel = int(127 + (amp_db * (127 / 60.0)))
        vel = max(1, min(127, vel))
        
        duration_pct = float(row["duration_percent"])
        duration_sec = (duration_pct / 100.0) * max_duration_sec
        
        events.append({'type': 'on', 'time_sec': 0.0, 'note': note, 'velocity': vel})
        events.append({'type': 'off', 'time_sec': duration_sec, 'note': note, 'velocity': 0})
        
    events.sort(key=lambda x: (x['time_sec'], 0 if x['type'] == 'on' else 1))
    
    ticks_per_sec = 960
    last_time = 0.0
    for ev in events:
        delta_sec = ev['time_sec'] - last_time
        delta_ticks = int(round(delta_sec * ticks_per_sec))
        last_time = ev['time_sec']
        
        msg_type = 'note_on' if ev['type'] == 'on' else 'note_off'
        track.append(mido.Message(msg_type, note=ev['note'], velocity=ev['velocity'], time=delta_ticks))
        
    out_buf = io.BytesIO()
    mid.save(file=out_buf)
    return out_buf.getvalue()


def generate_pdf_bytes(
    data: np.ndarray,
    sr: int,
    peaks: np.ndarray,
    spectrum: np.ndarray,
    freqs: np.ndarray,
    rows: list[dict[str, object]],
    n_labels: int,
    spec_db: np.ndarray,
    spec_times: np.ndarray,
    spec_freqs: np.ndarray,
    spec_floor: float,
    spectrum_floor: float,
    max_freq: float,
    pdf_dpi: int = 150,
    filename: str = "",
) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    fig = plt.figure(figsize=(16, 9))
    gs = GridSpec(2, 2, width_ratios=[3, 1])

    # --- Top Left subplot: spectrogram ---
    ax_spec = fig.add_subplot(gs[0, 0])
    y_max = min(max_freq, sr / 2.0)
    freq_mask = spec_freqs <= y_max
    spec_db_plot = np.maximum(spec_db, spec_floor)
    im = ax_spec.pcolormesh(
        spec_times,
        spec_freqs[freq_mask],
        spec_db_plot[freq_mask, :],
        shading="gouraud",
        cmap="magma",
        vmin=spec_floor,
        vmax=np.max(spec_db_plot),
        rasterized=True,
    )
    ax_spec.set_ylim(0, y_max)
    ax_spec.set_xlabel("Time (s)")
    ax_spec.set_ylabel("Frequency (Hz)")
    ax_spec.set_title("STFT Spectrogram (decay segment)")
    fig.colorbar(im, ax=ax_spec, label="Magnitude (dB)")

    # --- Bottom Left subplot: averaged spectrum with peaks ---
    ax_mag = fig.add_subplot(gs[1, 0])
    spectrum_db = 20.0 * np.log10(np.maximum(spectrum, 0.0) + 1e-12)
    spectrum_db_plot = np.maximum(spectrum_db, spectrum_floor)
    ax_mag.plot(freqs, spectrum_db_plot, color="steelblue", linewidth=0.8)

    if len(peaks) > 0:
        peak_freqs = freqs[peaks]
        peak_mags = np.maximum(spectrum_db[peaks], spectrum_floor)
        ax_mag.vlines(peak_freqs, ymin=spectrum_floor, ymax=peak_mags, color="red", linewidth=1.5, alpha=0.7)
        
        labeled_rows = rows[:n_labels]
        labeled_rows = sorted(labeled_rows, key=lambda r: r["frequency_hz"])
        for idx, row in enumerate(labeled_rows):
            x = row["frequency_hz"]
            y = max(float(np.interp(x, freqs, spectrum_db)), spectrum_floor)
            label = (f"{row['frequency_hz']:.1f} Hz\n"
                     f"{row['note_name']} {row['deviation_cents']:+.1f} c\n"
                     f"{row['amplitude_db']:.1f} dB")
            offsets = [(0, 14), (0, 24), (0, -14), (0, -24)]
            ox, oy = offsets[idx % len(offsets)]
            va = "bottom" if oy > 0 else "top"
            ax_mag.annotate(label, xy=(x, y), xytext=(ox, oy), textcoords="offset points",
                            fontsize=8, ha="center", va=va,
                            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="gray", alpha=0.8),
                            arrowprops=dict(arrowstyle="-", color="gray", lw=0.5))

    ax_mag.set_xlim(0, min(max_freq, sr / 2.0))
    ax_mag.set_ylim(bottom=spectrum_floor)
    ax_mag.set_xlabel("Frequency (Hz)")
    ax_mag.set_ylabel("Magnitude (dB)")
    ax_mag.set_title("Averaged Spectrum with Detected Partials")

    # --- Right subplot: table ---
    ax_table = fig.add_subplot(gs[:, 1])
    ax_table.axis('tight')
    ax_table.axis('off')
    if filename:
        ax_table.set_title(f"Analysis Results: {filename}", fontsize=12, fontweight="bold", pad=20)

    table_data = []
    headers = ["N", "Freq", "dB", "Dur%", "Note", "Dev"]
    for row in rows:
        table_data.append([
            str(row["peak_number"]),
            f"{float(row['frequency_hz']):.1f}",
            f"{float(row['amplitude_db']):.1f}",
            f"{float(row['duration_percent']):.1f}",
            str(row["note_name"]),
            f"{float(row['deviation_cents']):+.1f}"
        ])
    
    if table_data:
        table = ax_table.table(cellText=table_data, colLabels=headers, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.2)

    plt.tight_layout()

    out_buf = io.BytesIO()
    fig.savefig(out_buf, format='pdf', bbox_inches='tight', dpi=pdf_dpi)
    plt.close(fig)
    return out_buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    """Entry point for the analyzer CLI.

    Args:
        argv: Argument list. Uses ``sys.argv[1:]`` if ``None``.

    Returns:
        Exit code: 0 for success, 1 for general errors, 2 for empty signal
        after attack skip.
    """
    if argv is None:
        argv = sys.argv[1:]
        
    if len(argv) == 0:
        import subprocess
        print("No arguments provided. Launching GUI mode...", file=sys.stderr)
        project_root = Path(__file__).resolve().parent
        gui_path = project_root / "gui.py"
        try:
            subprocess.run([sys.executable, "-m", "streamlit", "run", str(gui_path)])
            return 0
        except KeyboardInterrupt:
            return 0
    try:
        args = parse_args(argv)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.save_config is not None:
        try:
            path = save_config(args)
            print(f"Saved configuration to {path}", file=sys.stderr)
            return 0
        except Exception as exc:  # pragma: no cover - unexpected IO errors
            print(f"Error: failed to save config: {exc}", file=sys.stderr)
            return 1

    try:
        data, sr = load_audio(args.input)
        decay_signal = skip_attack(data, sr, args.attack_skip_ms)
        spectrum, freqs = compute_mean_spectrum(
            decay_signal, sr, args.fft_size, args.hop_size
        )
        smoothed = smooth_spectrum(spectrum, args.smoothing_window)
        peaks, _ = detect_peaks(
            smoothed,
            freqs,
            args.min_freq,
            args.max_freq,
            args.prominence,
            args.distance,
        )
        # Compute spectrogram data for durations and visualization
        spec_db, spec_times, spec_freqs = compute_stft(
            decay_signal,
            sr,
            args.spec_nperseg,
            args.spec_noverlap,
            args.spec_nfft,
        )
        
        rows = format_peaks(peaks, freqs, smoothed, args.peak_count, spec_db, spec_freqs, spec_times, args.spec_floor)

        visualization_requested = (
            args.visualize or args.spectrogram or args.plot_save is not None
        )
        if visualization_requested:
            plot_analysis(
                data=decay_signal,
                sr=sr,
                peaks=peaks,
                spectrum=smoothed,
                freqs=freqs,
                rows=rows,
                args=args,
            )

        if not args.quiet:
            if args.format == "csv":
                write_csv(rows, args.output, input_path=args.input)
            else:
                write_table(rows, args.output, input_path=args.input)

        return 0
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1 if "not found" in str(exc) or "failed to read" in str(exc) else 2
    except Exception as exc:  # pragma: no cover - unexpected errors
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
