#!/usr/bin/env python3

import sys, logging, argparse, re

import simplesoapy
from soapypower import power
from soapypower.version import __version__

logger = logging.getLogger(__name__)
re_float_with_multiplier = re.compile(r'(?P<num>[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)(?P<multi>[kMGT])?')
multipliers = {'k': 1e3, 'M': 1e6, 'G': 1e9, 'T': 1e12}


def use_pyfftw():
    """Import pyfftw (if it is available) and monkey patch scipy.fftpack"""
    try:
        import pyfftw, scipy, scipy.signal
        power.array_empty = pyfftw.empty_aligned
        power.array_zeros = pyfftw.zeros_aligned
        scipy.fftpack = pyfftw.interfaces.scipy_fftpack
        scipy.signal.spectral.fftpack = pyfftw.interfaces.scipy_fftpack
        pyfftw.interfaces.cache.enable()
        pyfftw.interfaces.cache.set_keepalive_time(3600)
    except ImportError:
        logger.warning('pyfftw is not available, using scipy.fftpack instead')


def float_with_multiplier(string):
    """Convert string with optional k, M, G, T multiplier to float"""
    match = re_float_with_multiplier.search(string)
    if not match or not match.group('num'):
        raise ValueError('String "{}" is not numeric!'.format(string))

    num = float(match.group('num'))
    multi = match.group('multi')
    if multi:
        try:
            num *= multipliers[multi]
        except KeyError:
            raise ValueError('Unknown multiplier: {}'.format(multi))
    return num


def freq_or_freq_range(string):
    """Convert string with freq. or freq. range to list of floats"""
    return [float_with_multiplier(f) for f in string.split(':')]


def setup_argument_parser():
    """Setup command line parser"""
    parser = argparse.ArgumentParser(
        prog='soapy_power',
        description='obtain a power spectrum from SoapySDR devices'
    )

    parser.add_argument('-f', '--freq', metavar='Hz|Hz:Hz', type=freq_or_freq_range, default='1420405752',
                        help='center frequency or frequency range to scan, number '
                             'can be followed by a k, M or G multiplier (default: %(default)s)')

    bins_group = parser.add_mutually_exclusive_group()
    bins_group.add_argument('-b', '--bins', type=int, default=512,
                            help='number of FFT bins (incompatible with -B, default: %(default)s)')
    bins_group.add_argument('-B', '--bin-size', metavar='Hz', type=float_with_multiplier,
                            help='bin size in Hz (incompatible with -b)')

    spectra_group = parser.add_mutually_exclusive_group()
    spectra_group.add_argument('-n', '--repeats', type=int, default=1600,
                               help='number of spectra to average (incompatible with -t and -T, default: %(default)s)')
    spectra_group.add_argument('-t', '--time', metavar='SECONDS', type=float,
                               help='integration time (incompatible with -T and -n)')
    spectra_group.add_argument('-T', '--total-time', metavar='SECONDS', type=float,
                               help='total integration time of all hops (incompatible with -t and -n)')

    parser.add_argument('-d', '--device', default='',
                        help='SoapySDR device to use')
    parser.add_argument('-r', '--rate', metavar='Hz', type=float_with_multiplier, default=2e6,
                        help='sample rate (default: %(default)s)')
    parser.add_argument('-p', '--ppm', type=int, default=0,
                        help='frequency correction in ppm')

    crop_group = parser.add_mutually_exclusive_group()
    crop_group.add_argument('-o', '--overlap', metavar='PERCENT', type=float, default=0,
                            help='percent of overlap when frequency hopping (incompatible with -k)')
    crop_group.add_argument('-k', '--crop', metavar='PERCENT', type=float, default=0,
                            help='percent of crop when frequency hopping (incompatible with -o)')

    runs_group = parser.add_mutually_exclusive_group()
    runs_group.add_argument('-c', '--continue', dest='endless', action='store_true',
                            help='repeat the measurement endlessly (incompatible with -u)')
    runs_group.add_argument('-u', '--runs', type=int, default=1,
                            help='number of measurements (incompatible with -c, default: %(default)s)')
    runs_group.add_argument('-e', '--elapsed', metavar='SECONDS', type=float,
                            help='scan session duration (time limit in seconds, incompatible with -c and -u)')

    gain_group = parser.add_mutually_exclusive_group()
    gain_group.add_argument('-g', '--gain', metavar='1/10th of dB', type=int, default=372,
                            help='gain, expressed in tenths of a decibel, e.g. 207 means 20.7 dB '
                                 '(incompatible with -a, default: %(default)s)')
    gain_group.add_argument('-a', '--agc', action='store_true',
                            help='enable Automatic Gain Control (incompatible with -g)')

    parser.add_argument('-l', '--linear', action='store_true',
                        help='linear power values instead of logarithmic')
    parser.add_argument('-s', '--buffer-size', type=int, default=0,
                        help='base buffer size (number of samples, 0 = auto, default: %(default)s)')
    parser.add_argument('-S', '--max-buffer-size', type=int, default=0,
                        help='maximum buffer size (number of samples, -1 = unlimited, 0 = auto, default: %(default)s)')
    parser.add_argument('-O', '--output', metavar='FILE', type=argparse.FileType('w'), default=sys.stdout,
                        help='output to file (default is stdout)')
    parser.add_argument('-F', '--format', choices=['rtl_power', 'rtl_power_fftw'], default='rtl_power_fftw',
                        help='output format (default: %(default)s)')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='limit verbosity')
    parser.add_argument('--debug', action='store_true',
                        help='detailed debugging messages')
    parser.add_argument('--detect', action='store_true',
                        help='detect connected SoapySDR devices and exit')

    fft_rules_group = parser.add_mutually_exclusive_group()
    fft_rules_group.add_argument('--even', action='store_true',
                                 help='use only even numbers of FFT bins')
    fft_rules_group.add_argument('--pow2', action='store_true',
                                 help='use only powers of 2 as number of FFT bins')

    parser.add_argument('--pyfftw', action='store_true',
                        help='use pyfftw library instead of scipy.fftpack (should be faster)')
    parser.add_argument('--tune-delay', metavar='SECONDS', type=float, default=0,
                        help='time to delay measurement after changing frequency')

    parser.add_argument('--version', action='version',
                        version='%(prog)s {}'.format(__version__))

    return parser


def main():
    # Parse command line arguments
    parser = setup_argument_parser()
    args = parser.parse_args()

    # Setup logging
    if args.quiet:
        log_level = logging.WARNING
    elif args.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(levelname)s: %(message)s'
    )

    # Detect SoapySDR devices
    if args.detect:
        devices = simplesoapy.detect_devices()
        if not devices:
            parser.error('No SoapySDR devices detected!')

        logger.info('Detected SoapySDR devices:')
        for i, d in enumerate(devices):
            logger.info('  {} ... driver={}, label={}'.format(i + 1, d['driver'], d['label']))
        sys.exit(0)

    # Prepare arguments for SoapyPower
    if args.pyfftw:
        use_pyfftw()

    if args.gain:
        args.gain /= 10

    # Create SoapyPower instance
    sdr = power.SoapyPower(
        soapy_args=args.device, sample_rate=args.rate, corr=args.ppm,
        gain=args.gain, auto_gain=args.agc, output=args.output, output_format=args.format
    )
    logger.info('Using device: {}'.format(sdr.device.hardware))

    # Prepare arguments for SoapyPower.sweep()
    if len(args.freq) < 2:
        args.freq = [args.freq[0], args.freq[0]]

    if args.bin_size:
        args.bins = sdr.bin_size_to_bins(args.bin_size)

    args.bins = sdr.nearest_bins(args.bins, even=args.even, pow2=args.pow2)

    if args.total_time:
        args.time = args.total_time / len(sdr.freq_plan(args.freq[0], args.freq[1], args.bins, args.overlap))

    if args.time:
        args.repeats = sdr.time_to_repeats(args.bins, args.time)

    if args.endless:
        args.runs = 0

    if args.elapsed:
        args.runs = 0

    if args.crop:
        args.overlap = args.crop
        args.crop = True
    else:
        args.crop = False

    if args.overlap:
        args.overlap /= 100
        args.overlap = sdr.nearest_overlap(args.overlap, args.bins)

    # Start frequency sweep
    sdr.sweep(
        args.freq[0], args.freq[1], args.bins, args.repeats,
        runs=args.runs, time_limit=args.elapsed, overlap=args.overlap,
        crop=args.crop, log_scale=not args.linear, tune_delay=args.tune_delay,
        base_buffer_size=args.buffer_size, max_buffer_size=args.max_buffer_size
    )


if __name__ == '__main__':
    main()
