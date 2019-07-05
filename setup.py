#!/usr/bin/env python

from setuptools import find_packages, setup


required = [
    "picamera==1.13",
    "numpy==1.16.2",
    "opencv-contrib-python==3.4.4.19",
    "pyserial==3.4",
    "pytesseract",
    "RPi.GPIO",

    "Keras==2.2.4",
    "Keras-Applications==1.0.7",
    "Keras-Preprocessing==1.0.9",
    "tensorflow==1.13.1",
    "tensorflow-estimator==1.13.0"
]


setup(
    name="hns",
    version="1.0.0",
    description="PREN - 2/4 HNS",
    author="Team 10",
    packages=find_packages(),
    install_requires=required,
    license="MIT",
    classifiers=(
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation',
        'Programming Language :: Python :: Implementation :: CPython',
    )
)
