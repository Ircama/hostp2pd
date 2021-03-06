#!/usr/bin/env python3
# -*- coding: utf-8 -*-
##########################################################################
# hostp2pd - The Wi-Fi Direct Session Manager
# wpa_cli controller of Wi-Fi Direct connections handled by wpa_supplicant
# https://github.com/Ircama/hostp2pd
# (C) Ircama 2021 - CC-BY-NC-SA-4.0
##########################################################################
import termios
import subprocess
import re
import logging
import logging.config
from pathlib import Path
import yaml
import threading
import time
import os
import pty
import errno
import sys
import traceback
import ctypes
import importlib.util
from ctypes.util import find_library
from select import select
import signal
from distutils.spawn import find_executable
from multiprocessing import Process, Manager
from .__version__ import __version__
from .pin import get_pin


class RedactingFormatter(object):
    """
    Logging formatter that masks sensitive data like secrets and passwords
    from logging.
    patterns = list of secrets to mask (check also hardcoded patterns)
    mask = string to substitute to secrets
    """

    def __init__(self, orig_formatter, patterns, mask):
        self.orig_formatter = orig_formatter
        self._patterns = patterns
        self._mask = mask

    def format(self, record):
        """
        Masked items:
        - psk password (hardcoded here)
        - psk "password" (hardcoded here)
        - passphrase=password
        - passphrase="password"
        - all items included in the "patterns" list
        """
        msg = self.orig_formatter.format(record)

        match = re.search(
            r'.*[ \t]+psk[ \t]+("?[^" \t\']*").*', msg, flags=re.DOTALL
        )
        if match:
            secret = match.expand("\\1")
            if secret and secret not in self._patterns:
                self._patterns.append(secret)
        match = re.search(
            r'.*[ \t]+passphrase=("?[^" \t\']*").*', msg, flags=re.DOTALL
        )
        if match:
            secret = match.expand("\\1")
            if secret and secret not in self._patterns:
                self._patterns.append(secret)

        for pattern in self._patterns:
            msg = msg.replace(pattern, self._mask)
        return msg

    def __getattr__(self, attr):
        return getattr(self.orig_formatter, attr)


def hide_from_logging(password_list, mask):
    """
    Loop to all root log handlers adding a formatter plugin to hide
    secrets and passwords from logging
    """
    root = logging.getLogger()
    if root and root.handlers:
        for h in root.handlers:
            h.setFormatter(
                RedactingFormatter(
                    h.formatter, patterns=password_list, mask=mask
                )
            )


def get_type(value, conf_schema):
    """
    Validate a YAML configuration (value) against a YAML schema (conf_schema)
    Internal rules:
    - all types include the possibility of <class 'NoneType'>
    - <class 'float'> includes <class 'int'>
    - <class 'open_dict'> means dictionary with unvalidated items
    """
    if isinstance(value, dict):
        if conf_schema == "<class 'open_dict'>":
            return conf_schema
        if conf_schema is None:
            return {key: get_type(value[key], conf_schema) for key in value}
        for key in value:
            if key not in conf_schema:
                logging.critical(
                    'Configuration Error: unknown parameter "%s" '
                    "in configuration file.",
                    key,
                )
                return None
        return {key: get_type(value[key], conf_schema[key])}
    else:
        ret_val = "<class 'int'>" if value is None else str(type(value))
        if ret_val == "<class 'int'>" and conf_schema == "<class 'float'>":
            ret_val = conf_schema
        if ret_val == "<class 'NoneType'>":
            ret_val = conf_schema
        if conf_schema is not None and conf_schema != ret_val:
            logging.critical(
                'Configuration Error: "%s" shall be "%s" and not "%s".',
                value,
                conf_schema,
                ret_val,
            )
            return None
        return ret_val


class HostP2pD:
    """
    hostp2pd class
    """

    ################# Start of static configuration ################################
    p2p_primary_device_type = {
        # From Wi-Fi Peer-to-Peer (P2P) Technical Specification,
        #   Annex B P2P Specific WSC IE Attributes,
        #   B.2 Primary Device Type,
        #   Table B1—Predefined values for Category ID and Sub Category ID,
        #   assuming that the Wi-Fi Alliance OUI will always be 00 50 F2 04.
        '1-0050F204-1': 'Computer PC',
        '1-0050F204-2': 'Computer Server',
        '1-0050F204-3': 'Media Center',
        '1-0050F204-4': 'Ultra-mobile PC',
        '1-0050F204-5': 'Notebook',
        '1-0050F204-6': 'Desktop',
        '1-0050F204-7': 'MID (Mobile Internet Device)',
        '1-0050F204-8': 'Netbook',
        '1-0050F204-9': 'Tablet',
        '2-0050F204-1': 'Keyboard',
        '2-0050F204-2': 'Mouse device',
        '2-0050F204-3': 'Joystick device',
        '2-0050F204-4': 'Trackball device',
        '2-0050F204-5': 'Gaming controller',
        '2-0050F204-6': 'Remote device',
        '2-0050F204-7': 'Touchscreen device',
        '2-0050F204-8': 'Biometric reader',
        '2-0050F204-9': 'Barcode reader',
        '3-0050F204-1': 'Printer',
        '3-0050F204-2': 'Scanner',
        '3-0050F204-3': 'Fax',
        '3-0050F204-4': 'Copier',
        '3-0050F204-5': 'All-in-one Printer',
        '4-0050F204-1': 'Digital Still Camera',
        '4-0050F204-2': 'Video Camera',
        '4-0050F204-3': 'Web Camera',
        '4-0050F204-4': 'Security Camera',
        '5-0050F204-1': 'NAS storage device',
        '6-0050F204-1': 'AP Network Infrastructure device',
        '6-0050F204-2': 'Router device',
        '6-0050F204-3': 'Switch device',
        '6-0050F204-4': 'Gateway device',
        '7-0050F204-1': 'Television device',
        '7-0050F204-2': 'Electronic Picture Frame device',
        '7-0050F204-3': 'Projector device',
        '7-0050F204-4': 'Monitor device',
        '8-0050F204-1': 'DAR device',
        '8-0050F204-2': 'PVR device',
        '8-0050F204-3': 'MCX device',
        '8-0050F204-4': 'Set-top box',
        '8-0050F204-5': 'Media Server/Media Adapter/Media Extender',
        '8-0050F204-6': 'Portable Video Player',
        '9-0050F204-1': 'Xbox',
        '9-0050F204-2': 'Xbox360',
        '9-0050F204-3': 'Playstation',
        '9-0050F204-4': 'Game Console/Game Console Adapter',
        '9-0050F204-5': 'Portable Gaming Device',
        '10-0050F204-1': 'Windows Mobile',
        '10-0050F204-2': 'Phone – single mode',
        '10-0050F204-3': 'Phone – dual mode',
        '10-0050F204-4': 'Smartphone – single mode',
        '10-0050F204-5': 'Dual-band Smartphone',
        '11-0050F204-1': 'Audio tuner/receiver',
        '11-0050F204-2': 'Speakers',
        '11-0050F204-3': 'Portable Music Player (PMP)',
        '11-0050F204-4': 'Headset (headphones + microphone)',
        '11-0050F204-5': 'Headphones',
        '11-0050F204-6': 'Microphone',
        '255-0050F204-1': 'generic device' # also used by hostp2pd when the device type is not in table
    }

    p2p_password_id = {
        # From "Wi-Fi Simple ConfigurationTechnical Specification" Version 2.0.5
        #  Table 37 – Device Password ID
        0: 'Default (PIN)',
        1: 'User-specified', # means that the requestor enters PIN (ref. "Table 1—Summary of WSC Config Methods and Device Password ID usage" of "Wi-Fi Peer-to-Peer (P2P) Technical Specification"
        2: 'Machine-specified',
        3: 'Rekey',
        4: 'PushButton',  # means that the requestor uses PBC
        5: 'Registrar-specified',
        6: 'Reserved (for IBSS with Wi-Fi Protected Setup Specification)',
        7: 'NFC-Connection-Handover',
        8: 'P2Ps (Reserved for Wi-Fi Peer-to-Peer Services Specification)',
        9: 'Reserved',
        10: 'Reserved',
        11: 'Reserved',
        12: 'Reserved',
        13: 'Reserved',
        14: 'Reserved',
        15: 'Reserved'
        # Greater numbers: 0x0010 to 0xFFFF - Randomly generated value for Password given to the Enrollee or Registrar via an Out-of-Band Device Password attribute.
    }

    select_timeout_secs = {  # see read_wpa() and find_timing_level
        "normal": 10,    # seconds. Period to send p2p_find refreshes
        "connect": 90,   # seconds. Increased timing while p2p_connect
        "long": 600,     # seconds. Period to send p2p_find refreshes after exceeding self.max_scan_polling
        "enroller": 600, # seconds. Period used by the enroller
    }

    p2p_client = "wpa_cli"             # wpa_cli program name
    min_conn_delay = 40                # seconds delay before issuing another p2p_connect or enroll
    max_num_failures = 3               # max number of retries for a p2p_connect
    max_num_wpa_cli_failures = 9       # max number of wpa_cli errors
    max_scan_polling = 2               # max number of p2p_find consecutive polling (0=infinite number)
    save_config_enabled = True         # Disable if old wpa_supplicant version crashes with save_config when missing file
    pbc_in_use = None                  # Use method selected in config. (False=keypad, True=pbc, None=wpa_supplicant.conf)
    p2p_group_add_opts = None          # Arguments to add to p2p_group_add, like freq=2 or freq=5
    p2p_connect_opts = None            # Arguments to add to p2p_connect, like freq=2 or freq=5
    activate_persistent_group = True   # Activate a persistent group at process startup
    activate_autonomous_group = False  # Activate an autonomous group at process startup
    ssid_postfix = None                # Postfix string to be added to the automatically generated groups
    persistent_network_id = None       # persistent group network number (None = first in wpa_supplicant config.)
    max_negotiation_time = 120         # seconds. Time for a station to enter the PIN
    wpa_supplicant_min_err_warn = 0    # None(=all warned) or min n. of wpa_supplicant connection errors to skip warning
    dynamic_group = False              # allow removing group after a session disconnects
    config_file = None                 # default YAML configuration file
    pin = "00000000"                   # default pin
    pin_module = None                  # external pin module
    force_logging = None               # default force_logging
    interface = "auto"                 # default interface
    run_program = ""                   # default run_program
    pbc_white_list = []                # default name white list for push button (pbc) enrolment
    network_parms = []                 # network parameters when creating a persistent group if none is already defined
    config_parms = []                  # wpa_supplicant configuration parameters
    do_not_debug = [                   # do not add debug logs for the events in the list
        'CTRL-EVENT-SCAN-STARTED',
        'CTRL-EVENT-SCAN-RESULTS'
    ]
    conf_schema = """
%YAML 1.1
---
select_timeout_secs:
  normal: <class 'float'>
  connect: <class 'float'>
  long: <class 'float'>
p2p_client: <class 'str'>
min_conn_delay: <class 'float'>
max_num_failures: <class 'float'>
max_num_wpa_cli_failures: <class 'float'>
max_scan_polling: <class 'float'>
save_config_enabled: <class 'bool'>
pbc_in_use: <class 'bool'>
p2p_group_add_opts: <class 'str'>
p2p_connect_opts: <class 'str'>
activate_persistent_group: <class 'bool'>
activate_autonomous_group: <class 'bool'>
ssid_postfix: <class 'str'>
persistent_network_id: <class 'int'>
max_negotiation_time: <class 'float'>
wpa_supplicant_min_err_warn: <class 'float'>
dynamic_group: <class 'bool'>
pin: <class 'str'>
pin_module: <class 'str'>
force_logging: <class 'bool'>
interface: <class 'str'>
run_program: <class 'str'>
pbc_white_list: <class 'list'>
network_parms: <class 'list'>
config_parms: <class 'open_dict'>
"""

    ################# End of static configuration ##################################

    class THREAD:
        """
        Thread states
        """

        STOPPED = 0
        STARTING = 1
        ACTIVE = 2
        PAUSED = 3
        state = ["Stopped", "Starting", "Active", "Paused"]

    def read_configuration(
            self,
            configuration_file,
            default_level=logging.WARNING,
            env_key=os.path.basename(Path(__file__).stem).upper() + "_CFG",
            do_activation=False,
    ):
        success = True
        if configuration_file:
            self.config_file = configuration_file
        else:
            self.config_file = Path(__file__).stem + ".yaml"
        if not os.path.exists(self.config_file):
            self.config_file = os.path.join(
                os.path.dirname(Path(__file__)), "hostp2pd.yaml"
            )
        value = os.getenv(env_key, None)
        if value:
            self.config_file = value
        if self.config_file == "<stdin>":
            self.config_file = "/dev/stdin"
        if os.path.exists(self.config_file) and configuration_file != "reset":
            try:
                with open(self.config_file, "rt") as f:
                    try:
                        config = yaml.safe_load(f.read())
                    except Exception as e:
                        config = None
                        logging.critical(
                            'Cannot parse YAML configuration file "%s": %s.',
                            self.config_file,
                            e,
                        )
                        success = False
                    # Logging configuration ('logging' section)
                    if self.force_logging is None:
                        if config and "logging" in config:
                            try:
                                logging.config.dictConfig(config["logging"])
                            except Exception as e:
                                logging.basicConfig(level=default_level)
                                logging.critical(
                                    'Wrong "logging" section in YAML '
                                    'configuration file "%s": %s.',
                                    self.config_file,
                                    e,
                                )
                                success = False
                        else:
                            logging.warning(
                                'Missing "logging" section in YAML '
                                'configuration file "%s".',
                                self.config_file,
                            )
                            logging.basicConfig(level=default_level)
                            success = False
                    else:
                        self.logger.setLevel(self.force_logging)
                    # Configuration settings ('hostp2pd' section)
                    if config and "hostp2pd" in config and config["hostp2pd"]:
                        if hasattr(yaml, "FullLoader"):
                            yaml_conf_schema = yaml.load(
                                self.conf_schema, Loader=yaml.FullLoader
                            )
                        else:
                            yaml_conf_schema = yaml.load(self.conf_schema)
                        types = get_type(config["hostp2pd"], yaml_conf_schema)
                        if types:
                            for key, val in types.items():
                                if val is None:
                                    logging.critical(
                                        'Invalid parameter: "%s".', key
                                    )
                                    types = None
                                    success = False
                        if types:
                            try:
                                old_interface = self.interface
                                self.__dict__.update(config["hostp2pd"])
                                if (old_interface != "auto"
                                        and self.interface == "auto"):
                                    self.interface = old_interface
                            except Exception as e:
                                logging.critical(
                                    'Wrong "hostp2pd" section in YAML '
                                    'configuration file "%s": %s.',
                                    self.config_file,
                                    e,
                                )
                                success = False
                    else:
                        logging.debug(
                            'Missing "hostp2pd" section in YAML '
                            'configuration file "%s".',
                            self.config_file,
                        )
                        # success = False
            except (PermissionError, FileNotFoundError) as e:
                logging.critical(
                    'Cannot open YAML configuration file "%s": %s.',
                    self.config_file,
                    e,
                )
                success = False
        else:
            logging.basicConfig(level=default_level)
            if configuration_file == "reset":
                logging.debug("Resetting configuration to default values")
                self.config_file = None
                if self.force_logging is None:
                    logging.basicConfig(level=default_level)
                else:
                    self.logger.setLevel(self.force_logging)
            else:
                if self.config_file:
                    logging.critical(
                        'Cannot find YAML configuration file "%s".',
                        self.config_file,
                    )
                    success = False
        # logging.debug("YAML configuration logging pathname: %s", self.config_file)
        self.last_pwd = self.get_pin(self.pin)
        hide_from_logging([self.last_pwd], "********")
        if do_activation:
            if not self.is_enroller:
                logging.debug(
                    'Reloading "wpa_supplicant" configuration file...')
                self.threadState = self.THREAD.PAUSED
                time.sleep(0.1)
                self.write_wpa("ping")
                time.sleep(0.1)
                self.write_wpa("ping")
                time.sleep(0.1)
                self.write_wpa("reconfigure")
                cmd_timeout = time.time()
                error = 0
                while True:  # Wait 'OK' before continuing
                    input_line = self.read_wpa()
                    if input_line is None:
                        if error > self.max_num_failures:
                            logging.error(
                                "Internal Error (read_configuration): "
                                "read_wpa() abnormally terminated"
                            )
                            self.terminate_enrol()
                            self.terminate()
                        logging.error("no data (read_configuration)")
                        time.sleep(0.5)
                        error += 1
                        continue
                    error = 0
                    logging.debug("(reconfigure) Read '%s'", input_line)
                    if self.warn_on_input_errors(input_line):
                        continue
                    if time.time() > cmd_timeout + self.min_conn_delay:
                        logging.debug(
                            'Terminating reloading "wpa_supplicant" '
                            "configuration file after timeout "
                            "of %s seconds",
                            self.min_conn_delay,
                        )
                        break
                    if "OK" in input_line:
                        logging.debug('"wpa_supplicant" configuration reloaded.')
                        self.configure_wpa()
                        break
                    logging.debug("(reconfigure) PUSH '%s'", input_line)
                    self.stack.append(input_line)
                self.threadState = self.THREAD.ACTIVE
            self.do_activation = True
        if success:
            if self.check_enrol():
                os.kill(
                    self.enroller.pid, signal.SIGHUP
                )  # Ask the enroller to reload its configuration
            logging.debug("Configuration successfully loaded.")
        else:
            logging.error("Loading configuration failed.")
        return success

    def reset(self, sleep=0):
        """
        Resets statistics and address registers to their defaults
        """
        logging.debug(
            "Resetting statistics and sleeping for %s seconds", sleep)
        time.sleep(sleep)
        self.statistics = {}
        self.addr_register = {}
        self.dev_type_register = {}

    def set_defaults(self):
        self.p2p_connect_time = 0  # 0=run function (set by start_session() and enrol())
        self.group_type = None
        self.monitor_group = None
        self.can_register_cmds = False
        self.num_failures = 0
        self.station = None
        self.wpa_supplicant_errors = 0
        self.run_prog_stopped = False
        self.scan_polling = 0
        self.process = None
        self.thread = None
        self.threadState = self.THREAD.STOPPED
        self.master_fd = None
        self.slave_fd = None
        self.ssid_group = None
        self.do_activation = False
        self.find_timing_level = "normal"
        self.config_method_in_use = ""
        self.use_enroller = True  # False = run obsolete procedure instead of Enroller
        self.is_enroller = False  # False if I am Core, True if I am Enroller
        self.enroller = None  # Core can check this to know whether Enroller is active
        self.terminate_is_active = False  # silence read/write errors if terminating
        self.statistics = {}
        self.addr_register = {}
        self.dev_type_register = {}
        self.is_daemon = False
        self.last_pwd = None
        self.stack = []

    def __init__(
            self,
            config_file=config_file,
            interface=interface,
            run_program=run_program,
            force_logging=force_logging,
            pbc_white_list=pbc_white_list,
            pin=pin,
    ):
        """
        Class init procedure
        """

        os.umask(0o077)  # protect reserved information in logging
        self.logger = logging.getLogger()
        self.set_defaults()

        # Argument handling
        self.config_file = config_file
        self.interface = interface
        self.run_program = run_program
        self.force_logging = force_logging
        self.pbc_white_list = pbc_white_list
        self.pin = pin
        global get_pin
        self.get_pin = get_pin

    def start_process(self):
        """
        Run an external subprocess interconnected via pty, disabling echo
        """
        # make a new pty
        self.master_fd, self.slave_fd = pty.openpty()
        self.slave_name = os.ttyname(self.slave_fd)

        # Disable echo
        no_echo = termios.tcgetattr(self.slave_fd)
        no_echo[3] = no_echo[3] & ~termios.ECHO  # lflag
        termios.tcsetattr(self.slave_fd, termios.TCSADRAIN, no_echo)

        # Disable wpa_cli command line history
        if 'HOME' in os.environ:
            del os.environ['HOME']

        # Start process connected to the slave pty
        if self.interface == "auto":
            command = [self.p2p_client]
        else:
            command = [self.p2p_client, "-i", self.interface]
        try:
            self.process = subprocess.Popen(
                command,
                # shell=True,
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                bufsize=1,
                universal_newlines=True,
            )
        except FileNotFoundError as e:
            logging.critical('PANIC - Cannot run "wpa_cli" software: %s', e)
            return False
        return True

    def __enter__(self):
        """
        Activated when starting the Context Manager
        """
        if not self.start_process():
            return None
        threading.current_thread().name = "Main"
        # start the read thread
        self.threadState = self.THREAD.STARTING
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Activated when ending the Context Manager
        """
        self.terminate()
        return False  # don't suppress any exception

    def terminate(self):
        """
        hostp2pd termination procedure
        """
        if self.terminate_is_active:
            return False
        self.terminate_is_active = True
        logging.debug("Start termination procedure.")
        self.terminate_enrol()
        if self.thread and self.threadState != self.THREAD.STOPPED:
            time.sleep(0.1)
            try:
                self.thread.join(1)
            except:
                logging.debug("Cannot join current thread.")
            self.thread = None
        self.threadState = self.THREAD.STOPPED
        try:
            if self.slave_fd:
                os.close(self.slave_fd)
            if self.master_fd:
                os.close(self.master_fd)
        except:
            logging.debug("Cannot close file descriptors.")
        if not self.is_enroller:
            self.external_program(self.EXTERNAL_PROG_ACTION.TERMINATED)
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(1)
            except:
                logging.debug("wpa_cli process not terminated.")
            self.set_defaults()
        logging.debug("Terminated.")
        return True

    def run_enrol(self, child=False):
        """
        Core starts the Enroller child; child activates itself
        """
        if not child and self.check_enrol():
            return  # Avoid double instance of the Enroller process
        if child:  # I am Enroller
            threading.current_thread().name = "Enroller"
            self.enroller.name = threading.current_thread().name

            # Receive SIGTERM if the father dies
            libc = ctypes.CDLL(find_library("c"))
            PR_SET_PDEATHSIG = 1  # <sys/prctl.h>
            libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0)

            self.wpa_supplicant_errors = 0
            if not self.monitor_group:
                logging.critical("PANIC - Internal error: null monitor_group")
                return
            self.is_enroller = True
            self.father_slave_fd = self.slave_fd
            self.interface = self.monitor_group
            signal.SIGTERM: lambda signum, frame: self.terminate()
            signal.SIGINT: lambda signum, frame: self.terminate()
            signal.signal(  # Allow reloading Enroller configuration with SIGHUP
                signal.SIGHUP,
                lambda signum, frame: self.read_configuration(
                    configuration_file=self.config_file, do_activation=True
                ),
            )
            try:
                self.run()
            except KeyboardInterrupt:
                logging.debug("Enroller interrupted.")
                self.terminate()
                return None
        else:  # I am Core
            self.enroller = Process(target=self.run_enrol, args=(True,))
            self.enroller.daemon = True
            self.enroller.start()
            logging.debug(
                "Starting enroller process with PID %s", self.enroller.pid
            )

    def check_enrol(self):
        """
        Core checks whether Enroller process is active
        """
        if (
                self.use_enroller
                and not self.is_enroller
                and self.enroller is not None
                and self.enroller.is_alive()
                and self.enroller.pid > 0
        ):
            return True
        return False

    def terminate_enrol(self):
        """
        Core terminates active Enroller process
        """
        if self.check_enrol():
            enroller = self.enroller
            self.enroller = None
            logging.debug("Terminating Enroller process.")
            time.sleep(0.5)
            enroller.terminate()
            enroller.join(2)
            logging.debug("Enroller process terminated.")

    def run(self):
        """ Main procedure """
        if os.getppid() == 1 and os.getpgrp() == os.getsid(0):
            self.is_daemon = True
        if not self.is_enroller:
            threading.current_thread().name = "Core"
            self.external_program(self.EXTERNAL_PROG_ACTION.STARTED)
        if self.is_enroller or self.process is None:
            if not self.start_process():
                return
        self.read_configuration(configuration_file=self.config_file)

        if self.is_enroller:
            logging.info(
                'Enroller subprocess for group "%s" started',
                self.monitor_group
            )
        else:
            logging.warning(
                "__________"
                "hostp2pd Service started (v%s) "
                "PID=%s, PPID=%s, PGRP=%s, SID=%s, is_daemon=%s"
                "__________",
                __version__,
                os.getpid(),
                os.getppid(),
                os.getpgrp(),
                os.getsid(0),
                self.is_daemon,
            )

        if self.interface == "auto":
            self.auto_select_interface()

        # Load pin module
        if self.pin_module:
            module_name = "get_pin"
            spec = importlib.util.spec_from_file_location(
                module_name, self.pin_module
            )
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
                logging.debug(
                    'Using imported pin module "%s".', self.pin_module)
                if not "get_pin" in dir(module):
                    logging.error(
                        'Missing "get_pin" function '
                        'in imported pin module "%s".',
                        self.pin_module,
                    )
                    raise ValueError("missing function in imported module.")
                self.get_pin = module.get_pin
            except Exception as e:
                logging.error(
                    'Using builtin "get_pin" function ' "for this reason: %s",
                    e
                )
        self.last_pwd = self.get_pin(self.pin)
        hide_from_logging([self.last_pwd], "********")

        if self.activate_persistent_group and self.activate_autonomous_group:
            logging.error(
                'Error: "activate_persistent_group" '
                'and "activate_autonomous_group" are both active. '
                "Considering peristent group."
            )
            self.activate_autonomous_group = False

        self.threadState = self.THREAD.ACTIVE

        """ main loop """
        self.stack = []
        time.sleep(0.3)
        while self.threadState != self.THREAD.STOPPED:

            if self.threadState == self.THREAD.PAUSED:
                time.sleep(0.1)
                continue

            # get the command and process it
            self.cmd = None
            while len(self.stack) > 0:
                self.cmd = self.stack.pop(0)
                logging.debug(
                    "(enroller) POP: %s" if self.is_enroller else "POP: %s",
                    repr(self.cmd),
                )
                if self.cmd:
                    break
            if not self.cmd:
                self.cmd = None
            if self.cmd is None:
                self.cmd = self.read_wpa()
            if self.cmd is None:
                self.terminate()
                return
            if self.threadState == self.THREAD.STOPPED:
                return
            if not any(skip in self.cmd for skip in self.do_not_debug):
                logging.debug(
                    "(enroller) recv: %s" if self.is_enroller
                    else "recv: %s", repr(self.cmd),
                )
            if not self.handle(self.cmd):
                self.threadState = self.THREAD.STOPPED

    def read_wpa(self):
        """reads from wpa_cli until the next newline
        Returned value: void string (no data),
        or data (valued string), or None (error)
        """
        buffer = ""

        try:
            while True:
                if (
                        self.find_timing_level == "normal"
                        and self.max_scan_polling > 0
                        and self.scan_polling >= self.max_scan_polling
                ):
                    self.find_timing_level = "long"
                    logging.debug(
                        "New read_wpa timeout: %s seconds.",
                        self.select_timeout_secs[self.find_timing_level],
                    )
                timeout = self.select_timeout_secs[self.find_timing_level]
                reads, _, _ = select([self.master_fd], [], [], timeout)
                if len(reads) > 0:
                    c = os.read(self.master_fd, 1).decode("utf8", "ignore")
                else:
                    # Here some periodic tasks are handled:

                    # Controlling whether an active Enroller died
                    if self.process is not None:
                        ret = self.process.poll()
                        if ret is not None:  # Enroller died with ret code
                            logging.critical(
                                "wpa_cli died with return code %s."
                                " Terminating hostp2pd.",
                                ret,
                            )
                            os.kill(os.getpid(), signal.SIGTERM)

                    # Controlling frequency of periodic "p2p_find" and sending it
                    if (
                            self.max_scan_polling > 0
                            and self.scan_polling > self.max_scan_polling
                    ):
                        logging.info(
                            "Exceeded number of p2p_find pollings "
                            "after read timeout of %s seconds: %s",
                            timeout,
                            self.scan_polling,
                        )
                    else:
                        self.scan_polling += 1
                        logging.debug(
                            "p2p_find polling after read timeout "
                            "of %s seconds: %s of %s",
                            timeout,
                            self.scan_polling,
                            self.max_scan_polling,
                        )
                        self.write_wpa("p2p_find")
                    continue

                if c == "\n":
                    break  # complete the read operation and does not include the newline

                if c == "\r":
                    continue  # skip carriage returns

                buffer += c
        except TypeError as e:
            if self.master_fd is None:
                logging.debug("Process interrupted.")
            else:
                logging.critical(
                    "PANIC - Internal TypeError in read_wpa(): %s",
                    e,
                    exc_info=True,
                )
            return None  # error
        except OSError as e:
            if (
                    e.errno == errno.EBADF or e.errno == errno.EIO
            ):  # [Errno 9] Bad file descriptor/[Errno 5] Input/output error
                logging.debug("Read interrupted.")
            else:
                logging.critical(
                    "PANIC - Internal OSError in read_wpa(): %s",
                    e,
                    exc_info=True,
                )
            return None  # error
        except Exception as e:
            if self.terminate_is_active:
                logging.debug("Read interrupted: %s", e)
                return None  # error
            logging.critical(
                "PANIC - Internal error in read_wpa(): %s", e, exc_info=True
            )

        return buffer

    def write_wpa(self, resp):
        """ write to wpa_cli """
        logging.debug(
            "(enroller) Write: %s" if self.is_enroller else "Write: %s",
            repr(resp),
        )
        resp += "\n"
        try:
            return os.write(self.master_fd, resp.encode())
        except TypeError as e:
            if self.master_fd is None:
                logging.debug("Process interrupted.")
            else:
                logging.critical(
                    "PANIC - Internal TypeError in write_wpa(): %s",
                    e,
                    exc_info=True,
                )
            return None  # error
        except Exception as e:
            if not self.terminate_is_active:
                logging.critical(
                    "PANIC - Internal error in write_wpa(): %s",
                    e, exc_info=True
                )
            return None  # error

    def rotate_config_method(self):
        if self.pbc_in_use:
            self.write_wpa("p2p_stop_find")
            time.sleep(2)
            self.write_wpa("set config_methods keypad")
            self.config_method_in_use = "keypad"
            self.pbc_in_use = False
            self.write_wpa("p2p_find")
            time.sleep(2)
        else:
            self.write_wpa("p2p_stop_find")
            time.sleep(2)
            self.write_wpa("set config_methods virtual_push_button")
            self.config_method_in_use = "virtual_push_button"
            self.pbc_in_use = True
            self.write_wpa("p2p_find")
            time.sleep(2)

    def start_session(self, station=None):
        if time.time() < self.p2p_connect_time + self.min_conn_delay:
            logging.debug(
                "Will not p2p_conect due to unsufficient p2p_connect_time"
            )
            return
        self.find_timing_level = "connect"
        if station:
            self.station = station
        else:
            station = self.station
        if not station or station is None:
            return
        self.external_program(self.EXTERNAL_PROG_ACTION.START_GROUP)
        persistent_postfix = ""
        if self.activate_persistent_group and self.dynamic_group:
            persistent_postfix = " persistent"
            if self.persistent_network_id is not None:
                persistent_postfix += "=" + self.persistent_network_id
        self.p2p_command(self.P2P_COMMAND.P2P_CONNECT, station)
        self.p2p_connect_time = time.time()
        self.group_type = "Negotiated (always won)"

    def list_or_remove_group(self, remove=False):
        """ list or remove p2p groups; group name is returned """
        logging.debug(
            'Starting list_or_remove_group procedure. remove="%s"', remove
        )
        self.write_wpa("interface")
        self.write_wpa("ping")
        monitor_group = None
        wait_cmd = 0
        cmd_timeout = time.time()
        error = 0
        can_append = False
        while True:
            input_line = self.read_wpa()
            if input_line is None:
                if error > self.max_num_failures:
                    logging.critical(
                        "Internal Error (list_or_remove_group): "
                        "read_wpa() abnormally terminated"
                    )
                    self.terminate_enrol()
                    self.terminate()
                logging.error("no data (list_or_remove_group)")
                time.sleep(0.5)
                error += 1
                continue
            error = 0
            logging.debug("reading '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.debug(
                    "Terminating group list/deletion procedure "
                    "after timeout of %s seconds.",
                    self.min_conn_delay,
                )
                break
            if "P2P-GROUP-REMOVED " in input_line:
                self.p2p_connect_time = 0
                self.find_timing_level = "normal"
                logging.debug(
                    "Received %s. Terminating group list/deletion procedure.",
                    input_line,
                )
                break
            if "PONG" in input_line and not wait_cmd:
                logging.debug(
                    'Terminating group list/deletion. Group="%s".',
                    monitor_group
                )
                break
            tokens = input_line.split("-")
            if len(tokens) != 3:
                if can_append:
                    logging.debug("(list_or_remove_group) PUSH '%s'",
                                  input_line)
                    self.stack.append(input_line)
                continue
            if tokens[0] != "p2p":
                if can_append:
                    logging.debug("(list_or_remove_group) PUSH '%s'",
                                  input_line)
                    self.stack.append(input_line)
                continue
            if tokens[2].isnumeric() and not ">" in input_line:
                monitor_group = input_line
                if remove:
                    can_append = True
                    logging.debug(
                        'Removing "%s": %s group %s of interface %s',
                        input_line,
                        tokens[0],
                        tokens[2],
                        tokens[1],
                    )
                    self.write_wpa("p2p_group_remove " + monitor_group)
                    wait_cmd = time.time()
                    self.external_program(
                        self.EXTERNAL_PROG_ACTION.STOP_GROUP, monitor_group)
                    monitor_group = None
                    logging.warning("removed %s", input_line)
                    time.sleep(2)
                else:
                    logging.debug(
                        'Found "%s": %s group %s of interface %s',
                        input_line,
                        tokens[0],
                        tokens[2],
                        tokens[1],
                    )
                continue
            if can_append:
                logging.debug("(list_or_remove_group) PUSH '%s'", input_line)
                self.stack.append(input_line)
        return monitor_group

    def auto_select_interface(self):
        """ auto-select p2p device interface """
        logging.debug('Starting auto_select_interface.')
        self.write_wpa("interface")
        self.write_wpa("ping")
        wait_cmd = 0
        cmd_timeout = time.time()
        error = 0
        while True:
            input_line = self.read_wpa()
            if input_line is None:
                if error > self.max_num_failures:
                    logging.critical(
                        "Internal Error (auto_select_interface): "
                        "read_wpa() abnormally terminated"
                    )
                    self.terminate_enrol()
                    self.terminate()
                logging.error("no data (auto_select_interface)")
                time.sleep(0.5)
                error += 1
                continue
            error = 0
            logging.debug("reading '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.debug(
                    "Terminating auto_select_interface procedure "
                    "after timeout of %s seconds.",
                    self.min_conn_delay,
                )
                break
            if "PONG" in input_line and not wait_cmd:
                logging.debug(
                    'Terminating auto_select_interface. Interface="%s".',
                    self.interface
                )
                break
            tokens = input_line.split("-")
            if len(tokens) != 3:
                continue
            if tokens[0] != "p2p":
                continue
            if tokens[1] != "dev":
                continue
            if self.interface == "auto":
                logging.info('Using interface "%s".', input_line)
                self.interface = input_line
                self.p2p_command(self.P2P_COMMAND.SET_INTERFACE_P2P_DEVICE)
            else:
                logging.debug('List interface "%s".', input_line)
                continue
        return

    def count_active_sessions(self):
        """Enroller counts the number of active sessions
        of a P2P-GO group and writes this number to Core
        """
        logging.debug("Starting count_active_sessions procedure")
        if not self.is_enroller:
            self.p2p_command(self.P2P_COMMAND.SET_INTERFACE_P2P_GO)
        self.write_wpa("ping")
        self.write_wpa("list_sta")
        self.write_wpa("ping")
        n_stations = 0
        flush_data = True  # skip the first ping (used to flush previous data)
        cmd_timeout = time.time()
        error = 0
        while True:
            input_line = self.read_wpa()
            if input_line is None:
                if error > self.max_num_failures:
                    logging.critical(
                        "Internal Error (count_active_sessions): "
                        "read_wpa() abnormally terminated"
                    )
                    self.terminate_enrol()
                    self.terminate()
                logging.error("no data (count_active_sessions)")
                time.sleep(0.5)
                error += 1
                continue
            error = 0
            logging.debug("reading '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.debug(
                    "Terminating count_active_sessions procedure "
                    "after timeout of %s seconds.",
                    self.min_conn_delay,
                )
                break
            if flush_data:
                if "PONG" in input_line:
                    flush_data = False
                continue
            if re.match(
                    "^(?:> )?[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$",
                    input_line.lower(),
            ):
                n_stations += 1
                logging.debug(
                    'Active station "%s". n_stations=%s',
                    input_line, n_stations
                )
                continue
            if "PONG" in input_line:
                logging.debug(
                    "Terminating count_active_sessions. n_stations=%s.",
                    n_stations,
                )
                break
        os.write(
            self.father_slave_fd,
            (
                (
                        "HOSTP2PD_ACTIVE_SESSIONS" + "\t" + str(n_stations) + "\n"
                ).encode()
            ),
        )
        if not self.is_enroller:
            self.p2p_command(self.P2P_COMMAND.SET_INTERFACE_P2P_DEVICE)
        return n_stations

    def configure_wpa(self):
        if len(self.config_parms) == 0:
            return None
        logging.debug("Starting configure_wpa procedure")
        network_id = None
        error = 0
        cmd_timeout = time.time()
        success = None
        for parm in self.config_parms:
            self.write_wpa("set " + parm + " " + str(self.config_parms[parm]))
            while True:
                input_line = self.read_wpa()
                if input_line is None:
                    if error > self.max_num_failures:
                        logging.critical(
                            "Internal Error (configure_wpa): "
                            "read_wpa() abnormally terminated"
                        )
                        self.terminate_enrol()
                        self.terminate()
                    logging.error("no data (configure_wpa)")
                    time.sleep(0.5)
                    error += 1
                    continue
                error = 0
                logging.debug("(configure_wpa) Read '%s'", input_line)
                if self.warn_on_input_errors(input_line):
                    continue
                if time.time() > cmd_timeout + self.min_conn_delay:
                    logging.error(
                        "Terminating configure_wpa procedure "
                        "after timeout of %s seconds.",
                        self.min_conn_delay,
                    )
                    return False
                if "FAIL" in input_line:
                    logging.error(
                        'Cannot set parameter "%s" to "%s".',
                        parm,
                        self.config_parms[parm],
                    )
                    success = False
                    break
                if "OK" in input_line:
                    if success is None:
                        success = True
                    break
                logging.debug("(configure_wpa) PUSH '%s'", input_line)
                self.stack.append(input_line)
        if success is None:
            logging.debug(
                "configure_wpa procedure terminated without updating config."
            )
        if not success:
            logging.error(
                "configure_wpa procedure terminated without saving config."
            )
        if success:
            if self.save_config_enabled:
                self.flush_wpa()
                self.write_wpa("save_config")
                if not self.ok_fail_wpa():
                    logging.error(
                        'Save configuration not allowed by wpa_supplicant. '
                        'Missing configuration file.')
            logging.debug("configure_wpa procedure completed.")
        return success

    def flush_wpa(self):
        """Flush read data from wpa_cli
        """
        logging.debug("Starting flush_wpa procedure")
        self.write_wpa("ping")
        cmd_timeout = time.time()
        error = 0
        while True:
            input_line = self.read_wpa()
            if input_line is None:
                if error > self.max_num_failures:
                    logging.critical(
                        "Internal Error (flush_wpa): "
                        "read_wpa() abnormally terminated"
                    )
                    self.terminate_enrol()
                    self.terminate()
                logging.error("no data (flush_wpa)")
                time.sleep(0.5)
                error += 1
                continue
            error = 0
            logging.debug("reading '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.debug(
                    "Terminating flush_wpa procedure "
                    "after timeout of %s seconds.",
                    self.min_conn_delay,
                )
                break
            if "PONG" in input_line:
                logging.debug(
                    "Terminating flush_wpa.")
                break
            logging.debug("(flush_wpa) PUSH '%s'", input_line)
            self.stack.append(input_line)
        return

    def ok_fail_wpa(self):
        """Read OK or FAIL from wpa_cli
        """
        logging.debug("Starting ok_fail_wpa procedure")
        cmd_timeout = time.time()
        error = 0
        while True:
            input_line = self.read_wpa()
            if input_line is None:
                if error > self.max_num_failures:
                    logging.critical(
                        "Internal Error (ok_fail_wpa): "
                        "read_wpa() abnormally terminated"
                    )
                    self.terminate_enrol()
                    self.terminate()
                logging.error("no data (ok_fail_wpa)")
                time.sleep(0.5)
                error += 1
                continue
            error = 0
            logging.debug("reading '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.debug(
                    "Terminating ok_fail_wpa procedure "
                    "after timeout of %s seconds.",
                    self.min_conn_delay,
                )
                break
            if "OK" in input_line:
                logging.debug(
                    "OK Received. Terminating ok_fail_wpa.")
                return True
            if "FAIL" in input_line:
                logging.debug(
                    "FAIL Received. Terminating ok_fail_wpa.")
                return False
            logging.debug("(ok_fail_wpa) PUSH '%s'", input_line)
            self.stack.append(input_line)
        return False

    def add_network(self, cmd_timeout):
        if len(self.network_parms) == 0:
            return False
        logging.debug("Starting add_network procedure")
        network_id = None
        listn = None
        self.write_wpa("add_network")
        can_append = False
        error = 0
        last_command = "(Unknown command)"
        while True:
            input_line = self.read_wpa()
            if input_line is None:
                if error > self.max_num_failures:
                    logging.critical(
                        "Internal Error (add_network): "
                        "read_wpa() abnormally terminated"
                    )
                    self.terminate_enrol()
                    self.terminate()
                logging.error("no data (add_network)")
                time.sleep(0.5)
                error += 1
                continue
            error = 0
            logging.debug("(add_network) Read '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.error(
                    "Terminating add_network procedure "
                    "after timeout of %s seconds.",
                    self.min_conn_delay,
                )
                break
            tokens = input_line.split()
            if tokens and tokens[0] == ">":  # remove prompt
                tokens.pop(0)
                if tokens and tokens[0].isnumeric():
                    network_id = tokens[0]
                    listn = 0
                    input_line = "OK"
                    can_append = True
            if "FAIL" in input_line:
                logging.error(
                    'Cannot add network. '
                    'Check configuration and password length: "%s"',
                    last_command)
                listn = None
                break
            if "OK" in input_line:
                if (
                        listn is None
                        or network_id is None
                        or listn >= len(self.network_parms)
                ):
                    break
                last_command = self.network_parms[listn]
                self.write_wpa(
                    "set_network "
                    + network_id
                    + " "
                    + last_command
                )
                listn += 1
                continue
            if can_append:
                logging.debug("(add_network) PUSH '%s'", input_line)
                self.stack.append(input_line)
        if listn and network_id:
            self.flush_wpa()
            self.write_wpa("set_network " + network_id + " mode 3")
            if not self.ok_fail_wpa():
                logging.error(
                    'cannot set "mode 3" to network "%s".', network_id)
            self.write_wpa("set_network " + network_id + " disabled 2")
            if not self.ok_fail_wpa():
                logging.error(
                    'cannot set "disabled 2" to network "%s".', network_id)
            if self.save_config_enabled:
                self.write_wpa("save_config")
                if not self.ok_fail_wpa():
                    logging.error(
                        'Save configuration not supported by wpa_supplicant.')
            self.persistent_network_id = None
            logging.debug("add_network procedure completed.")
            return True
        return False

    def list_start_pers_group(self, start_group=False):
        """ list or start p2p persistent group; ssid (or None) is returned """
        logging.debug(
            'Starting list_start_pers_group procedure. start_group="%s"',
            start_group,
        )
        ssid = None
        if start_group and self.monitor_group:
            logging.error("Group '%s' already active", self.monitor_group)
            return None
        self.write_wpa("list_networks")
        self.write_wpa("ping")
        wait_cmd = 0
        cmd_timeout = time.time()
        error = 0
        test_add_network = False
        while True:
            input_line = self.read_wpa()
            if input_line is None:
                if error > self.max_num_failures:
                    logging.critical(
                        "Internal Error (list_start_pers_group): "
                        "read_wpa() abnormally terminated"
                    )
                    self.terminate_enrol()
                    self.terminate()
                logging.error("no data (list_start_pers_group)")
                time.sleep(0.5)
                error += 1
                continue
            error = 0
            logging.debug("(list_start_pers_group) Read '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.debug(
                    "Terminating persistent group start procedure "
                    "after timeout of %s seconds.",
                    self.min_conn_delay,
                )
                if self.monitor_group:
                    self.ssid_group = self.analyze_existing_group(
                        self.monitor_group
                    )
                if self.monitor_group:
                    logging.info(
                        'Active group interface "%s"', self.monitor_group
                    )
                break
            tokens = input_line.split("\t")
            if "P2P-GROUP-STARTED" in tokens[0]:
                tokens = input_line.split()
                if tokens[0] == ">":  # remove prompt
                    tokens.pop(0)
                wait_cmd = 0
                self.monitor_group = tokens[1]
                ssid_arg = re.sub(
                    r'.*ssid="([^"]*).*', r"\1", input_line, 1
                )  # read ssid="<name>"
                if not ssid:
                    ssid = ssid_arg
                logging.info(
                    "Persistent group started %s", self.monitor_group)
                logging.debug(
                    "Persistent group activation procedure completed. "
                    'ssid="%s"',
                    ssid,
                )
                return ssid
            if "OK" in input_line:
                continue
            if "FAIL" in input_line:
                logging.error("Cannot start persistent group.")
                ssid = None
                break
            if "PONG" in input_line and not wait_cmd:
                logging.debug(
                    "Terminating list_start_pers_group "
                    'without finding any group. ssid="%s"',
                    ssid,
                )
                if test_add_network:
                    logging.error("Could not add network")
                else:
                    test_add_network = True
                    if start_group and self.add_network(cmd_timeout):
                        self.write_wpa("list_networks")
                        self.write_wpa("ping")
                        wait_cmd = 0
                        error = 0
                        continue
                if (
                        start_group
                        and self.activate_persistent_group
                        and not self.dynamic_group
                        and not ssid
                ):
                    self.write_wpa(
                        "p2p_group_add persistent"
                        + (
                            " " + self.p2p_group_add_opts
                            if self.p2p_group_add_opts
                            else ""
                        )
                    )
                    wait_cmd = time.time()
                    logging.warning("Starting generic persistent group")
                    self.group_type = "Generic persistent"
                    time.sleep(1)
                else:
                    self.write_wpa("p2p_find")
                    break
            if len(tokens) == 0:  # remove null line
                continue
            if tokens[0] == "network":
                continue
            if (
                    len(tokens) == 4
                    and "[P2P-PERSISTENT]" in tokens[3]
                    and tokens[0].isnumeric()
            ):
                ssid = tokens[1]
                if (
                        self.persistent_network_id is not None
                        and str(self.persistent_network_id) != tokens[0]
                ):
                    logging.debug(
                        "Skipping persistent group "
                        '"%s" with network ID %s, different from %s"',
                        tokens[1],
                        tokens[0],
                        self.persistent_network_id,
                    )
                    continue
                self.persistent_network_id = tokens[0]
                if not start_group:
                    continue
                self.write_wpa(
                    "p2p_group_add persistent="
                    + self.persistent_network_id
                    + (
                        " " + self.p2p_group_add_opts
                        if self.p2p_group_add_opts
                        else ""
                    )
                )
                self.group_type = "Persistent"
                wait_cmd = time.time()
                logging.warning(
                    'Starting persistent group "%s", n. %s '
                    "in the wpa_supplicant conf file.",
                    ssid,
                    self.persistent_network_id,
                )
                self.external_program(
                    self.EXTERNAL_PROG_ACTION.START_GROUP, ssid)
                time.sleep(1)
        return ssid

    def analyze_existing_group(self, group):
        """ ssid is returned if a persistent group is active, otherwise None """
        logging.debug(
            'Starting analyze_existing_group procedure. group="%s"', group
        )
        if not group:
            logging.error("No group available.")
            return None
        ssid = None
        ssid_pg = self.list_start_pers_group(start_group=False)
        if not ssid_pg:
            logging.info(
                'No persistent group available for interface "%s".', group
            )
            return None
        self.p2p_command(self.P2P_COMMAND.SET_INTERFACE_P2P_GO)
        self.write_wpa("status")
        self.p2p_command(self.P2P_COMMAND.SET_INTERFACE_P2P_DEVICE)
        self.write_wpa("ping")
        cmd_timeout = time.time()
        logging.debug(
            'List status of persistent group "%s", '
            'checking existence of ssid "%s"',
            group,
            ssid_pg,
        )
        error = 0
        while True:
            input_line = self.read_wpa()
            if input_line is None:
                if error > self.max_num_failures:
                    logging.critical(
                        "Internal Error (analyze_existing_group): "
                        "read_wpa() abnormally terminated"
                    )
                    self.terminate_enrol()
                    self.terminate()
                logging.error("no data (analyze_existing_group)")
                time.sleep(0.5)
                error += 1
                continue
            error = 0
            logging.debug("(analyze_existing_group) Read '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.debug(
                    'Terminating status retrieve of persistent group "%s" '
                    'with ssid "%s" after timeout of %s seconds.',
                    group,
                    ssid_pg,
                    self.min_conn_delay,
                )
                break
            tokens = input_line.split("=", 1)
            if tokens[0] == ">":  # remove prompt
                tokens.pop(0)
            if "ssid" in tokens[0]:
                if tokens[1] == ssid_pg:
                    ssid = tokens[1]
                logging.debug(
                    'Persistent group "%s" with ssid "%s" reports '
                    'status ssid "%s".',
                    group,
                    ssid_pg,
                    tokens[1],
                )
                continue
            if "PONG" in input_line:
                logging.debug('Terminating analysis; ssid="%s".', ssid)
                break
        return ssid

    def get_config_methods(self, pbc_in_use=None):
        logging.debug(
            "Starting 'get config_methods' procedure. pbc_in_use=%s",
            pbc_in_use
        )
        self.write_wpa("get config_methods")
        self.write_wpa("ping")
        wait_cmd = 0
        cmd_timeout = time.time()
        found = False
        error = 0
        while True:
            input_line = self.read_wpa()
            if input_line is None:
                if error > self.max_num_failures:
                    logging.critical(
                        "Internal Error (get_config_methods): "
                        "read_wpa() abnormally terminated"
                    )
                    self.terminate_enrol()
                    self.terminate()
                logging.error("no data (get_config_methods)")
                time.sleep(0.5)
                error += 1
                continue
            error = 0
            logging.debug("(get_config_methods) Read '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.debug(
                    "Terminating get_config_methods procedure after timeout "
                    "of %s seconds; pbc_in_use=%s",
                    self.min_conn_delay,
                    pbc_in_use,
                )
                break
            if "virtual_push_button" in input_line and not found:
                pbc_in_use = True
                logging.debug('Use "pbc" for config_methods, without pin.')
                continue
            if "keypad" in input_line and not found:
                pbc_in_use = False
                found = True  # keypad has priority to virtual_push_button if both are included
                logging.debug(
                    'Use "keypad" for config_methods, '
                    'with pin (do not use pbc).'
                )
                continue
            if "PONG" in input_line:
                logging.debug(
                    "Terminating get config_methods procedure; pbc_in_use=%s",
                    pbc_in_use,
                )
                break
        return pbc_in_use

    class EXTERNAL_PROG_ACTION:
        STARTED = "started"  # executed at hostp2pd startup
        TERMINATED = "terminated"  # executed at hostp2pd termination
        START_GROUP = "start_group"  # executed before creating a group
        STOP_GROUP = "stop_group"  # executed after removing a group
        CONNECT = "connect"  # executed after a station connects a group
        DISCONNECT = "disconnect"  # executed after a station disconnects a group

    def external_program(self, action, *args):
        if (
                not self.run_program
                or self.run_program.isspace()
                or self.run_program == "-"
        ):
            return

        if action == self.EXTERNAL_PROG_ACTION.START_GROUP:
            if self.run_prog_stopped:
                return
            else:
                self.run_prog_stopped = True

        if action == self.EXTERNAL_PROG_ACTION.STOP_GROUP:
            if not self.run_prog_stopped:
                return
            else:
                self.run_prog_stopped = False

        arguments = " ".join(args)
        if arguments:
            arguments = " " + arguments
        logging.debug(
            "Running %s %s %s", self.run_program, action, arguments)
        ret = os.system(self.run_program + " " + action + arguments)
        logging.debug(
            "%s completed with exit code %s",
            self.run_program,
            os.WEXITSTATUS(ret))

    def default_workflow(self, event_stat_name):
        if "CTRL-EVENT-TERMINATING" in event_stat_name:
            logging.warning("Service terminated")
            self.external_program(self.EXTERNAL_PROG_ACTION.TERMINATED)
            # self.terminate() # uncomment if you wan to terminate on CTRL-EVENT-TERMINATING
            logging.error("wpa_supplicant disconnected")
            return True

        # Update statistics with unknown messages
        if (
                self.can_register_cmds and event_stat_name
        ):  # and [c for c in event_stat_name if c.islower()] == []: # uncomment to remove lower case commands from statistics
            unmanaged_event = "unmanaged_" + event_stat_name
            if self.is_enroller and not self.is_daemon:
                os.write(
                    self.father_slave_fd,
                    (
                        (
                                "HOSTP2PD_STATISTICS"
                                + "\t"
                                + unmanaged_event
                                + "\n"
                        ).encode()
                    ),
                )
                return True
            if unmanaged_event not in self.statistics:
                self.statistics[unmanaged_event] = 0
            self.statistics[unmanaged_event] += 1
        return True

    class ENROL_TYPE:
        PIN = 0
        PBC = 1
        DISPLAY = 2

    def in_process_enrol(self, dev_name, mac_addr, type):
        """ Obsolete basic in-process function to perform the enrolling in the
            Core thread; using the Enroller process is suggested instead of
            this function (use_enroller).
        """
        if self.use_enroller:
            logging.debug("Using enroller subprocess to connect.")
            return
        if time.time() < self.p2p_connect_time + self.min_conn_delay:
            logging.debug(
                "Will not enroll due to unsufficient p2p_connect_time")
            return
        self.find_timing_level = "connect"
        logging.debug(
            'Enrol dev_name="%s", mac_addr="%s", '
            'type="%s" to monitor_group="%s"',
            dev_name,
            mac_addr,
            type,
            self.monitor_group,
        )
        cmd_timeout = time.time()
        self.p2p_command(self.P2P_COMMAND.SET_INTERFACE_P2P_GO)
        error = 0
        while True:
            input_line = self.read_wpa()
            if input_line is None:
                if error > self.max_num_failures:
                    logging.critical(
                        "Internal Error (in_process_enrol): "
                        "read_wpa() abnormally terminated"
                    )
                    self.terminate_enrol()
                    self.terminate()
                logging.error("no data (in_process_enrol)")
                time.sleep(0.5)
                error += 1
                continue
            error = 0
            logging.debug("(in_process_enrol) Read '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.max_negotiation_time:
                logging.error(
                    "Missing received enrolment request within %s seconds",
                    self.max_negotiation_time,
                )
                type = None  # comment this if you want to try the enrolment anyway
                break
            # > <3>WPS-ENROLLEE-SEEN ee:54:44:24:70:df 811e2280-33d1-5ce8-97e5-6fcf1598c173 10-0050F204-5 0x4388 0 1 [test]
            if "WPS-ENROLLEE-SEEN " in input_line:
                tokens = input_line.split()
                if tokens[0] == ">":  # remove prompt
                    tokens.pop(0)
                if tokens[1] == mac_addr:
                    break
        if type == self.ENROL_TYPE.PIN:
            self.last_pwd = self.get_pin(self.pin)
            hide_from_logging([self.last_pwd], "********")
            self.write_wpa("wps_pin " + mac_addr + " " + self.last_pwd)
        if type == self.ENROL_TYPE.PBC:
            self.write_wpa("wps_pbc " + mac_addr)
        self.p2p_command(self.P2P_COMMAND.SET_INTERFACE_P2P_DEVICE)
        logging.debug("Enrol procedure terminated")
        return

    def warn_on_input_errors(self, input_msg):
        if (
                input_msg == "Interactive mode"
                or "Connection to wpa_supplicant re-established" in input_msg
                or "Connection established" in input_msg
        ):  # startup activator
            if input_msg != "Interactive mode":
                logging.error(input_msg)
            self.do_activation = True
            self.find_timing_level = "normal"
            self.max_scan_polling = 0
            self.terminate_enrol()
            return True
        if "Connected to interface" in input_msg:
            return True
        if input_msg == self.last_pwd:  # do not add the PIN in statistics
            return True
        # Process wpa_supplicant connection problems
        if (
                "Could not connect to wpa_supplicant" in input_msg
                or "Connection to wpa_supplicant lost" in input_msg
                or "Not connected to wpa_supplicant" in input_msg
        ):
            if (self.wpa_supplicant_min_err_warn is None or
                    self.wpa_supplicant_errors >
                        self.wpa_supplicant_min_err_warn):
                logging.error(
                    "%s - %s of %s",
                    input_msg,
                    self.wpa_supplicant_errors,
                    self.max_num_wpa_cli_failures,
                )
            self.wpa_supplicant_errors += 1
            self.monitor_group = None
            self.ssid_group = None
            return True
        if "wpa_supplicant" in input_msg:
            logging.warning(input_msg)
            return True
        if "'SAVE_CONFIG' command timed out." in input_msg:
            logging.critical("wpa_supplicant crashed due to missing configuration file.")
            return True
        if "'PING' command failed." in input_msg:
            logging.critical("wpa_supplicant connection error.")
            return True
        return False

    def register_statistics(self, event_stat_name):
        self.statistics["last_response_message"] = event_stat_name
        if "response_messages" not in self.statistics:
            self.statistics["response_messages"] = 0
        self.statistics["response_messages"] += 1
        if event_stat_name not in self.statistics:
            self.statistics[event_stat_name] = 0
        self.statistics[event_stat_name] += 1

    class P2P_COMMAND:
        """ P2P commands to be used with p2p_command(). """
        SET_INTERFACE_P2P_GO = 0
        SET_INTERFACE_P2P_DEVICE = 1
        P2P_INVITE_PERSISTENT = 2
        P2P_INVITE_GROUP = 3
        P2P_CONNECT = 4  # parameters: MAC address; optional join, go_intent

    def p2p_command(self, command, mac_addr=None, go_intent=None, join=False):
        """ pre-tested p2p commands to be used inside the program
            for current and future needs, or to be assessed with the
            command-line interpreter.
        """
        persistent_postfix = ""
        if self.activate_persistent_group:
            persistent_postfix = " persistent"
            if self.persistent_network_id is not None:
                persistent_postfix += "=" + self.persistent_network_id

        if command == self.P2P_COMMAND.SET_INTERFACE_P2P_GO:
            self.write_wpa("interface " + self.monitor_group)
            return True

        if command == self.P2P_COMMAND.SET_INTERFACE_P2P_DEVICE:
            self.write_wpa("interface " + self.interface)
            return True

        if command == self.P2P_COMMAND.P2P_INVITE_PERSISTENT:
            self.write_wpa(
                "p2p_invite"
                + persistent_postfix
                + " peer=" + mac_addr
                + (" " + self.p2p_connect_opts
                   if self.p2p_connect_opts
                   else "")
            )
            logging.debug('Invite %s to "%s" with %s',
                          mac_addr, self.monitor_group, persistent_postfix)
            return True

        if command == self.P2P_COMMAND.P2P_INVITE_GROUP:
            self.write_wpa(
                "p2p_invite"
                + " group=" + self.monitor_group
                + " peer=" + mac_addr
                + (" " + self.p2p_connect_opts
                   if self.p2p_connect_opts
                   else "")
            )
            logging.debug('Invite %s to "%s"', mac_addr, self.monitor_group)
            return True

        if command == self.P2P_COMMAND.P2P_CONNECT:
            self.last_pwd = self.get_pin(self.pin)
            hide_from_logging([self.last_pwd], "********")
            self.write_wpa(
                "p2p_connect "
                + mac_addr + " "
                + ("pbc" if self.pbc_in_use
                   else self.last_pwd + " display")
                + persistent_postfix
                + (" join" if join else "")
                + (" go_intent=" + str(go_intent) if go_intent is not None else "")
                + (" " + self.p2p_connect_opts
                   if self.p2p_connect_opts
                   else "")
            )
            logging.warning("Connection request " +
                            ("(pbc method)" if self.pbc_in_use else "(PIN method)") +
                            ": %s", mac_addr)
            return True
        return None

    def handle(self, wpa_cli):
        """ handles all events """
        # https://w1.fi/wpa_supplicant/devel/ctrl_iface_page.html

        # Define response messages tokens
        wpa_cli_word = wpa_cli.split()
        if len(wpa_cli_word) == 0:  # remove null line
            return True
        if wpa_cli_word[0] == ">":  # remove prompt
            wpa_cli_word.pop(0)
        if len(wpa_cli_word) == 0:  # remove prompt only line
            return True
        event_name = re.sub(
            r"<[0-9]*>", r"", wpa_cli_word[0], 1
        )  # first word is the event_name
        if event_name == "P2P:":
            event_name = wpa_cli_word[0]
        if len(wpa_cli_word) > 1:
            mac_addr = wpa_cli_word[1]  # second word is generally the mac_addr
        else:
            mac_addr = ""
        dev_name = re.sub(
            r".*name='([^']*).*", r"\1", wpa_cli, 1
        )  # some event have "name="
        p2p_dev_addr = re.sub(
            r".*p2p_dev_addr=([^ ]*).*", r"\1", wpa_cli, 1
        )  # some events have "p2p_dev_addr="
        sa_addr = re.sub(
            r".*sa=([^ ]*).*", r"\1", wpa_cli, 1
        )  # some events have "sa="
        sa_name = "[unknown]"
        if sa_addr and sa_addr in self.addr_register:
            sa_name = self.addr_register[sa_addr]
        device_name_mac_addr = "[unknown]"
        if mac_addr and mac_addr in self.addr_register:
            device_name_mac_addr = self.addr_register[mac_addr]
        device_name = "[unknown]"
        if p2p_dev_addr and p2p_dev_addr in self.addr_register:
            device_name = self.addr_register[p2p_dev_addr]
        pri_dev_type = re.sub(
            r".*pri_dev_type=([^ ]*).*", r"\1", wpa_cli, 1
        )  # some events have "pri_dev_type="
        device_type = self.p2p_primary_device_type['255-0050F204-1']
        if pri_dev_type in self.p2p_primary_device_type:
            device_type = self.p2p_primary_device_type[pri_dev_type]
        dev_passwd_id = re.sub(
            r".*dev_passwd_id=([^ ]*).*", r"\1", wpa_cli, 1
        )  # some events have "dev_passwd_id="
        password_id = 'Unknown'
        if dev_passwd_id.isnumeric():
            password_id = 'Random'
            if int(dev_passwd_id) in self.p2p_password_id:
                password_id = self.p2p_password_id[int(dev_passwd_id)]
        go_intent = re.sub(
            r".*go_intent=([^ ]*).*", r"\1", wpa_cli, 1
        )  # some events have "go_intent="
        ssid_arg = re.sub(
            r'.*ssid="([^"]*).*', r"\1", wpa_cli, 1
        )  # read ssid="<name>"
        persistent_arg = re.sub(
            r".*persistent=([0-9]*).*", r"\1", wpa_cli, 1
        )  # read persistent=number

        if self.warn_on_input_errors(wpa_cli):
            # if ((self.is_enroller and self.wpa_supplicant_errors) or
            #        self.wpa_supplicant_errors > self.max_num_wpa_cli_failures):
            if self.wpa_supplicant_errors > self.max_num_wpa_cli_failures:
                if self.is_enroller:
                    os.write(self.father_slave_fd,
                             "HOSTP2PD_TERMINATE_ENROLLER".encode())
                self.terminate()
                return False
            return True
        self.wpa_supplicant_errors = 0

        # Account "self.statistics"
        if event_name == "HOSTP2PD_ADD_REGISTER":
            stat_tokens = wpa_cli.split("\t")
            if stat_tokens[1] and stat_tokens[2] and stat_tokens[3]:
                self.addr_register[stat_tokens[1]] = stat_tokens[2]
                self.dev_type_register[stat_tokens[1]] = stat_tokens[3]
            return True
        if event_name == "HOSTP2PD_STATISTICS":
            stat_tokens = wpa_cli.split("\t")
            if stat_tokens[1]:
                self.register_statistics("E>" + stat_tokens[1])
            return True
        if (
                wpa_cli == self.last_pwd or event_name == self.last_pwd
        ):  # do not add the pin in statistics
            return True
        event_stat_name = ""
        if event_name:
            event_stat_name = "<P2P>" if event_name in "P2P:" else event_name
        if self.is_enroller:
            if self.can_register_cmds:
                if not self.is_daemon:
                    os.write(
                        self.father_slave_fd,
                        (
                                "HOSTP2PD_STATISTICS"
                                + "\t"
                                + event_stat_name
                                + "\n"
                        ).encode()
                    )
        else:
            if event_stat_name and self.can_register_cmds:
                self.register_statistics(event_stat_name)

        # Startup procedure
        if self.do_activation:
            self.do_activation = False
            if not self.is_enroller:
                self.configure_wpa()
            # Initialize self.pbc_in_use
            if self.pbc_in_use is None:
                self.pbc_in_use = self.get_config_methods(self.pbc_in_use)

            # Initialize config method
            self.write_wpa("p2p_stop_find")
            time.sleep(1)
            if self.pbc_in_use:
                self.write_wpa("set config_methods virtual_push_button")
                self.config_method_in_use = "virtual_push_button"
            else:
                self.write_wpa("set config_methods keypad")
                self.config_method_in_use = "keypad"

            # Announce
            self.write_wpa("p2p_find")
            time.sleep(1)

            # Manage groups
            if self.is_enroller:
                logging.debug(
                    '(enroller) Started on group "%s"', self.monitor_group
                )
                self.find_timing_level = "enroller"
            else:  # Core startup
                if self.ssid_postfix:
                    self.write_wpa("p2p_set ssid_postfix " + self.ssid_postfix)
                self.monitor_group = self.list_or_remove_group(remove=False)
                if self.activate_autonomous_group and not self.monitor_group:
                    self.write_wpa(
                        "p2p_group_add"
                        + (
                            " " + self.p2p_group_add_opts
                            if self.p2p_group_add_opts
                            else ""
                        )
                    )
                    self.group_type = "Autonomous"
                    self.monitor_group = self.list_or_remove_group(
                        remove=False)
                if self.monitor_group:
                    self.ssid_group = self.analyze_existing_group(
                        self.monitor_group
                    )
                else:
                    self.ssid_group = self.list_start_pers_group(
                        start_group=(
                                self.activate_persistent_group
                                and not self.dynamic_group
                        )
                    )
                if self.ssid_group:
                    logging.info(
                        'Configured autonomous/persistent group "%s"',
                        self.ssid_group,
                    )
                if self.monitor_group:
                    logging.info(
                        'Active group interface "%s"', self.monitor_group
                    )
                    self.run_enrol()
                    if not self.group_type:
                        self.group_type = "Existing autonomous/persistent"

                # Announce again
                self.write_wpa("p2p_stop_find")
                time.sleep(1)
                self.write_wpa("p2p_find")

            # Start processing commands
            self.can_register_cmds = True

        # Discard some unrelevant commands or messages
        if event_name == "OK":
            logging.debug("OK received")
            return True
        self.scan_polling = 0  # scan polling is reset by any message different than 'OK' and 'p2p_find'

        if not any(skip in event_name for skip in self.do_not_debug):
            logging.debug(
                "(enroller) event_name: %s" if self.is_enroller
                else "event_name: %s", repr(event_name),
            )

        # <3>CTRL-EVENT-SCAN-STARTED
        if event_name == "CTRL-EVENT-SCAN-STARTED":
            return True

        # <3>CTRL-EVENT-EAP-RETRANSMIT 02:87:01:8c:ce:f6
        if event_name == "CTRL-EVENT-EAP-RETRANSMIT":
            return True

        # <3>CTRL-EVENT-SCAN-RESULTS
        if event_name == "CTRL-EVENT-SCAN-RESULTS":
            return True

        # FAIL-CHANNEL-UNSUPPORTED
        if event_name == "FAIL-CHANNEL-UNSUPPORTED":
            logging.error("The requested channel is not available for P2P. "
                          "(Possibly already in use)")
            return True

        # <3>CTRL-EVENT-DISCONNECTED bssid=de:a6:32:01:82:03 reason=3 locally_generated=1
        if self.is_enroller and event_name == "CTRL-EVENT-DISCONNECTED":
            logging.debug(
                "CTRL-EVENT-DISCONNECTED received: terminating enroller"
            )
            self.count_active_sessions()
            os.write(self.father_slave_fd,
                     "HOSTP2PD_TERMINATE_ENROLLER".encode())
            self.terminate()
            return False

        # <3>RX-PROBE-REQUEST sa=b6:3b:9b:7a:08:96 signal=0
        if self.is_enroller and event_name == "RX-PROBE-REQUEST":
            logging.debug(
                "(enroller) Received RX-PROBE-REQUEST from '%s' (%s)",
                sa_addr,
                sa_name,
            )
            return True

        # <3>CTRL-EVENT-SUBNET-STATUS-UPDATE status=0
        if event_name == "CTRL-EVENT-SUBNET-STATUS-UPDATE":
            return True

        # <3>CTRL-EVENT-EAP-STARTED 56:3b:c6:4a:4a:b3
        if event_name == "CTRL-EVENT-EAP-STARTED":  # only on the GO (Enroller)
            return True

        # <3>CTRL-EVENT-EAP-PROPOSED-METHOD vendor=0 method=1
        if (
                event_name == "CTRL-EVENT-EAP-PROPOSED-METHOD"
        ):  # only on the GO (Enroller)
            logging.debug(
                "(enroller) Proposed method %s %s",
                wpa_cli_word[1],
                wpa_cli_word[2],
            )
            return True

        # <3>WPS-REG-SUCCESS 72:dd:a8:c9:97:0e 811e2280-33d1-5ce8-97e5-6fcf1598c173
        if event_name == "WPS-REG-SUCCESS":
            return True

        # <3>WPS-SUCCESS
        if event_name == "WPS-SUCCESS":
            return True

        # <3>CTRL-EVENT-EAP-FAILURE 56:3b:c6:4a:4a:b3
        if event_name == "CTRL-EVENT-EAP-FAILURE":  # only on the GO (Enroller)
            return True

        # <3>AP-STA-CONNECTED 56:3b:c6:4a:4a:b3 p2p_dev_addr=56:3b:c6:4a:4a:b3
        if self.is_enroller and event_name == "AP-STA-CONNECTED":
            logging.debug(
                "(enroller) Station '%s' (%s) CONNECTED to group '%s'",
                p2p_dev_addr,
                device_name,
                self.monitor_group,
            )
            self.count_active_sessions()
            return True

        # <3>AP-STA-DISCONNECTED 56:3b:c6:4a:4a:b3 p2p_dev_addr=56:3b:c6:4a:4a:b3
        if self.is_enroller and event_name == "AP-STA-DISCONNECTED":
            logging.debug(
                "(enroller) Station '%s' (%s) DISCONNECTED from group '%s'",
                p2p_dev_addr,
                device_name,
                self.monitor_group,
            )
            self.count_active_sessions()
            return True

        # <3>AP-DISABLED
        if self.is_enroller and event_name == "AP-DISABLED":
            logging.debug(
                "(enroller) AP-DISABLED: terminating Enroller on group '%s'",
                self.monitor_group,
            )
            self.count_active_sessions()
            os.write(self.father_slave_fd,
                     "HOSTP2PD_TERMINATE_ENROLLER".encode())
            self.terminate()
            return False

        # <3>WPS-ENROLLEE-SEEN 56:3b:c6:4a:4a:b3 811e2280-33d1-5ce8-97e5-6fcf1598c173 10-0050F204-5 0x4388 0 1 [test]
        if event_name == "WPS-ENROLLEE-SEEN" and self.is_enroller:  # only on the GO (Enroller)
            e_device_name = re.sub(
                r"^\[(.*)\]$", r"\1", " ".join(wpa_cli_word[7:]), 1
            )
            device_type = self.p2p_primary_device_type['255-0050F204-1']
            if wpa_cli_word[3] in self.p2p_primary_device_type:
                device_type = self.p2p_primary_device_type[wpa_cli_word[3]]
            self.addr_register[mac_addr] = e_device_name
            self.dev_type_register[mac_addr] = device_type
            os.write(self.father_slave_fd, ("HOSTP2PD_ADD_REGISTER" + "\t"
                                            + mac_addr + "\t" + e_device_name + "\t" + device_type
                                            + "\n").encode())
            logging.debug(
                'Enrolling %s "%s" with address "%s".',
                device_type,
                e_device_name,
                mac_addr,
            )
            if self.pbc_in_use and (
                    self.pbc_white_list == [] or dev_name in self.pbc_white_list
            ):
                self.write_wpa("wps_pbc " + mac_addr)
            else:
                self.last_pwd = self.get_pin(self.pin)
                hide_from_logging([self.last_pwd], "********")
                self.write_wpa("wps_pin " + mac_addr + " " + self.last_pwd)
            return True

        if self.is_enroller:  # processing enroller commands terminates here
            return self.default_workflow(event_stat_name)

        # ___________________________________________________________________________________________
        if event_name == "HOSTP2PD_TERMINATE_ENROLLER":
            self.terminate_enrol()
            self.find_timing_level = "normal"
            self.monitor_group = None
            return True

        if event_name == "HOSTP2PD_ACTIVE_SESSIONS":
            stat_tokens = wpa_cli.split("\t")
            if stat_tokens[1]:
                n_stations = stat_tokens[1]
                self.statistics["n_stations"] = n_stations
                if (
                        n_stations == 0
                        and self.dynamic_group
                        and not self.activate_persistent_group
                ):
                    if self.monitor_group:
                        self.write_wpa(
                            "p2p_group_remove " + self.monitor_group)
                        self.external_program(
                            self.EXTERNAL_PROG_ACTION.STOP_GROUP,
                            self.monitor_group)
                        self.monitor_group = ""
                    else:
                        self.monitor_group = self.list_or_remove_group(True)
                        self.external_program(
                            self.EXTERNAL_PROG_ACTION.STOP_GROUP)
                    time.sleep(3)
                self.write_wpa("p2p_find")
            return True

        # <3>P2P: Reject scan trigger since one is already pending
        if "P2P: Reject scan trigger since one is already pending" in wpa_cli:
            self.scan_polling += 1
            self.find_timing_level = "long"
            return True

        # <3>P2P-GROUP-FORMATION-SUCCESS
        if event_name == "P2P-GROUP-FORMATION-SUCCESS":
            self.find_timing_level = "connect"
            return True

        # <3>P2P-DEVICE-FOUND ae:e2:d3:41:27:14 p2p_dev_addr=ae:e2:d3:41:a7:14 pri_dev_type=3-0050F204-1 name='test' config_methods=0x0 dev_capab=0x25 group_capab=0x81 vendor_elems=1 new=1
        if event_name == "P2P-DEVICE-FOUND" and mac_addr:
            self.addr_register[mac_addr] = dev_name
            self.dev_type_register[mac_addr] = device_type
            if self.is_enroller:
                os.write(self.father_slave_fd, ("HOSTP2PD_ADD_REGISTER" + "\t"
                                                + mac_addr + "\t" + dev_name + "\t" + device_type
                                                + "\n").encode())
            logging.debug(
                'Found %s with name "%s" and address "%s".',
                device_type,
                dev_name,
                mac_addr,
            )
            return True

        # <3>P2P-GO-NEG-REQUEST ee:54:44:24:70:df dev_passwd_id=1 go_intent=6
        # dev_passwd_id=<value> parameter indicates which config method is being requested.
        if event_name == "P2P-GO-NEG-REQUEST" and mac_addr:  # This does not provide "dev_name"
            self.find_timing_level = "connect"
            logging.debug(
                "P2P-GO-NEG-REQUEST received, password ID=%s, go_intent=%s",
                password_id, go_intent)
            if self.pbc_in_use and not self.monitor_group:
                if not mac_addr in self.addr_register:
                    logging.error(
                        'While pbc is in use, cannot find name '
                        'related to address "%s".',
                        mac_addr,
                    )
                    return True
                if (
                        self.pbc_white_list != []
                        and not self.addr_register[mac_addr] in self.pbc_white_list
                ):
                    self.rotate_config_method()
                    return True
            if self.monitor_group:
                logging.debug(
                    'Connecting station with address "%s" '
                    'to existing group "%s".',
                    mac_addr,
                    self.monitor_group,
                )
                persistent_postfix = ""
                if not self.pbc_in_use and dev_passwd_id != '1':
                    logging.error(
                        'Wrong dev_passwd_id received by address "%s": %s',
                        mac_addr,
                        dev_passwd_id
                    )
                    return True
                if self.pbc_in_use and dev_passwd_id != '4':
                    logging.error(
                        'Wrong dev_passwd_id received by address "%s": %s',
                        mac_addr,
                        dev_passwd_id
                    )
                    return True
                logging.error(
                    'Invalid negotiation request from station with address '
                    '"%s".', mac_addr)
                # self.write_wpa("p2p_group_remove " + self.monitor_group)
                # self.monitor_group = ""
                # self.p2p_command(
                #    self.P2P_COMMAND.P2P_CONNECT, mac_addr)
                return True
            else:
                logging.debug(
                    'Connecting station with address "%s".', mac_addr)
                self.start_session(mac_addr)
                return True

        if (
                event_name == "P2P-PROV-DISC-PBC-REQ"
                or event_name == "P2P-PROV-DISC-ENTER-PIN"
                or (event_name == "P2P-PROV-DISC-SHOW-PIN"
                    and len(wpa_cli_word) > 2)
        ) and mac_addr:
            self.find_timing_level = "connect"
            self.p2p_connect_time = 0

            # <3>P2P-PROV-DISC-ENTER-PIN 02:5e:6d:3d:99:8b p2p_dev_addr=02:5e:6d:3d:99:8b pri_dev_type=10-0050F204-5 name='test' config_methods=0x188 dev_capab=0x25 group_capab=0x0
            if event_name == "P2P-PROV-DISC-ENTER-PIN":
                logging.error(
                    "%s '%s' with name '%s' asked "
                    "to enter its PIN to connect",
                    device_type,
                    mac_addr,
                    dev_name,
                )
                self.dev_type_register[mac_addr] = device_type
                # self.write_wpa("p2p_reject " + mac_addr)

            # <3>P2P-PROV-DISC-PBC-REQ ca:d5:d5:38:d6:69 p2p_dev_addr=ca:d5:d5:38:d6:69 pri_dev_type=10-0050F204-5 name='test' config_methods=0x88 dev_capab=0x25 group_capab=0x0
            if event_name == "P2P-PROV-DISC-PBC-REQ" and not self.pbc_in_use:
                logging.error(
                    "%s '%s' with name '%s' asked to connect with PBC",
                    device_type,
                    mac_addr,
                    dev_name,
                )
                self.dev_type_register[mac_addr] = device_type
                # self.write_wpa("p2p_reject " + mac_addr)

            # <3>P2P-PROV-DISC-SHOW-PIN ee:54:44:24:70:df 93430999 p2p_dev_addr=ee:54:44:24:70:df pri_dev_type=10-0050F204-5 name='test' config_methods=0x188 dev_capab=0x25 group_capab=0x0
            if event_name == "P2P-PROV-DISC-SHOW-PIN" and self.pbc_in_use:
                logging.error(
                    "%s '%s' with name '%s' asked to connect with PIN",
                    device_type,
                    mac_addr,
                    dev_name,
                )
                self.dev_type_register[mac_addr] = device_type
                # self.write_wpa("p2p_reject " + mac_addr)

            if event_name == "P2P-PROV-DISC-SHOW-PIN" and not self.pbc_in_use:
                if self.monitor_group:
                    logging.debug(
                        'Connecting station with name "%s" and address "%s" '
                        "using PIN to existing group.",
                        dev_name,
                        mac_addr,
                    )
                    self.in_process_enrol(
                        dev_name, mac_addr, self.ENROL_TYPE.PIN
                    )
                    return True
                else:
                    self.start_session(mac_addr)
                    return True

            if (
                    event_name == "P2P-PROV-DISC-PBC-REQ"
                    and self.pbc_in_use
                    and dev_name
            ):
                if (
                        self.pbc_white_list != []
                        and not dev_name in self.pbc_white_list
                ):
                    self.rotate_config_method()
                    return True
                if self.monitor_group:
                    logging.debug(
                        'Connecting station with name "%s" and address "%s" '
                        "using PBC to existing group.",
                        dev_name,
                        mac_addr,
                    )
                    self.in_process_enrol(
                        dev_name, mac_addr, self.ENROL_TYPE.PBC
                    )
                    return True
                else:
                    self.start_session(mac_addr)
                    return True

            logging.debug(
                'Invalid connection request. Event="%s", station name="%s", '
                'address="%s", group="%s", persistent group="%s".',
                event_name,
                dev_name,
                mac_addr,
                self.monitor_group,
                self.ssid_group,
            )
            if self.pbc_in_use:
                # self.write_wpa("p2p_remove_client " + mac_addr)
                self.write_wpa("p2p_prov_disc " + mac_addr + " pbc")
            else:
                # self.write_wpa("p2p_remove_client " + mac_addr)
                self.write_wpa("p2p_prov_disc " + mac_addr + " keypad")
            self.in_process_enrol(
                dev_name, mac_addr, self.ENROL_TYPE.PIN
            )  # this has the effect to remove the invitation at the end of the failure
            return True

        # <3>AP-STA-CONNECTED ee:54:44:24:70:df p2p_dev_addr=ee:54:44:24:70:df
        if event_name == "AP-STA-CONNECTED":
            self.p2p_connect_time = 0
            self.find_timing_level = "normal"
            logging.warning(
                "Station '%s' (%s) CONNECTED to group '%s'",
                p2p_dev_addr,
                device_name,
                self.monitor_group,
            )
            self.external_program(
                self.EXTERNAL_PROG_ACTION.CONNECT,
                p2p_dev_addr, device_name, self.monitor_group)
            return True

        # <3>AP-STA-DISCONNECTED ee:54:44:24:70:df p2p_dev_addr=ee:54:44:24:70:df
        if event_name == "AP-STA-DISCONNECTED":
            logging.warning(
                'Station "%s" (%s) disconnected.', p2p_dev_addr, device_name
            )
            self.external_program(
                self.EXTERNAL_PROG_ACTION.DISCONNECT,
                p2p_dev_addr, device_name, self.monitor_group)
            self.p2p_connect_time = 0
            self.find_timing_level = "normal"
            return True

        # <3>P2P-PROV-DISC-FAILURE p2p_dev_addr=b6:3b:9b:7a:08:96 status=1
        if event_name == "P2P-PROV-DISC-FAILURE":
            logging.warning(
                'Provision discovery failed for station "%s" (%s).',
                p2p_dev_addr,
                device_name,
            )
            self.p2p_connect_time = 0
            self.find_timing_level = "normal"
            if self.dynamic_group and not self.activate_persistent_group:
                if self.monitor_group:
                    self.write_wpa("p2p_group_remove " + self.monitor_group)
                    self.external_program(
                        self.EXTERNAL_PROG_ACTION.STOP_GROUP,
                        self.monitor_group)
                    self.monitor_group = ""
                else:
                    self.monitor_group = self.list_or_remove_group(True)
                    self.external_program(
                        self.EXTERNAL_PROG_ACTION.STOP_GROUP)
                time.sleep(3)
            self.write_wpa("p2p_find")
            return True

        # <3>P2P-INVITATION-ACCEPTED sa=5a:5f:0a:96:ee:5e persistent=4 freq=5220
        if event_name == "P2P-INVITATION-ACCEPTED":
            logging.warning(
                "Accepted invitation to persistent group %s.", persistent_arg
            )
            self.find_timing_level = "connect"
            self.external_program(
                self.EXTERNAL_PROG_ACTION.START_GROUP, persistent_arg)
            return True

        if event_name == "P2P-FIND-STOPPED":
            if time.time() > self.p2p_connect_time + self.min_conn_delay:
                self.write_wpa("p2p_find")
            return True

        # <3>P2P-DEVICE-LOST p2p_dev_addr=02:87:01:8c:ce:f6
        if event_name == "P2P-DEVICE-LOST":
            logging.info(
                'Received P2P-DEVICE-LOST, station "%s" (%s)',
                p2p_dev_addr,
                device_name,
            )
            return True

        if event_name == "WPS-TIMEOUT":
            logging.error("Received WPS-TIMEOUT")
            self.find_timing_level = "normal"
            self.p2p_connect_time = 0
            return True

        #  <3>P2P-GO-NEG-SUCCESS role=GO freq=5200 ht40=1 peer_dev=ea:cb:a8:16:a5:d9 peer_iface=ea:cb:a8:16:a5:d9 wps_method=PBC, event_name=P2P-GO-NEG-SUCCESS
        if event_name == "P2P-GO-NEG-SUCCESS":
            logging.debug("P2P-GO-NEG-SUCCESS")
            self.find_timing_level = "connect"
            return True

        if event_name == "P2P-GROUP-STARTED" and wpa_cli_word[1]:
            self.find_timing_level = "connect"
            self.monitor_group = wpa_cli_word[1]
            if ssid_arg:
                self.ssid_group = ssid_arg
            logging.warning(
                "Autonomous group started: %s", self.monitor_group)
            self.run_enrol()
            return True

        # <3>P2P-GROUP-REMOVED p2p-wlan0-0 GO reason=REQUESTED
        # <3>P2P-GROUP-REMOVED p2p-wlan0-22 GO reason=FORMATION_FAILED
        if event_name == "P2P-GROUP-REMOVED":
            self.terminate_enrol()
            self.find_timing_level = "normal"
            if self.monitor_group:
                if self.monitor_group == wpa_cli_word[1]:
                    logging.info(
                        'Removed group "%s" of type "%s", %s',
                        self.monitor_group,
                        wpa_cli_word[2],
                        wpa_cli_word[3],
                    )
                else:
                    logging.error(
                        'Even if active group was "%s", '
                        'removed group "%s" of type "%s", %s',
                        self.monitor_group,
                        wpa_cli_word[1],
                        wpa_cli_word[2],
                        wpa_cli_word[3],
                    )
            else:
                logging.info(
                    'Could not create group "%s" of type "%s", %s',
                    wpa_cli_word[1],
                    wpa_cli_word[2],
                    wpa_cli_word[3],
                )
            self.monitor_group = None
            if time.time() > self.p2p_connect_time + self.min_conn_delay:
                self.write_wpa("p2p_find")
            return True

        # <3>P2P-GROUP-FORMATION-FAILURE
        if event_name == "P2P-GROUP-FORMATION-FAILURE":
            self.monitor_group = None
            self.p2p_connect_time = 0
            self.find_timing_level = "normal"
            if self.dynamic_group and not self.activate_persistent_group:
                self.num_failures += 1
                if self.num_failures < self.max_num_failures:
                    logging.warning(
                        "Retrying group formation: %s of %s",
                        self.num_failures,
                        self.max_num_failures,
                    )
                    if self.num_failures > 1:
                        time.sleep(2)
                    self.start_session()  # use the last value of self.station
                else:
                    logging.error("Group formation failed.")
                    self.num_failures = 0
                    self.external_program(
                        self.EXTERNAL_PROG_ACTION.STOP_GROUP)
                    self.write_wpa("p2p_find")
                return True
            else:
                logging.critical(
                    "Group formation failed (P2P-GROUP-FORMATION-FAILURE)."
                )
                return True
                # self.terminate()
                # return False

        if event_name == "P2P-GO-NEG-FAILURE":
            self.find_timing_level = "normal"
            self.p2p_connect_time = 0
            if self.dynamic_group and not self.activate_persistent_group:
                self.num_failures += 1
                if self.num_failures < self.max_num_failures:
                    logging.warning(
                        "Retrying negotiation: %s of %s",
                        self.num_failures,
                        self.max_num_failures,
                    )
                    if self.num_failures > 1:
                        time.sleep(2)
                    self.start_session()  # use the last value of self.station
                else:
                    logging.error("Cannot negotiate P2P Group Owner.")
                    self.num_failures = 0
                    self.external_program(
                        self.EXTERNAL_PROG_ACTION.STOP_GROUP)
                    self.write_wpa("p2p_find")
                return True

        if event_name == "FAIL":
            self.find_timing_level = "normal"
            self.p2p_connect_time = 0
            if self.dynamic_group and not self.activate_persistent_group:
                logging.info("Connection failed")
                self.monitor_group = self.list_or_remove_group(True)
                self.num_failures += 1
                if self.num_failures < self.max_num_failures:
                    if self.num_failures > 1:
                        time.sleep(2)
                    self.start_session()  # use the last value of self.station
                else:
                    self.num_failures = 0
                    self.external_program(
                        self.EXTERNAL_PROG_ACTION.STOP_GROUP)
                    self.write_wpa("p2p_find")
                return True

        return self.default_workflow(event_stat_name)
