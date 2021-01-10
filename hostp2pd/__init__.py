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
    if sys.hexversion < 0x3050000:
        raise ImportError("Python version must be >= 3.5")
    import threading
    import logging
    from .hostp2pd import HostP2pD
    import time
    from cmd import Cmd
    import rlcompleter
    import glob
    import os
    import os.path
    import argparse
    import signal
    import daemon
    import daemon.pidfile
    from lockfile.pidlockfile import PIDLockFile
    from lockfile import AlreadyLocked, NotLocked, LockFailed
    from .__version__ import __version__
    try:
        import readline
    except ImportError:
        readline = None
except ImportError as detail:
    print("hostp2pd error:\n " + str(detail))
    sys.exit(1)

DAEMON_PIDFILE_DIR_ROOT = '/var/run/'
DAEMON_PIDFILE_DIR_NON_ROOT = '/tmp/'
DAEMON_PIDFILE_BASE = 'hostp2pd-'
DAEMON_UMASK = 0o002
DAEMON_DIR = '/tmp'

class Interpreter(Cmd):

    __hiden_methods = ('do_EOF',)
    rlc = rlcompleter.Completer().complete
    histfile = os.path.expanduser('~/.hostp2pd_mgr_history')
    host_lib = 'hostp2pd' # must be declared in default(), completedefault(), completenames()
    histfile_size = 1000

    def __init__(self, hostp2pd, args):
        self.args = args
        self.hostp2pd = hostp2pd
        self.prompt_active = True
        self.color_active = True
        self.__set_ps_string('CMD')
        if self.args.batch_mode:
            self.prompt_active = False
            self.color_active = False
            Cmd.prompt = ''
            self.use_rawinput = False
        Cmd.__init__(self)

    def __set_ps_string(self, ps_string):
        self.ps_color = '\x01\033[01;32m\x02' + ps_string + '>\x01\033[00m\x02 '
        if os.name == 'nt':
            self.ps_color = '\033[01;32m' + ps_string + '>\033[00m '
        self.ps_nocolor = ps_string + '> '
        self.__set_ps()

    def __set_ps(self):
        ps = self.ps_color if self.color_active else self.ps_nocolor
        Cmd.prompt = ps if self.prompt_active else ''

    def print_topics(self, header, cmds, cmdlen, maxcol):
        if not cmds:
            return
        if self.args.batch_mode:
            return
        self.stdout.write(
        "Available commands include the following list (type help <topic>"
        "\nfor more information on each command). Besides, any Python"
        "\ncommand is accepted. Autocompletion is fully allowed."
        "\n=============================================================="
        "==\n")
        self.columnize(cmds, maxcol-1)
        self.stdout.write("\n")

    def emptyline(self):
        return

    def do_EOF(self, arg):
        'Quit hostp2pd'
        if self.args.batch_mode:
            print("End of batch commands.")
            while threading.active_count() == 2:
                time.sleep(0.5)
        else:
            print("Terminating...")
        sys.exit(0)

    def do_quit(self, arg):
        "Quit hostp2pd. Also Control-D or interrupt \n"\
        "(Control-C) can be used."
        print("Terminating...")
        if arg:
            print ("Invalid format")
            return
        sys.exit(0)

    def do_version(self, arg):
        "Print hostp2pd version."
        print(f'hostp2pd version {__version__}.')
    
    def do_wait(self, arg):
        "Perform an immediate sleep of the seconds specified in the argument.\n"\
        "(Floating point number; default is 10 seconds.)"
        try:
            delay = 10 if len(arg) == 0 else float(arg.split()[0])
        except ValueError:
            print ("Invalid format")
            return
        print("Sleeping for %s seconds" % delay)
        time.sleep(delay)

    def do_prompt(self, arg):
        "Toggle prompt off/on or change the prompt."
        if arg:
            self.__set_ps_string(arg.split()[0])
            return
        self.prompt_active = not self.prompt_active
        print("Prompt %s" % repr(self.prompt_active))
        self.__set_ps()

    def do_color(self, arg):
        "Toggle color off/on."
        if arg:
            print ("Invalid format")
            return
        self.color_active = not self.color_active
        if not self.color_active:
            sys.stdout.write("\033[00m")
            sys.stdout.flush()
        print("Color %s" % repr(self.color_active))
        self.__set_ps()

    def precmd(self, line):
        if self.color_active:
            sys.stdout.write("\033[36m")
            sys.stdout.flush()
        return Cmd.precmd(self, line)

    def postcmd(self, stop, line):
        return Cmd.postcmd(self, stop, line)

    def do_reset(self, arg):
        "Reset hostp2pd statistics"
        if arg:
            print ("Invalid format")
            return
        self.hostp2pd.reset()
        print("Reset done.")

    def do_loglevel(self, arg):
        "If an argument is given, set the logging level,\n"\
        "otherwise show the current one.\n"\
        "CRITICAL=50, ERROR=40, WARNING=30, INFO=20, DEBUG=10."
        conf_file = self.hostp2pd.config_file
        if arg and arg.isnumeric():
            hostp2pd.logger.setLevel(int(arg))
            print("Logging level set to", hostp2pd.logger.getEffectiveLevel())
        else:
            print("Current logging level:", hostp2pd.logger.getEffectiveLevel())

    def do_reload(self, arg):
        "Reload configuration from the latest valid configuration file.\n"\
        "Optional argument is a new configuration file; to load defaults\n"\
        "use 'reset' as argument."
        conf_file = self.hostp2pd.config_file
        if arg:
            if self.hostp2pd.read_configuration(
                    configuration_file=arg,
                    do_activation=True):
                print("Reloaded configuration file", arg)
            else:
                print("Errors while reloading configuration from file", arg)
                self.hostp2pd.config_file = conf_file
        else:
            if self.hostp2pd.read_configuration(
                    configuration_file=self.hostp2pd.config_file,
                    do_activation=True):
                print("Reloaded configuration file", self.hostp2pd.config_file)
            else:
                print("Errors while reloading configuration from file",
                    self.hostp2pd.config_file)
                self.hostp2pd.config_file = conf_file

    def do_stats(self, arg):
        "Print execution statistics."
        if arg:
            print ("Invalid format")
            return
        format_string = "  {:35s} = {}"
        if self.hostp2pd.addr_register:
            print("Station addresses:")
            for i in self.hostp2pd.addr_register:
                print(format_string.format(i, self.hostp2pd.addr_register[i]))
        else:
            print("No station addresses available.")
        if self.hostp2pd.statistics:
            print("Statistics:")
            for i in sorted(self.hostp2pd.statistics):
                print(format_string.format(i, self.hostp2pd.statistics[i]))
        else:
            print("No statistics available.")
        print("Internal parameters:")
        print(format_string.format("Configuration file",
            self.hostp2pd.config_file))
        print(format_string.format("Interface name",
            self.hostp2pd.interface))
        print(format_string.format("SSID persistent/autonomous group",
            self.hostp2pd.ssid_group))
        print(format_string.format("Active group",
            self.hostp2pd.monitor_group))
        print(format_string.format("Group formation technique",
            self.hostp2pd.group_type))
        print(format_string.format("Persistent group number (net id)",
            self.hostp2pd.persistent_network_id))
        print(format_string.format("Activation/deactivation program",
            self.hostp2pd.run_program))
        print(format_string.format("Deactivation program was run",
            self.hostp2pd.run_prog_stopped))
        print(format_string.format("Thread backend state",
            self.hostp2pd.THREAD.state[self.hostp2pd.threadState]))
        print(format_string.format("Pbc is in use",
            self.hostp2pd.pbc_in_use))
        print(format_string.format("Configuration method in use",
            self.hostp2pd.config_method_in_use))
        print(format_string.format("p2p_connect_time",
            self.hostp2pd.p2p_connect_time))
        print(format_string.format("find_timing_level",
            self.hostp2pd.find_timing_level))
        print(format_string.format("Logging level",
            self.hostp2pd.logger.level))
        print(format_string.format("Number of failures",
            self.hostp2pd.num_failures))
        print(format_string.format("Stored station name",
            self.hostp2pd.station))
        print(format_string.format("wpa_supplicant errors",
            self.hostp2pd.wpa_supplicant_errors))
        print(format_string.format("Number of scan pollings",
            self.hostp2pd.scan_polling))
        try:
            print(format_string.format("wpa_cli process Pid",
                self.hostp2pd.process.pid))
        except:
            print("  Error: wpa_cli process ID not existing!")
        try:
            print(format_string.format("Enroller wpa_cli process Pid",
                self.hostp2pd.enroller.pid))
        except:
            print("  Enroller wpa_cli process ID is not existing.")
        

    def do_pause(self, arg):
        "Pause the execution."
        if arg:
            print ("Invalid format")
            return
        self.hostp2pd.threadState = self.hostp2pd.THREAD.PAUSED
        print("Backend hostp2pd paused")

    def do_resume(self, arg):
        "Resume the execution after pausing; prints the used device."
        if arg:
            print ("Invalid format")
            return
        self.hostp2pd.threadState = self.hostp2pd.THREAD.ACTIVE
        print("Backend hostp2pd resumed.")

    def do_history(self, arg):
        "Print the command history; if an argument is given, print the last\n"\
        "n commands in the history; with argument 'clear', clears the history"
        if arg == "clear":
            readline.clear_history()
            return
        try:
            n = 20 if len(arg) == 0 else int(arg.split()[0])
        except ValueError:
            print ("Invalid format")
            return
        num=readline.get_current_history_length() - n
        for i in range(num if num > 0 else 0,
                       readline.get_current_history_length()):
            print (readline.get_history_item(i + 1))

    def is_matched(self, expression):
        opening = tuple('({[')
        closing = tuple(')}]')
        mapping = dict(zip(opening, closing))
        queue = []
        for letter in expression:
            if letter in opening:
                queue.append(mapping[letter])
            elif letter in closing:
                if not queue or letter != queue.pop():
                    return False
        return not queue

    # completedefault and completenames manage autocompletion of Python
    # identifiers and namespaces
    def completedefault(self, text, line, begidx, endidx):
        hostp2pd = self.hostp2pd # ref. host_lib
        rld = '.'.join(text.split('.')[:-1])
        rlb = text.split('.')[-1]
        if (begidx > 0 and line[begidx-1] in ')]}' and
                line[begidx] == '.' and self.is_matched(line)):
            rlds = line.rstrip('.' + rlb)
            rl = [ rld + '.' + x for x in dir(eval(rlds))
                if x.startswith(rlb) and not x.startswith('__')
            ]
            return(rl)
        if rld:
            rl = [
                rld + '.' + x for x in dir(eval(rld))
                if x.startswith(rlb) and not x.startswith('__')
            ]
        else:
            rl = ['self'] if rlb != '' and 'self'.startswith(rlb) else []
            if self.host_lib.startswith(text):
                rl += [self.host_lib]
        return rl + [self.rlc(text, x) for x in range(400) if self.rlc(text, x)]

    def get_names(self):
        return [n for n in dir(self.__class__) if n not in self.__hiden_methods]

    def completenames(self, text, *ignored):
        hostp2pd = self.hostp2pd # ref. host_lib
        dotext = 'do_'+text
        rld = '.'.join(text.split('.')[:-1])
        rlb = text.split('.')[-1]
        if rld:
            rl = [
                rld + '.' + x for x in dir(eval(rld))
                if x.startswith(rlb) and not x.startswith('__')
            ]
        else:
            rl = ['self'] if rlb != '' and 'self'.startswith(rlb) else []
            if self.host_lib.startswith(text):
                rl += [self.host_lib]
        if not text:
            return [a[3:] for a in self.get_names() if a.startswith(dotext)]
        return [a[3:] for a in self.get_names() if a.startswith(dotext)
                ] + rl + [self.rlc(text, x) for x in range(400) if self.rlc(text, x)]

    def preloop(self):
        if readline and os.path.exists(self.histfile) and not self.args.batch_mode:
            try:
                readline.read_history_file(self.histfile)
            except FileNotFoundError:
                pass

    def postloop(self):
        if readline and not self.args.batch_mode:
            readline.set_history_length(self.histfile_size)
            readline.write_history_file(self.histfile)
        if self.color_active and not self.args.batch_mode:
            sys.stdout.write("\033[00m")
            sys.stdout.flush()

    # Execution of unrecognized commands
    def default(self, arg):
        hostp2pd = self.hostp2pd # ref. host_lib
        try:
            print ( eval(arg) )
        except Exception:
            try:
                exec(arg, globals())
            except Exception as e:
                print("Error executing command: %s" % e)

    def cmdloop_with_keyboard_interrupt(self, arg):
        doQuit = False
        while doQuit != True:
            try:
                self.cmdloop(arg)
                doQuit = True
            except KeyboardInterrupt:
                print("Terminating...")
                sys.exit(0)


def main():
    # Option handling
    parser = argparse.ArgumentParser(
        epilog=f'hostp2pd v.{__version__} - The Wi-Fi Direct '
            ' Session Manager. wpa_cli controller of Wi-Fi '
            ' Direct connections handled by wpa_supplicant.'
        )
    parser.prog = "hostp2pd"
    parser.add_argument(
        '-V',
        "--version",
        dest='version',
        action='store_true',
        help="print hostp2pd version and exit")
    parser.add_argument(
        '-v',
        "--verbosity",
        dest='verbosity',
        action='store_true',
        help="print execution logging")
    parser.add_argument(
        '-vv',
        "--debug",
        dest='debug',
        action='store_true',
        help="print debug logging information")
    parser.add_argument(
        '-t',
        "--terminate",
        dest='terminate',
        action='store_true',
        help="terminate a daemon process sending SIGTERM")
    parser.add_argument(
        '-r',
        "--reload",
        dest='reload',
        action='store_true',
        help="reload configuration of a daemon process sending SIGHUP")
    parser.add_argument(
        "-c", "--config",
        dest = "config_file",
        type = argparse.FileType('r'),
        help = "Configuration file.",
        default = 0,
        nargs = 1,
        metavar = 'CONFIG_FILE')
    parser.add_argument(
        "-d", "--daemon",
        dest = "daemon_mode",
        action='store_true',
        help = "Run hostp2pd in daemon mode. ")
    parser.add_argument(
        "-b", "--batch",
        dest = "batch_mode",
        type = argparse.FileType('w'),
        help = "Run hostp2pd in batch mode. "
             "Argument is the output file. "
             "Use an hyphen (-) for standard output.",
        default = 0,
        nargs = 1,
        metavar = 'FILE')
    parser.add_argument(
        '-i', '--interface',
        dest = 'interface',
        help = "Set the interface managed by hostp2pd.",
        default = ['p2p-dev-wlan0'],
        nargs = 1,
        metavar = 'INTERFACE')
    parser.add_argument(
        '-p', '--run_program',
        dest = 'run_program',
        help = "Name of the program to run with start and stop arguments. ",
        default = [''],
        nargs = 1,
        metavar = 'RUN_PROGRAM')
    args = parser.parse_args()

    if args.version:
        print(f'hostp2pd version {__version__}.')
        sys.exit(0)

    # Redirect stdout
    if args.batch_mode and not args.batch_mode[0].isatty():
        sys.stdout = args.batch_mode[0]

    # Configuration file
    if args.config_file and args.config_file[0].name:
        config_file = args.config_file[0].name
    else:
        config_file = None

    # Debug
    force_logging = None
    if args.verbosity:
        force_logging = logging.INFO
    if args.debug:
        force_logging = logging.DEBUG

    # Instantiate the class
    hostp2pd = HostP2pD(
        config_file,
        args.interface[0],
        args.run_program[0],
        force_logging)

    if os.getuid() == 0:
        daemon_pid_fname = (DAEMON_PIDFILE_DIR_ROOT +
            DAEMON_PIDFILE_BASE + args.interface[0] + ".pid")
    else:
        daemon_pid_fname = (DAEMON_PIDFILE_DIR_NON_ROOT +
            DAEMON_PIDFILE_BASE + args.interface[0] + ".pid")
    pidfile = daemon.pidfile.PIDLockFile(daemon_pid_fname)
    pid = pidfile.read_pid()

    if args.terminate:
        if pid:
            print(f'Terminating daemon process {pid}.')
            try:
                Ret = os.kill(pid, signal.SIGTERM)
            except Exception as e:
                print(f'Error while terminating daemon process {pid}: {e}.')
                sys.exit(1)
            if Ret:
                print(f'Error while terminating daemon process {pid}.')
                sys.exit(1)
            else:
                sys.exit(0)
        else:
            print('Cannot terminate daemon process: not running.')
            sys.exit(0)

    if args.reload:
        if pid:
            print(f'Reloading configuration file for daemon process {pid}.')
            try:
                Ret = os.kill(pid, signal.SIGHUP)
            except Exception as e:
                print(f'Error while reloading configuration file for daemon process {pid}: {e}.')
                sys.exit(1)
            if Ret:
                print(f'Error while reloading configuration file for daemon process {pid}.')
                sys.exit(1)
            else:
                sys.exit(0)
        else:
            print('Cannot reload the configuration of the daemon process: not running.')
            sys.exit(0)

    if args.daemon_mode and not args.batch_mode:
        if pid:
            try:
                pidfile.acquire()
                pidfile.release() # this might occur only in rare contention cases
            except AlreadyLocked:
                try:
                    os.kill(pid, 0)
                    print(f'Process {pid} already running'
                        f' on the same interface "{args.interface[0]}". '
                        f'Check lockfile "{daemon_pid_fname}".')
                    sys.exit(1)
                except OSError:  #No process with locked PID
                    pidfile.break_lock()
                    print(f"Previous process {pid} terminated abnormally.")
            except NotLocked:
                print("Internal error: lockfile", daemon_pid_fname)
        context = daemon.DaemonContext(
            working_directory=DAEMON_DIR,
            umask=DAEMON_UMASK,
            pidfile=pidfile,
            detach_process=True,
            stdin=sys.stdin if args.debug else None,
            stdout=sys.stdout if args.debug else None,
            stderr=sys.stderr if args.debug else None,
            signal_map={
                signal.SIGTERM: lambda signum, frame: hostp2pd.terminate(),
                signal.SIGINT: lambda signum, frame: hostp2pd.terminate(),
                signal.SIGHUP: lambda signum, frame: hostp2pd.read_configuration(
                    configuration_file=hostp2pd.config_file,
                    do_activation=True
                    )
                }
            )
        try:
            with context:
                print('hostp2pd daemon service STARTED')
                hostp2pd.run()
                print("\nhostp2pd daemon service ENDED")
        except LockFailed as e:
            print('Internal error: cannot start daemon', e)
            sys.exit(1)
        sys.exit(0)

    if pid:
        print(f'Warning: lockfile "{daemon_pid_fname}" reports pid {pid}.')

    if args.batch_mode and args.daemon_mode:
        print('hostp2pd service STARTED')
        signal.signal(
            signal.SIGHUP, lambda signum, frame: hostp2pd.read_configuration(
                configuration_file=hostp2pd.config_file,
                do_activation=True
                )
            )
        try:
            hostp2pd.run()
        except (KeyboardInterrupt, SystemExit):
            hostp2pd.terminate()
        print("\nhostp2pd service ENDED")
        sys.exit(0)
    else:
        w_p2p_interpreter = None
        try:
            with hostp2pd as session:
                if hostp2pd.process == None or hostp2pd.process.pid == None:
                    print("\nCannot start hostp2pd.\n")
                    os._exit(1) # does not raise SystemExit
                while hostp2pd.threadState == hostp2pd.THREAD.STARTING:
                    time.sleep(0.1)
                if not args.batch_mode:
                    logging.info(
                        f'\n\nhostp2pd (v{__version__}) started in interactive mode.\n')
                sys.stdout.flush()
                w_p2p_interpreter = Interpreter(hostp2pd, args)
                if args.batch_mode:
                    w_p2p_interpreter.cmdloop_with_keyboard_interrupt(
                        'hostp2pd batch mode STARTED\n'
                        'Begin batch commands.')
                else:
                    w_p2p_interpreter.cmdloop_with_keyboard_interrupt(
                        'Welcome to hostp2pd - The Wi-Fi Direct Session Manager.\n'
                        'https://github.com/Ircama/hostp2pd\n'
                        'hostp2pd is running in interactive mode.\n'
                        'Type help or ? to list commands.\n')
        except (KeyboardInterrupt, SystemExit):
            if not args.batch_mode and w_p2p_interpreter:
                w_p2p_interpreter.postloop()
                print('\nExiting.\n')
            else:
                print("hostp2pd batch mode ENDED.")
            sys.exit(1)
