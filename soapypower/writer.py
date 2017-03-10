#!/usr/bin/env python3

import sys, logging, struct, collections

import numpy

from soapypower import threadpool

logger = logging.getLogger(__name__)


class BaseWriter:
    """Power Spectral Density writer base class"""
    def __init__(self, output=sys.stdout):
        self.output = output

        # Use only one writer thread to preserve sequence of written frequencies
        self._executor = threadpool.ThreadPoolExecutor(
            max_workers=1,
            max_queue_size=100,
            thread_name_prefix='Writer_thread'
        )

    def write(self, psd_data_or_future, time_start, time_stop, samples):
        """Write PSD of one frequency hop"""
        raise NotImplementedError

    def write_async(self, psd_data_or_future, time_start, time_stop, samples):
        """Write PSD of one frequncy hop (asynchronously in another thread)"""
        return self._executor.submit(self.write, psd_data_or_future, time_start, time_stop, samples)

    def write_next(self):
        """Write marker for next run of measurement"""
        raise NotImplementedError

    def write_next_async(self):
        """Write marker for next run of measurement (asynchronously in another thread)"""
        return self._executor.submit(self.write_next)


class SoapyPowerBinFormat:
    """Power Spectral Density binary file format"""
    header_struct = struct.Struct('<BddddQQ10x')
    header = collections.namedtuple('Header', 'version timestamp start stop step samples size')
    magic = b'SDRFF'
    version = 1

    def read(self, f):
        """Read data from file-like object"""
        magic = f.read(len(self.magic))
        if not magic:
            return None
        if magic != self.magic:
            raise ValueError('Magic bytes not found! Read data: {}'.format(magic))

        header = self.header._make(
            self.header_struct.unpack(f.read(self.header_struct.size))
        )
        pwr_array = numpy.fromstring(f.read(header.size), dtype='float32')
        return (header, pwr_array)

    def write(self, f, timestamp, start, stop, step, samples, pwr_array):
        """Write data to file-like object"""
        f.write(self.magic)
        f.write(
            self.header_struct.pack(self.version, timestamp, start, stop, step, samples, pwr_array.nbytes)
        )
        pwr_array.tofile(f)
        #f.write(pwr_array.tostring())
        f.flush()

    def header_size(self):
        """Return total size of header"""
        return len(self.magic) + self.header_struct.size


class SoapyPowerBinWriter(BaseWriter):
    """Write Power Spectral Density to stdout or file (in soapy_power binary format)"""
    def __init__(self, output=sys.stdout):
        super().__init__(output=output)

        # Get underlying raw file object
        try:
            self.output = output.buffer.raw
        except AttributeError:
            self.output = output

        self.formatter = SoapyPowerBinFormat()

    def write(self, psd_data_or_future, time_start, time_stop, samples):
        """Write PSD of one frequency hop"""
        try:
            # Wait for result of future
            f_array, pwr_array = psd_data_or_future.result()
        except AttributeError:
            f_array, pwr_array = psd_data_or_future

        try:
            step = f_array[1] - f_array[0]
            self.formatter.write(
                self.output,
                time_stop.timestamp(),
                f_array[0],
                f_array[-1] + step,
                step,
                samples,
                pwr_array
            )
        except Exception as e:
            logging.exception('Error writing to output file:')

    def write_next(self):
        """Write marker for next run of measurement"""
        pass


class RtlPowerFftwWriter(BaseWriter):
    """Write Power Spectral Density to stdout or file (in rtl_power_fftw format)"""
    def write(self, psd_data_or_future, time_start, time_stop, samples):
        """Write PSD of one frequency hop"""
        try:
            # Wait for result of future
            f_array, pwr_array = psd_data_or_future.result()
        except AttributeError:
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

    def write_next(self):
        """Write marker for next run of measurement"""
        self.output.write('\n')
        self.output.flush()


class RtlPowerWriter(BaseWriter):
    """Write Power Spectral Density to stdout or file (in rtl_power format)"""
    def write(self, psd_data_or_future, time_start, time_stop, samples):
        """Write PSD of one frequency hop"""
        try:
            # Wait for result of future
            f_array, pwr_array = psd_data_or_future.result()
        except AttributeError:
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
            logging.exception('Error writing to output file:')

    def write_next(self):
        """Write marker for next run of measurement"""
        pass


formats = {
    'soapy_power_bin': SoapyPowerBinWriter,
    'rtl_power_fftw': RtlPowerFftwWriter,
    'rtl_power': RtlPowerWriter,
}
