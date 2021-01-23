#!/usr/bin/env python3
# -*- coding: utf-8 -*-
##########################################################################
# hostp2pd - The Wi-Fi Direct Session Manager
# wpa_cli controller of Wi-Fi Direct connections handled by wpa_supplicant
# https://github.com/Ircama/hostp2pd
# (C) Ircama 2021 - CC-BY-NC-SA-4.0
#########################################################################

import sys
try:
    from .interpreter import main
except (ImportError, ValueError):
    print("hostp2pd must be run as a module. E.g., python3 -m hostp2pd")
    sys.exit(1)

if __name__ == "__main__":
    main()
