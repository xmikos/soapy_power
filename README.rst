soapy_power
===========

Obtain power spectrum from SoapySDR devices (RTL-SDR, Airspy, SDRplay, HackRF, bladeRF, USRP, LimeSDR, etc.)

Requirements
------------

- `Python 3 <https://www.python.org>`_
- `NumPy <http://www.numpy.org>`_
- `SimpleSoapy <https://github.com/xmikos/simplesoapy>`_
- `SimpleSpectral <https://github.com/xmikos/simplespectral>`_
- Optional: `pyFFTW <https://github.com/pyFFTW/pyFFTW>`_ (for fastest FFT calculations with FFTW library)
- Optional: `SciPy <https://www.scipy.org>`_ (for faster FFT calculations with scipy.fftpack library)

You should always install SciPy or pyFFTW, because numpy.fft has horrible
memory usage and is also much slower.

Usage
-----
::

    usage: soapy_power [-h] [-f Hz|Hz:Hz] [-O FILE | --output-fd NUM] [-F {rtl_power,rtl_power_fftw,soapy_power_bin}] [-q]
                       [--debug] [--detect] [--info] [--version] [-b BINS | -B Hz] [-n REPEATS | -t SECONDS | -T SECONDS]
                       [-c | -u RUNS | -e SECONDS] [-d DEVICE] [-C CHANNEL] [-A ANTENNA] [-r Hz] [-w Hz] [-p PPM]
                       [-g dB | -G STRING | -a] [--lnb-lo Hz] [--device-settings STRING] [--force-rate] [--force-bandwidth]
                       [--tune-delay SECONDS] [--reset-stream] [-o PERCENT | -k PERCENT] [-s BUFFER_SIZE] [-S MAX_BUFFER_SIZE]
                       [--even | --pow2] [--max-threads NUM] [--max-queue-size NUM] [--no-pyfftw] [-l] [-R]
                       [-D {none,constant}] [--fft-window {boxcar,hann,hamming,blackman,bartlett,kaiser,tukey}]
                       [--fft-window-param FLOAT] [--fft-overlap PERCENT]
    
    Obtain a power spectrum from SoapySDR devices
    
    Main options:
      -h, --help            show this help message and exit
      -f Hz|Hz:Hz, --freq Hz|Hz:Hz
                            center frequency or frequency range to scan, number can be followed by a k, M or G multiplier
                            (default: 1420405752)
      -O FILE, --output FILE
                            output to file (incompatible with --output-fd, default is stdout)
      --output-fd NUM       output to existing file descriptor (incompatible with -O)
      -F {rtl_power,rtl_power_fftw,soapy_power_bin}, --format {rtl_power,rtl_power_fftw,soapy_power_bin}
                            output format (default: rtl_power)
      -q, --quiet           limit verbosity
      --debug               detailed debugging messages
      --detect              detect connected SoapySDR devices and exit
      --info                show info about selected SoapySDR device and exit
      --version             show program's version number and exit
    
    FFT bins:
      -b BINS, --bins BINS  number of FFT bins (incompatible with -B, default: 512)
      -B Hz, --bin-size Hz  bin size in Hz (incompatible with -b)
    
    Averaging:
      -n REPEATS, --repeats REPEATS
                            number of spectra to average (incompatible with -t and -T, default: 1600)
      -t SECONDS, --time SECONDS
                            integration time (incompatible with -T and -n)
      -T SECONDS, --total-time SECONDS
                            total integration time of all hops (incompatible with -t and -n)
    
    Measurements:
      -c, --continue        repeat the measurement endlessly (incompatible with -u and -e)
      -u RUNS, --runs RUNS  number of measurements (incompatible with -c and -e, default: 1)
      -e SECONDS, --elapsed SECONDS
                            scan session duration (time limit in seconds, incompatible with -c and -u)
    
    Device settings:
      -d DEVICE, --device DEVICE
                            SoapySDR device to use
      -C CHANNEL, --channel CHANNEL
                            SoapySDR RX channel (default: 0)
      -A ANTENNA, --antenna ANTENNA
                            SoapySDR selected antenna
      -r Hz, --rate Hz      sample rate (default: 2000000.0)
      -w Hz, --bandwidth Hz
                            filter bandwidth (default: 0)
      -p PPM, --ppm PPM     frequency correction in ppm
      -g dB, --gain dB      total gain (incompatible with -G and -a, default: 37.2)
      -G STRING, --specific-gains STRING
                            specific gains of individual amplification elements (incompatible with -g and -a, example:
                            LNA=28,VGA=12,AMP=0
      -a, --agc             enable Automatic Gain Control (incompatible with -g and -G)
      --lnb-lo Hz           LNB LO frequency, negative for upconverters (default: 0)
      --device-settings STRING
                            SoapySDR device settings (example: biastee=true)
      --force-rate          ignore list of sample rates provided by device and allow any value
      --force-bandwidth     ignore list of filter bandwidths provided by device and allow any value
      --tune-delay SECONDS  time to delay measurement after changing frequency (to avoid artifacts)
      --reset-stream        reset streaming after changing frequency (to avoid artifacts)
    
    Crop:
      -o PERCENT, --overlap PERCENT
                            percent of overlap when frequency hopping (incompatible with -k)
      -k PERCENT, --crop PERCENT
                            percent of crop when frequency hopping (incompatible with -o)
    
    Performance options:
      -s BUFFER_SIZE, --buffer-size BUFFER_SIZE
                            base buffer size (number of samples, 0 = auto, default: 0)
      -S MAX_BUFFER_SIZE, --max-buffer-size MAX_BUFFER_SIZE
                            maximum buffer size (number of samples, -1 = unlimited, 0 = auto, default: 0)
      --even                use only even numbers of FFT bins
      --pow2                use only powers of 2 as number of FFT bins
      --max-threads NUM     maximum number of PSD threads (0 = auto, default: 0)
      --max-queue-size NUM  maximum size of PSD work queue (-1 = unlimited, 0 = auto, default: 0)
      --no-pyfftw           don't use pyfftw library even if it is available (use scipy.fftpack or numpy.fft)
    
    Other options:
      -l, --linear          linear power values instead of logarithmic
      -R, --remove-dc       interpolate central point to cancel DC bias (useful only with boxcar window)
      -D {none,constant}, --detrend {none,constant}
                            remove mean value from data to cancel DC bias (default: none)
      --fft-window {boxcar,hann,hamming,blackman,bartlett,kaiser,tukey}
                            Welch's method window function (default: hann)
      --fft-window-param FLOAT
                            shape parameter of window function (required for kaiser and tukey windows)
      --fft-overlap PERCENT
                            Welch's method overlap between segments (default: 50)

Example
-------
::

    [user@host ~] soapy_power -r 2.56M -f 88M:98M -B 500k -F rtl_power -O output.txt --even -T 1 --debug
    DEBUG: pyfftw module found (using 4 threads by default)
    DEBUG: Applying fixes for RTLSDR quirks...
    INFO: Using device: RTLSDR
    DEBUG: SoapySDR stream - buffer size: 8192
    DEBUG: SoapySDR stream - read timeout: 0.103200
    INFO: repeats: 106667
    INFO: samples: 640002 (time: 0.25000 s)
    INFO: max_buffer_size (samples): 32768000 (repeats: 5461333.33, time: 12.80000 s)
    INFO: buffer_size (samples): 647168 (repeats: 107861.33, time: 0.25280 s)
    INFO: buffer_repeats: 1
    INFO: overlap: 0.00000
    INFO: bin_size: 426666.67 Hz
    INFO: bins: 6
    INFO: bins (after crop): 6
    INFO: sample_rate: 2.560 MHz
    INFO: sample_rate (after crop): 2.560 MHz
    INFO: freq_range: 10.000 MHz
    INFO: hopping: YES
    INFO: hop_size: 2.560 MHz
    INFO: hops: 4
    INFO: min_center_freq: 89.280 MHz
    INFO: max_center_freq: 96.960 MHz
    INFO: min_freq (after crop): 88.000 MHz
    INFO: max_freq (after crop): 98.240 MHz
    DEBUG: Frequency hops table:
    DEBUG:   Min:          Center:       Max:    
    DEBUG:     88.000 MHz    89.280 MHz    90.560 MHz
    DEBUG:     90.560 MHz    91.840 MHz    93.120 MHz
    DEBUG:     93.120 MHz    94.400 MHz    95.680 MHz
    DEBUG:     95.680 MHz    96.960 MHz    98.240 MHz
    DEBUG: Run: 1
    DEBUG:   Frequency hop: 89280000.00 Hz
    DEBUG:     Tune time: 0.017 s
    DEBUG:     Repeat: 1
    DEBUG:       Acquisition time: 0.251 s
    DEBUG:     Total hop time: 0.282 s
    DEBUG: FFT time: 0.103 s
    DEBUG:   Frequency hop: 91840000.00 Hz
    DEBUG:     Tune time: 0.010 s
    DEBUG:     Repeat: 1
    DEBUG:       Acquisition time: 0.251 s
    DEBUG:     Total hop time: 0.272 s
    DEBUG: FFT time: 0.006 s
    DEBUG:   Frequency hop: 94400000.00 Hz
    DEBUG:     Tune time: 0.010 s
    DEBUG:     Repeat: 1
    DEBUG:       Acquisition time: 0.252 s
    DEBUG:     Total hop time: 0.266 s
    DEBUG: FFT time: 0.004 s
    DEBUG:   Frequency hop: 96960000.00 Hz
    DEBUG:     Tune time: 0.010 s
    DEBUG:     Repeat: 1
    DEBUG:       Acquisition time: 0.253 s
    DEBUG:     Total hop time: 0.267 s
    DEBUG: FFT time: 0.004 s
    DEBUG:   Total run time: 1.095 s
    DEBUG: Number of USB buffer overflow errors: 0
    DEBUG: PSD worker threads: 4
    DEBUG: Max. PSD queue size: 2 / 40
    DEBUG: Writer worker threads: 1
    DEBUG: Max. Writer queue size: 2 / 100
    INFO: Total time: 1.137 s

Output::

    2017-03-17, 13:18:25, 88000000.0, 90560000.0, 426666.666667, 647168, -98.6323, -98.7576, -97.3716, -98.3133, -98.8829, -98.9333
    2017-03-17, 13:18:25, 90560000.0, 93120000.0, 426666.666667, 647168, -95.7163, -96.2564, -97.01, -98.1281, -90.701, -88.0872
    2017-03-17, 13:18:25, 93120000.0, 95680000.0, 426666.666667, 647168, -99.0242, -91.3061, -91.9134, -85.4561, -86.0053, -97.8411
    2017-03-17, 13:18:26, 95680000.0, 98240000.0, 426666.666667, 647168, -94.2324, -83.7932, -78.3108, -82.033, -89.1212, -97.4499
