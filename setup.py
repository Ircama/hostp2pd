#!/usr/bin/env python3
# -*- coding: utf-8 -*-
##########################################################################
# hostp2pd - The Wi-Fi Direct Session Manager
# wpa_cli controller of Wi-Fi Direct connections handled by wpa_supplicant
# https://github.com/Ircama/hostp2pd
# (C) Ircama 2021 - CC-BY-NC-SA-4.0
#########################################################################

from setuptools import setup, find_packages
import re
import os

import json
import sys
from urllib import request
from pkg_resources import parse_version

def versions_pypi(pkg_name):
    url = f'https://pypi.python.org/pypi/{pkg_name}/json'
    releases = json.loads(request.urlopen(url).read())['releases']
    return sorted(releases, key=parse_version, reverse=True)

def versions_testpypi(pkg_name):
    url = f'https://testpypi.python.org/pypi/{pkg_name}/json'
    releases = json.loads(request.urlopen(url).read())['releases']
    return sorted(releases, key=parse_version, reverse=True)

with open("README.md", "r") as readme:
    long_description = readme.read()

epilogue = '''

Full information and usage details at the [hostp2pd GitHub repository](https://github.com/Ircama/hostp2pd).

'''

PROGRAM_NAME = "hostp2pd"
VERSIONFILE = PROGRAM_NAME + "/__version__.py"

build = ''
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))

if os.environ.get('GITHUB_RUN_NUMBER') is not None:
    version_list_pypi = [
        a for a in versions_pypi(PROGRAM_NAME) if a.startswith(verstr)]
    version_list_testpypi = [
        a for a in versions_testpypi(PROGRAM_NAME) if a.startswith(verstr)]
    if version_list_pypi or version_list_testpypi:
        print("-------------------------------------------------------------------------")
        print(f"Using build number {os.environ['GITHUB_RUN_NUMBER']}")
        if version_list_pypi:
            print(f"Version list available in pypi {version_list_pypi}")
        if version_list_testpypi:
            print(f"Version list available in testpypi {version_list_testpypi}")
        print("-------------------------------------------------------------------------")
        verstr += '-' + os.environ['GITHUB_RUN_NUMBER']

setup(
    name=PROGRAM_NAME,
    version=verstr,
    description=("Wi-Fi Direct Session Manager, implementing a host AP daemon in Wi-Fi Direct mode, including P2P WPS enrollment"),
    long_description=long_description[:long_description.find('# Connecting')] + epilogue,
    long_description_content_type="text/markdown",
    classifiers=[
        "Operating System :: POSIX :: Linux",
        "License :: Other/Proprietary License",
        "Topic :: Communications",
        "Topic :: Software Development :: Libraries :: Python Modules",
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
    entry_points={'console_scripts': [
        'hostp2pd = hostp2pd:main',
    ]},
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'python-daemon',
        'pyyaml'
    ],
)
