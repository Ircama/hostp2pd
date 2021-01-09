#!/usr/bin/env python3
# -*- coding: utf-8 -*-
##########################################################################
# hostp2pd - The Wi-Fi Direct Session Manager
# wpa_cli controller of Wi-Fi Direct connections handled by wpa_supplicant
# https://github.com/Ircama/hostp2pd
# (C) Ircama 2021 - CC-BY-NC-SA-4.0
#########################################################################
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
from ctypes.util import find_library
from select import select
import signal
from distutils.spawn import find_executable
from multiprocessing import Process, Manager
from .__version__ import __version__


class RedactingFormatter(object):
    def __init__(self, orig_formatter, patterns, mask):
        self.orig_formatter = orig_formatter
        self._patterns = patterns
        self._mask = mask

    def format(self, record):
        msg = self.orig_formatter.format(record)
        for pattern in self._patterns:
            msg = msg.replace(pattern, self._mask)
        return msg

    def __getattr__(self, attr):
        return getattr(self.orig_formatter, attr)


def hide_from_logging(password_list, mask):
    root = logging.getLogger()
    if root and root.handlers:
        for h in root.handlers:
            h.setFormatter(RedactingFormatter(
                    h.formatter,
                    patterns=password_list,
                    mask=mask)
                )


def get_type(value, conf_schema):
    if isinstance(value, dict):
        if conf_schema == None: 
            return {key: get_type(value[key], conf_schema) for key in value}
        for key in value:
            if key not in conf_schema:
                logging.critical(
                    'Configuration Error: unkown parameter "%s" '
                    'in configuration file.', key)
                return None
        return {key: get_type(value[key], conf_schema[key]) for key in value}
    else:
        ret_val = "<class 'int'>" if value == None else str(type(value))
        if ret_val == "<class 'int'>" and conf_schema == "<class 'float'>":
            ret_val = conf_schema
        if ret_val == "<class 'NoneType'>":
            ret_val = conf_schema
        if conf_schema != None and conf_schema != ret_val:
            logging.critical(
                'Configuration Error: "%s" shall be "%s" and not "%s".',
                value, conf_schema, ret_val)
            return None
        return ret_val


class HostP2pD:

    ################# Start of static configuration ################################
    select_timeout_secs = { # see read_wpa() and find_timing_level
        'normal':    10, # seconds. Period to send p2p_find refreshes
        'connect':   90, # seconds. Increased timing while p2p_connect
        'long':     600,  # seconds. Period to send p2p_find refreshes after exceeding self.max_scan_polling
        'enroller': 600  # seconds. Period used by the enroller
    }
    p2p_client = 'wpa_cli' # wpa_cli program name
    min_conn_delay = 40 # seconds delay before issuing another p2p_connect or enroll
    max_num_failures = 3 # max number of retries for a p2p_connect
    max_num_wpa_cli_failures = 20 # max number of wpa_cli errors
    max_scan_polling = 2 # max number of p2p_find consecutive polling (0=infinite number)
    pbc_in_use = None # Use methdod selected in config. (False=keypad, True=pbc, None=wpa_supplicant.conf)
    activate_persistent_group = True # Activate a persistent group at process startup
    activate_autonomous_group = False # Activate an autonomous group at process startup
    persistent_network_id = None # persistent group network number (None = first in wpa_supplicant config.)
    max_negotiation_time = 120 # seconds. Time for a station to enter the PIN
    dynamic_group = False # allow removing group after a session disconnects
    config_file = None # default YAML configuration file
    password = '00000000' # default password
    force_logging = None # default force_logging
    interface = 'p2p-dev-wlan0' # default interface
    run_program = '' # default run_program
    pbc_white_list = [] # default name white list for push button (pbc) enrolment
    conf_schema = '''
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
pbc_in_use: <class 'bool'>
activate_persistent_group: <class 'bool'>
activate_autonomous_group: <class 'bool'>
persistent_network_id: <class 'int'>
max_negotiation_time: <class 'float'>
dynamic_group: <class 'bool'>
password: <class 'str'>
force_logging: <class 'bool'>
interface: <class 'str'>
run_program: <class 'str'>
pbc_white_list: <class 'list'>
'''
    ################# End of static configuration ##################################


    class THREAD:
        STOPPED = 0
        STARTING = 1
        ACTIVE = 2
        PAUSED = 3
        state = [ 'Stopped', 'Starting', 'Active', 'Paused' ]


    def read_configuration(self,
            configuration_file,
            default_level=logging.WARNING,
            env_key=os.path.basename(Path(__file__).stem).upper() + '_CFG',
            do_activation=False):
        successs = True
        if configuration_file:
            self.config_file = configuration_file
        else:
            self.config_file = Path(__file__).stem + '.yaml'
        if not os.path.exists(self.config_file):
            self.config_file = os.path.join(
                os.path.dirname(Path(__file__)), 'hostp2pd.yaml')
        value = os.getenv(env_key, None)
        if value:
            self.config_file = value
        if self.config_file == '<stdin>':
            self.config_file = '/dev/stdin'
        if os.path.exists(self.config_file) and configuration_file != 'reset':
            try:
                with open(self.config_file, 'rt') as f:
                    try:
                        config = yaml.safe_load(f.read())
                    except Exception as e:
                        config = None
                        logging.critical(
                            'Cannot parse YAML configuration file "%s": %s.',
                            self.config_file, e)
                        successs = False
                    # Logging configuration ('logging' section)
                    if self.force_logging == None:
                        if config and 'logging' in config:
                            try:
                                logging.config.dictConfig(config['logging'])
                            except Exception as e:
                                logging.basicConfig(level=default_level)
                                logging.critical(
                                    'Wrong "logging" section in YAML configuration file "%s": %s.',
                                    self.config_file, e)
                                successs = False
                        else:
                            logging.warning(
                                'Missing "logging" section in YAML configuration file "%s".',
                                self.config_file)
                            logging.basicConfig(level=default_level)
                            successs = False
                    else:
                        self.logger.setLevel(self.force_logging)
                    # Configuration settings ('hostp2pd' section)
                    if config and 'hostp2pd' in config and config['hostp2pd']:
                        if hasattr(yaml, 'FullLoader'):
                            yaml_conf_schema = yaml.load(self.conf_schema, Loader=yaml.FullLoader)
                        else:
                            yaml_conf_schema = yaml.load(self.conf_schema)
                        types = get_type(config['hostp2pd'], yaml_conf_schema)
                        if types:
                            for key, val in types.items():
                                if val == None:
                                    logging.critical('Invalid parameter: "%s".', key)
                                    types = None
                                    successs = False
                        if types:
                            try:
                                self.__dict__.update(config['hostp2pd'])
                            except Exception as e:
                                logging.critical(
                                    'Wrong "hostp2pd" section in YAML configuration file "%s": %s.',
                                    self.config_file, e)
                                successs = False
                    else:
                        logging.debug(
                            'Missing "hostp2pd" section in YAML configuration file "%s".',
                            self.config_file)
                        #successs = False
            except (PermissionError, FileNotFoundError) as e:
                logging.critical('Cannot open YAML configuration file "%s": %s.',
                    self.config_file, e)
                successs = False
        else:
            logging.basicConfig(level=default_level)
            if configuration_file == 'reset':
                logging.debug("Resetting configuration to default values")
                self.config_file = None
                if self.force_logging == None:
                    logging.basicConfig(level=default_level)
                else:
                    self.logger.setLevel(self.force_logging)
            else:
                if self.config_file:
                    logging.critical(
                        'Cannot find YAML configuration file "%s".',
                        self.config_file)
                    successs = False
        #logging.debug("YAML configuration logging pathname: %s", self.config_file)
        hide_from_logging([self.password], "********")
        if do_activation:
            if not self.is_enroller:
                logging.debug(
                    'Reloading "wpa_supplicant" configuration file...')
                self.threadState = self.THREAD.PAUSED
                time.sleep(0.1)
                self.write_wpa('ping')
                time.sleep(0.1)
                self.write_wpa('ping')
                time.sleep(0.1)
                self.write_wpa('reconfigure')
                cmd_timeout = time.time()
                while True: # Wait 'OK' before continuing
                    input_line = self.read_wpa()
                    if input_line == None:
                        logging.error(
                            'Internal Error (read_configuration): '
                            'read_wpa() abnormally terminated')
                        time.sleep(0.1)
                        continue
                    logging.debug("(reconfigure) Read '%s'", input_line)
                    if self.warn_on_input_errors(input_line):
                        continue
                    if time.time() > cmd_timeout + self.min_conn_delay:
                        logging.debug(
                            'Terminating reloading "wpa_supplicant" configuration file after timeout '
                            'of %s seconds', self.min_conn_delay)
                        break
                    if 'OK' in input_line:
                        logging.debug(
                            '"wpa_supplicant" configuration reloaded.')
                        break
                self.threadState = self.THREAD.ACTIVE
            self.do_activation = True
        if successs:
            if self.check_enrol():
                os.kill(self.enroller.pid, signal.SIGHUP) # Ask the enroller to reload its configuration
            logging.debug('Configuration successfully loaded.')
        else:
            logging.error('Loading configuration failed.')
        return successs

    def reset(self, sleep=0):
        """ returns all settings to their defaults """
        logging.debug(
            "Resetting statistics and sleeping for %s seconds",
            sleep)
        time.sleep(sleep)
        self.statistics = {}
        self.addr_register = {}


    def set_defaults(self):
        self.p2p_connect_time = 0 # 0=run function (set by start_session() and enrol())

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
        self.find_timing_level = 'normal'
        self.config_method_in_use = ''
        self.use_enroller = True # False = run obsolete procedure instead of Enroller
        self.is_enroller = False # False if I am Core, True if I am Enroller
        self.enroller = None # Core can check this to know Enroller is active
        self.terminate_is_active = False # silence read/write errors if terminating
        self.statistics = {}
        self.addr_register = {}
        self.is_daemon = False


    def __init__(
            self,
            config_file=config_file,
            interface=interface,
            run_program=run_program,
            force_logging=force_logging,
            pbc_white_list=pbc_white_list,
            password=password):

        os.umask(0o077) # protect reserved information in logging
        self.logger = logging.getLogger()
        self.set_defaults()

        # Argument handling
        self.config_file = config_file
        self.interface = interface
        self.run_program = run_program
        self.force_logging = force_logging
        self.pbc_white_list = pbc_white_list
        self.password = password


    def start_process(self):
        # make a new pty
        self.master_fd, self.slave_fd = pty.openpty()
        self.slave_name = os.ttyname(self.slave_fd)
        
        # Disable echo
        no_echo = termios.tcgetattr(self.slave_fd)
        no_echo[3] = no_echo[3] & ~termios.ECHO # lflag
        termios.tcsetattr(self.slave_fd, termios.TCSADRAIN, no_echo)
        
        # Start process connected to the slave pty
        try:
            self.process = subprocess.Popen(
                    [self.p2p_client, '-i', self.interface],
                    #shell=True,
                    stdin=self.slave_fd,
                    stdout=self.slave_fd,
                    stderr=self.slave_fd,
                    bufsize=1,
                    universal_newlines=True
                )
        except FileNotFoundError as e:
            logging.critical(
                'PANIC - Cannot run "wpa_cli" software: %s', e)
            return False
        return True


    def __enter__(self):
        """ Activated when starting the Context Manager"""
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
        """ Activated when ending the Context Manager"""
        self.terminate()
        return False # don't suppress any exception


    def terminate(self):
        """ hostp2pd termination procedure """
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
        if self.process != None:
            self.process.terminate()
            try:
                self.process.wait(1)
            except:
                logging.debug("wpa_cli process not terminated.")
            self.set_defaults()
        logging.debug("Terminated.")
        return True


    def run_enrol(self, child=False):
        """ Core starts the Enroller child; child activates itself """
        if not child and self.check_enrol():
            return # Avoid double instance of the Enroller process
        if child: # I am Enroller
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
            signal.SIGTERM: lambda signum, frame: self.terminate();
            signal.SIGINT: lambda signum, frame: self.terminate();
            signal.signal( # Allow reloading enroller configuration with SIGHUP
                signal.SIGHUP, lambda signum, frame: self.read_configuration(
                    configuration_file=self.config_file,
                    do_activation=True)
                )
            try:
                self.run()
            except KeyboardInterrupt:
                logging.debug("Enroller interrupted.")
                self.terminate()
                return None
        else: # I am Core
            self.enroller = Process(
                target=self.run_enrol,
                args=(True,)
            )
            self.enroller.daemon = True
            self.enroller.start()
            logging.debug("Starting enroller process with PID %s",
                self.enroller.pid)


    def check_enrol(self):
        """ Core checks whether Enroller process is active """
        if (self.use_enroller and
                not self.is_enroller and
                self.enroller != None and
                self.enroller.is_alive() and
                    self.enroller.pid > 0):
            return True
        return False


    def terminate_enrol(self):
        """ Core terminates active Enroller process """
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
        if (os.getppid() == 1 and os.getpgrp() == os.getsid(0)):
            self.is_daemon = True
        if not self.is_enroller:
            threading.current_thread().name = "Core"
        if self.is_enroller or self.process == None:
            if not self.start_process():
                return
        self.read_configuration(
            configuration_file=self.config_file)
        if self.activate_persistent_group and self.activate_autonomous_group:
            logging.error('Error: "activate_persistent_group" '
            'and "activate_autonomous_group" are both active. '
            'Considering peristent group.')
            self.activate_autonomous_group = False

        if self.is_enroller:
            logging.info(
                'Enroller subprocess for group "%s" started',
                self.monitor_group)
        else:
            logging.warning(
                '__________'
                'hostp2pd Service started (v%s) '
                'PID=%s, PPID=%s, PGRP=%s, SID=%s, is_daemon=%s'
                '__________',
                    __version__, os.getpid(), os.getppid(),
                    os.getpgrp(), os.getsid(0), self.is_daemon)

        self.threadState = self.THREAD.ACTIVE

        """ main loop """
        time.sleep(0.3)
        while self.threadState != self.THREAD.STOPPED:

            if self.threadState == self.THREAD.PAUSED:
                time.sleep(0.1)
                continue

            # get the command and process it
            self.cmd = self.read_wpa()
            if self.cmd == None:
                self.terminate()
                return
            if self.threadState == self.THREAD.STOPPED:
                return
            logging.debug(
                "(enroller) recv: %s" if self.is_enroller else "recv: %s",
                repr(self.cmd))
            if not self.handle(self.cmd):
                self.threadState = self.THREAD.STOPPED


    def read_wpa(self):
        """ reads from wpa_cli until the next newline
            Returned value: void string (no data),
            or data (valued string), or None (error)
        """
        buffer = ""

        try:
            while True:
                if (self.find_timing_level == 'normal' and
                        self.max_scan_polling > 0 and
                        self.scan_polling >= self.max_scan_polling):
                    self.find_timing_level = 'long'
                timeout = self.select_timeout_secs[self.find_timing_level]
                reads, _, _ = select([ self.master_fd ], [], [], timeout)
                if len(reads) > 0:
                    c = os.read(self.master_fd, 1).decode('utf8', 'ignore')
                else:
                    # Here some periodic tasks are handled:
                    
                    # Controlling whether an active Enroller died
                    if self.process != None:
                        ret = self.process.poll()
                        if ret != None: # Enroller died with ret code
                            logging.critical(
                                'wpa_cli died with return code %s.'
                                ' Terminating hostp2pd.', ret)
                            os.kill(os.getpid(), signal.SIGTERM)

                    # Controlling frequency of periodic "p2p_find" and sending it
                    if (self.max_scan_polling > 0 and
                            self.scan_polling > self.max_scan_polling):
                        logging.info(
                            "Exceeded number of p2p_find pollings "
                            "after read timeout of %s seconds: %s",
                            timeout, self.scan_polling)
                    else:
                        self.scan_polling += 1
                        logging.debug(
                            'p2p_find polling after read timeout '
                            'of %s seconds: %s of %s',
                            timeout, self.scan_polling, self.max_scan_polling)
                        self.write_wpa("p2p_find")
                    continue

                if c == '\n':
                    break # complete the read operation and does not include the newline

                if c == '\r':
                    continue # skip carriage returns

                buffer += c
        except TypeError as e:
            if self.master_fd == None:
                logging.debug("Process interrupted.")
            else:
                logging.critical("PANIC - Internal TypeError in read_wpa(): %s", e,
                    exc_info=True)
            return None # error
        except OSError as e:
            if e.errno == errno.EBADF or e.errno == errno.EIO: # [Errno 9] Bad file descriptor/[Errno 5] Input/output error
                logging.debug("Read interrupted.")
            else:
                logging.critical("PANIC - Internal OSError in read_wpa(): %s", e,
                    exc_info=True)
            return None # error
        except Exception as e:
            if  self.terminate_is_active:
                logging.debug("Read interrupted: %s", e)
                return None # error
            logging.critical("PANIC - Internal error in read_wpa(): %s", e,
                exc_info=True)

        return buffer


    def write_wpa(self, resp):
        """ write to wpa_cli """
        logging.debug("(enroller) Write: %s" if self.is_enroller else "Write: %s",
            repr(resp))
        resp += '\n'
        try:
            return os.write(self.master_fd, resp.encode())
        except TypeError as e:
            if self.master_fd == None:
                logging.debug("Process interrupted.")
            else:
                logging.critical("PANIC - Internal TypeError in write_wpa(): %s",
                    e, exc_info=True)
            return None # error
        except Exception as e:
            if not self.terminate_is_active:
                logging.critical("PANIC - Internal error in write_wpa(): %s", e,
                    exc_info=True)
            return None # error

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


    def start_session(self, station = None):
        if time.time() < self.p2p_connect_time + self.min_conn_delay:
            logging.debug('Will not p2p_conect due to unsufficient p2p_connect_time')
            return
        self.find_timing_level = 'connect'
        if station:
            self.station = station
        else:
            station = self.station
        if not station or station == None:
            return
        self.external_program("stop")
        persistent_postfix = ""
        if self.activate_persistent_group and self.dynamic_group:
            persistent_postfix = " persistent"
            if self.persistent_network_id != None:
                persistent_postfix += "=" + self.persistent_network_id
        if self.pbc_in_use:
            self.write_wpa("p2p_connect " + station + " pbc" +
                persistent_postfix)
            logging.warning('Connection request (pbc method): %s', station)
        else:
            self.write_wpa(
                "p2p_connect " + station + " " + self.password + ' display' +
                     persistent_postfix)
            logging.warning('Connection request (PIN method): %s', station)
        self.p2p_connect_time = time.time()
        self.group_type = 'Negotiated (always won)'


    def list_or_remove_group(self, remove=False):
        """ list or remove p2p groups; group name is returned """
        logging.debug(
            'Starting list_or_remove_group procedure. remove="%s"', remove)
        self.write_wpa("interface")
        self.write_wpa("ping")
        monitor_group = None
        wait_cmd = 0
        cmd_timeout = time.time()
        while True:
            input_line = self.read_wpa()
            if input_line == None:
                logging.error(
                    'Internal Error (list_or_remove_group): '
                    'read_wpa() abnormally terminated')
                time.sleep(0.1)
                continue
            logging.debug("reading '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.debug(
                    'Terminating group list/deletion procedure '
                    'after timeout of %s seconds.',
                    self.min_conn_delay)
                break
            if "P2P-GROUP-REMOVED " in input_line:
                self.p2p_connect_time = 0
                self.find_timing_level = 'normal'
                logging.debug(
                    'Received %s. Terminating group list/deletion procedure.',
                    input_line)
                break
            if "PONG" in input_line and not wait_cmd:
                logging.debug('Terminating group list/deletion. Group="%s".',
                    monitor_group)
                break
            tokens = input_line.split('-')
            if len(tokens) != 3:
                continue
            if tokens[0] != 'p2p':
                continue
            if tokens[2].isnumeric() and not '>' in input_line:
                monitor_group = input_line
                if remove:
                    logging.debug(
                        'Removing "%s": %s group %s of interface %s',
                        input_line, tokens[0], tokens[2], tokens[1])
                    self.write_wpa("p2p_group_remove " + monitor_group)
                    wait_cmd = time.time()
                    monitor_group = None
                    logging.warning("removed %s", input_line)
                    time.sleep(2)
                    self.external_program("start")
                else:
                    logging.debug(
                        'Found "%s": %s group %s of interface %s',
                        input_line, tokens[0], tokens[2], tokens[1])
        return monitor_group


    def list_start_pers_group(self, start_group=False):
        """ list or start p2p persistent group; ssid (or None) is returned """
        logging.debug(
            'Starting list_start_pers_group procedure. start_group="%s"',
            start_group)
        ssid = None
        if start_group and self.monitor_group:
            logging.error("Group '%s' already active", self.monitor_group)
            return None
        self.write_wpa("list_networks")
        self.write_wpa("ping")
        wait_cmd = 0
        cmd_timeout = time.time()
        while True:
            input_line = self.read_wpa()
            if input_line == None:
                logging.error(
                    'Internal Error (list_start_pers_group): '
                    'read_wpa() abnormally terminated')
                time.sleep(0.1)
                continue
            logging.debug("(list_start_pers_group) Read '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.debug(
                    'Terminating persistent group start procedure after timeout of %s seconds.',
                    self.min_conn_delay)
                if self.monitor_group:
                    self.ssid_group = self.analyze_existing_group(
                        self.monitor_group)
                if self.monitor_group:
                    logging.info('Active group interface "%s"',
                        self.monitor_group)
                break
            tokens = input_line.split('\t')
            if "P2P-GROUP-STARTED" in tokens[0]:
                tokens = input_line.split()
                if tokens[0] == '>': # remove prompt
                    tokens.pop(0)
                wait_cmd = 0
                self.monitor_group = tokens[1]
                ssid_arg = re.sub(
                    r'.*ssid="([^"]*).*', r'\1', input_line, 1) # read ssid="<name>"
                if not ssid:
                    ssid = ssid_arg
                logging.info('Persistent group started %s', self.monitor_group)
                logging.debug(
                    'Persistent group activation procedure completed. ssid="%s"',
                    ssid)
                return ssid
            if 'OK' in input_line:
                continue
            if 'FAIL' in input_line:
                logging.error('Cannot start persistent group.')
                ssid = None
                break
            if "PONG" in input_line and not wait_cmd:
                logging.debug(
                    'Terminating list_start_pers_group '
                    'without starting any group. ssid="%s"',
                    ssid)
                if (self.activate_persistent_group
                        and not self.dynamic_group
                        and not ssid):
                    self.write_wpa("p2p_group_add persistent")
                    wait_cmd = time.time()
                    logging.warning("Starting generic persistent group")
                    self.group_type = 'Generic persistent'
                    time.sleep(1)
                else:
                    self.write_wpa("p2p_find")
                    break
            if len(tokens) == 0: # remove null line
                continue
            if tokens[0] == 'network':
                continue
            if (len(tokens) == 4 and '[P2P-PERSISTENT]' in tokens[3] and
                    tokens[0].isnumeric()):
                ssid = tokens[1]
                if (self.persistent_network_id != None and
                    str(self.persistent_network_id) != tokens[0]):
                        logging.debug('Skipping persistent group '
                            '"%s" with network ID %s, different'
                            ' from %s',
                            tokens[1], tokens[0], self.persistent_network_id)
                        continue
                self.persistent_network_id = tokens[0]
                if not start_group:
                    continue
                self.external_program("stop")
                self.write_wpa("p2p_group_add persistent=" +
                    self.persistent_network_id)
                self.group_type = 'Persistent'
                wait_cmd = time.time()
                logging.warning(
                        'Starting persistent group "%s", n. %s '
                        'in the wpa_supplicant conf file',
                    ssid, self.persistent_network_id)
                time.sleep(1)
        return ssid


    def analyze_existing_group(self, group):
        """ ssid is returned if a persistent group is active, otherwise None """
        logging.debug('Starting analyze_existing_group procedure. group="%s"', group)
        if not group:
            logging.error("No group available.")
            return None
        ssid = None
        ssid_pg = self.list_start_pers_group(start_group=False)
        if not ssid_pg:
            logging.info('No persistent group available for interface "%s".', group)
            return None
        self.write_wpa("interface " + group)
        self.write_wpa("status")
        self.write_wpa("interface " + self.interface)
        self.write_wpa("ping")
        cmd_timeout = time.time()
        logging.debug(
            'List status of persistent group "%s", checking existence of ssid "%s"',
            group, ssid_pg)
        while True:
            input_line = self.read_wpa()
            if input_line == None:
                logging.error(
                    'Internal Error (analyze_existing_group): '
                    'read_wpa() abnormally terminated')
                time.sleep(0.1)
                continue
            logging.debug("(analyze_existing_group) Read '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.debug(
                    'Terminating status retrieve of persistent group "%s" '
                    'with ssid "%s" after timeout of %s seconds.',
                    group, ssid_pg, self.min_conn_delay)
                break
            tokens = input_line.split('=', 1)
            if tokens[0] == '>': # remove prompt
                tokens.pop(0)
            if "ssid" in tokens[0]:
                if tokens[1] == ssid_pg:
                    ssid = tokens[1]
                logging.debug(
                    'Persistent group "%s" with ssid "%s" reports status ssid "%s".',
                    group, ssid_pg, tokens[1])
                continue
            if "PONG" in input_line:
                logging.debug('Terminating analysis; ssid="%s".', ssid)
                break
        return ssid


    def get_config_methods(self, pbc_in_use=None):
        logging.debug(
            "Starting 'get config_methods' procedure. pbc_in_use=%s",
            pbc_in_use)
        self.write_wpa("get config_methods")
        self.write_wpa("ping")
        wait_cmd = 0
        cmd_timeout = time.time()
        found = False
        while True:
            input_line = self.read_wpa()
            if input_line == None:
                logging.error(
                    'Internal Error (get_config_methods): '
                    'read_wpa() abnormally terminated')
                time.sleep(0.1)
                continue
            logging.debug("(get_config_methods) Read '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.min_conn_delay:
                logging.debug(
                    'Terminating get_config_methods procedure after timeout '
                    'of %s seconds; pbc_in_use=%s',
                    self.min_conn_delay, pbc_in_use)
                break
            if 'virtual_push_button' in input_line and not found:
                pbc_in_use = True
                logging.debug('Use "pbc" for config_methods, without pin.')
                continue
            if 'keypad' in input_line and not found:
                pbc_in_use = False
                found = True # keypad has priority to virtual_push_button if both are included
                logging.debug(
                    'Use "keypad" for config_methods, with pin (do not use pbc).')
                continue
            if "PONG" in input_line:
                logging.debug(
                    'Terminating get config_methods procedure; pbc_in_use=%s', pbc_in_use)
                break
        return pbc_in_use


    def external_program(self, action):
        if not self.run_program or self.run_program.isspace() or self.run_program == '-':
            return

        if action == "stop" and self.run_prog_stopped:
            return
        else:
            self.run_prog_stopped = True

        if action == "start" and not self.run_prog_stopped:
            return
        else:
            self.run_prog_stopped = False

        logging.debug('Running %s %s', self.run_program, action)
        ret = os.system(self.run_program + ' ' + action)
        logging.debug('%s completed with exit code %s', self.run_program, os.WEXITSTATUS(ret))


    def default_workflow(self, event_stat_name):
        if 'CTRL-EVENT-TERMINATING' in event_stat_name:
            logging.warning('Service terminated')
            #self.terminate() # uncomment if you wan to terminate on CTRL-EVENT-TERMINATING
            logging.error("wpa_supplicant disconnected")
            return True

        # Update statistics with unknown messages
        if self.can_register_cmds and event_stat_name: # and [c for c in event_stat_name if c.islower()] == []: # uncomment to remove lower case commands from statistics
            unmanaged_event = "unmanaged_" + event_stat_name
            if self.is_enroller and not self.is_daemon:
                os.write(self.father_slave_fd,
                    (("HOSTP2PD_STATISTICS" +
                        "\t" + unmanaged_event + '\n').encode()))
                return True
            if unmanaged_event not in self.statistics:
                self.statistics[unmanaged_event] = 0
            self.statistics[unmanaged_event] += 1
        return True


    class ENROL_TYPE:
        PIN = 0
        PBC = 1
        DISPLAY = 2


    def in_process_enrol(self, dev_name, mac_addr, type): # Obsolete
        if self.use_enroller:
            logging.debug('Using enroller subprocess to connect.')
            return
        if time.time() < self.p2p_connect_time + self.min_conn_delay:
            logging.debug('Will not enroll due to unsufficient p2p_connect_time')
            return
        self.find_timing_level = 'connect'
        logging.debug(
            'Enrol dev_name="%s", mac_addr="%s", type="%s" to monitor_group="%s"',
            dev_name, mac_addr, type, self.monitor_group)
        cmd_timeout = time.time()
        self.write_wpa("interface " + self.monitor_group)
        while True:
            input_line = self.read_wpa()
            if input_line == None:
                logging.error(
                    'Internal Error (in_process_enrol): '
                    'read_wpa() abnormally terminated')
                time.sleep(0.1)
                continue
            logging.debug("(in_process_enrol) Read '%s'", input_line)
            if self.warn_on_input_errors(input_line):
                continue
            if time.time() > cmd_timeout + self.max_negotiation_time:
                logging.error(
                    'Missing received enrolment request within %s seconds',
                    self.max_negotiation_time)
                type = None # comment this if you want to try the enrolment anyway
                break
            #> <3>WPS-ENROLLEE-SEEN ee:54:44:24:70:df 811e2280-33d1-5ce8-97e5-6fcf1598c173 10-0050F204-5 0x4388 0 1 [test]
            if 'WPS-ENROLLEE-SEEN ' in input_line:
                tokens = input_line.split()
                if tokens[0] == '>': # remove prompt
                    tokens.pop(0)
                if tokens[1] == mac_addr:
                    break
        if type == self.ENROL_TYPE.PIN:
            self.write_wpa("wps_pin " + mac_addr + " " + self.password)
        if type == self.ENROL_TYPE.PBC:
            self.write_wpa("wps_pbc " + mac_addr)
        self.write_wpa("interface " + self.interface)
        logging.debug('Enrol procedure terminated')
        return


    def warn_on_input_errors(self, input):
        if (input == "Interactive mode"
                or "Connection to wpa_supplicant re-established" in input
                or "Connection established" in input): # startup activator
            if input != "Interactive mode":
                logging.error(input)
            self.do_activation = True
            self.terminate_enrol()
            return True
        if 'Connected to interface' in input:
            return True
        if input == self.password: # do not add the password in statistics
            return True
        # Process wpa_supplicant connection problems
        if ("Could not connect to wpa_supplicant" in input
                or 'Connection to wpa_supplicant lost' in input
                or 'Not connected to wpa_supplicant' in input):
            logging.error(
                "%s - %s of %s", input, self.wpa_supplicant_errors,
                self.max_num_wpa_cli_failures)
            self.wpa_supplicant_errors += 1
            self.monitor_group = None
            self.ssid_group = None
            return True
        if "wpa_supplicant" in input:
            logging.warning(input)
            return True
        return False


    def register_statistics(self, event_stat_name):
        self.statistics["last_response_message"] = event_stat_name
        if 'response_messages' not in self.statistics:
            self.statistics['response_messages'] = 0
        self.statistics['response_messages'] += 1
        if event_stat_name not in self.statistics:
            self.statistics[event_stat_name] = 0
        self.statistics[event_stat_name] += 1


    def handle(self, wpa_cli):
        """ handles all events """
        # https://w1.fi/wpa_supplicant/devel/ctrl_iface_page.html

        # Define response messages tokens
        wpa_cli_word = wpa_cli.split()
        if len(wpa_cli_word) == 0: # remove null line
            return True
        if wpa_cli_word[0] == '>': # remove prompt
            wpa_cli_word.pop(0)
        if len(wpa_cli_word) == 0: # remove prompt only line
            return True
        event_name = re.sub(r'<[0-9]*>', r'', wpa_cli_word[0], 1) # first word is the event_name
        if event_name == 'P2P:':
            event_name = wpa_cli_word[0]
        if len(wpa_cli_word) > 1:
            mac_addr = wpa_cli_word[1] # second word is generally the mac_addr
        else:
            mac_addr = ''
        dev_name = re.sub(r".*name='([^']*).*", r'\1', wpa_cli, 1) # some event have "name="
        p2p_dev_addr = re.sub(r".*p2p_dev_addr=([^ ]*).*", r'\1', wpa_cli, 1) # some events have "p2p_dev_addr="
        pri_dev_type = re.sub(r".*pri_dev_type=([^ ]*).*", r'\1', wpa_cli, 1) # some events have "pri_dev_type="
        ssid_arg = re.sub(r'.*ssid="([^"]*).*', r'\1', wpa_cli, 1) # read ssid="<name>"
        persistent_arg = re.sub(r'.*persistent=([0-9]*).*', r'\1', wpa_cli, 1) # read persistent=number

        if self.warn_on_input_errors(wpa_cli):
            #if ((self.is_enroller and self.wpa_supplicant_errors) or
            #        self.wpa_supplicant_errors > self.max_num_wpa_cli_failures):
            if self.wpa_supplicant_errors > self.max_num_wpa_cli_failures:
                self.terminate()
                return False
            return True
        self.wpa_supplicant_errors = 0

        # Account "self.statistics"
        if event_name == "HOSTP2PD_ADD_REGISTER":
            stat_tokens = wpa_cli.split('\t')
            if stat_tokens[1] and stat_tokens[2]:
                self.addr_register[stat_tokens[1]] = stat_tokens[2]
            return True
        if event_name == "HOSTP2PD_STATISTICS":
            stat_tokens = wpa_cli.split('\t')
            if stat_tokens[1]:
                self.register_statistics("E>" + stat_tokens[1])
            return True
        if wpa_cli == self.password or event_name == self.password: # do not add the password in statistics
            return True
        event_stat_name = ''
        if event_name:
            event_stat_name = "<P2P>" if event_name in 'P2P:' else event_name
        if self.is_enroller:
            if self.can_register_cmds:
                if not self.is_daemon:
                    os.write(self.father_slave_fd,
                        ("HOSTP2PD_STATISTICS" +
                            "\t" + event_stat_name + '\n').encode())
        else:
            if event_stat_name and self.can_register_cmds:
                self.register_statistics(event_stat_name)

        # Startup procedure
        if self.do_activation:
            self.do_activation = False
            # Initialize self.pbc_in_use
            if self.pbc_in_use == None:
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
                logging.debug('(enroller) Started on group "%s"',
                    self.monitor_group)
                self.find_timing_level = 'enroller'
            else: # Core startup
                self.monitor_group = self.list_or_remove_group(remove=False)
                if self.activate_autonomous_group and not self.monitor_group:
                    self.write_wpa("p2p_group_add")
                    self.group_type = 'Autonomous'
                    self.monitor_group = self.list_or_remove_group(remove=False)
                if self.monitor_group:
                    self.ssid_group = self.analyze_existing_group(
                        self.monitor_group)
                else:
                    self.ssid_group = self.list_start_pers_group(
                        start_group=(
                            self.activate_persistent_group
                            and not self.dynamic_group
                            )
                        )
                if self.ssid_group:
                    logging.info('Configured autonomous/persistent group "%s"',
                        self.ssid_group)
                if self.monitor_group:
                    logging.info('Active group interface "%s"',
                        self.monitor_group)
                    self.run_enrol()
                    if not self.group_type:
                        self.group_type = 'Existing autonomous/persistent'

                # Announce again
                self.write_wpa("p2p_stop_find")
                time.sleep(1)
                self.write_wpa("p2p_find")

            # Start processing commands
            self.can_register_cmds = True

        # Discard some unrelevant commands or messages
        if event_name == 'OK':
            logging.debug('OK received')
            return True
        self.scan_polling = 0 # scan polling is reset by any message different than 'OK' and 'p2p_find'

        if self.is_enroller:
            logging.debug("(enroller) event_name: %s", event_name)
        else:
            logging.debug("event_name: %s", event_name)

        # > <3>CTRL-EVENT-SCAN-STARTED
        if event_name == 'CTRL-EVENT-SCAN-STARTED':
            return True

        # <3>CTRL-EVENT-DISCONNECTED bssid=de:a6:32:01:82:03 reason=3 locally_generated=1
        if self.is_enroller and event_name == 'CTRL-EVENT-DISCONNECTED':
            logging.debug('CTRL-EVENT-DISCONNECTED received: terminating enroller')
            self.terminate()
            return False

        # <3>CTRL-EVENT-SCAN-RESULTS
        if event_name == 'CTRL-EVENT-SCAN-RESULTS':
            return True

        # <3>RX-PROBE-REQUEST sa=b6:3b:9b:7a:08:96 signal=0
        if event_name == 'RX-PROBE-REQUEST':
            return True

        # <3>CTRL-EVENT-SUBNET-STATUS-UPDATE status=0
        if event_name == 'CTRL-EVENT-SUBNET-STATUS-UPDATE':
            return True

        # <3>CTRL-EVENT-EAP-STARTED 56:3b:c6:4a:4a:b3
        if event_name == 'CTRL-EVENT-EAP-STARTED': # only on the GO (Enroller)
            return True

        # <3>CTRL-EVENT-EAP-PROPOSED-METHOD vendor=0 method=1
        if event_name == 'CTRL-EVENT-EAP-PROPOSED-METHOD': # only on the GO (Enroller)
            logging.debug(
                "(enroller) Proposed method %s %s",
                wpa_cli_word[1], wpa_cli_word[2])
            return True

        # <3>WPS-REG-SUCCESS 72:dd:a8:c9:97:0e 811e2280-33d1-5ce8-97e5-6fcf1598c173
        if event_name == 'WPS-REG-SUCCESS':
            return True

        # <3>WPS-SUCCESS
        if event_name == 'WPS-SUCCESS':
            return True

        # <3>CTRL-EVENT-EAP-FAILURE 56:3b:c6:4a:4a:b3
        if event_name == 'CTRL-EVENT-EAP-FAILURE': # only on the GO (Enroller)
            return True

        # <3>AP-STA-CONNECTED 56:3b:c6:4a:4a:b3 p2p_dev_addr=56:3b:c6:4a:4a:b3
        if self.is_enroller and event_name == 'AP-STA-CONNECTED':
            logging.debug(
                "(enroller) Station '%s' CONNECTED to group '%s'",
                p2p_dev_addr, self.monitor_group)
            return True

        # <3>AP-STA-DISCONNECTED 56:3b:c6:4a:4a:b3 p2p_dev_addr=56:3b:c6:4a:4a:b3
        if self.is_enroller and event_name == 'AP-STA-DISCONNECTED':
            logging.debug(
                "(enroller) Station '%s' DISCONNECTED from group '%s'",
                p2p_dev_addr, self.monitor_group)
            return True

        # <3>WPS-ENROLLEE-SEEN 56:3b:c6:4a:4a:b3 811e2280-33d1-5ce8-97e5-6fcf1598c173 10-0050F204-5 0x4388 0 1 [test]
        if event_name == 'WPS-ENROLLEE-SEEN': # only on the GO (Enroller)
            logging.debug('Found station "%s" with address "%s".',
                dev_name, mac_addr)

            if self.pbc_in_use and (
                    self.pbc_white_list == [] or dev_name in self.pbc_white_list):
                self.write_wpa("wps_pbc " + mac_addr)
            else:
                self.write_wpa("wps_pin " + mac_addr + " " + self.password)
            return True

        if self.is_enroller: # processing enroller commands terminates here
            return self.default_workflow(event_stat_name)

        #___________________________________________________________________________________________
        # <3>P2P: Reject scan trigger since one is already pending
        if 'P2P: Reject scan trigger since one is already pending' in wpa_cli:
            self.scan_polling += 1
            self.find_timing_level = 'long'
            return True

        # <3>P2P-GROUP-FORMATION-SUCCESS
        if event_name == 'P2P-GROUP-FORMATION-SUCCESS':
            self.find_timing_level = 'connect'
            return True

        # <3>P2P-DEVICE-FOUND ae:e2:d3:41:27:14 p2p_dev_addr=ae:e2:d3:41:a7:14 pri_dev_type=3-0050F204-1 name='test' config_methods=0x0 dev_capab=0x25 group_capab=0x81 vendor_elems=1 new=1
        if event_name == 'P2P-DEVICE-FOUND' and mac_addr:
            if self.is_enroller:
                os.write(self.father_slave_fd,
                    ("HOSTP2PD_ADD_REGISTER" +
                        "\t" + mac_addr + "\t" + dev_name + '\n').encode())
            else:
                self.addr_register[mac_addr] = dev_name
            logging.debug('Found station with name "%s" and address "%s".', dev_name, mac_addr)
            return True

        # <3>P2P-GO-NEG-REQUEST ee:54:44:24:70:df dev_passwd_id=1 go_intent=6
        if event_name == 'P2P-GO-NEG-REQUEST' and mac_addr: # This does not provide "dev_name"
            self.find_timing_level = 'connect'
            logging.debug('P2P-GO-NEG-REQUEST received')
            if self.pbc_in_use:
                if not mac_addr in self.addr_register:
                    logging.error('While pbc is in use, cannot find name related to address "%s".', mac_addr)
                    return True
                if self.pbc_white_list != [] and not self.addr_register[mac_addr] in self.pbc_white_list:
                    self.rotate_config_method()
                    return True
            if self.monitor_group:
                logging.debug(
                    'Connecting station with address "%s" to existing group "%s".',
                    mac_addr, self.monitor_group)
                self.in_process_enrol(dev_name, mac_addr, self.ENROL_TYPE.PBC)
                return True
            else:
                logging.debug(
                    'Connecting station with address "%s".', mac_addr)
                self.start_session(mac_addr)
                return True

        if (event_name == 'P2P-PROV-DISC-PBC-REQ' or
            event_name == 'P2P-PROV-DISC-ENTER-PIN' or
            (event_name == 'P2P-PROV-DISC-SHOW-PIN' and len(wpa_cli_word) > 2)) and mac_addr:
            self.find_timing_level = 'connect'
            self.p2p_connect_time = 0

            # <3>P2P-PROV-DISC-ENTER-PIN 02:5e:6d:3d:99:8b p2p_dev_addr=02:5e:6d:3d:99:8b pri_dev_type=10-0050F204-5 name='test' config_methods=0x188 dev_capab=0x25 group_capab=0x0
            if event_name == 'P2P-PROV-DISC-ENTER-PIN':
                logging.error(
                    "Station '%s' with name '%s' asked to enter its PIN to connect",
                    mac_addr, dev_name)
                #self.write_wpa("p2p_reject " + mac_addr)

            # <3>P2P-PROV-DISC-PBC-REQ ca:d5:d5:38:d6:69 p2p_dev_addr=ca:d5:d5:38:d6:69 pri_dev_type=10-0050F204-5 name='test' config_methods=0x88 dev_capab=0x25 group_capab=0x0
            if event_name == 'P2P-PROV-DISC-PBC-REQ' and not self.pbc_in_use:
                logging.error(
                    "Station '%s' with name '%s' asked to connect with PBC",
                    mac_addr, dev_name)
                #self.write_wpa("p2p_reject " + mac_addr)

            # <3>P2P-PROV-DISC-SHOW-PIN ee:54:44:24:70:df 93430999 p2p_dev_addr=ee:54:44:24:70:df pri_dev_type=10-0050F204-5 name='test' config_methods=0x188 dev_capab=0x25 group_capab=0x0
            if event_name == 'P2P-PROV-DISC-SHOW-PIN' and self.pbc_in_use:
                logging.error(
                    "Station '%s' with name '%s' asked to connect with PIN",
                    mac_addr, dev_name)
                #self.write_wpa("p2p_reject " + mac_addr)

            if event_name == 'P2P-PROV-DISC-SHOW-PIN' and not self.pbc_in_use:
                if self.monitor_group:
                    logging.debug(
                        'Connecting station with name "%s" and address "%s" '
                        'using PIN to existing group.',
                        dev_name, mac_addr)
                    self.in_process_enrol(dev_name, mac_addr, self.ENROL_TYPE.PIN)
                    return True
                else:
                    self.start_session(mac_addr)
                    return True

            if (event_name == 'P2P-PROV-DISC-PBC-REQ'
                    and self.pbc_in_use
                    and dev_name):
                if self.pbc_white_list != [] and not dev_name in self.pbc_white_list:
                    self.rotate_config_method()
                    return True
                if self.monitor_group:
                    logging.debug(
                        'Connecting station with name "%s" and address "%s" '
                        'using PBC to existing group.',
                        dev_name, mac_addr)
                    self.in_process_enrol(dev_name, mac_addr, self.ENROL_TYPE.PBC)
                    return True
                else:
                    self.start_session(mac_addr)
                    return True

            logging.debug(
                'Invalid connection request. Event="%s", station name="%s", '
                'address="%s", group="%s", persistent group="%s".',
                event_name, dev_name, mac_addr, self.monitor_group,
                self.ssid_group)
            if self.pbc_in_use:
                #self.write_wpa("p2p_remove_client " + mac_addr)
                self.write_wpa("p2p_prov_disc " + mac_addr + " pbc")
            else:
                #self.write_wpa("p2p_remove_client " + mac_addr)
                self.write_wpa("p2p_prov_disc " + mac_addr + " keypad")
            self.in_process_enrol(dev_name, mac_addr, self.ENROL_TYPE.PIN) # this has the effect to remove the invitation at the end of the failure
            return True

        # <3>AP-STA-CONNECTED ee:54:44:24:70:df p2p_dev_addr=ee:54:44:24:70:df
        if event_name == 'AP-STA-CONNECTED':
            self.p2p_connect_time = 0
            self.find_timing_level = 'normal'
            logging.warning(
                "Station '%s' CONNECTED to group '%s'",
                p2p_dev_addr, self.monitor_group)
            return True

        # <3>AP-STA-DISCONNECTED ee:54:44:24:70:df p2p_dev_addr=ee:54:44:24:70:df
        if event_name == 'AP-STA-DISCONNECTED':
            logging.warning('Station "%s" disconnected.', p2p_dev_addr)
            self.p2p_connect_time = 0
            self.find_timing_level = 'normal'
            if self.dynamic_group and not self.activate_persistent_group:
                if self.monitor_group:
                    self.write_wpa("p2p_group_remove " + self.monitor_group)
                    self.monitor_group = ''
                else:
                    self.monitor_group = self.list_or_remove_group(True)
                time.sleep(3)
                self.external_program("start")
            self.write_wpa("p2p_find")
            return True

        # <3>P2P-PROV-DISC-FAILURE p2p_dev_addr=b6:3b:9b:7a:08:96 status=1
        if event_name == 'P2P-PROV-DISC-FAILURE':
            logging.warning('Provision discovery failed for station "%s".',
                p2p_dev_addr)
            self.p2p_connect_time = 0
            self.find_timing_level = 'normal'
            if self.dynamic_group and not self.activate_persistent_group:
                if self.monitor_group:
                    self.write_wpa("p2p_group_remove " + self.monitor_group)
                    self.monitor_group = ''
                else:
                    self.monitor_group = self.list_or_remove_group(True)
                time.sleep(3)
                self.external_program("start")
            self.write_wpa("p2p_find")
            return True

        # <3>P2P-INVITATION-ACCEPTED sa=5a:5f:0a:96:ee:5e persistent=4 freq=5220
        if event_name == 'P2P-INVITATION-ACCEPTED':
            logging.warning('Accepted invitation to persistent group %s.',
                persistent_arg)
            self.find_timing_level = 'connect'
            self.external_program("stop")
            return True

        if event_name == 'P2P-FIND-STOPPED':
            if time.time() > self.p2p_connect_time + self.min_conn_delay:
                self.write_wpa("p2p_find")
            return True

        if event_name == 'P2P-DEVICE-LOST':
            logging.info('Received P2P-DEVICE-LOST')
            return True

        if event_name == 'WPS-TIMEOUT':
            logging.error('Received WPS-TIMEOUT')
            self.find_timing_level = 'normal'
            self.p2p_connect_time = 0
            return True

        #  <3>P2P-GO-NEG-SUCCESS role=GO freq=5200 ht40=1 peer_dev=ea:cb:a8:16:a5:d9 peer_iface=ea:cb:a8:16:a5:d9 wps_method=PBC, event_name=P2P-GO-NEG-SUCCESS
        if event_name == 'P2P-GO-NEG-SUCCESS':
            logging.debug('P2P-GO-NEG-SUCCESS')
            self.find_timing_level = 'connect'
            return True

        if event_name == 'P2P-GROUP-STARTED' and wpa_cli_word[1]:
            self.find_timing_level = 'connect'
            self.monitor_group = wpa_cli_word[1]
            if ssid_arg:
                self.ssid_group = ssid_arg
            logging.warning("Autonomous group started: %s", self.monitor_group)
            self.run_enrol()
            return True

        # <3>P2P-GROUP-REMOVED p2p-wlan0-0 GO reason=REQUESTED
        # <3>P2P-GROUP-REMOVED p2p-wlan0-22 GO reason=FORMATION_FAILED
        if event_name == 'P2P-GROUP-REMOVED':
            self.terminate_enrol()
            self.find_timing_level = 'normal'
            if self.monitor_group:
                if self.monitor_group == wpa_cli_word[1]:
                    logging.info('Removed group "%s" of type "%s", %s',
                        self.monitor_group, wpa_cli_word[2], wpa_cli_word[3])
                else:
                    logging.error(
                        'Even if active group was "%s", removed group "%s" of type "%s", %s',
                        self.monitor_group, wpa_cli_word[1],
                        wpa_cli_word[2], wpa_cli_word[3])
            else:
                logging.info('Could not create group "%s" of type "%s", %s',
                    wpa_cli_word[1], wpa_cli_word[2], wpa_cli_word[3])
            self.monitor_group = None
            if time.time() > self.p2p_connect_time + self.min_conn_delay:
                self.write_wpa("p2p_find")
            return True

        # <3>P2P-GROUP-FORMATION-FAILURE
        if event_name == 'P2P-GROUP-FORMATION-FAILURE':
            self.monitor_group = None
            self.p2p_connect_time = 0
            self.find_timing_level = 'normal'
            if self.dynamic_group and not self.activate_persistent_group:
                self.num_failures += 1
                if self.num_failures < self.max_num_failures:
                    logging.warning(
                        'Retrying group formation: %s of %s',
                        self.num_failures, self.max_num_failures)
                    if self.num_failures > 1:
                        time.sleep(2)
                    self.start_session() # use the last value of self.station
                else:
                    logging.error('Group formation failed.')
                    self.num_failures = 0
                    self.external_program("start")
                    self.write_wpa("p2p_find")
                return True
            else:
                logging.critical(
                    'Group formation failed (P2P-GROUP-FORMATION-FAILURE).')
                return True
                #self.terminate()
                #return False

        if event_name == 'P2P-GO-NEG-FAILURE':
            self.find_timing_level = 'normal'
            self.p2p_connect_time = 0
            if self.dynamic_group and not self.activate_persistent_group:
                self.num_failures += 1
                if self.num_failures < self.max_num_failures:
                    logging.warning(
                        'Retrying negotiation: %s of %s',
                        self.num_failures, self.max_num_failures)
                    if self.num_failures > 1:
                        time.sleep(2)
                    self.start_session() # use the last value of self.station
                else:
                    logging.error('Cannot negotiate P2P Group Owner.')
                    self.num_failures = 0
                    self.external_program("start")
                    self.write_wpa("p2p_find")
                return True

        if event_name == 'FAIL':
            self.find_timing_level = 'normal'
            self.p2p_connect_time = 0
            if self.dynamic_group and not self.activate_persistent_group:
                logging.info('Connection failed')
                self.monitor_group = self.list_or_remove_group(True)
                self.num_failures += 1
                if self.num_failures < self.max_num_failures:
                    if self.num_failures > 1:
                        time.sleep(2)
                    self.start_session() # use the last value of self.station
                else:
                    self.num_failures = 0
                    self.external_program("start")
                    self.write_wpa("p2p_find")
                return True

        return self.default_workflow(event_stat_name)
