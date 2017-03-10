#!/usr/bin/env python

from setuptools import setup
from soapypower.version import __version__

setup(
    name='soapy_power',
    version=__version__,
    description='Obtain power spectrum from SoapySDR devices (RTL-SDR, Airspy, SDRplay, HackRF, bladeRF, USRP, LimeSDR, etc.)',
    long_description=open('README.rst').read(),
    author='Michal Krenek (Mikos)',
    author_email='m.krenek@gmail.com',
    url='https://github.com/xmikos/soapy_power',
    license='MIT',
    packages=['soapypower'],
    entry_points={
        'console_scripts': [
            'soapy_power=soapypower.__main__:main'
        ],
    },
    install_requires=[
        'simplesoapy'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Communications :: Ham Radio',
        'Topic :: Utilities'
    ]
)
