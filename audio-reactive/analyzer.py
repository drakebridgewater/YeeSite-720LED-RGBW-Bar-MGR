"""
Real-time audio analyzer.

Captures audio from a sounddevice InputStream, performs windowed FFT,
extracts frequency band energies (bass/mid/high), detects beats, and
computes a per-zone spectrum for visualizations.
"""
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd


class AudioAnalyzer:
    def __init__(
        self,
        device=None,
        sample_rate=44100,
        chunk_size=2048,
        bass_range=(60, 250),
        mid_range=(250, 2000),
        high_range=(2000, 8000),
        beat_threshold=1.6,
        beat_cooldown=0.25,
        peak_decay=0.995,
        n_spectrum_buckets=48,
    ):
        self.device      = device
        self.sample_rate = sample_rate
        self.chunk_size  = chunk_size
        self.beat_threshold = beat_threshold
        self.beat_cooldown  = beat_cooldown
        self.peak_decay     = peak_decay

        self._latest_chunk = None
        self._lock         = threading.Lock()
        self._stream       = None

        # Running peaks for normalization
        self._peak_bass = 0.001
        self._peak_mid  = 0.001
        self._peak_high = 0.001
        self._peak_rms  = 0.001

        # Beat detection: ~1 second of bass energy history
        history_len = max(8, int(sample_rate / chunk_size))
        self._energy_history = deque(maxlen=history_len)
        self._last_beat_time = 0.0

        # Pre-compute frequency axis and band masks (static for given chunk_size)
        freqs = np.fft.rfftfreq(chunk_size, 1.0 / sample_rate)
        self._freqs     = freqs
        self._bass_mask = (freqs >= bass_range[0])  & (freqs < bass_range[1])
        self._mid_mask  = (freqs >= mid_range[0])   & (freqs < mid_range[1])
        self._high_mask = (freqs >= high_range[0])  & (freqs < high_range[1])
        self._window    = np.hanning(chunk_size).astype(np.float32)

        # Spectrum bucket edges (logarithmic from ~40 Hz to 16 kHz)
        lo = np.log10(max(freqs[1], 40.0))
        hi = np.log10(min(freqs[-1], 16000.0))
        self._spectrum_edges = np.logspace(lo, hi, n_spectrum_buckets + 1)
        self._n_buckets = n_spectrum_buckets

    # ------------------------------------------------------------------
    # Stream control
    # ------------------------------------------------------------------

    def start(self):
        self._stream = sd.InputStream(
            device=self.device,
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.chunk_size,
            dtype="float32",
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        mono = indata[:, 0].copy() if indata.ndim > 1 else indata.flatten().copy()
        with self._lock:
            self._latest_chunk = mono

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def process(self):
        """
        Consume the latest audio chunk and return analysis results, or None
        if no new chunk is available yet.

        Returns dict:
            bass, mid, high, rms  – normalized 0.0–1.0
            beat                  – True on detected beat
            spectrum              – list of 48 floats (0.0–1.0), log-spaced bins
        """
        with self._lock:
            if self._latest_chunk is None:
                return None
            chunk = self._latest_chunk
            self._latest_chunk = None

        # FFT with Hann window
        fft = np.abs(np.fft.rfft(chunk * self._window))

        # RMS of raw chunk
        rms_raw = float(np.sqrt(np.mean(chunk ** 2)))

        # Band energies (mean magnitude in each band)
        def band_mean(mask):
            return float(np.mean(fft[mask])) if np.any(mask) else 0.0

        bass_raw = band_mean(self._bass_mask)
        mid_raw  = band_mean(self._mid_mask)
        high_raw = band_mean(self._high_mask)

        # Update running peaks (decay + new max)
        self._peak_bass = max(self._peak_bass * self.peak_decay, bass_raw, 0.001)
        self._peak_mid  = max(self._peak_mid  * self.peak_decay, mid_raw,  0.001)
        self._peak_high = max(self._peak_high * self.peak_decay, high_raw, 0.001)
        self._peak_rms  = max(self._peak_rms  * self.peak_decay, rms_raw,  0.001)

        bass = min(1.0, bass_raw / self._peak_bass)
        mid  = min(1.0, mid_raw  / self._peak_mid)
        high = min(1.0, high_raw / self._peak_high)
        rms  = min(1.0, rms_raw  / self._peak_rms)

        # Beat detection: bass spike above rolling average
        self._energy_history.append(bass_raw)
        avg = float(np.mean(self._energy_history))
        now = time.time()
        beat = False
        if avg > 0 and bass_raw > self.beat_threshold * avg:
            if now - self._last_beat_time > self.beat_cooldown:
                beat = True
                self._last_beat_time = now

        return {
            "bass":     bass,
            "mid":      mid,
            "high":     high,
            "rms":      rms,
            "beat":     beat,
            "spectrum": self._compute_spectrum(fft),
        }

    def _compute_spectrum(self, fft):
        """Map FFT magnitudes into n logarithmically-spaced buckets, normalized 0–1."""
        buckets = np.zeros(self._n_buckets)
        for i in range(self._n_buckets):
            mask = (self._freqs >= self._spectrum_edges[i]) & (self._freqs < self._spectrum_edges[i + 1])
            if np.any(mask):
                buckets[i] = float(np.mean(fft[mask]))
        peak = buckets.max()
        if peak > 0:
            buckets /= peak
        return buckets.tolist()
