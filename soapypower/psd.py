#!/usr/bin/env python3

import math, logging, threading, concurrent.futures

import numpy
import scipy.signal

from soapypower import threadpool

logger = logging.getLogger(__name__)


class PSD:
    """Compute averaged power spectral density using Welch's method"""
    def __init__(self, bins, sample_rate, fft_window='hann', fft_overlap=0.5,
                 crop_factor=0, log_scale=True, remove_dc=False, detrend=None,
                 max_threads=0, max_queue_size=0):
        self._bins = bins
        self._sample_rate = sample_rate
        self._fft_window = fft_window
        self._fft_overlap = fft_overlap
        self._fft_overlap_bins = math.floor(self._bins * self._fft_overlap)
        self._crop_factor = crop_factor
        self._log_scale = log_scale
        self._remove_dc = remove_dc
        self._detrend = detrend
        self._executor = threadpool.ThreadPoolExecutor(
            max_workers=max_threads,
            max_queue_size=max_queue_size,
            thread_name_prefix='PSD_thread'
        )
        self._base_freq_array = numpy.fft.fftfreq(self._bins, 1 / self._sample_rate)

    def set_center_freq(self, center_freq):
        """Set center frequency and clear averaged PSD data"""
        psd_state = {
            'repeats': 0,
            'freq_array': self._base_freq_array + center_freq,
            'pwr_array': None,
            'update_lock': threading.Lock(),
            'futures': [],
        }
        return psd_state

    def result(self, psd_state):
        """Return freqs and averaged PSD for given center frequency"""
        freq_array = numpy.fft.fftshift(psd_state['freq_array'])
        pwr_array = numpy.fft.fftshift(psd_state['pwr_array'])

        if self._crop_factor:
            crop_bins_half = round((self._crop_factor * self._bins) / 2)
            freq_array = freq_array[crop_bins_half:-crop_bins_half]
            pwr_array = pwr_array[crop_bins_half:-crop_bins_half]

        if psd_state['repeats'] > 1:
            pwr_array = pwr_array / psd_state['repeats']

        if self._log_scale:
            pwr_array = 10 * numpy.log10(pwr_array)

        return (freq_array, pwr_array)

    def wait_for_result(self, psd_state):
        """Wait for all PSD threads to finish and return result"""
        if len(psd_state['futures']) > 1:
            concurrent.futures.wait(psd_state['futures'])
        elif psd_state['futures']:
            psd_state['futures'][0].result()
        return self.result(psd_state)

    def result_async(self, psd_state):
        """Return freqs and averaged PSD for given center frequency (asynchronously in another thread)"""
        return self._executor.submit(self.wait_for_result, psd_state)

    def update(self, psd_state, samples_array):
        """Compute PSD from samples and update average for given center frequency"""
        freq_array, pwr_array = scipy.signal.welch(samples_array, self._sample_rate, nperseg=self._bins,
                                                   window=self._fft_window, noverlap=self._fft_overlap_bins,
                                                   detrend=self._detrend)

        if self._remove_dc:
            pwr_array[0] = (pwr_array[1] + pwr_array[-1]) / 2

        with psd_state['update_lock']:
            psd_state['repeats'] += 1
            if psd_state['pwr_array'] is None:
                psd_state['pwr_array'] = pwr_array
            else:
                psd_state['pwr_array'] += pwr_array

    def update_async(self, psd_state, samples_array):
        """Compute PSD from samples and update average for given center frequency (asynchronously in another thread)"""
        future = self._executor.submit(self.update, psd_state, samples_array)
        psd_state['futures'].append(future)
        return future
