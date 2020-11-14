#########################################################################
# wpa_cli controller to manage WiFi Direct connections (wpa_supplicant)
#########################################################################
import subprocess
import re
import signal
import logging
import time

#########################################################################
white_list = [ '......' ]
find_refresh = 20 # seconds
group_root = 'p2p-wlan0-'
logging.basicConfig(level=logging.INFO)
#########################################################################


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
    logging.debug("send p2p_find")
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
        logging.debug("DEBUG %s", interf)
        if 'interface' in interf:
            continue
        if '>' in interf:
            write(process, "p2p_find")
        if group_root in interf and not '>' in interf:
            write(process, "p2p_group_remove " + interf)                
            monitor_group = ''
            logging.info("removed %s", interf)
            time.sleep(2)
            write(process, "p2p_connect " + monitor_address + " pbc")
        if interf == 'OK':
            break
    force_remove_group = 0


process = start(["stdbuf", "-oL", 'wpa_cli', '-i', 'p2p-dev-wlan0'])
write(process, "wps_pbc")
write(process, "p2p_find")

monitor_address = ''
monitor_group = ''
signal.signal(signal.SIGALRM, timeout)
force_remove_group = 1

while True:
    wpa_cli = read(process)
    #logging.debug("TRACE %s", wpa_cli)
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
    if token == 'P2P-DEVICE-FOUND':
        if name in white_list:
            monitor_address = arg
            #write(process, "p2p_connect " + monitor_address + " pbc")
        logging.debug('P2P-DEVICE-FOUND %s', monitor_address)
        continue
    if token == 'P2P-FIND-STOPPED':
        #write(process, "p2p_find")
        # commented out because might not allow connection when P2P-FIND-STOPPED is received just after a p2p_connect
        continue
    if token == 'P2P-DEVICE-LOST':
        logging.debug('P2P-DEVICE-LOST')
        continue
    if token == 'WPS-TIMEOUT':
        logging.debug('WPS-TIMEOUT')
        continue
    if (token == 'P2P-GO-NEG-REQUEST' or token == 'P2P-PROV-DISC-PBC-REQ') and monitor_address == arg:
        if force_remove_group:
            remove_group(process)
        write(process, "p2p_connect " + monitor_address + " pbc")
        logging.info('Connection request')
        continue
    if token == 'P2P-GROUP-STARTED':
        monitor_group = arg
        logging.debug('P2P-GROUP-STARTED %s', monitor_group)
        continue
    if token == 'P2P-GROUP-REMOVED':
        logging.debug('P2P-GROUP-REMOVED')
        continue
    if token == 'P2P-GROUP-STARTED':
        logging.debug('P2P-GROUP-STARTED')
        continue
    if token == 'AP-STA-CONNECTED':
        logging.info('Access point station CONNECTED')
        continue
    if token == 'AP-STA-DISCONNECTED':
        logging.info('Access point station disconnected')
        if monitor_group:
            write(process, "p2p_group_remove " + monitor_group)
            monitor_group = ''
        else:
            remove_group(process)
        write(process, "p2p_find")
        #monitor_address = ''
        force_remove_group = 0
        continue
    if token == 'FAIL':
        logging.debug('FAIL')
        remove_group(process)
        continue

terminate(process)
