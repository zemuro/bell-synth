import streamlit as st
st.set_page_config(page_title="Bell Analyzer", layout="wide")
st.markdown("""
    <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 0rem;
        }
    </style>
""", unsafe_allow_html=True)
import numpy as np
import soundfile as sf
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

# Import the core logic from analyze_bell
from analyze_bell import (
    load_audio,
    skip_attack,
    find_transient_ms,
    compute_mean_spectrum,
    smooth_spectrum,
    detect_peaks,
    compute_stft,
    format_peaks,
    config_defaults,
    generate_midi_bytes,
    generate_pdf_bytes,
)

# Main title and description moved to sidebar

st.sidebar.markdown("##### [Bell Sample Overtone Analyzer](https://github.com/zemuro/bell-analyzer)")
st.sidebar.caption("Analyze WAV files to extract and visualize spectral overtones and harmonic durations.")
st.sidebar.caption("&copy; Ruslan Mazavin, 2026. Licensed under [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/).")

defaults = config_defaults()

st.sidebar.markdown("**1. Input**")

source_folder = st.sidebar.text_input("Source Folder", value="samples", help="Path can be absolute (e.g. C:/audio) or relative to the script root (e.g. samples).")
samples_dir = Path(source_folder)
if samples_dir.exists() and samples_dir.is_dir():
    wav_files = list(samples_dir.glob("*.wav"))
else:
    wav_files = []
    st.sidebar.warning(f"Folder '{source_folder}' not found.")
    
wav_options = [str(p) for p in wav_files]

selected_file = st.sidebar.selectbox("Sample:", wav_options)

uploaded_file = st.sidebar.file_uploader("Or Upload WAV", type=["wav"])
if uploaded_file is not None:
    samples_dir = Path("samples")
    samples_dir.mkdir(exist_ok=True)
    temp_path = samples_dir / uploaded_file.name
    temp_path.write_bytes(uploaded_file.getvalue())
    selected_file = str(temp_path)

if "start_offset_ms" not in st.session_state:
    st.session_state.start_offset_ms = 0.0
if "last_file" not in st.session_state:
    st.session_state.last_file = selected_file

if st.session_state.last_file != selected_file:
    st.session_state.start_offset_ms = 0.0
    st.session_state.last_file = selected_file

with st.sidebar.expander("Analysis Parameters", expanded=False):
    col1, col2 = st.columns([2, 1])
    start_offset_ms = col1.number_input(
        "Start Offset (ms)", 
        min_value=0.0,
        value=float(st.session_state.start_offset_ms), 
        step=5.0, 
        format="%.1f",
        help="The starting time of the analysis window. Used to trim silence before the bell strike."
    )
    st.session_state.start_offset_ms = start_offset_ms
    
    if col2.button("Auto-Detect"):
        if selected_file:
            tmp_data, tmp_sr = load_audio(Path(selected_file))
            detected = find_transient_ms(tmp_data, tmp_sr)
            st.session_state.start_offset_ms = detected
            st.rerun()

    attack_skip_ms = st.number_input(
        "Attack Skip (ms)", 
        min_value=0.0,
        value=float(defaults["attack_skip_ms"]),
        step=10.0,
        help="How much of the chaotic initial strike (transient) to skip over before analyzing the stable tonal decay."
    )
    
    if selected_file:
        try:
            from matplotlib.figure import Figure
            tmp_data, tmp_sr = load_audio(Path(selected_file))
            end_ms = max(100.0, start_offset_ms + attack_skip_ms + 50.0)
            end_sample = int((end_ms / 1000.0) * tmp_sr)
            end_sample = min(end_sample, len(tmp_data))
            
            plot_data = tmp_data[:end_sample]
            time_axis = np.linspace(0, end_ms, len(plot_data), endpoint=False)
            
            fig = Figure(figsize=(3, 3))
            ax = fig.add_subplot(111)
            ax.plot(time_axis, plot_data, color='black', linewidth=0.5)
            ax.axvline(start_offset_ms, color='green', linestyle='--', linewidth=1.5, label='Start')
            ax.axvline(start_offset_ms + attack_skip_ms, color='red', linestyle='--', linewidth=1.5, label='Attack End')
            ax.set_title("Transient Window", fontsize=10)
            ax.set_xlabel("Time (ms)", fontsize=8)
            ax.tick_params(axis='both', which='major', labelsize=8)
            ax.set_yticks([])
            fig.tight_layout()
            st.pyplot(fig)
        except Exception:
            pass

    min_freq = st.number_input("Min Freq (Hz)", min_value=10.0, max_value=20000.0, value=float(defaults["min_freq"]), step=10.0, help="Lower bound of frequencies to search for overtones.")
    max_freq = st.number_input("Max Freq (Hz)", min_value=100.0, max_value=24000.0, value=float(defaults["max_freq"]), step=100.0, help="Upper bound of frequencies to search for overtones.")
    prominence = st.number_input("Prominence", min_value=0.0001, max_value=1.0, value=float(defaults["prominence"]), format="%.4f", step=0.001, help="How much a spectral peak must stand out above the surrounding noise to be considered an overtone. Lower this if it misses quiet notes.")
    distance = st.number_input("Min Bin Dist.", min_value=1, max_value=2000, value=int(defaults["distance"]), step=5, help="Minimum number of FFT bins between two peaks. Increase this if a single note is incorrectly detected as multiple tiny peaks.")
    
    # Force odd smoothing window
    smooth_default = int(defaults["smoothing_window"])
    if smooth_default % 2 == 0:
        smooth_default += 1
    smoothing_window = st.number_input("Smooth Win.", min_value=3, max_value=999, value=smooth_default, step=2, help="Smooths the jagged spectrum before peak detection to avoid finding false peaks in noise. Must be an odd number.")

with st.sidebar.expander("Display Options", expanded=False):
    spectrum_floor = st.number_input("Spec. Floor (dB)", max_value=0.0, value=float(defaults["spectrum_floor"]), step=5.0, help="Sets the lowest visible dB level on the 1D spectrum plot. Lower this if peaks are cut off at the bottom.")
    spec_floor = st.number_input("STFT Floor (dB)", max_value=0.0, value=float(defaults["spec_floor"]), step=5.0, help="Sets the lowest visible dB level on the 2D spectrogram. Raise this to filter out background noise in the visual.")
    n_labels = st.number_input("Number of Labels", min_value=0, max_value=100, value=int(defaults["n_labels"]), step=1, help="Limit the number of text labels on the spectrum plot to avoid crowding.")

with st.sidebar.expander("Advanced FFT Parameters", expanded=False):
    fft_options = [256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]
    
    def get_index(val, options, default_idx):
        try:
            return options.index(val)
        except ValueError:
            return default_idx
            
    fft_size = st.selectbox(
        "FFT Size",
        options=fft_options,
        index=get_index(int(defaults["fft_size"]), fft_options, 6),
        help="Size of the FFT window. Higher values give better frequency resolution (pitch accuracy) but worse time resolution."
    )
    hop_size = st.number_input("Hop Size", min_value=64, max_value=65536, value=int(defaults["hop_size"]), step=256, help="Number of samples between successive FFT frames. Lower values give smoother time-based analysis but increase computation time.")
    
    spec_nperseg = st.selectbox(
        "STFT Win Size",
        options=fft_options,
        index=get_index(int(defaults["spec_nperseg"]), fft_options, 4),
        help="Length of each segment for the spectrogram's Short-Time Fourier Transform. Usually matches FFT Size."
    )
    safe_max_overlap = max(0, spec_nperseg - 64)
    default_overlap = int(defaults["spec_noverlap"])
    if default_overlap > safe_max_overlap:
        spec_noverlap_val = min(safe_max_overlap, (spec_nperseg * 3) // 4)
    else:
        spec_noverlap_val = default_overlap

    spec_noverlap = st.number_input("STFT Overlap", min_value=0, max_value=safe_max_overlap, value=spec_noverlap_val, step=256, help="Overlap between STFT segments. Higher overlap gives a smoother visual but takes longer to compute.")
    
    spec_nfft_options = [x for x in fft_options if x >= spec_nperseg]
    spec_nfft = st.selectbox(
        "STFT FFT Size",
        options=spec_nfft_options,
        index=get_index(max(int(defaults["spec_nfft"]), spec_nperseg), spec_nfft_options, 0),
        help="Zero-padded FFT size for the spectrogram. Must be greater than or equal to the STFT Window Size."
    )

with st.sidebar.expander("Export Options", expanded=False):
    midi_top_n = st.number_input("Max MIDI Overtones", min_value=1, max_value=128, value=16, step=1, help="Only export the N loudest overtones to the MIDI file to prevent cluttering the synthesizer.")
    pdf_dpi = st.number_input("PDF Image DPI", min_value=50, max_value=600, value=150, step=10, help="Resolution of the spectrogram image embedded in the PDF. Lower this if the exported PDF file size is too large.")

if selected_file:
    try:
        input_path = Path(selected_file)
        data, sr = load_audio(input_path)
        
        # Process the audio
        decay_signal = skip_attack(data, sr, attack_skip_ms, start_offset_ms=start_offset_ms)
        spectrum, freqs = compute_mean_spectrum(decay_signal, sr, fft_size, hop_size)
        smoothed = smooth_spectrum(spectrum, smoothing_window)
        peaks, _ = detect_peaks(smoothed, freqs, min_freq, max_freq, prominence, distance)
        
        # STFT for spectrogram and durations
        spec_db, spec_times, spec_freqs = compute_stft(
            decay_signal, sr, spec_nperseg, spec_noverlap, spec_nfft
        )
        
        # Format peaks
        rows = format_peaks(peaks, freqs, smoothed, None, spec_db, spec_freqs, spec_times, spec_floor)
        
        # Display data
        st.markdown(f"**Analysis Results:** `{input_path.name}`")
        
        main_col1, main_col2 = st.columns([1, 3])
        
        with main_col2:
            fig, axes = plt.subplots(2, 1, figsize=(12, 7))
            
            # Spectrogram
            ax_spec = axes[0]
            y_max = min(max_freq, sr / 2.0)
            freq_mask = spec_freqs <= y_max
            spec_db_plot = np.maximum(spec_db, spec_floor)
            im = ax_spec.pcolormesh(
                spec_times, spec_freqs[freq_mask], spec_db_plot[freq_mask, :],
                shading="gouraud", cmap="magma", vmin=spec_floor, vmax=np.max(spec_db_plot)
            )
            ax_spec.set_ylim(0, y_max)
            ax_spec.set_xlabel("Time (s)")
            ax_spec.set_ylabel("Frequency (Hz)")
            ax_spec.set_title("STFT Spectrogram (decay segment)")
            fig.colorbar(im, ax=ax_spec, label="Magnitude (dB)")
            
            # Spectrum
            ax_mag = axes[1]
            spectrum_db = 20.0 * np.log10(np.maximum(smoothed, 0.0) + 1e-12)
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
                                    
            ax_mag.set_xlim(min_freq, min(max_freq, sr / 2.0))
            ax_mag.set_ylim(bottom=spectrum_floor)
            ax_mag.set_xlabel("Frequency (Hz)")
            ax_mag.set_ylabel("Magnitude (dB)")
            ax_mag.set_title("Averaged Spectrum with Detected Partials")
            plt.tight_layout()
            
            st.pyplot(fig)
        
        with main_col1:
            st.markdown("**Detected Peaks**")
            if rows:
                df = pd.DataFrame(rows)
                # Reorder columns slightly for better UI display
                df = df[["peak_number", "frequency_hz", "amplitude_db", "duration_percent", "note_name", "deviation_cents"]]
                st.dataframe(df.style.format({
                    "frequency_hz": "{:.1f}",
                    "amplitude_db": "{:.1f}",
                    "duration_percent": "{:.1f}",
                    "deviation_cents": "{:+.1f}"
                }), width='stretch', height=800, hide_index=True)
                
                # Allow downloading CSV, MIDI, and PDF side-by-side
                col1, col2, col3 = st.columns(3)
                with col1:
                    csv_data = df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name=f"{input_path.stem}_bell_analysis.csv",
                        mime="text/csv",
                    )
                
                with col2:
                    midi_rows = sorted(rows, key=lambda r: r["amplitude_db"], reverse=True)[:midi_top_n]
                    midi_bytes = generate_midi_bytes(midi_rows, max_duration_sec=4.0)
                    if midi_bytes:
                        st.download_button(
                            label="Save as MIDI",
                            data=midi_bytes,
                            file_name=f"{input_path.stem}_bell_chords.mid",
                            mime="audio/midi",
                        )
                
                with col3:
                    pdf_bytes = generate_pdf_bytes(
                        data=decay_signal,
                        sr=sr,
                        peaks=peaks,
                        spectrum=spectrum,
                        freqs=freqs,
                        rows=rows,
                        n_labels=n_labels,
                        spec_db=spec_db,
                        spec_times=spec_times,
                        spec_freqs=spec_freqs,
                        spec_floor=spec_floor,
                        spectrum_floor=spectrum_floor,
                        max_freq=max_freq,
                        pdf_dpi=pdf_dpi,
                        filename=input_path.name,
                    )
                    st.download_button(
                        label="Save as PDF",
                        data=pdf_bytes,
                        file_name=f"{input_path.stem}_bell_analysis.pdf",
                        mime="application/pdf",
                    )
            
    except Exception as e:
        st.error(f"Error analyzing file: {e}")
