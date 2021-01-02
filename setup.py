#!/usr/bin/env python3
# -*- coding: utf-8 -*-
##########################################################################
# hostp2pd - The Wi-Fi Direct Session Manager
# wpa_cli controller of Wi-Fi Direct connections handled by wpa_supplicant
# https://github.com/Ircama/hostp2pd
# (C) Ircama 2021 - CC-BY-NC-SA-4.0
#########################################################################

from setuptools import setup, find_packages
from hostp2pd.__version__ import __version__

with open("README.md", "r") as readme:
    long_description = readme.read()

setup(
    name="hostp2pd",
    version=__version__,
    description=("Wi-Fi Direct Session Manager, implementing a host AP daemon in Wi-Fi Direct mode, including P2P WPS enrollment"),
    long_description=long_description[:long_description.find('# Connecting')],
    long_description_content_type="text/markdown",
    classifiers=[
        "Operating System :: POSIX :: Linux",
        "License :: Creative Commons Creative Commons Attribution Non Commercial Share Alike 4.0 International (CC-BY-NC-SA-4.0)"
        "Topic :: Communications",
        "Topic :: Software Development :: Libraries :: Python Modules"
        'Programming Language :: Python :: 3 :: Only',
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Telecommunications Industry",
        "Intended Audience :: Developers",
    ],
    keywords="wi-fi-direct p2p wpa-supplicant wpa-cli",
    author="Ircama",
    url="https://github.com/Ircama/hostp2pd",
    license='CC-BY-NC-SA-4.0',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'python-daemon',
        'pyyaml'
    ],
)