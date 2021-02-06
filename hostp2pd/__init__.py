#!/usr/bin/env python3
# -*- coding: utf-8 -*-
##########################################################################
# hostp2pd - The Wi-Fi Direct Session Manager
# wpa_cli controller of Wi-Fi Direct connections handled by wpa_supplicant
# https://github.com/Ircama/hostp2pd
# (C) Ircama 2021 - CC-BY-NC-SA-4.0
##########################################################################

from __future__ import print_function
import sys
if sys.hexversion < 0x3050000:
    print("hostp2pd error: Python version must be >= 3.5."
          " Current version: " + ".".join(
              map(str, sys.version_info[:3])) + ".")
    sys.exit(1)

from .hostp2pd import HostP2pD
from .interpreter import main
