hostp2pd
========

__The Wi-Fi Direct Session Manager__

*wpa_cli* controller of Wi-Fi Direct connections handled by *wpa_supplicant*, including P2P WPS enrollment.

Tested with wpa_cli and wpa_supplicant version v2.8-devel

This program accepts [Wi-Fi Direct](https://www.wi-fi.org/discover-wi-fi/wi-fi-direct) connections from P2P Clients. It activates a local P2P-GO (Wi-Fi Direct Group Owner) by interfacing [wpa_supplicant](https://en.wikipedia.org/wiki/Wpa_supplicant) via [wpa_cli](https://manpages.debian.org/stretch/wpasupplicant/wpa_cli.8.en.html).

In order to fully automate the workflow of a P2P-GO in [AP mode](https://en.wikipedia.org/wiki/Wireless_access_point), the program runs *wpa_cli* in background and pipes [p2p commands](https://w1.fi/cgit/hostap/plain/wpa_supplicant/README-P2P) to it via pseudo-tty communication, while reading events.

hostp2pd includes a command-line interface for extensive monitoring and controlling, can be executed as a batch or as a daemon and provides an API for integration into other Python programs.

# Why using Wi-Fi Direct with Android devices

Wi-Fi Direct (formerly named Wi-Fi Peer-to-Peer, or P2P) allows two devices to connect directly to each other, without the need for a traditional Wireless Access Point (AP). The role of the access point is replaced by the so-called Group Owner, typically negotiated during the connection setup.

An advantage of Wi-Fi Direct with Android is that it can coexist with a traditional Wi-Fi connection as well as with a cellular connection: this means that an Android smartphone can be connected to a mobile network, or to a Wi-Fi AP with internet access (which always takes priority to the mobile network for its internal Android routing configuration) and at the same time connect to the UNIX device via Wi-Fi Direct, without losing the routing to the mobile network or AP because, differently from the standard Wi-Fi connection, Wi-Fi Direct does not interfere with the mobile routing.

Apple iOS devices do not support Wi-Fi Direct.

*hostp2pd* enables *wpa_supplicant* to accept Wi-Fi Direct connections from Android smartphones, as well as managing standard AP connection to the same group in P2P-GO mode.

# Installation

```shell
# Checking Python version (should be 3.5 or higher)
python3 -V

# Installing prerequisites
python3 -m pip install pyyaml
python3 -m pip install python-daemon
python3 -m pip install git+https://github.com/Ircama/hostp2pd.git
```

# Usage

To start hostp2pd in interactive mode, run the following command:

```shell
python3 -m hostp2pd -i p2p-dev-wlan0 -c /etc/hostp2pd.yaml
```

To start a Wi-Fi Direct connection with Android and connect a UNIX system running *hostp2pd*, tap Settings > Wi-Fi > Advanced settings > Wi-Fi Direct and wait for the peer device to appear. Select it and wait for connection established. Notice that through this process, the mobile/cellular connection is not disabled while the Wi-Fi Direct connection is active.

The P2P-Device interface is created by *wpa_supplicant* over the physical wlan interface, if default options are used. Use `iw dev` to list the available wlan interfaces. An unnamed/non-netdev interface with type P2P-device should be found. If no P2P-Device is shown (e.g., only the physical *phy#0* Interface *wlan0* is present), either *wpa_supplicant* is not active or is not appropriately compiled/configured. With *wlan0* as physical interface (ref. `iw dev`), to get the name of the P2P-Interface use the command `wpa_cli -i wlan0 interface`: it should return the physical interface *wlan0* and the P2P-device (e.g., *p2p-dev-wlan0*). Use this name as argument to the `-i` option of *hostp2pd*. Notice also that, if a P2P-Device is configured, `wpa_cli` without option automatically points to this interface.

Notice that, depending the capabilities of the wlan device driver, the AP virtual interface has to be stopped before creating a P2P-GO group. Also, a persistent P2P-GO group can provide AP capabilities together with the Wi-Fi Direct functionalities.

Check this command:

```bash
iw list | grep "Supported interface modes" -A 8
```

It should return one line including P2P-GO. If only STA and managed are returned, the device driver of the board (or the hw itself) does not allow creating a P2P-GO interface. Output of the Raspberry Pi 4:

```
        Supported interface modes:
                 * IBSS
                 * managed
                 * AP
                 * P2P-client
                 * P2P-GO
                 * P2P-device
```

Use this command to check the allowed combination options:

```bash
iw list | grep "valid interface combinations" -A 8
```

Every line contains alternative combinations. With the Broadcom BCM2711 SoC included in a Raspberry Pi 4 B, I get the following:

```
        valid interface combinations:
                 * #{ managed } <= 1, #{ P2P-device } <= 1, #{ P2P-client, P2P-GO } <= 1,
                   total <= 3, #channels <= 2
                 * #{ managed } <= 1, #{ AP } <= 1, #{ P2P-client } <= 1, #{ P2P-device } <= 1,
                   total <= 4, #channels <= 1
        Device supports scan flush.
        Device supports randomizing MAC-addr in sched scans.
        Supported extended features:
                * [ 4WAY_HANDSHAKE_STA_PSK ]: 4-way handshake with PSK in station mode
```

It means that not more than one AP or P2P-GO interface can be configured at the same time.

Optionally, *hostp2pd* allows the `-p` option, which defines an external program to be run with "stop" argument before activating a group and with "start" argument after deactivating a group; this allows controlling AP resources before groups are created or after groups are removed.

This is an example of RUN_PROGRAM controlling an AP interface named *uap0*:

```bash
#!/bin/bash

set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # dont hide errors within pipes
set -eE -o functrace
set -o errtrace

case "$1" in
stop) systemctl is-active --quiet uap0 && systemctl stop uap0;;
start) systemctl is-active --quiet uap0 && exit 3
       systemctl stop dhcpcd || exit $?
       sleep 3
       systemctl start uap0
       uap_ret=$?
       sleep 3
       systemctl start dhcpcd
       dhcpcd_ret=$?
       test "$uap_ret" -ne 0 && exit $uap_ret
       exit $dhcpcd_ret
       ;;
esac
```

# Configuration files

The following files need to be configured.

/var/run/hostp2pd-

## wpa_supplicant.conf

Relevant documents:
- [wpa_supplicant.conf configuration file format](https://w1.fi/cgit/hostap/plain/wpa_supplicant/wpa_supplicant.conf)
- [Wi-Fi P2P implementation in wpa_supplicant](https://w1.fi/cgit/hostap/plain/wpa_supplicant/README-P2P).

Ensure that *wpa_supplicant.conf* includes the following P2P configuration lines (skip all comments):

```ini
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev # this allows using wpa_cli as wpa_supplicant client
update_config=1 # this allows wpa_supplicant to update the wpa_supplicant.conf configuration file
device_name=DIRECT-test # this is the P2P name shown to the Android phones while connecting via Wi-Fi Direct
device_type=6-0050F204-1 # (Network Infrastructure / AP)
config_methods=keypad # Use a fixed password on UNIX, which is asked from a keypad popped up on the Android devices
p2p_go_intent=15 # force UNIX to become a P2P-GO (Group Owner)
persistent_reconnect=1 # allow reconnecting to a persistent group without asking a password
p2p_go_ht40=1 # Optional: use HT40 channel bandwidth (300 Mbps) when operating as GO (instead of 144.5Mbps).
country=<country ID> # Use your country code here

# This is an example of P2P persistent group:
network={
        ssid="DIRECT-PP-group" # Name of the persistent group saved on the Android phone and shown within the AP names
        psk="mysecretpassword" # Password used when connecting to the AP (unrelated to P2P-GO enrolment, which is done via WPS)
        proto=RSN
        key_mgmt=WPA-PSK
        pairwise=CCMP
        auth_alg=OPEN
        mode=3 # WPAS MODE P2P-GO
        disabled=2 # Persistent P2P group
}
```

The `network` stanzas will define persistent GO groups if the following three conditions occur:

-	The SSID shall begin with the `ssid="DIRECT-..."` prefix (P2P_WILDCARD_SSID), otherwise the group is not announced to the network as a P2P group; any alphanumeric string can be used after DIRECT- prefix; empirically, the documented format "DIRECT-<random two octets>" (with optional postfix) is not needed.
-	A `mode=3` directive shall be present, meaning WPAS_MODE_P2P_GO, otherwise the related p2p_group_add command fails for unproper group specification
-	A `disabled=2` directive shall be present, meaning persistent P2P group, otherwise the stanza is not even recognized and listed as persistent (`disabled=0` means normal network; `disabled=1` will announce a disabled network).

The following usage modes are allowed:

- interactive mode (with no option, by default *hostp2pd* starts in interactive mode; a prompt is shown)
- batch mode (use `-b` option; e.g., `-b -` or `-b output_file_name`
- daemon mode (use `-d` option; alternatively to `-d`, option `-t` terminates a running daemon and option `-r` dynamically reloads the configuration of a running program)

## hostp2pd.yaml

Check the [hostp2pd.yaml example file](hostp2pd.yaml). It is suggested to install it to /etc/hostp2pd.yaml

## systemctl

Run the following to install the service:

```ini
sudo -Es
SYSTEMD_EDITOR=tee systemctl edit --force --full hostp2pd <<\EOF
[Unit]
Description=hostp2pd - The Wi-Fi Direct Session Manager
After=network.target

[Service]
Type=simple
Type=forking
Environment="CONF=/etc/hostp2pd.yaml"
ExecStart=/usr/bin/python3 -m hostp2pd -c ${CONF} -d
ExecReload=/usr/bin/python3 -m hostp2pd -c ${CONF} -r
ExecStop=/usr/bin/python3 -m hostp2pd -c ${CONF} -t

[Install]
WantedBy=multi-user.target
EOF

systemctl enable hostp2pd
systemctl start hostp2pd
exit
```

# Compatibility

hostp2pd has been tested with Python 3.7.3 on Debian (Raspberry Pi OS Buster). Python 2 is not supported.

Only UNIX operating systems running *wpa_supplicant* and *wpa_cli* are allowed.

## Built-in keywords

At the `CMD> ` prompt, the emulator accepts the following commands:

- `loglevel` = If an argument is given, set the logging level, otherwise show the current one. Valid numbers: CRITICAL=50, ERROR=40, WARNING=30, INFO=20, DEBUG=10.
- `reload` = Reload configuration from the latest valid configuration file. Optional argument is a new configuration file; to load defaults use `reset` as argument.
- `reset` = Reset the hostp2pd statistics.
- `stats` = Print execution statistics. Besides, the following variables can be used at prompt level:
  - `hostp2pd.statistics`: list of all commands issued by wpa_supplicant
  - `hostp2pd.addr_register`: list of all discovered peers
- `quit` (or end-of-file/Control-D, or break/Control-C) = quit the program
- `help` = List available commands (a detailed help can be obtained with the command name as argument).
- `pause` = pause the execution. (Related attribute is `hostp2pd.threadState = THREAD.PAUSED`.)
- `prompt` = toggle prompt off/on if no argument is used, or change the prompt if using an argument
- `resume` = resume the execution after pausing; also prints the used device. (Related attribute is `hostp2pd.threadState = THREAD.ACTIVE`)
- `wait <n>` = delay the execution of the next command of `<n>` seconds (floating point number; default is 10 seconds)
- `color` = toggle off/on the usage of colors in the prompt
- `history [<n>]` = print the last 20 items of the command history; if an argument is given, print the last n items in the history; with argument *clear*, clears the history. The command history is permanently saved to file *.hostp2pd_mgr_history* within the home directory.

In addition to the previously listed keywords, any Python command is allowed to query/configure the backend thread.

At the command prompt, cursors and [keyboard shortcuts](https://github.com/chzyer/readline/blob/master/doc/shortcut.md) are allowed. Autocompletion (via TAB key) is active with UNIX systems for all previously described commands and also allows Python keywords and namespaces (built-ins, self and global). If the autocompletion matches a single item, this is immediately expanded; Conversely, if more possibilities are matched, none of them is returned, but pressing TAB again displays a list of available options.

# Limitations

The current implementation has the following limitations:

- tested with an Android 10 phone connecting to a Raspberry Pi 4 with Wi-Fi Direct protocol (and also using AP mode)
- At the moment, only one P2P GO active group is managed for a specific P2P-Device, even if more instances of hostp2pd are allowed, each one referred to a specific P2P-Device (generally a specific wireless wlan board). This is because *wpa_supplicant* appears to announce the P2P-Device id to the Android clients (ref. "device_name" in the related configuration, which is the same for all groups) and not the specific active P2P GO groups; likewise, it is not known how an Android client can inform *wpa_supplicant* to enrol a specific group of a known P2P-device through the default Wi-Fi Direct user interface. Notice also that some wireless drivers only allow one P2P-GO group; in case more P2P-GO group are defined, only the first one in the configuration file is used (e.g., the first group listed by the *wpa_cli* `list_networks` command including `[P2P-PERSISTENT]`); in case a persistent group is active, it is linked to the *wpa_supplicant* configuration with same SSID. If a group is not created, the first P2P client connection creates a dynamic group; all other P2P client connections are enrolled to the same group.
- Tested with only one station; two or more stations should concurrently connect to the same persistent group.
- Only the first persistent group configured in *wpa_supplicant.conf* is used; other groups can be defined in the configuration, but they are not automatically activated.
- as hostp2pd is fully unattended, the following WPS credential methods are available: *pbc* and *keypad*. The *display* configuration method (much more secure than *keypad*) is not implemented and need interaction (to insert the PIN presented by the Android handset). This means that at the moment the enrolment is done with a either static PIN saved in the hostp2p.yaml configuration file (or passed to the object) or with no PIN at all (PBC mode). To protect PBC (no PIN), a list of enabled enrollees names can be defined. Notice that this is a weak authentication method, because the enrollees names are publicly announced.

# Command-line arguments

```
usage: python3 -m hostp2pd [-h] [-v] [-vv] [-t] [-r] [-c CONFIG_FILE] [-d]
                           [-b FILE] [-i INTERFACE] [-p RUN_PROGRAM]

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbosity       print execution logging
  -vv, --debug          print debug logging information
  -t, --terminate       terminate a daemon process sending SIGTERM
  -r, --reload          reload configuration of a daemon process sending
                        SIGHUP
  -c CONFIG_FILE, --config CONFIG_FILE
                        Configuration file.
  -d, --daemon          Run hostp2pd in daemon mode.
  -b FILE, --batch FILE
                        Run hostp2pd in batch mode. Argument is the output
                        file. Use an hyphen (-) for standard output.
  -i INTERFACE, --interface INTERFACE
                        Set the interface managed by hostp2pd.
  -p RUN_PROGRAM, --run_program RUN_PROGRAM
                        Name of the program to run with start and stop
                        arguments.

hostp2pd - The Wi-Fi Direct Session Manager. wpa_cli controller of Wi-Fi
Direct connections handled by wpa_supplicant.
```

# Configuration methods

The program allows the following configuration method settings:

- `pbc_in_use: None`: use the configuration method set in *wpa_supplicant.conf* (this is the suggested one, defining `keypad` method in *wpa_supplicant.conf*)
- `pbc_in_use: False`: force the *keypad* configuration method, using `password: "<8 digits>"` configured in *hostp2pd.yaml*. (Notice also that any password different from eight digits is not accepted by *wpa_supplicant*.)
- `pbc_in_use: True`: force the *virtual_push_button* configuration method.

Notice that the keypad password shall be of exactly 8 digits (ref. `p2p_passphrase_len=8`, which is a default configuration in *wpa_supplicant.conf*).

Configuration methods:
- *keypad*: the Android phone prompts a keypad; the user has to enter a fixed passkey set in the *hostp2pd.yaml* configuration file.
- *virtual_push_button* (pbc): no password is used. Anyway, a withe list of client names can be defined.

Using *virtual_push_button* is a extremely weak enrolment method, where discovering the P2P client names can be easily made by any user.

# Use cases

The UNIX system will always be a GO (Group Owner).

In standard group creation, the UNIX device negotiates a group on demand. In autonomous and persistent group creation, a device becomes a group owner by itself without any client request. Persistent groups are saved in the *wpa_supplicant* configuration file and can be reused after restarting *wpa_supplicant* or rebooting the UNIX system (or after reboot of the Android device). Wi-Fi MAC addressess are generally randomized. With persistent groups, both the Android device and the UNIX system keep the same wireless MAC address (see note below on *wpa_supplicant*).

The following use cases are allowed:

- P2P Group formation method using Negotiation Method with standard groups (dynamically created and removed): no group is created at startup; the first client connection performs the P2P group formation; the group is removed after the client disconnection (`activate_persistent_group: False`, `dynamic_gropus: True`, no persistent group defined in *wpa_supplicant.conf*).
- P2P Group Formation using Autonomous GO Method, configuring an autonomous group activated at startup: an autonomous group (`activate_persistent_group: False`, `dynamic_gropus: False`, no persistent group defined in *wpa_supplicant.conf*)
- Persistent group activated at the first access (`activate_persistent_group: False`, `dynamic_gropus: False`, with persistent group defined in *wpa_supplicant.conf*)
- Persistent group activated at startup (`activate_persistent_group: True`, `dynamic_gropus: False`, with persistent group defined in *wpa_supplicant.conf*). This is the suggested method

If a whitelist (`white_list: ...`) is configured with PCB (`pbc_in_use: True` or `config_methods=virtual_push_button`) and if the client name does not correspond to any whitelisted names, then the configuration method is changed from pbc to keypad.

Internally, hostp2pd activates ordinary connections via `p2p_connect`. Autonomous/Persistent Groups are activated with `p2p_group_add`. Connections to Autonomous/Persistent Groups are managed by a subprocess named Enroller, which does `wps_pin` or `wps_pbc` over the group interface. wpa_cli commands `interface` and `list_networks` are used to check groups. `p2p_find` is periodically executed to ensure announcements (especially when P2P group beacons are not active). A number of events are managed.

With standard group negotiation using fixed password method, an Android client will not save the password (authorization has to be performed on every connection). Using persistent groups, a local group information element is permanently stored in the Android handset (until it is deleted by hand) and this enables to directly perform all subsequent reconnections without separate authorization (e.g., without user interaction).

# Logging

Logging is configured in *hostp2pd.yaml*. This is in [Pyhton logging configuration format](https://docs.python.org/3/library/logging.config.html). By default, logs are saved in /var/log/hostp2pd.log. Also, logs can be forced to a specific loglevel through the `force_logging` configuration attribute.

In interactive mode, logging can be changed using `loglevel`.

To browse the log files, [lnav](https://github.com/tstack/lnav) is suggested.

# Python application integration

## Instantiating the class

All arguments are optional.

```python
hostp2pd = HostP2pD(
    config_file=config_file,    # optional pathname of the hostp2pd.yaml configuration file
    interface="p2p-dev-wlan0",  # optional string defining the wlan interface (check it with iw dev)
    run_program="",             # optional run_program
    force_logging=None,         # optional logging mode
    white_list=[],              # optional white list of allowed PBC station names
    password="00000000")        # optional PIN of keypad enrollment
```

Check *__main__.py* for usage examples of the three allowed invocation methods: interactive, batch and daemon modes.

## interactive mode

```python
with hostp2pd as session:
    # do interactive monitoring while the process run
```

## batch/daemon mode

```
hostp2pd.run()
# execution suspended until process terminates
```

To terminate the process:

```
hostp2pd.terminate()
```

To perform process reconfiguration:

```python
hostp2pd.read_configuration(
    configuration_file=hostp2pd.config_file,
    do_activation=True
    )
```

# Software architecture

Two threads are started when using the context manager: "Main" and "Core"; the first returns the context to the caller, the second runs the engine. In batch/daemon mode, only the in-process "Core" runs.

The "Core" thread starts *wpy_cli* as subprocess connected to the P2P-Device, interfacing it in both IN and OUT directions via pty, using no-echo mode.

When a group is activated, a second process is started, named Enroller, to manage the WPS Enrolling procedure. This process communicates with the core thread via multiprocessing Manager and in turn starts another *wpy_cli* as subprocess connected to the P2P group, interfaced in the same way as what done by the Core.

Signals are configured among processes, so that termination is synced. Core sends SIGHUP to Enroller if a configuration needs to be reloaded.

# Wi-Fi Direct configuration on a Raspberry Pi

To configure Wi-Fi Direct on a Raspberry Pi, follow [this link](https://raspberrypi.stackexchange.com/q/117238/126729).

Notice that with Raspberry Pi, running AP and P2P concurrently is not supported. Specifically, if a command like `iw dev wlan0 interface add uap0 type __ap` is issued to create a virtual Wi-Fi interface (in order for an access point to be managed for instance by *hostapd*), `wpa_cli -i p2p-dev-wlan0 p2p_connect <address> pbc` subsequently fails to create the *p2p-wlan0-0* interface and *wpa_supplicant* returns EBUSY error code -16 (Device or resource busy). Deleting the virtual interface (via `iw dev uap0 del`) restores the correct behavior.

# MAC Randomization

Linux and Android devices use by default randomized MAC addresses when probing for new Wi-Fi Direct networks while not currently associated with a network.

MAC randomization prevents listeners from using MAC addresses to build a history of device activity, thus increasing user privacy.

Anyway, when using persistent groups, MAC addresses shall not vary in order to avoid breaking reconnections. This appears to be appropriately managed by Android devices.

Nevertheless, on some UNIX devices (e.g., with Raspberry Pi OS., based on Debian Buster) reinvoking a persistent group after restarting wpa_supplicant will change the related virtual interface local address, breaking the reuse of the saved group in the peer system.

This limitation prevents to setup effective Wi-Fi Direct configurations between Raspberry Pi and Android mobile phones.

At the moment a valid configuration that prevents MAC randomization with persistent groups is not known. The following is a workaround that implies modifying wpa_supplicant sources and recompiling it.

To download wpa_supplicant sources and prepare the environment:

```bash
git clone git://w1.fi/srv/git/hostap.git
sudo apt-get install -y libnl-genl-3-dev libnl-route-3-dev
sudo apt install build-essential libdbus-glib-1-dev libgirepository1.0-dev
```

Perform the following modifications:

Edit *hostap/src/drivers/driver_nl80211.c*. In `nl80211_create_iface_once()`, after

```c
	if (nla_put_flag(msg, NL80211_ATTR_IFACE_SOCKET_OWNER))
		goto fail;
```

and before

```c
	ret = send_and_recv_msgs(drv, msg, handler, arg, NULL, NULL);
```

Add the following:

```c
#define STATIC_MAC_ADDRESS "dc:a6:32:01:02:03"

	if (iftype == NL80211_IFTYPE_P2P_DEVICE) {
        u8 mac_addr[ETH_ALEN];
        if (hwaddr_aton2(STATIC_MAC_ADDRESS, mac_addr))
            if(nla_put(msg, NL80211_ATTR_MAC, ETH_ALEN, mac_addr))
                goto fail;
    }
```

Then you can recompile.

As alternative modding, instead of adding the MAC address in the driver controller, you can do the following change, so that the MAC address is set in *p2p_supplicant.c*:

```c
    if (addr && (iftype == NL80211_IFTYPE_P2P_DEVICE)) {
            if(nla_put(msg, NL80211_ATTR_MAC, ETH_ALEN, addr))
                goto fail;
    }
```

Then edit *hostap/wpa_supplicant/p2p_supplicant.c*. In `wpas_p2p_add_p2pdev_interface(()`, change *NULL* with *addr* as in the following line:

```
	ret = wpa_drv_if_add(wpa_s, WPA_IF_P2P_DEVICE, ifname, addr, NULL,
```

And, before it, add:

```
#define STATIC_MAC_ADDRESS "dc:a6:32:01:02:03"

    u8 mac_addr[ETH_ALEN], *addr;
    addr = mac_addr;
    if (!hwaddr_aton2(STATIC_MAC_ADDRESS, addr))
        addr = NULL;
```

To go on compiling the sources, perform the following commands:

```bash
cd hostap
cp wpa_supplicant/defconfig wpa_supplicant/.config
cd wpa_supplicant
make
```

To ensure usage of the same static MAC address with the P2P-Device virtual interface, you can use the created *wpa_supplicant* in place of the existing one.

# Licensing

(C) Ircama 2021 - CC BY SA 4.0

_______________

__Notes__

_Running wpa_supplicant from the command line_

Standard distribution already include a wpa_supplicant service. Anyway, for information, the following allows running it from the command line:

```bash
sudo /sbin/wpa_supplicant -c/etc/wpa_supplicant/wpa_supplicant-wlan0.conf -Dnl80211,wext -iwlan0
```

Blog with [in-depth notes on Wi-Fi Direct](https://praneethwifi.in/)
