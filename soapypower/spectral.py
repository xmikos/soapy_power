#!/usr/bin/env python
"""Heavily simplified scipy.signal.spectral module which only depends on numpy"""

import numpy


### Window functions ###
def window_boxcar(M):
    """Return a boxcar window, also known as a rectangular window"""
    return numpy.ones(M, float)


def window_tukey(M, alpha=0.5):
    """Return a Tukey window, also known as a tapered cosine window.
    The function returns a Hann window for `alpha=0` and a boxcar window for `alpha=1`
    """
    if alpha == 0:
        return numpy.hann(M)
    elif alpha == 1:
        return window_boxcar(M)

    n = numpy.arange(0, M)
    width = int(numpy.floor(alpha * (M - 1) / 2.0))
    n1 = n[0:width + 1]
    n2 = n[width + 1:M - width - 1]
    n3 = n[M - width - 1:]
    w1 = 0.5 * (1 + numpy.cos(numpy.pi * (-1 + 2.0 * n1 / alpha / (M - 1))))
    w2 = numpy.ones(n2.shape)
    w3 = 0.5 * (1 + numpy.cos(numpy.pi * (-2.0 / alpha + 1 + 2.0 * n3 / alpha / (M - 1))))

    return numpy.concatenate((w1, w2, w3))


windows = {
    'boxcar': window_boxcar,
    'tukey': window_tukey,
    'hann': numpy.hanning,
    'hamming': numpy.hamming,
    'bartlett': numpy.bartlett,
    'blackman': numpy.blackman,
    'kaiser': numpy.kaiser
}


def get_window(window, Nx, fftbins=True):
    """Return a window
    (if fftbins=True, generates a periodic window, for use in spectral analysis)
    """
    if isinstance(window, tuple):
        winstr = window[0]
        args = window[1:]
    else:
        winstr = window
        args = []

    try:
        winfunc = windows[winstr]
    except KeyError:
        raise ValueError("Unknown window type.")

    odd = Nx % 2
    if fftbins and not odd:
        Nx = Nx + 1

    w = winfunc(Nx, *args)

    if fftbins and not odd:
        w = w[:-1]

    return w


### Boundary functions ###
boundaries = {
    'even': ('reflect', {'reflect_type': 'even'}),
    'odd': ('reflect', {'reflect_type': 'odd'}),
    'constant': ('edge', {}),
    'zeros': ('constant', {'constant_values': 0}),
}


def extend_boundaries(x, width, boundary):
    """Extend input signal at both ends"""
    try:
        pad_mode, pad_args = boundaries[boundary]
    except KeyError:
        raise ValueError('Unknown boundary extension mode.')

    return numpy.pad(x, width, pad_mode, **pad_args)


### Detrend functions ###
def detrend_constant(data, axis=-1):
    """Remove trend from data by subtracting mean of data"""
    ret = data - numpy.expand_dims(numpy.mean(data, axis), axis)
    return ret


detrend_types = {
    'constant': detrend_constant,
}


def get_detrend(type):
    """Return detrending function"""
    try:
        detrend_func = detrend_types[type]
    except KeyError:
        raise ValueError('Unknown detrend type.')

    return detrend_func


### Power spectral density estimation ###
def periodogram(x, fs, nperseg, window='boxcar', detrend='constant', scaling='density'):
    """Estimate power spectral density using a periodogram
       (same as Welch's method with zero overlap and same number of FFT bins as input samples)
    """
    if nperseg < len(x):
        x = x[:nperseg]
    elif nperseg > len(x):
        nperseg = len(x)

    return welch(x, fs, nperseg, window=window, noverlap=0, detrend=detrend, scaling=scaling)


def welch(x, fs, nperseg, window='hann', noverlap=None, detrend='constant', scaling='density'):
    """Estimate power spectral density using Welch's method"""
    if noverlap is None:
        noverlap = nperseg // 2

    freqs, time, Pxx = _spectral_helper(x, fs, nperseg, window=window, noverlap=noverlap,
                                        detrend=detrend, scaling=scaling, mode='psd')

    # Average over windows
    if len(Pxx.shape) >= 2 and Pxx.size > 0:
        if Pxx.shape[-1] > 1:
            Pxx = Pxx.mean(axis=-1)
        else:
            Pxx = numpy.reshape(Pxx, Pxx.shape[:-1])

    return freqs, Pxx.real


def spectrogram(x, fs, nperseg, window=('tukey', 0.25), noverlap=None, detrend='constant',
                scaling='density', mode='psd'):
    """Compute a spectrogram with consecutive Fourier transforms"""
    if noverlap is None:
        noverlap = nperseg // 8

    # Modes:
    #   'psd' uses Welch's method
    #   'complex' is equivalent to the output of `stft` with no padding or boundary extension
    #   'magnitude' returns the absolute magnitude of the STFT
    if mode == 'psd':
        freqs, time, Sxx = _spectral_helper(x, fs, nperseg, window=window, noverlap=noverlap,
                                            detrend=detrend, scaling=scaling, mode='psd')
    else:
        freqs, time, Sxx = _spectral_helper(x, fs, nperseg, window=window, noverlap=noverlap,
                                            detrend=detrend, scaling=scaling, mode='stft',
                                            boundary=None, padded=False)
        if mode == 'magnitude':
            Sxx = numpy.abs(Sxx)
        elif mode == 'complex':
            pass

    return freqs, time, Sxx


def stft(x, fs, nperseg, window='hann', noverlap=None, detrend=False, boundary='zeros', padded=True):
    """Compute the Short Time Fourier Transform (STFT)"""
    if noverlap is None:
        noverlap = nperseg // 2

    freqs, time, Zxx = _spectral_helper(x, fs, nperseg, window=window, noverlap=noverlap,
                                        detrend=detrend, scaling='spectrum', mode='stft',
                                        boundary=boundary, padded=padded)

    return freqs, time, Zxx


### Helper functions ###
def _spectral_helper(x, fs, nperseg, window='hann', noverlap=None, detrend='constant',
                     scaling='spectrum', mode='psd', boundary=None, padded=False):
    """Calculate various forms of windowed FFTs for STFT, PSD, etc."""
    if noverlap is None:
        noverlap = nperseg // 2

    nstep = nperseg - noverlap
    outdtype = numpy.result_type(x, numpy.complex64)
    win = get_window(window, nperseg)
    if numpy.result_type(win, numpy.complex64) != outdtype:
        win = win.astype(outdtype)

    # Extend input signal at both ends
    if boundary is not None:
        x = extend_boundaries(x, nperseg // 2, boundary)

    # Make the input signal zero-padded at the end to make the signal
    # fit exactly into an integer number of window segments
    if padded:
        nadd = (-(len(x) - nperseg) % nstep) % nperseg
        x = numpy.concatenate((x, numpy.zeros(nadd)), axis=-1)

    # Specify how to detrend each segment
    if not detrend:
        def detrend_func(d):
            return d
    elif not hasattr(detrend, '__call__'):
        detrend_func = get_detrend(detrend)
    else:
        detrend_func = detrend

    # Calculate windowed FFT
    freqs = numpy.fft.fftfreq(nperseg, 1 / fs)
    result = _fft_helper(x, win, detrend_func, nperseg, noverlap)

    if mode == 'psd':
        result = numpy.conjugate(result) * result

    # Scale result as the power spectral density ('density')
    # where `Pxx` has units of V**2/Hz or the power spectrum
    # ('spectrum') where `Pxx` has units of V**2
    if scaling == 'density':
        scale = 1.0 / (fs * (win * win).sum())
    elif scaling == 'spectrum':
        scale = 1.0 / win.sum()**2

    if mode == 'stft':
        scale = numpy.sqrt(scale)

    result *= scale
    result = result.astype(outdtype)

    # All imaginary parts are zero anyways
    if mode != 'stft':
        result = result.real

    # Create array of times corresponding to each data segment
    time = numpy.arange(nperseg / 2, x.shape[-1] - nperseg / 2 + 1, nperseg - noverlap) / float(fs)
    if boundary is not None:
        time -= (nperseg / 2) / fs

    # Make sure window/time index is last axis
    result = numpy.rollaxis(result, -1, -2)

    return freqs, time, result


def _fft_helper(x, win, detrend_func, nperseg, noverlap):
    """Calculate windowed FFT, for internal use by _spectral_helper"""
    step = nperseg - noverlap
    shape = ((len(x) - noverlap) // step, nperseg)
    strides = (step * x.strides[-1], x.strides[-1])
    result = numpy.lib.stride_tricks.as_strided(x, shape=shape, strides=strides)

    # Detrend each data segment individually
    result = detrend_func(result)

    # Apply window by multiplication
    result = win * result

    # Compute FFT
    # Note: numpy.fft.fft gives slightly different results than scipy.fftpack.fft,
    # maybe different precision? Anyway, difference is small and can be ignored.
    #result = scipy.fftpack.fft(result, n=nperseg)
    result = numpy.fft.fft(result, n=nperseg)

    return result
