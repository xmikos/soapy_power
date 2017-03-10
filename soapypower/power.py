#!/usr/bin/env python3

import sys, time, datetime, math, logging

import simplesoapy
import numpy

from soapypower import psd, writer

logger = logging.getLogger(__name__)
array_empty = numpy.empty
array_zeros = numpy.zeros


class SoapyPower:
    """SoapySDR spectrum analyzer"""
    def __init__(self, soapy_args='', sample_rate=2.00e6, bandwidth=0, corr=0, gain=20.7,
                 auto_gain=False, channel=0, antenna='',
                 force_sample_rate=False, force_bandwidth=False,
                 output=sys.stdout, output_format='rtl_power'):
        self.device = simplesoapy.SoapyDevice(
            soapy_args=soapy_args, sample_rate=sample_rate, bandwidth=bandwidth, corr=corr,
            gain=gain, auto_gain=auto_gain, channel=channel, antenna=antenna,
            force_sample_rate=force_sample_rate, force_bandwidth=force_bandwidth
        )

        self._buffer = None
        self._buffer_repeats = None
        self._base_buffer_size = None
        self._max_buffer_size = None
        self._bins = None
        self._repeats = None
        self._tune_delay = None
        self._psd = None

        self._writer = writer.formats[output_format](output)

    def nearest_freq(self, freq, bin_size):
        """Return nearest frequency based on bin size"""
        return round(freq / bin_size) * bin_size

    def nearest_bins(self, bins, even=False, pow2=False):
        """Return nearest number of FFT bins (even or power of two)"""
        if pow2:
            bins_log2 = math.log(bins, 2)
            if bins_log2 % 1 != 0:
                bins = 2**math.ceil(bins_log2)
                logger.warning('number of FFT bins should be power of two, changing to {}'.format(bins))
        elif even:
            if bins % 2 != 0:
                bins = math.ceil(bins / 2) * 2
                logger.warning('number of FFT bins should be even, changing to {}'.format(bins))

        return bins

    def nearest_overlap(self, overlap, bins):
        """Return nearest overlap/crop factor based on number of bins"""
        bins_overlap = overlap * bins
        if bins_overlap % 2 != 0:
            bins_overlap = math.ceil(bins_overlap / 2) * 2
            overlap = bins_overlap / bins
            logger.warning('number of overlapping FFT bins should be even, '
                           'changing overlap/crop factor to {:.5f}'.format(overlap))
        return overlap

    def bin_size_to_bins(self, bin_size):
        """Convert bin size [Hz] to number of FFT bins"""
        return math.ceil(self.device.sample_rate / bin_size)

    def bins_to_bin_size(self, bins):
        """Convert number of FFT bins to bin size [Hz]"""
        return self.device.sample_rate / bins

    def time_to_repeats(self, bins, integration_time):
        """Convert integration time to number of repeats"""
        return math.ceil((self.device.sample_rate * integration_time) / bins)

    def repeats_to_time(self, bins, repeats):
        """Convert number of repeats to integration time"""
        return (repeats * bins) / self.device.sample_rate

    def freq_plan(self, min_freq, max_freq, bins, overlap=0, quiet=False):
        """Returns list of frequencies for frequency hopping"""
        bin_size = self.bins_to_bin_size(bins)
        bins_crop = round((1 - overlap) * bins)
        sample_rate_crop = (1 - overlap) * self.device.sample_rate

        freq_range = max_freq - min_freq
        hopping = True if freq_range >= sample_rate_crop else False
        hop_size = self.nearest_freq(sample_rate_crop, bin_size)
        hops = math.ceil(freq_range / hop_size) if hopping else 1
        min_center_freq = min_freq + (hop_size / 2) if hopping else min_freq + (freq_range / 2)
        max_center_freq = min_center_freq + ((hops - 1) * hop_size)

        freq_list = [min_center_freq + (i * hop_size) for i in range(hops)]

        if not quiet:
            logger.info('overlap: {:.5f}'.format(overlap))
            logger.info('bin_size: {:.2f} Hz'.format(bin_size))
            logger.info('bins: {}'.format(bins))
            logger.info('bins (after crop): {}'.format(bins_crop))
            logger.info('sample_rate: {:.3f} MHz'.format(self.device.sample_rate / 1e6))
            logger.info('sample_rate (after crop): {:.3f} MHz'.format(sample_rate_crop / 1e6))
            logger.info('freq_range: {:.3f} MHz'.format(freq_range / 1e6))
            logger.info('hopping: {}'.format('YES' if hopping else 'NO'))
            logger.info('hop_size: {:.3f} MHz'.format(hop_size / 1e6))
            logger.info('hops: {}'.format(hops))
            logger.info('min_center_freq: {:.3f} MHz'.format(min_center_freq / 1e6))
            logger.info('max_center_freq: {:.3f} MHz'.format(max_center_freq / 1e6))
            logger.info('min_freq (after crop): {:.3f} MHz'.format((min_center_freq - (hop_size / 2)) / 1e6))
            logger.info('max_freq (after crop): {:.3f} MHz'.format((max_center_freq + (hop_size / 2)) / 1e6))

            logger.debug('Frequency hops table:')
            logger.debug('  {:8s}      {:8s}      {:8s}'.format('Min:', 'Center:', 'Max:'))
            for f in freq_list:
                logger.debug('  {:8.3f} MHz  {:8.3f} MHz  {:8.3f} MHz'.format(
                    (f - (self.device.sample_rate / 2)) / 1e6,
                    f / 1e6,
                    (f + (self.device.sample_rate / 2)) / 1e6,
                ))

        return freq_list

    def create_buffer(self, bins, repeats, base_buffer_size, max_buffer_size=0):
        """Create buffer for reading samples"""
        samples = bins * repeats
        buffer_repeats = 1
        buffer_size = math.ceil(samples / base_buffer_size) * base_buffer_size

        if not max_buffer_size:
            max_buffer_size = base_buffer_size * 100

        if max_buffer_size > 0:
            max_buffer_size = math.ceil(max_buffer_size / base_buffer_size) * base_buffer_size
            if buffer_size > max_buffer_size:
                logger.warning('Required buffer size ({}) will be shrinked to max_buffer_size ({})!'.format(
                    buffer_size, max_buffer_size
                ))
                buffer_repeats = math.ceil(buffer_size / max_buffer_size)
                buffer_size = max_buffer_size

        logger.info('repeats: {}'.format(repeats))
        logger.info('samples: {} (time: {:.5f} s)'.format(samples, samples / self.device.sample_rate))
        if max_buffer_size > 0:
            logger.info('max_buffer_size (samples): {} (repeats: {:.2f}, time: {:.5f} s)'.format(
                max_buffer_size, max_buffer_size / bins, max_buffer_size / self.device.sample_rate
            ))
        else:
            logger.info('max_buffer_size (samples): UNLIMITED')
        logger.info('buffer_size (samples): {} (repeats: {:.2f}, time: {:.5f} s)'.format(
            buffer_size, buffer_size / bins, buffer_size / self.device.sample_rate
        ))
        logger.info('buffer_repeats: {}'.format(buffer_repeats))

        return (buffer_repeats, array_zeros(buffer_size, numpy.complex64))

    def setup(self, bins, repeats, base_buffer_size=0, max_buffer_size=0,
              fft_window='hann', fft_overlap=0.5, crop_factor=0, log_scale=True, remove_dc=False,
              detrend=None, tune_delay=0, max_threads=0, max_queue_size=0):
        """Prepare samples buffer and start streaming samples from device"""
        if self.device.is_streaming:
            self.device.stop_stream()

        base_buffer = self.device.start_stream(buffer_size=base_buffer_size)
        self._bins = bins
        self._repeats = repeats
        self._base_buffer_size = len(base_buffer)
        self._max_buffer_size = max_buffer_size
        self._buffer_repeats, self._buffer = self.create_buffer(
            bins, repeats, self._base_buffer_size, self._max_buffer_size
        )
        self._tune_delay = tune_delay
        self._psd = psd.PSD(bins, self.device.sample_rate, fft_window=fft_window, fft_overlap=fft_overlap,
                            crop_factor=crop_factor, log_scale=log_scale, remove_dc=remove_dc, detrend=detrend,
                            max_threads=max_threads, max_queue_size=max_queue_size)

    def stop(self):
        """Stop streaming samples from device and delete samples buffer"""
        if not self.device.is_streaming:
            return

        self.device.stop_stream()
        self._bins = None
        self._repeats = None
        self._base_buffer_size = None
        self._max_buffer_size = None
        self._buffer_repeats = None
        self._buffer = None
        self._tune_delay = None
        self._psd = None

    def psd(self, freq):
        """Tune to specified center frequency and compute Power Spectral Density"""
        if not self.device.is_streaming:
            raise RuntimeError('Streaming is not initialized, you must run setup() first!')

        # Tune to new frequency in main thread
        logger.debug('  Frequency hop: {:.2f} Hz'.format(freq))
        t_freq = time.time()
        if self.device.freq != freq:
            self.device.freq = freq
            if self._tune_delay:
                time.sleep(self._tune_delay)
        else:
            logger.debug('    Same frequency as before, tuning skipped')
        psd_state = self._psd.set_center_freq(freq)
        t_freq_end = time.time()
        logger.debug('    Tune time: {:.3f} s'.format(t_freq_end - t_freq))

        for repeat in range(self._buffer_repeats):
            logger.debug('    Repeat: {}'.format(repeat + 1))
            # Read samples from SDR in main thread
            t_acq = time.time()
            acq_time_start = datetime.datetime.utcnow()
            self.device.read_stream_into_buffer(self._buffer)
            acq_time_stop = datetime.datetime.utcnow()
            t_acq_end = time.time()
            logger.debug('      Acquisition time: {:.3f} s'.format(t_acq_end - t_acq))

            # Start FFT computation in another thread
            self._psd.update_async(psd_state, numpy.copy(self._buffer))

            t_final = time.time()
            logger.debug('      FFT time: {:.3f} s'.format(t_final - t_acq_end))
        psd_future = self._psd.result_async(psd_state)
        logger.debug('    Total hop time: {:.3f} s'.format(t_final - t_freq))

        return (psd_future, acq_time_start, acq_time_stop)

    def sweep(self, min_freq, max_freq, bins, repeats, runs=0, time_limit=0, overlap=0,
              fft_window='hann', fft_overlap=0.5, crop=False, log_scale=True, remove_dc=False, detrend=None,
              tune_delay=0, base_buffer_size=0, max_buffer_size=0, max_threads=0, max_queue_size=0):
        """Sweep spectrum using frequency hopping"""
        self.setup(
            bins, repeats, base_buffer_size, max_buffer_size,
            fft_window=fft_window, fft_overlap=fft_overlap,
            crop_factor=overlap if crop else 0, log_scale=log_scale, remove_dc=remove_dc, detrend=detrend,
            tune_delay=tune_delay, max_threads=max_threads, max_queue_size=max_queue_size
        )
        freq_list = self.freq_plan(min_freq, max_freq, bins, overlap)

        t_start = time.time()
        run = 0
        while (runs == 0 or run < runs):
            run += 1
            t_run_start = time.time()
            logger.debug('Run: {}'.format(run))

            for freq in freq_list:
                # Tune to new frequency, acquire samples and compute Power Spectral Density
                psd_future, acq_time_start, acq_time_stop = self.psd(freq)

                # Write PSD to stdout (in another thread)
                self._writer.write_async(psd_future, acq_time_start, acq_time_stop, len(self._buffer))

            # Write end of measurement marker (in another thread)
            write_next_future = self._writer.write_next_async()
            t_run = time.time()
            logger.debug('  Total run time: {:.3f} s'.format(t_run - t_run_start))

            # End measurement if time limit is exceeded
            if time_limit and (time.time() - t_start) >= time_limit:
                logger.info('Time limit of {} s exceeded, completed {} runs'.format(time_limit, run))
                break

        # Wait for last write to be finished
        write_next_future.result()

        # Debug thread pool queues
        logging.debug('Number of USB buffer overflow errors: {}'.format(self.device.buffer_overflow_count))
        logging.debug('PSD worker threads: {}'.format(self._psd._executor._max_workers))
        logging.debug('Max. PSD queue size: {} / {}'.format(self._psd._executor.max_queue_size_reached,
                                                            self._psd._executor.max_queue_size))
        logging.debug('Writer worker threads: {}'.format(self._writer._executor._max_workers))
        logging.debug('Max. Writer queue size: {} / {}'.format(self._writer._executor.max_queue_size_reached,
                                                               self._writer._executor.max_queue_size))

        # Shutdown SDR
        self.stop()
        t_stop = time.time()
        logger.info('Total time: {:.3f} s'.format(t_stop - t_start))
