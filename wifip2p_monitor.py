#########################################################################
# wpa_cli controller to manage WiFi Direct connections (wpa_supplicant)
#########################################################################
import subprocess
import re
import signal
import logging
import time

################# start of configuration ################################
find_refresh = 20 # seconds
group_root = 'p2p-wlan0-'

password = '00000000' # The pin must be of 8 digits
white_list = [ 'sample of name of the client device' ]
# Dynamic method: unset use_conn_str; static method: set use_conn_str
use_conn_str = 'virtual_push_button' # unset "use_conn_str" to use "config_methods"
connection_string = 'pbc'
config_methods = 'virtual_push_button keypad' # not used if use_conn_str is set

logging.basicConfig(level=logging.INFO)

# Fixed password method without wihite_list:
# in password, the pin must be of 8 digits,
# connection_string shall add the 'display' label,
# config_methods must be set to 'keypad'.
# Autologin method with wihite_list:
# config_methods must be set to 'virtual_push_button'.

# Examples of configuration with "use_conn_str" static method:
# - Fixed password method without wihite_list
#   Connection_string shall add the 'display' label,
#   Config_methods must be set to 'keypad'.
#use_conn_str = 'keypad'
#connection_string = password + ' display'
#white_list = []
# - Autologin method with wihite_list
#   Config_methods must be set to 'virtual_push_button'
#use_conn_str = 'virtual_push_button'
#connection_string = 'pbc'
#white_list = [ 'Cellulare di servizio' ]
################# end of configuration ##################################


def start(executable_file):
    return subprocess.Popen(
        executable_file,
        #shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        bufsize=0,
        #stderr=subprocess.PIPE
    )


def timeout(sig, frm):
    logging.info("send p2p_find")
    write(process, "p2p_find")
    signal.alarm(find_refresh)


def read(process):
    signal.alarm(find_refresh)
    return process.stdout.readline().decode("utf-8").strip()


def write(process, message):
    signal.alarm(find_refresh)
    process.stdin.write(f"{message.strip()}\n".encode("utf-8"))
    process.stdin.flush()


def terminate(process):
    process.stdin.close()
    process.terminate()
    process.wait(timeout=0.2)


def remove_group(process):
    write(process, "interface")
    while True:
        interf = read(process)
        logging.debug("Reading '%s'", interf)
        if 'interface' in interf:
            continue
        if '>' in interf:
            write(process, "p2p_find")
        if group_root in interf and not '>' in interf:
            write(process, "p2p_group_remove " + interf)                
            monitor_group = ''
            logging.warning("removed %s", interf)
            time.sleep(2)
            if address_cs == arg or use_conn_str:
                write(process, "p2p_connect " + address_cs + " " + connection_string)
                logging.warning('Connection request (' + connection_string + ')')
            else:
                if address_pwd:
                    write(process, "p2p_connect " + address_pwd + " " + password + ' display')
                    logging.warning('Connection request (password): %s', address_pwd)
        if interf == 'OK':
            break
    force_remove_group = 0


if use_conn_str:
    default_config_methods = use_conn_str
else:
    default_config_methods = config_methods

process = start(["stdbuf", "-oL", 'wpa_cli', '-i', 'p2p-dev-wlan0'])
write(process, "set config_methods " + default_config_methods)
write(process, "p2p_find")

address_pwd = ''
address_cs = ''
monitor_group = ''
signal.signal(signal.SIGALRM, timeout)
force_remove_group = 1
logging.warning('Service started')

while True:
    wpa_cli = read(process)
    wpa_cli_l = wpa_cli.split()
    if len(wpa_cli_l) == 0:
        continue
    if wpa_cli_l[0] == '>':
        wpa_cli_l.pop(0)
    if len(wpa_cli_l) == 0:
        continue
    token = wpa_cli_l[0]
    if len(wpa_cli_l) > 1:
        arg = wpa_cli_l[1]
    else:
        arg = ''
    name = re.sub(r".*name='([^']*).*", r'\1', wpa_cli, 1)
    p2p_dev_addr = re.sub(r".*p2p_dev_addr=([^ ]*).*", r'\1', wpa_cli, 1)
    pri_dev_type = re.sub(r".*pri_dev_type=([^ ]*).*", r'\1', wpa_cli, 1)
    token = re.sub(r'<[0-9]*>', r'', token, 1)
    if token == 'CTRL-EVENT-SCAN-STARTED':
        continue
    logging.debug("TRACE %s", wpa_cli)
    if "wpa_supplicant" in wpa_cli:
        logging.warning(wpa_cli)
    if "Connection established" in wpa_cli:
        logging.warning(wpa_cli)
    if token == 'P2P-DEVICE-FOUND' and arg:
        if name in white_list:
            address_cs = arg
            if not use_conn_str:
                write(process, "set config_methods virtual_push_button")
            logging.info('Found device "%s": %s', name, address_cs)
        else:
            logging.debug('Found unknown device "%s"', arg)
        continue
    if token == 'P2P-FIND-STOPPED':
        #write(process, "p2p_find")
        # commented out because might not allow connection when P2P-FIND-STOPPED is received just after a p2p_connect
        continue
    if token == 'P2P-DEVICE-LOST' and arg and address_cs == arg:
        logging.info('P2P-DEVICE-LOST')
        write(process, "p2p_find")
        continue
    if token == 'WPS-TIMEOUT':
        logging.info('WPS-TIMEOUT')
        continue
    if (token == 'P2P-GO-NEG-REQUEST' or token == 'P2P-PROV-DISC-PBC-REQ') and arg:
        if address_cs == arg or use_conn_str:
            if force_remove_group:
                remove_group(process)
            write(process, "p2p_connect " + address_cs + " " + connection_string)
            logging.warning('Connection request (' + connection_string + ')')
            continue
        else:
            address_pwd = arg
            if not use_conn_str:
                write(process, "set config_methods keypad")
            write(process, "p2p_connect " + address_pwd + " " + password + ' display')
            logging.warning('Connection request (password): %s', address_pwd)
            continue
    if token == 'P2P-GROUP-STARTED' and arg:
        monitor_group = arg
        logging.info('P2P-GROUP-STARTED %s', monitor_group)
        continue
    if token == 'P2P-PROV-DISC-SHOW-PIN' and len(wpa_cli_l) > 2:
        logging.warning('Show PIN %s for %s', wpa_cli_l[2], wpa_cli_l[1])
        if name in white_list:
            address_cs = arg
            if not use_conn_str:
                write(process, "set config_methods virtual_push_button")
            logging.info('Found device "%s": %s', name, address_cs)
        else:
            logging.info('Found unknown device "%s"', address_cs)
        continue
    if token == 'P2P-GROUP-REMOVED':
        logging.info('P2P-GROUP-REMOVED')
        continue
    if token == 'P2P-GROUP-STARTED':
        logging.info('P2P-GROUP-STARTED')
        continue
    if token == 'AP-STA-CONNECTED':
        logging.warning('Access point station CONNECTED')
        continue
    if token == 'AP-STA-DISCONNECTED':
        logging.warning('Access point station disconnected')
        if monitor_group:
            write(process, "p2p_group_remove " + monitor_group)
            monitor_group = ''
        else:
            remove_group(process)
        time.sleep(1)
        write(process, "p2p_find")
        #address_cs = ''
        force_remove_group = 0
        continue
    if token == 'FAIL':
        logging.info('FAIL')
        remove_group(process)
        continue
    if token == 'CTRL-EVENT-TERMINATING':
        logging.warning('Service terminated')
        break

terminate(process)
