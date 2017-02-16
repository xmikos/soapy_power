#!/usr/bin/env python3

import math, logging, concurrent.futures

import numpy
import scipy.signal

logger = logging.getLogger(__name__)


class PSD:
    """Compute averaged power spectral density using Welch's method"""
    def __init__(self, bins, sample_rate, fft_window='hann', fft_overlap=0.5,
                 crop_factor=0, log_scale=True):
        self._bins = bins
        self._sample_rate = sample_rate
        self._fft_window = fft_window
        self._fft_overlap = fft_overlap
        self._fft_overlap_bins = math.floor(self._bins * self._fft_overlap)
        self._crop_factor = crop_factor
        self._log_scale = log_scale
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._base_freq_array = numpy.fft.fftfreq(self._bins, 1 / self._sample_rate)
        self.reset()

    def reset(self):
        """Clear averaged PSD data"""
        self._repeats = 0
        self._freq_array = self._base_freq_array
        self._pwr_array = None

    def set_center_freq(self, center_freq):
        """Set center frequency and clear averaged PSD data"""
        self.reset()
        self._freq_array = self._base_freq_array + center_freq

    def set_center_freq_async(self, center_freq):
        """Set center frequency and clear averaged PSD data (asynchronously in another thread)"""
        return self._executor.submit(self.set_center_freq, center_freq)

    def result(self):
        """Return frequencies and averaged PSD"""
        freq_array = numpy.fft.fftshift(self._freq_array)
        pwr_array = numpy.fft.fftshift(self._pwr_array)

        if self._crop_factor:
            crop_bins_half = round((self._crop_factor * self._bins) / 2)
            freq_array = freq_array[crop_bins_half:-crop_bins_half]
            pwr_array = pwr_array[crop_bins_half:-crop_bins_half]

        pwr_array = pwr_array / self._repeats
        if self._log_scale:
            pwr_array = 10 * numpy.log10(pwr_array)

        return (freq_array, pwr_array)

    def update(self, samples_array):
        """Compute PSD from samples and update average"""
        freq_array, pwr_array = scipy.signal.welch(samples_array, self._sample_rate, nperseg=self._bins,
                                                   window=self._fft_window, noverlap=self._fft_overlap_bins)
        self._repeats += 1
        if self._pwr_array is None:
            self._pwr_array = pwr_array
        else:
            self._pwr_array += pwr_array

        return self.result()

    def update_async(self, samples_array):
        """Compute PSD from samples and update average (asynchronously in another thread)"""
        return self._executor.submit(self.update, samples_array)
