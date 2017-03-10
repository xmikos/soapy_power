#!/usr/bin/env python3

import os, sys, logging, argparse, re, shutil

import simplesoapy
from soapypower import power, writer
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


def detect_devices():
    devices = simplesoapy.detect_devices()
    text = []
    text.append('Detected SoapySDR devices:')
    if devices:
        for i, d in enumerate(devices):
            text.append('  device_id={}, driver={}, label={}'.format(i, d['driver'], d['label']))
    else:
        text.append('  No devices found')
    return (devices, '\n'.join(text))


def setup_argument_parser():
    """Setup command line parser"""
    # Fix help formatter width
    if 'COLUMNS' not in os.environ:
        os.environ['COLUMNS'] = str(shutil.get_terminal_size().columns)

    parser = argparse.ArgumentParser(
        prog='soapy_power',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Obtain a power spectrum from SoapySDR devices',
        epilog=detect_devices()[1],
        add_help=False
    )

    main_title = parser.add_argument_group('Main options')
    main_title.add_argument('-h', '--help', action='help',
                            help='show this help message and exit')
    main_title.add_argument('-f', '--freq', metavar='Hz|Hz:Hz', type=freq_or_freq_range, default='1420405752',
                            help='center frequency or frequency range to scan, number '
                            'can be followed by a k, M or G multiplier (default: %(default)s)')
    main_title.add_argument('-O', '--output', metavar='FILE', type=argparse.FileType('w'), default=sys.stdout,
                            help='output to file (default is stdout)')
    main_title.add_argument('-F', '--format', choices=sorted(writer.formats.keys()), default='rtl_power',
                            help='output format (default: %(default)s)')
    main_title.add_argument('-q', '--quiet', action='store_true',
                            help='limit verbosity')
    main_title.add_argument('--debug', action='store_true',
                            help='detailed debugging messages')
    main_title.add_argument('--detect', action='store_true',
                            help='detect connected SoapySDR devices and exit')
    main_title.add_argument('--version', action='version',
                            version='%(prog)s {}'.format(__version__))

    bins_title = parser.add_argument_group('FFT bins')
    bins_group = bins_title.add_mutually_exclusive_group()
    bins_group.add_argument('-b', '--bins', type=int, default=512,
                            help='number of FFT bins (incompatible with -B, default: %(default)s)')
    bins_group.add_argument('-B', '--bin-size', metavar='Hz', type=float_with_multiplier,
                            help='bin size in Hz (incompatible with -b)')

    spectra_title = parser.add_argument_group('Averaging')
    spectra_group = spectra_title.add_mutually_exclusive_group()
    spectra_group.add_argument('-n', '--repeats', type=int, default=1600,
                               help='number of spectra to average (incompatible with -t and -T, default: %(default)s)')
    spectra_group.add_argument('-t', '--time', metavar='SECONDS', type=float,
                               help='integration time (incompatible with -T and -n)')
    spectra_group.add_argument('-T', '--total-time', metavar='SECONDS', type=float,
                               help='total integration time of all hops (incompatible with -t and -n)')

    runs_title = parser.add_argument_group('Measurements')
    runs_group = runs_title.add_mutually_exclusive_group()
    runs_group.add_argument('-c', '--continue', dest='endless', action='store_true',
                            help='repeat the measurement endlessly (incompatible with -u and -e)')
    runs_group.add_argument('-u', '--runs', type=int, default=1,
                            help='number of measurements (incompatible with -c and -e, default: %(default)s)')
    runs_group.add_argument('-e', '--elapsed', metavar='SECONDS', type=float,
                            help='scan session duration (time limit in seconds, incompatible with -c and -u)')

    device_title = parser.add_argument_group('Device settings')
    device_title.add_argument('-d', '--device', default='',
                              help='SoapySDR device to use')
    device_title.add_argument('-C', '--channel', type=int, default=0,
                              help='SoapySDR RX channel (default: %(default)s)')
    device_title.add_argument('-A', '--antenna', default='',
                              help='SoapySDR selected antenna')
    device_title.add_argument('-r', '--rate', metavar='Hz', type=float_with_multiplier, default=2e6,
                              help='sample rate (default: %(default)s)')
    device_title.add_argument('-w', '--bandwidth', metavar='Hz', type=float_with_multiplier, default=0,
                              help='filter bandwidth (default: %(default)s)')
    device_title.add_argument('-p', '--ppm', type=int, default=0,
                              help='frequency correction in ppm')

    gain_group = device_title.add_mutually_exclusive_group()
    gain_group.add_argument('-g', '--gain', metavar='1/10th of dB', type=int, default=372,
                            help='gain, expressed in tenths of a decibel, e.g. 207 means 20.7 dB '
                                 '(incompatible with -a, default: %(default)s)')
    gain_group.add_argument('-a', '--agc', action='store_true',
                            help='enable Automatic Gain Control (incompatible with -g)')

    device_title.add_argument('--force-rate', action='store_true',
                              help='ignore list of sample rates provided by device and allow any value')
    device_title.add_argument('--force-bandwidth', action='store_true',
                              help='ignore list of filter bandwidths provided by device and allow any value')
    device_title.add_argument('--tune-delay', metavar='SECONDS', type=float, default=0,
                              help='time to delay measurement after changing frequency')

    crop_title = parser.add_argument_group('Crop')
    crop_group = crop_title.add_mutually_exclusive_group()
    crop_group.add_argument('-o', '--overlap', metavar='PERCENT', type=float, default=0,
                            help='percent of overlap when frequency hopping (incompatible with -k)')
    crop_group.add_argument('-k', '--crop', metavar='PERCENT', type=float, default=0,
                            help='percent of crop when frequency hopping (incompatible with -o)')

    perf_title = parser.add_argument_group('Performance options')
    perf_title.add_argument('-s', '--buffer-size', type=int, default=0,
                            help='base buffer size (number of samples, 0 = auto, default: %(default)s)')
    perf_title.add_argument('-S', '--max-buffer-size', type=int, default=0,
                            help='maximum buffer size (number of samples, -1 = unlimited, 0 = auto, default: %(default)s)')

    fft_rules_group = perf_title.add_mutually_exclusive_group()
    fft_rules_group.add_argument('--even', action='store_true',
                                 help='use only even numbers of FFT bins')
    fft_rules_group.add_argument('--pow2', action='store_true',
                                 help='use only powers of 2 as number of FFT bins')

    perf_title.add_argument('--pyfftw', action='store_true',
                            help='use pyfftw library instead of scipy.fftpack (should be faster)')
    perf_title.add_argument('--max-threads', metavar='NUM', type=int, default=0,
                            help='maximum number of FFT threads (0 = auto, default: %(default)s)')
    perf_title.add_argument('--max-queue-size', metavar='NUM', type=int, default=0,
                            help='maximum size of FFT work queue (-1 = unlimited, 0 = auto, default: %(default)s)')

    other_title = parser.add_argument_group('Other options')
    other_title.add_argument('-l', '--linear', action='store_true',
                             help='linear power values instead of logarithmic')
    other_title.add_argument('-R', '--remove-dc', action='store_true',
                             help='interpolate central point to cancel DC bias (useful only with boxcar window)')
    other_title.add_argument('-D', '--detrend', choices=['no', 'constant', 'linear'], default='no',
                             help='remove mean value or linear trend from data (default: %(default)s)')
    other_title.add_argument('--fft-window', choices=['boxcar', 'hann', 'hamming', 'triang', 'blackman', 'bartlett',
                                                      'flattop', 'parzen', 'bohman', 'blackmanharris', 'nuttall', 'barthann'],
                             default='hann', help='Welch\'s method window function (default: %(default)s)')
    other_title.add_argument('--fft-overlap', metavar='PERCENT', type=float, default=50,
                             help='Welch\'s method overlap between segments (default: %(default)s)')

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
        devices, devices_text = detect_devices()
        print(devices_text)
        sys.exit(0 if devices else 1)

    # Prepare arguments for SoapyPower
    if args.pyfftw:
        use_pyfftw()

    if args.gain:
        args.gain /= 10

    # Create SoapyPower instance
    sdr = power.SoapyPower(
        soapy_args=args.device, sample_rate=args.rate, bandwidth=args.bandwidth, corr=args.ppm,
        gain=args.gain, auto_gain=args.agc, channel=args.channel, antenna=args.antenna,
        force_sample_rate=args.force_rate, force_bandwidth=args.force_bandwidth,
        output=args.output, output_format=args.format
    )
    logger.info('Using device: {}'.format(sdr.device.hardware))

    # Prepare arguments for SoapyPower.sweep()
    if len(args.freq) < 2:
        args.freq = [args.freq[0], args.freq[0]]

    if args.bin_size:
        args.bins = sdr.bin_size_to_bins(args.bin_size)

    args.bins = sdr.nearest_bins(args.bins, even=args.even, pow2=args.pow2)

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

    if args.total_time:
        args.time = args.total_time / len(sdr.freq_plan(args.freq[0], args.freq[1], args.bins, args.overlap, quiet=True))

    if args.time:
        args.repeats = sdr.time_to_repeats(args.bins, args.time)

    # Start frequency sweep
    sdr.sweep(
        args.freq[0], args.freq[1], args.bins, args.repeats,
        runs=args.runs, time_limit=args.elapsed, overlap=args.overlap, crop=args.crop,
        fft_window=args.fft_window, fft_overlap=args.fft_overlap / 100, log_scale=not args.linear,
        remove_dc=args.remove_dc, detrend=args.detrend if args.detrend != 'no' else None,
        tune_delay=args.tune_delay, base_buffer_size=args.buffer_size, max_buffer_size=args.max_buffer_size,
        max_threads=args.max_threads, max_queue_size=args.max_queue_size
    )


if __name__ == '__main__':
    main()
