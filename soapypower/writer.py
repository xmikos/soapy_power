#!/usr/bin/env python3

import sys, logging, concurrent.futures

logger = logging.getLogger(__name__)


class RtlPowerFftwWriter:
    """Write Power Spectral Density to stdout or file (in rtl_power_fftw format)"""
    def __init__(self, output=sys.stdout):
        self.output = output
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def write(self, psd_data_or_future, time_start, time_stop, samples):
        """Write PSD of one frequency hop"""
        try:
            # Wait for result of future
            f_array, pwr_array = psd_data_or_future.result()
        except NameError:
            f_array, pwr_array = psd_data_or_future

        self.output.write('# soapy_power output\n')
        self.output.write('# Acquisition start: {}\n'.format(time_start))
        self.output.write('# Acquisition end: {}\n'.format(time_stop))
        self.output.write('#\n')
        self.output.write('# frequency [Hz] power spectral density [dB/Hz]\n')

        for f, pwr in zip(f_array, pwr_array):
            self.output.write('{} {}\n'.format(f, pwr))

        self.output.write('\n')
        self.output.flush()

    def write_async(self, psd_data_or_future, time_start, time_stop, samples):
        """Write PSD of one frequncy hop (asynchronously in another thread)"""
        return self._executor.submit(self.write, psd_data_or_future, time_start, time_stop, samples)

    def write_next(self):
        """Write marker for next run of measurement"""
        self.output.write('\n')
        self.output.flush()

    def write_next_async(self):
        """Write marker for next run of measurement (asynchronously in another thread)"""
        return self._executor.submit(self.write_next)


class RtlPowerWriter:
    """Write Power Spectral Density to stdout or file (in rtl_power format)"""
    def __init__(self, output=sys.stdout):
        self.output = output
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def write(self, psd_data_or_future, time_start, time_stop, samples):
        """Write PSD of one frequency hop"""
        try:
            # Wait for result of future
            f_array, pwr_array = psd_data_or_future.result()
        except NameError:
            f_array, pwr_array = psd_data_or_future

        try:
            step = f_array[1] - f_array[0]
            row = [
                time_stop.strftime('%Y-%m-%d'), time_stop.strftime('%H:%M:%S'),
                f_array[0], f_array[-1] + step, step, samples
            ]
            row += list(pwr_array)
            self.output.write('{}\n'.format(', '.join(str(x) for x in row)))
            self.output.flush()
        except Exception as e:
            print(e, file=sys.stderr)

    def write_async(self, psd_data_or_future, time_start, time_stop, samples):
        """Write PSD of one frequncy hop (asynchronously in another thread)"""
        self._executor.submit(self.write, psd_data_or_future, time_start, time_stop, samples)

    def write_next(self):
        """Write marker for next run of measurement"""
        pass

    def write_next_async(self):
        """Write marker for next run of measurement (asynchronously in another thread)"""
        self._executor.submit(self.write_next)


formats = {
    'rtl_power_fftw': RtlPowerFftwWriter,
    'rtl_power': RtlPowerWriter
}
