hostp2pd
========

__The Wi-Fi Direct Session Manager__

*hostp2pd* implements a soft host [Access Point](https://en.wikipedia.org/wiki/Wireless_access_point) (AP) user space [daemon](https://en.wikipedia.org/wiki/Daemon_(computing)) software in [Wi-Fi Direct](https://en.wikipedia.org/wiki/Wi-Fi_Direct) mode, enabling a [wireless network interface card](https://en.wikipedia.org/wiki/Wireless_network_interface_controller) to act as *Ad hoc* access point and [Wi-Fi Protected Setup](https://en.wikipedia.org/wiki/Wi-Fi_Protected_Setup) (WPS) [authentication server](https://en.wikipedia.org/wiki/Authentication_server). It features basic functionalities roughly similar to [hostapd](https://en.wikipedia.org/wiki/Hostapd) (with its [hostapd.conf](https://w1.fi/cgit/hostap/plain/hostapd/hostapd.conf) configuration file), which is the widely adopted and higly functional AP software, generally used for [infrastructure mode networking](https://en.wikipedia.org/wiki/Service_set_(802.11_network)#Infrastructure_mode). When implementing a [P2P persistent group](https://praneethwifi.in/2019/11/23/p2p-group-formation-procedure-persistent-method/), [wpa_supplicant](https://en.wikipedia.org/wiki/Wpa_supplicant) offers the [P2P-GO](https://en.wikipedia.org/wiki/Wireless_LAN#Peer-to-peer) features enabled by *hostp2pd* to connect P2P Clients like Android smartphones, as well as provide the standard infrastructure AP mode to the same P2P-GO group, without the need of *hostapd*.

In order to accept [Wi-Fi Direct](https://www.wi-fi.org/discover-wi-fi/wi-fi-direct) connections from P2P Clients, activate a local [P2P-GO](https://w1.fi/wpa_supplicant/devel/p2p.html) (Wi-Fi Direct Group Owner) and perform WPS authentication, *hostp2pd* fully relies on *wpa_supplicant*, interfacing it through [wpa_cli](https://manpages.debian.org/stretch/wpasupplicant/wpa_cli.8.en.html) command-line interface ([CLI](https://en.wikipedia.org/wiki/Command-line_interface)): *wpa_cli* is run in background and [p2p commands](https://w1.fi/cgit/hostap/plain/wpa_supplicant/README-P2P) are piped via pseudo-tty communication, while events returned by *wpa_cli* are read and processed.

*hostp2pd* includes a command-line interface mode for monitoring and controlling; it can be executed as a batch or as a daemon and provides an API for integration into other Python programs.

# Connecting via Wi-Fi Direct with Android devices

Wi-Fi Direct (formerly named Wi-Fi Peer-to-Peer, or *P2P*) allows devices to connect directly to each other, without the need for a traditional Wireless Access Point (AP). The role of the access point is replaced by the so-called Group Owner (GO), either negotiated during the connection setup, or autonomously created.

An advantage of Wi-Fi Direct with Android is that it can coexist with a traditional Wi-Fi connection as well as with a cellular connection: it means that an Android smartphone can be connected to a mobile network, or to an infrastructure-mode Wi-Fi AP with internet access and at the same time connect to a UNIX device via Wi-Fi Direct, without losing the routing to the mobile (or AP) network. This is because with Android, differently from the standard infrastructure-mode Wi-Fi AP connection where an active Wi-Fi session always takes routing priority to the mobile network for its internal Android routing configuration that disables mobile routing, Wi-Fi Direct does not interfere with the routing table.

Apple iOS devices do not support Wi-Fi Direct, but can concurrently connect to a P2P persistent group in AP mode the same way as for traditional infrastructure-mode Access Points managed by *hostapd*. Differently from Android phones, if the persistent group does not configure a default router, iOS does not change the routing tables of the cellular network, which is by consequence not lost.

# Installation

```shell
# Checking Python version (should be 3.5 or higher)
python3 -V

# Installing prerequisites
python3 -m pip install pyyaml
python3 -m pip install python-daemon

# Installing hostp2pd
python3 -m pip install git+https://github.com/Ircama/hostp2pd.git
```

# Usage

To run *hostp2pd* in interactive mode, use the following command:

```shell
python3 -m hostp2pd -i p2p-dev-wlan0 -c /etc/hostp2pd.yaml
```

- `-i` option: The P2P-Device interface used by hostp2pd is created by *wpa_supplicant* over the physical wlan interface (if default options are used). Use `iw dev` to list the available wlan interfaces. An *unnamed/non-netdev* interface with *type P2P-device* should be found. If no P2P-Device is shown (e.g., only the physical *phy#0* Interface *wlan0* is present), either *wpa_supplicant* is not active or it is not appropriately compiled/configured. With *wlan0* as physical interface (ref. `iw dev`), to get the name of the P2P-Interface use the command `wpa_cli -i wlan0 interface`: it should return the physical interface *wlan0* and the P2P-device (e.g., *p2p-dev-wlan0*). Use this name as argument to the `-i` option of *hostp2pd*. Notice also that, if a P2P-Device is configured, `wpa_cli` without option should automatically point to this interface.
- `-c` option: a configuration file ([here](hostp2pd.yaml) an example) is not strictly necessary to start the first test; a minimum parameter would be the password, which can be alternatively defined using a shell [Here Document](https://en.wikipedia.org/wiki/Here_document) expression:
  ```shell
  python3 -m hostp2pd -i p2p-dev-wlan0 -c - <<\eof
  password: "00000000"
  eof
  ```

To start a Wi-Fi Direct connection of an Android smartphone and connect a UNIX system running *hostp2pd*, tap Settings > Wi-Fi > Advanced settings > Wi-Fi Direct and wait for the peer UNIX device to appear. Select it, optionally type the PIN and wait for connection established. If the default configuration is used, which exploits a predefined persistent group, any subsequent reconnection to this group is done without repeating the WPS authorization process. As previously explained, through this process the mobile/cellular connection is not disabled while the Wi-Fi Direct connection is active.

Depending on the capabilities of the wlan device driver, the AP virtual interface has to be stopped before creating a P2P-GO group. As already mentioned, a persistent P2P-GO group can provide AP capabilities together with the Wi-Fi Direct functionalities.

Check the supported interface modes with this command:

```shell
iw list | grep "Supported interface modes" -A 8
```

It should return one line including P2P-GO. If only STA and managed are returned, the device driver of the board (or the hw itself) does not support creating a P2P-GO interface.

As an example, this is the output of the Raspberry Pi 4:

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

Every line contains alternative combinations. For instance, with the Broadcom BCM2711 SoC included in a Raspberry Pi 4 B, we get the following:

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

It means that not more than one AP or P2P-GO interface can be configured at the same time, with a single P2P-GO group supported.

Optionally, *hostp2pd* allows the `-p` option, which defines an external program to be run with "stop" argument before activating a group and with "start" argument after deactivating a group; this allows controlling external AP resources before groups are created or after groups are removed.

This is an example of RUN_PROGRAM controlling an AP interface named *uap0*, by disabling and enabling it according to the GO group creation/removal:

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

hostp2pd needs *wpa_supplicant.conf* and optionally *hostp2pd.yaml*.

## wpa_supplicant.conf

For a reference description of the file format of *wpa_supplicant.conf*, ref. these relevant documents:
- [wpa_supplicant.conf configuration file format](https://w1.fi/cgit/hostap/plain/wpa_supplicant/wpa_supplicant.conf),
- [Wi-Fi P2P implementation in wpa_supplicant](https://w1.fi/cgit/hostap/plain/wpa_supplicant/README-P2P).

Ensure that *wpa_supplicant.conf* includes the following P2P configuration lines (skip all comments):

```ini
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev # this allows using wpa_cli as wpa_supplicant client
update_config=1                                         # this allows wpa_supplicant to update the wpa_supplicant.conf configuration file
device_name=DIRECT-test                                 # this is the P2P name shown to the Android phones while connecting via Wi-Fi Direct;
                                                        # use any name in place of "test" and keep the "DIRECT-" prefix.
device_type=6-0050F204-1                                # (Network Infrastructure / AP)
config_methods=keypad                                   # keypad uses a fixed password on UNIX, which is asked from a keypad popped up on the Android devices
p2p_go_intent=15                                        # force UNIX to become a P2P-GO (Group Owner)
persistent_reconnect=1                                  # allow reconnecting to a persistent group without user acknowledgement
p2p_go_ht40=1                                           # Optional: use HT40 channel bandwidth (300 Mbps) when operating as GO (instead of 144.5Mbps).
country=<country ID>                                    # Use your country code here

# This is an example of P2P persistent group:
network={
        ssid="DIRECT-PP-group"                          # Name of the persistent group saved on the Android phone and shown within the AP names;
                                                        # use any name in place of "PP-group" and keep the "DIRECT-" prefix.
        psk="mysecretpassword"                          # Password used when connecting to the AP (unrelated to P2P-GO enrolment, which is done via WPS)
        proto=RSN
        key_mgmt=WPA-PSK
        pairwise=CCMP
        auth_alg=OPEN
        mode=3                                          # WPAS MODE P2P-GO
        disabled=2                                      # Persistent P2P group
}
```

The above example shows how to predefine a P2P persistent group. Specifically, the `network` stanzas will define persistent GO groups if the following three conditions occur:

-	The SSID shall begin with the `DIRECT-...` prefix (P2P_WILDCARD_SSID), otherwise the group is not appropriately announced to the network as a P2P group; any alphanumeric string can be used after `DIRECT-` prefix; empirically, the documented format `DIRECT-<random two octets>` (with optional postfix) is not needed.
-	A `mode=3` directive shall be present, meaning [WPAS_MODE_P2P_GO](https://w1.fi/wpa_supplicant/devel/structwpa__ssid.html), otherwise the related `p2p_group_add` command fails for unproper group specification.
-	A `disabled=2` directive shall be present, meaning persistent P2P group, otherwise the stanza is not even recognized and listed as persistent (`disabled=0` indicates normal network; `disabled=1` will announce a disabled network).

If no persistent group is predefined in in *wpa_supplicant.conf* and if `activate_persistent_group` is set to `True`, then *hostp2pd* creates a generic persistent group, giving it a name with format `DIRECT-<random two octets>`.

The following usage modes of *hostp2pd* are allowed:

- interactive mode (with no option, by default *hostp2pd* starts in this mode and a prompt is shown)
- batch mode (use `-b` option; e.g., `-b -` for standard log output, or `-b output_file_name`)
- daemon mode (use `-d` option). Suggested configuration. If a daemon process is active, option `-t` terminates a running daemon and option `-r` dynamically reloads the configuration of a running program.

When running as a daemon, *hostp2pd* prevents multiple instances over the same P2P-Device interface by using lock files with name `/var/run/hostp2pd-<interface>.pid`, where `<interface>` is the name of the P2P-Device interface. (For instance, */var/run/hostp2pd-p2p-dev-wlan0.pid*.)

## hostp2pd.yaml

Check the [hostp2pd.yaml example file](hostp2pd.yaml). It is suggested to install it to /etc/hostp2pd.yaml.

## Installing the service

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

*hostp2pd* has been tested with:

- wpa_cli and wpa_supplicant version v2.8-devel
- Python 3.7.3 on Debian (Raspberry Pi OS Buster). Python 2 is not supported.

Only UNIX operating systems running *wpa_supplicant* and *wpa_cli* are allowed.

## Built-in keywords

At the `CMD> ` prompt in interactive mode, *hostp2pd* accepts the following commands:

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

The current *hostp2pd* implementation has the following limitations:

- tested with an Android 10 smartphone connecting to a Raspberry Pi 4 with Wi-Fi Direct protocol (and also using AP mode); all [use cases](#use-cases) are referred to this scenario.
- At the moment, only one P2P GO active group is managed for a specific P2P-Device, even if more instances of hostp2pd are allowed, each one referred to a specific P2P-Device (generally a specific wireless wlan board). This is because *wpa_supplicant* appears to announce the P2P-Device id to the Android clients (ref. "device_name" in the related configuration, which is the same for all groups) and not the specific active P2P GO groups; likewise, it is not known how an Android client can inform *wpa_supplicant* to enrol a specific group of a known P2P-device through the default Wi-Fi Direct user interface. Notice also that some wireless drivers only allow one P2P-GO group; in case more P2P-GO group are defined, only the first one in the configuration file is used (e.g., the first group listed by the *wpa_cli* `list_networks` command including `[P2P-PERSISTENT]`); in case a persistent group is active, it is linked to the *wpa_supplicant* configuration with same SSID. If a group is not created, the first P2P client connection creates a dynamic group; all other P2P client connections are enrolled to the same group.
- The authorization process (WPS enrollment) is always done if a P2P Client asks to connect, regardless the group selected by the client.
- Tested with only one station; two or more stations should concurrently connect to the same persistent group.
- Only the first persistent group configured in *wpa_supplicant.conf* is used; other groups can be defined in the configuration, but they are not automatically activated.
- as hostp2pd is fully unattended, the following WPS credential methods are available: *pbc* and *keypad*. The *display* configuration method (much more secure than *keypad*) is not implemented and need interaction (to insert the PIN presented by the Android handset). This means that at the moment the enrolment is done with a either static PIN saved in the hostp2p.yaml configuration file (or passed to the object) or with no PIN at all (PBC mode). To protect PBC (no PIN), a list of enabled enrollees names can be defined. Notice that this is a weak authentication method, because the enrollees names are publicly announced.

# Command-line arguments

Output of `python3 -m hostp2pd -h`:

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

When running as a daemon, standard and error outputs are closed, but log file is always configurable (see Logging chapter).

# Configuration methods

The program allows the following configuration methods, which can be configured in *hostp2pd.yaml*:

- `pbc_in_use: None`: setting *pbc_in_use* to *None* will retrieve the configuration method defined in *wpa_supplicant.conf* (this is the suggested mode, where also the `keypad` method is the suggested one to adopt in *wpa_supplicant.conf*)
- `pbc_in_use: False`: force the *keypad* configuration method, using `password: "8 digits"` configured in *hostp2pd.yaml*. (Notice also that any password different from eight digits is not accepted by *wpa_supplicant*.)
- `pbc_in_use: True`: force the *virtual_push_button* configuration method, performing the enrolment without password.

Notice that the keypad password shall be of exactly 8 digits (ref. `p2p_passphrase_len=8`, which is a default configuration in *wpa_supplicant.conf*).

Configuration methods:
- *keypad*: the Android phone prompts a soft keypad; the user has to enter a fixed passkey compliant to the one set in the *hostp2pd.yaml* configuration file.
- *virtual_push_button* (pbc): no password is used. Anyway, a whitelist of client names can be defined.

Using *virtual_push_button* is an extremely weak enrolment method, where discovering the P2P client names can be easily made by any user.

# Use cases

The UNIX system will always be a GO (Group Owner).

In standard group creation, the UNIX device negotiates a group on demand. In autonomous and persistent group creation, a device becomes a group owner by itself without any client request. Persistent groups are saved in the *wpa_supplicant* configuration file and can be reused after restarting *wpa_supplicant* or rebooting the UNIX system (or after reboot of the Android device). Wi-Fi MAC addressess are generally randomized. With persistent groups, both the Android device and the UNIX system keep the same wireless MAC address (see note below on *wpa_supplicant*).

The following use cases are allowed:

Group Formation technique|Configuration|Description
-------------------------|-------------|-----------
Negotiated on demand|`activate_persistent_group: False`, `activate_autonomous_group: False`, `dynamic_group: True`|P2P Group formation method using negotiation technique, where the UNIX System will always become GO of a standard non-persistent group (ref. `p2p_go_intent=15` in *wpa_supplicant.conf*); groups are dynamically created and removed by *hostp2pd* via `p2p_connect` and `p2p_group_remove`; in other terms, no group is created at startup and the first client connection performs the P2P group formation; besides, the group is removed upon client disconnection. The related virtual network interface is activated only on demand and the related device driver resource is released when not in use. Authorization process is slow and always done.
Autonomous on demand|`activate_persistent_group: False`, `activate_autonomous_group: False`, `dynamic_group: False`|P2P Group Formation using on-demand Autonomous GO Method, configuring a non-persistent autonomous group activated upon the first connection: *hostp2pd* uses `p2p_connect` to setup the first session, while all subsequent connections are managed through WPS enrollment. Once created, the related virtual network interface will be kept active. Authorization process is always done, slow the first time (when the group formation is required on the GO).
Autonomous|`activate_persistent_group: False`, `activate_autonomous_group: True`, `dynamic_group: False`|P2P Group Formation using Autonomous GO Method, configuring a non-persistent autonomous group at startup (using `p2p_group_create`); all connections are managed through WPS enrollment. The related virtual network interface will be always active.  Authorization process is always done.
Persistent|`activate_persistent_group: True`, `activate_autonomous_group: False`, `dynamic_group: False`|The persistent group is autonomously activated at program startup. All connections are managed through the WPS enrollment technique. A virtual network interface is constantly active. If the persistent group is predefined in *wpa_supplicant.conf*, it is restarted, otherwise a new persistent group is created. Authorization process is slow the first time (if the persistent group is not saved in the peer), then fast. Usage of persistent group predefined in *wpa_supplicant.conf* is the suggested method.
Negotiated persistent|(not used)|Negotiated persistent group (`p2p_connect ... persistent or persistent=<network id>`) is not used in this version of *hostp2pd*.

If a whitelist (`white_list: ...`) is configured with PCB (`pbc_in_use: True` or `config_methods=virtual_push_button`) and if the client name does not correspond to any whitelisted names, then the configuration method is changed from *pbc* to *keypad*.

Internally, connections to Autonomous/Persistent Groups are managed by a subprocess named Enroller, which does `wps_pin` or `wps_pbc` over the group interface. The `interface` and `list_networks` commands of wpa_cli are used to check groups. `p2p_find` is periodically executed to ensure that announcements are always performed (especially when [P2P group beacons](https://en.wikipedia.org/wiki/Beacon_frame) are not active). A number of events are managed.

Using standard group negotiation method with fixed password, an Android client will not save the password (the authorization has to be performed on every connection). Using persistent groups, a local group information element is permanently stored in the Android handset (until it is deleted by hand) and this enables to directly perform all subsequent reconnections without separate authorization (e.g., without user interaction).

Invitation (`p2p_invite`) is not used by the current version of *hostp2pd*, which is at the moment designed to enable integration of the Wi-Fi Direct Android connection panel with a P2P-GO group on UNIX systems running *wpa_supplicant*; in such use case, invitation is not actually needed, because the Android user must manually form the connection and the Android 10 P2P client announces itself (*P2P-DEVICE-FOUND*) only at connection time.

# Logging

Logging is configured in *hostp2pd.yaml*. This is in [Pyhton logging configuration format](https://docs.python.org/3/library/logging.config.html). By default, logs are saved in /var/log/hostp2pd.log, rolled into three files. Also, logs can be forced to a specific log level through the `force_logging` configuration attribute.

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
    password="00000000")        # optional PIN of keypad enrolment
```

Check [__main__.py](hostp2pd/__main__.py) for usage examples of the three allowed invocation methods: interactive, batch and daemon modes.

## Interactive mode

```python
with hostp2pd as session:
    # do interactive monitoring while the process run
```

## Batch/daemon mode

```
hostp2pd.run()
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

Two threads are started when using the context manager: "Main" and "Core"; the first returns the context to the caller, the second runs the engine in background. In batch/daemon mode, only the in-process "Core" runs in foreground.

The "Core" thread starts *wpy_cli* as [subprocess](https://docs.python.org/3/library/subprocess.html) connected to the P2P-Device, bidirectionally interfacing it via [pty](https://docs.python.org/3/library/pty.html), using no-echo mode.

When a group is activated, a second [process](https://docs.python.org/3/library/multiprocessing.html#reference) is started, named Enroller, to manage the WPS Enrolling procedure. This process communicates with the Core thread via [multiprocessing Manager](https://docs.python.org/3/library/multiprocessing.html#sharing-state-between-processes) and in turn starts another *wpy_cli* as subprocess connected to the P2P group, interfaced the same way as what done by the Core.

[Signals](https://docs.python.org/3/library/signal.html) are configured among processes, so that termination is synced. Core sends SIGHUP to Enroller if a configuration needs to be reloaded.

# Wi-Fi Direct configuration on a Raspberry Pi

To configure Wi-Fi Direct on a Raspberry Pi, follow [this link](https://raspberrypi.stackexchange.com/q/117238/126729).

Notice that with Raspberry Pi, running AP and P2P concurrently is not supported. Specifically, if a command like `iw dev wlan0 interface add uap0 type __ap` is issued to create a virtual Wi-Fi interface (in order for an access point to be managed for instance by *hostapd*), `wpa_cli -i p2p-dev-wlan0 p2p_connect <address> pbc` subsequently fails to create the *p2p-wlan0-0* interface and *wpa_supplicant* returns EBUSY error code -16 (Device or resource busy). Deleting the virtual interface (via `iw dev uap0 del`) restores the correct behavior.

# MAC Randomization

Linux and Android devices use by default randomized MAC addresses when probing for new Wi-Fi Direct networks while not currently associated with a network.

MAC randomization prevents listeners from using MAC addresses to build a history of device activity, thus increasing user privacy.

Anyway, when using persistent groups, MAC addresses shall not vary in order to avoid breaking reconnections. This appears to be appropriately managed by Android devices.

Nevertheless, on some UNIX devices (e.g., with Raspberry Pi OS., based on Debian Buster) reinvoking a persistent group after restarting wpa_supplicant will change the related virtual interface local address, breaking the reuse of the saved group in the peer system.

This limitation prevents to setup effective Wi-Fi Direct configurations between Raspberry Pi and Android mobile phones.

There is no valid configuration strategy at the moment that prevents MAC randomization with persistent groups. The following is a workaround that implies modifying *wpa_supplicant* sources and recompiling them.

To download *wpa_supplicant* sources and prepare the environment:

```bash
git clone git://w1.fi/srv/git/hostap.git
sudo apt-get install -y libnl-genl-3-dev libnl-route-3-dev
sudo apt install build-essential libdbus-glib-1-dev libgirepository1.0-dev
cd hostap
cp wpa_supplicant/defconfig wpa_supplicant/.config
```

Perform the following modifications:

```bash
sed 's/ret = wpa_drv_if_add(wpa_s, WPA_IF_P2P_DEVICE, ifname, NULL, NULL,/\
\tret = wpa_drv_if_add(wpa_s, WPA_IF_P2P_DEVICE, ifname, is_zero_ether_addr(\
\t\twpa_s->conf->p2p_device_persistent_mac_addr)?NULL:\
\t\twpa_s->conf->p2p_device_persistent_mac_addr, NULL,/' -i.bak ./wpa_supplicant/p2p_supplicant.c

sed 's/ret = send_and_recv_msgs(drv, msg, handler, arg, NULL, NULL);/if (addr \&\& (iftype == NL80211_IFTYPE_P2P_DEVICE)) {\
\t\tif(nla_put(msg, NL80211_ATTR_MAC, ETH_ALEN, addr))\
\t\t\tgoto fail;\
\t}\
\
\tret = send_and_recv_msgs(drv, msg, handler, arg, NULL, NULL);/' -i.bak ./src/drivers/driver_nl80211.c
```

Description of the above modifications:

Edit *hostap/src/drivers/driver_nl80211.c*. In `nl80211_create_iface_once()`, search for `ret = send_and_recv_msgs(drv, msg, handler, arg, NULL, NULL);` and add the following lines before:

```c
    if (addr && (iftype == NL80211_IFTYPE_P2P_DEVICE)) {
            if(nla_put(msg, NL80211_ATTR_MAC, ETH_ALEN, addr))
                goto fail;
    }
```

Then edit *hostap/wpa_supplicant/p2p_supplicant.c*. In `wpas_p2p_add_p2pdev_interface(()`, search `ret = wpa_drv_if_add(wpa_s, WPA_IF_P2P_DEVICE, ifname, NULL, NULL,` and replace the whole line with the following:

```c
	ret = wpa_drv_if_add(wpa_s, WPA_IF_P2P_DEVICE, ifname, is_zero_ether_addr(
		wpa_s->conf->p2p_device_persistent_mac_addr)?NULL:
		wpa_s->conf->p2p_device_persistent_mac_addr, NULL,
```

You can recompile with the following commands:

```bash
cd wpa_supplicant
make
```

To ensure usage of the same static MAC address with the P2P-Device virtual interface, you can use the created *wpa_supplicant* in place of the existing one:

```bash
mv /sbin/wpa_supplicant /sbin/wpa_supplicant-org
cp wpa_supplicant /sbin
```

Add the following in *wpa_supplicant.conf*:

```ini
p2p_device_persistent_mac_addr=<mac address>
```

Example:

```ini
p2p_device_persistent_mac_addr=dc:a6:32:01:02:03
```

This modification exploits `p2p_device_persistent_mac_addr`, which has been introduced in [a previous patch](http://w1.fi/cgit/hostap/commit/?id=9359cc8483eb84fbbb0a75cf64dcffd213fb412e). If this patch is not available, as alternative, edit *hostap/src/drivers/driver_nl80211.c*. In `nl80211_create_iface_once()`,  before `ret = send_and_recv_msgs(drv, msg, handler, arg, NULL, NULL);` add the following:

```c
#define STATIC_MAC_ADDRESS "dc:a6:32:01:02:03"

	if (iftype == NL80211_IFTYPE_P2P_DEVICE) {
        u8 mac_addr[ETH_ALEN];
        if (hwaddr_aton2(STATIC_MAC_ADDRESS, mac_addr))
            if(nla_put(msg, NL80211_ATTR_MAC, ETH_ALEN, mac_addr))
                goto fail;
    }
```

# License

(C) Ircama 2021 - CC BY SA 4.0

_______________

__Notes__

_Running wpa_supplicant from the command line_

Standard distribution already include a wpa_supplicant service. Anyway, for information, the following allows running it from the command line:

```bash
sudo /sbin/wpa_supplicant -c/etc/wpa_supplicant/wpa_supplicant-wlan0.conf -Dnl80211,wext -iwlan0
```

There is a relevant blog with [in-depth notes on Wi-Fi Direct](https://praneethwifi.in/)
