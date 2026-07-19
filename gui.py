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

st.sidebar.markdown("##### Bell Sample Overtone Analyzer")
st.sidebar.caption("Analyze WAV files to extract and visualize spectral overtones and harmonic durations.")

defaults = config_defaults()

st.sidebar.markdown("**1. Input**")

# Find all wav files in samples/
samples_dir = Path("samples")
wav_files = list(samples_dir.glob("*.wav"))
wav_options = [str(p) for p in wav_files]

selected_file = st.sidebar.selectbox("Sample:", wav_options)

with st.sidebar.expander("Analysis Parameters", expanded=False):
    attack_skip_ms = st.number_input("Skip (ms)", value=float(defaults["attack_skip_ms"]))
    min_freq = st.number_input("Min Freq (Hz)", value=float(defaults["min_freq"]))
    max_freq = st.number_input("Max Freq (Hz)", value=float(defaults["max_freq"]))
    prominence = st.number_input("Prominence", value=float(defaults["prominence"]), format="%.4f", step=0.001)
    distance = st.number_input("Min Bin Dist.", value=int(defaults["distance"]))
    smoothing_window = st.number_input("Smooth Win.", value=int(defaults["smoothing_window"]))

with st.sidebar.expander("Display Options", expanded=False):
    spectrum_floor = st.number_input("Spec. Floor (dB)", value=float(defaults["spectrum_floor"]))
    spec_floor = st.number_input("STFT Floor (dB)", value=float(defaults["spec_floor"]))
    n_labels = st.number_input("Number of Labels", value=int(defaults["n_labels"]))

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
        index=get_index(int(defaults["fft_size"]), fft_options, 6)
    )
    hop_size = st.number_input("Hop Size", value=int(defaults["hop_size"]), step=512)
    
    spec_nperseg = st.selectbox(
        "STFT Win Size",
        options=fft_options,
        index=get_index(int(defaults["spec_nperseg"]), fft_options, 4)
    )
    spec_noverlap = st.number_input("STFT Overlap", value=int(defaults["spec_noverlap"]), step=512)
    
    spec_nfft = st.selectbox(
        "STFT FFT Size",
        options=fft_options,
        index=get_index(int(defaults["spec_nfft"]), fft_options, 4)
    )

with st.sidebar.expander("Export Options", expanded=False):
    midi_top_n = st.number_input("Max MIDI Overtones", min_value=1, max_value=128, value=16, step=1)
    pdf_dpi = st.number_input("PDF Image DPI", min_value=50, max_value=600, value=150, step=50)

if selected_file:
    try:
        input_path = Path(selected_file)
        data, sr = load_audio(input_path)
        
        # Process the audio
        decay_signal = skip_attack(data, sr, attack_skip_ms)
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
