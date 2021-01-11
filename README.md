hostp2pd
========

__The Wi-Fi Direct Session Manager__

*hostp2pd* implements a soft host [Access Point](https://en.wikipedia.org/wiki/Wireless_access_point) (AP) software in [Wi-Fi Direct](https://en.wikipedia.org/wiki/Wi-Fi_Direct) mode, enabling a [wireless network interface card](https://en.wikipedia.org/wiki/Wireless_network_interface_controller) to act as *Ad hoc* access point and [Wi-Fi Protected Setup](https://en.wikipedia.org/wiki/Wi-Fi_Protected_Setup) (WPS) [authentication server](https://en.wikipedia.org/wiki/Authentication_server). It features basic functionalities roughly similar to [hostapd](https://en.wikipedia.org/wiki/Hostapd) (with its [hostapd.conf](https://w1.fi/cgit/hostap/plain/hostapd/hostapd.conf) configuration file), which is the common AP software integrated with *wpa_supplicant*, generally used for [infrastructure mode networking](https://en.wikipedia.org/wiki/Service_set_(802.11_network)#Infrastructure_mode). When implementing a [P2P persistent group](https://praneethwifi.in/2019/11/23/p2p-group-formation-procedure-persistent-method/), [wpa_supplicant](https://en.wikipedia.org/wiki/Wpa_supplicant) offers the [P2P-GO](https://en.wikipedia.org/wiki/Wireless_LAN#Peer-to-peer) features enabled by *hostp2pd* to connect P2P Clients like Android smartphones, as well as provide the standard infrastructure AP mode to the same P2P-GO group, without the need of *hostapd*.

In order to accept [Wi-Fi Direct](https://www.wi-fi.org/discover-wi-fi/wi-fi-direct) connections from P2P Clients, activate a local [P2P-GO](https://w1.fi/wpa_supplicant/devel/p2p.html) (Wi-Fi Direct Group Owner) and perform WPS authentication, *hostp2pd* fully relies on *wpa_supplicant*, interfacing it through [wpa_cli](https://manpages.debian.org/stretch/wpasupplicant/wpa_cli.8.en.html) command-line interface ([CLI](https://en.wikipedia.org/wiki/Command-line_interface)): *wpa_cli* is run in background and [p2p commands](https://w1.fi/cgit/hostap/plain/wpa_supplicant/README-P2P) are piped via pseudo-tty communication, while events returned by *wpa_cli* are read and processed.

*hostp2pd* includes a command-line interface mode for monitoring and controlling; it can be executed as a batch or as a daemon and provides an API for integration into other Python programs.

# Connecting via Wi-Fi Direct with Android devices

Wi-Fi Direct (formerly named Wi-Fi Peer-to-Peer, or *P2P*) allows devices to connect directly to each other, without the need for a traditional Wireless Access Point (AP). The role of the access point is replaced by the so-called Group Owner (GO), either negotiated during the connection setup, or autonomously created.

An advantage of Wi-Fi Direct with Android is that it can coexist with a traditional Wi-Fi connection as well as with a cellular connection: it means that an Android smartphone can be connected to a mobile network, or to an infrastructure-mode Wi-Fi AP with internet access and at the same time connect to a UNIX device via Wi-Fi Direct, without losing the routing to the mobile (or AP) network. This is because with Android, differently from the standard infrastructure-mode Wi-Fi AP connection where an active Wi-Fi session always takes routing priority to the mobile network for its internal Android routing configuration that disables mobile routing, Wi-Fi Direct does not interfere with the routing table.

Apple iOS devices do not support Wi-Fi Direct, but can concurrently connect to a P2P persistent group in AP mode the same way as for traditional infrastructure-mode Access Points managed by *hostapd*. Differently from Android phones, if the persistent group does not configure a default router, iOS does not change the routing tables of the cellular network, which is by consequence not lost.

# Installation

Check that the Python version is 3.5 or higher (`python3 -V`), then install *hostp2pd* with the following command:

```shell
python3 -m pip install hostp2pd
```

To install from GitHub:

```shell
sudo apt-get install git
python3 -m pip install git+https://github.com/Ircama/hostp2pd
```

To uninstall:

```shell
python3 -m pip uninstall -y hostp2pd
```

Prerequisite components (already included in the installation procedure): *pyyaml*, *python-daemon*.

# Usage

To run *hostp2pd* in interactive mode, use the following command:

```shell
python3 -m hostp2pd
```

or simply:

```shell
hostp2pd
```

Using a P2P-Device interface and a configuration file:

```shell
hostp2pd -i p2p-dev-wlan0 -c /etc/hostp2pd.yaml
```

- `-i` option: The P2P-Device interface used by hostp2pd is created by *wpa_supplicant* over the physical wlan interface (if default options are used). Use `iw dev` to list the available wlan interfaces. An *unnamed/non-netdev* interface with *type P2P-device* should be found. If no P2P-Device is shown (e.g., only the physical *phy#0* Interface *wlan0* is present), either *wpa_supplicant* is not active or it is not appropriately compiled/configured. With *wlan0* as physical interface (ref. `iw dev`), to get the name of the P2P-Interface use the command `wpa_cli -i wlan0 interface`: it should return the interface device *wlan0* and the P2P-device (e.g., *p2p-dev-wlan0*). Use this name as argument to the `-i` option of *hostp2pd*. Notice also that, if a P2P-Device is configured, `wpa_cli` without option should automatically point to this interface.
- `-c` option: a [YAML](https://en.wikipedia.org/wiki/YAML) configuration file ([here](hostp2pd/hostp2pd.yaml) an example) is not strictly necessary to start a first test; a minimum parameter would be the password, which can be alternatively defined using a shell [Here Document](https://en.wikipedia.org/wiki/Here_document) expression:
  ```shell
  hostp2pd -i p2p-dev-wlan0 -c - <<\eof
  password: "00000000"
  eof
  ```

To start a Wi-Fi Direct connection of an Android smartphone and connect a UNIX system running *hostp2pd*, tap Settings > Wi-Fi > Advanced settings > Wi-Fi Direct and wait for the peer UNIX device to appear. Select it, optionally type the PIN and wait for connection established. If the default configuration is used, which exploits a predefined persistent group, any subsequent reconnection to this group is done without repeating the WPS authorization process. As previously explained, through this process the mobile/cellular connection is not disabled while the Wi-Fi Direct connection is active.

Depending on the capabilities of the wlan device driver, the AP virtual interface has to be stopped before creating a P2P-GO group. As already mentioned, a persistent P2P-GO group can provide AP capabilities together with the Wi-Fi Direct functionalities.

Check the supported interface modes with this command:

```shell
iw list | grep "Supported interface modes" -A 8
```

It should return one line including `P2P-GO` (together with `P2P-device`). If only `STA` and `managed` are returned, the device driver of the board (or the hw itself) does not support creating a P2P-GO interface.

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


Same for the Intel Wireless-AC 9560 Ubuntu driver:

```
valid interface combinations:
     * #{ managed } <= 1, #{ AP, P2P-client, P2P-GO } <= 1, #{ P2P-device } <= 1,
       total <= 3, #channels <= 2
```

Optionally, *hostp2pd* allows the `-p` option, which defines an external program to be run with "stop" argument before activating a group and with "start" argument after deactivating a group; this allows controlling external AP resources before groups are created or after groups are removed.

This is an example of RUN_PROGRAM:

```bash
#!/bin/bash
set -o errexit nounset -o pipefail -o functrace -o errtrace -eE
case "$1" in
stop) echo "Received 'stop' command due to a P2P-GO group creation";;
start) echo "Received 'start' command due to a P2P-GO group removal";;
esac
```

In all cases, *wpa_cli* can be used in parallel to *hostp2pd*. Specifically, *wpa_cli* can be started on the physical interface (`wpa_cli -i wlan0`), on the P2P-Device (`wpa_cli -i p2p-dev-wlan0`) and on a specific P2P-GO group when available (e.g., `wpa_cli -i p2p-wlan0-0`).

# Configuration files

hostp2pd needs *wpa_supplicant.conf* and optionally *hostp2pd.yaml*.

## wpa_supplicant.conf

For a reference description of the file format of *wpa_supplicant.conf*, ref. these relevant documents:
- [wpa_supplicant.conf configuration file format](https://w1.fi/cgit/hostap/plain/wpa_supplicant/wpa_supplicant.conf),
- [Wi-Fi P2P implementation in wpa_supplicant](https://w1.fi/cgit/hostap/plain/wpa_supplicant/README-P2P).

Ensure that *wpa_supplicant.conf* includes the following P2P configuration lines (skip all comments):

```ini
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev # This allows using wpa_cli as wpa_supplicant client.
          # Note: /var/run/wpa_supplicant is the directory where wpa_supplicant creates UNIX sockets to allow interaction with wpa_cli. The group name is the
          # one associated with the sockets; use the appropriated group configured for your wpa_supplicant installation (might not be used).
update_config=1                                         # This allows wpa_supplicant to update the wpa_supplicant.conf configuration file
device_name=DIRECT-test                                 # This is the P2P name shown to the Android phones while connecting via Wi-Fi Direct;
                                                        # Use any name in place of "test" and keep the "DIRECT-" prefix.
device_type=6-0050F204-1                                # (Network Infrastructure / AP)
config_methods=keypad                                   # "keypad" uses a fixed password on UNIX, which is asked from a keypad popped up on the Android devices
p2p_go_intent=15                                        # Force UNIX to become a P2P-GO (Group Owner)
persistent_reconnect=1                                  # Allow reconnecting to a persistent group without user acknowledgement
p2p_go_ht40=1                                           # Optional: use HT40 channel bandwidth (300 Mbps) when operating as GO (instead of 144.5Mbps).
country=<country ID>                                    # Use your country code here
p2p_device_persistent_mac_addr=<mac address>            # Fixed MAC address overcoming MAC Randomization, to be used with persistent group

# This is an example of P2P persistent group:
network={                                               # Network profile
        ssid="DIRECT-PP-group"                          # Name of the persistent group saved on the Android phone and shown within the AP names;
                                                        # use any name in place of "PP-group" and keep the "DIRECT-" prefix.
        mode=3                                          # WPAS MODE P2P-GO
        disabled=2                                      # Persistent P2P group
        psk="mysecretpassword"                          # Password used when connecting to the AP (unrelated to P2P-GO enrolment, which is done via WPS)
        proto=RSN                                       # For the security parameters, the persistent group profile is like a normal network profile
        key_mgmt=WPA-PSK
        pairwise=CCMP
        auth_alg=OPEN
}
```

The above example shows how to predefine a P2P persistent group. Specifically, the `network` profiles will define persistent GO groups [if the following three conditions occur](https://www.spinics.net/lists/hostap/msg05313.html):

-	The SSID shall begin with the `DIRECT-...` prefix (P2P_WILDCARD_SSID), otherwise the group is not appropriately announced to the network as a P2P group; any alphanumeric string can be used after `DIRECT-` prefix; empirically, the documented format `DIRECT-<random two octets>` (with optional postfix) is not needed.
-	A `mode=3` directive shall be present, meaning [WPAS_MODE_P2P_GO](https://w1.fi/wpa_supplicant/devel/structwpa__ssid.html), otherwise the related `p2p_group_add` command fails for unproper group specification.
-	A `disabled=2` directive shall be present, meaning persistent P2P group, otherwise the stanza is not even recognized and listed as persistent (`disabled=0` indicates normal network; `disabled=1` will announce a disabled network).

If no persistent group is predefined in in *wpa_supplicant.conf* and if `activate_persistent_group` is set to `True`, then *hostp2pd* creates a generic persistent group, giving it a name with format `DIRECT-<random two octets>`.

See below for the usage of `p2p_device_persistent_mac_addr`; some nl80211 device drivers allow `p2p_device_random_mac_addr=1` instead of modifying the *wpa_supplicant* code.

The following usage modes of *hostp2pd* are allowed:

- interactive mode (when neither `-b` option nor `-d` is used, by default *hostp2pd* starts in this mode and a prompt is shown)
- batch mode with input commands, activated with the `-b` option (`-b file` or `-b -`; e.g., `-b -` for standard log output, or `-b output_file_name`). This mode reads the standard input for the same commands that can be issued by the user in interactive mode;
- batch mode light, without input commands (no separate thread is created and the command interpreter is not used). This is activated when both `-b` and `-d` options are used;
- daemon mode (use `-d` option). Suggested configuration. If a daemon process is active, option `-t` terminates a running daemon and option `-r` dynamically reloads the configuration of a running program.

When running as a daemon, *hostp2pd* prevents multiple instances over the same P2P-Device interface by using lock files with name `/var/run/hostp2pd-<interface>.pid`, where `<interface>` is the name of the P2P-Device interface. (For instance, */var/run/hostp2pd-p2p-dev-wlan0.pid*.)

Example of execution in batch mode with input commands (where also Python instructions can be used):

```shell
hostp2pd -c /etc/hostp2pd.yaml -b - <<\eof
stats
wait 60
stats
eof
```

## hostp2pd.yaml

Check the [hostp2pd.yaml example file](hostp2pd/hostp2pd.yaml). It is suggested to install it to /etc/hostp2pd.yaml.

## Installing the service

Run the following to install the service:

```ini
sudo SYSTEMD_EDITOR=tee systemctl edit --force --full hostp2pd <<\EOF
[Unit]
Description=hostp2pd - The Wi-Fi Direct Session Manager
After=network.target

[Service]
Type=forking
Environment="CONF=/etc/hostp2pd.yaml" "P2PDEVICE=p2p-dev-wlan0"
ExecStart=/usr/bin/python3 -m hostp2pd  -i ${P2PDEVICE} -c ${CONF} -d
ExecReload=/usr/bin/python3 -m hostp2pd -i ${P2PDEVICE} -c ${CONF} -r
ExecStop=/usr/bin/python3 -m hostp2pd -i ${P2PDEVICE} -c ${CONF} -t
PIDFile=/var/run/hostp2pd-p2p-dev-wlan0.pid

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable hostp2pd
sudo systemctl start hostp2pd
```

Note: `PIDFile` variable cannot be parametrized with `${CONF}` and `${P2PDEVICE}`.

# WPS Authorization methods

The program allows the following WPS authorization methods, named "config_methods"/configuration methods in *wpa_supplicant*, which can be defined in *hostp2pd.yaml*:

- `pbc_in_use: None`: setting *pbc_in_use* to *None* will retrieve the configuration method defined in *wpa_supplicant.conf* (this is the suggested mode, where also the `keypad` method is the suggested one to adopt in *wpa_supplicant.conf*);
- `pbc_in_use: False`: force the *keypad* configuration method, performing the enrolment with configured password;
- `pbc_in_use: True`: force the *virtual_push_button* configuration method, performing the enrolment without password.

Configuration methods:
- *keypad*: the Android phone prompts a soft keypad; the user has to enter a fixed passkey compliant to the one set in the *hostp2pd.yaml* configuration file.
- *virtual_push_button* (pbc): no password is used. Anyway, a whitelist of client names can be defined (`pbc_white_list`).

The *keypad* configuration method needs a password configured in *hostp2pd.yaml* through the `password` directive (e.g., `password: "12345678"`; notice also that any password different from eight digits is not accepted by *wpa_supplicant*, unless differently specified by `p2p_passphrase_len`).

Using *virtual_push_button* is extremely weak and discovering the P2P client names can be easily made by any user.

# Use cases

In summary, with the standard group formation technique negotiated on demand, when a P2P Client starts a connection, the UNIX device will always become a GO (Group Owner) if `p2p_go_intent` in *wpa_supplicant.conf* is set to 15. In autonomous and persistent group formation technique, the UNIX device becomes a group owner by itself without any client request. Persistent groups are saved in the *wpa_supplicant* configuration file and can be reused after restarting *wpa_supplicant* or rebooting the UNIX system (and after rebooting the Android device). While Wi-Fi MAC addressess are generally randomized, with persistent groups both the Android device and the UNIX system keep the same wireless MAC address (see note below on *wpa_supplicant*).

The following table details the use cases:

Group Formation technique|Configuration|Description
-------------------------|-------------|-----------
Negotiated on demand|`activate_persistent_group: False`, `activate_autonomous_group: False`, `dynamic_group: True`|Non-persistent P2P Group formation method using non-autonomous negotiation technique; groups are dynamically created and removed by *hostp2pd* via `p2p_connect` and `p2p_group_remove`; in other terms, no group is created at startup and the first client connection performs the P2P group formation; besides, the group is removed upon client disconnection in order to enable subsequent formation of sessions by always keeping a single P2P-GO group active; this means that with this use case only a single P2P Client is allowed (because when a P2P Client disconnects, all active sessions to this group terminate). The related virtual network interface is activated only on demand and the related device driver resource is released when not in use. Authorization process is slow and always needed.
Autonomous on demand|`activate_persistent_group: False`, `activate_autonomous_group: False`, `dynamic_group: False`|P2P Group Formation using on-demand Autonomous GO Method, configuring a non-persistent autonomous group activated upon the first connection: *hostp2pd* uses `p2p_connect` to setup the first session, while all subsequent connections are managed through WPS enrolment. Once created, the related virtual network interface will be kept active. Authorization process is always needed and generally slow (especially the first time, when the group formation is required on the GO).
Autonomous|`activate_persistent_group: False`, `activate_autonomous_group: True`, `dynamic_group: False`|P2P Group Formation using Autonomous GO Method, configuring a non-persistent autonomous group at startup (using `p2p_group_create`); all connections are managed through WPS enrolment. The related virtual network interface will always be active. Authorization process is always needed.
Persistent on demand|`activate_persistent_group: True`, `activate_autonomous_group: False`, `dynamic_group: True`|Negotiated persistent group. To setup the first session, *hostp2pd* uses `p2p_connect ... persistent or persistent=<network id>`, depending on the existence of a valid persistent group in *wpa_supplicant* configuration file). The authorization process is only performed the first time (slow), than all reconnections are pretty fast and fully automated by *wpa_supplicant*. With this setting, the P2P Client is able on demand to automatically restart the P2P-GO group on the UNIX system and then connect to this group without WPS enrolment. So, after the P2P-GO group is saved to the P2P Client, any subsequent reconnection of the same client is not mediated by *hostp2pd*; the only task of *hostp2pd* is to enrol new clients, in order to allow them to locally save the persistent group. The related virtual network interface is activated only on demand and then kept active.
Persistent|`activate_persistent_group: True`, `activate_autonomous_group: False`, `dynamic_group: False`|The persistent group is autonomously activated at program startup. If the persistent group is predefined in *wpa_supplicant.conf*, it is restarted, otherwise a new persistent group is created. The virtual network interface is kept constantly active. The authorization process of a P2P Device is only performed the first time (if the persistent group is not saved in the peer), through WPS enrolment technique; after the persistent group data is saved to the P2P Device, all reconnections of the same device are fast and automatically done without WPS enrolment (so not mediated by *hostp2pd*). Usage of persistent group predefined in *wpa_supplicant.conf* is the suggested method.

Using an autonomous GO for a non-persistent group, the passphrase and SSID are automatically created by *wpa_supplicant* (using random strings) and the related settings should not be modified. A persistent group can be either manually or automatically created.

Using the standard group negotiation method with fixed password, an Android client (at least, up to Android 10) will not save the password (the authorization has to be performed on every connection). Using persistent groups, with newer Android releases a local group information element is permanently stored in the Android handset (until it is deleted by hand) and this enables to directly perform all subsequent reconnections without separate authorization (e.g., without user interaction). Ref. also [Compatibility](#Compatibility)

In all cases that foresee a negotiation (usage of `p2p_connect`), the UNIX System will always become GO (ref. `p2p_go_intent=15` in *wpa_supplicant.conf*).

If a whitelist (`pbc_white_list: ...`) is configured with push button mode/PBC (`pbc_in_use: True` or `config_methods=virtual_push_button`) and if the client name does not correspond to any whitelisted names, then the configuration method is changed from *pbc* to *keypad*.

Internally, connections to Autonomous/Persistent Groups are managed by a subprocess named Enroller, which does `wps_pin` or `wps_pbc` over the group interface. The `interface` and `list_networks` commands of *wpa_cli* are used to check groups. `p2p_find` is periodically executed to ensure that announcements are performed (especially when [P2P group beacons](https://en.wikipedia.org/wiki/Beacon_frame) are not active). A number of events are managed.

If different P2P-GO persistent groups are defined in the *wpa_supplicant* configuration file, by default the first one in the configuration file is used (e.g., the first group listed by the *wpa_cli* `list_networks` command including `[P2P-PERSISTENT]`); use `persistent_network_id` to force a specific network id instead of the first one (provided that it is correctly configured in the *wpa_supplicant* configuration file, so that it is recognized as persistent group).

Invitation (`p2p_invite`) is not used by the current version of *hostp2pd*, which is at the moment designed to enable integration of the Wi-Fi Direct Android connection panel with a P2P-GO group on the UNIX system running *wpa_supplicant*; in such use case, invitation is not actually needed, because the Android user must manually form the connection and the Android P2P client (e.g., the Android 10 one) announces itself (*P2P-DEVICE-FOUND* event) only at connection time.

# Compatibility

Only UNIX operating systems running *wpa_supplicant* and *wpa_cli* are allowed.

*hostp2pd* has been tested with:

- UNIX wpa_cli and wpa_supplicant version v2.8-devel (Debian Buster); the recompiled code to overcome the [MAC randomization issue with persistent groups](#mac-randomization) is based on *wpa_supplicant* version [v2.10-devel-hostap_2_9-1798-g581dfcc41+.](http://w1.fi/cgit/hostap).
- Python 3.7.3 on Debian (Raspberry Pi OS Buster). Python 2 is not supported.
- P2P Clients including Android 10 and Android 7 smartphones. Wi-Fi Direct is present in most smartphones with at least Android 4.0; notice anyway that only recent Android versions support the local saving of persistent groups. Android 10+ supports it for instance, while Android 7 does not, so an Android 7 device always needs enrolment when connecting a persistent group. Android 10 has a very slow notification of announced groups and needs to exit and re-enter the Wi-Fi Direct panel each time a connection is disconnected and then reconnected. Android 7 does not require exiting and re-entering; it also shows the UNIX system immediately, including the AP icon (not shown by Android 10). Sometimes the enrolling might fail, often depending on the Android version (this is possibly due to timeout issues, especially correlated to missing *WPS-ENROLLEE-SEEN* events sent by the Android device).

## Built-in keywords

At the `CMD> ` prompt in interactive mode, *hostp2pd* accepts the following commands:

- `version` = Print hostp2pd version.
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

The *reload* command refreshes the configuration of *hostp2pd* as well as the one of *wpa_supplicant*.

# Suggested scenario

The suggested scenario configures a persistent group. Specifically:

- single persistent group for the whole UNIX system;
- predefinition of a persistent P2P group in the *wpa_suppicant* configuration file;
- appropriate configuration of *wpa_suppicant* so that the persistent P2P group will not randomize the MAC address of the related virtual wireless interface;
- usage of appropriate group name and related WPA configuration in the *wpa_suppicant* configuration file (e.g., WPA2 password), so that this P2P group can also act as AP (instead of using *hostapd*); defining a secret WPA2 password is a workaround to deny AP connections);
- for better usage of Wi-Fi Direct naming, differentiate the name of the P2P device and the P2P group in the *wpa_suppicant* configuration file (e.g., P2P-Device = "DIRECT-Host"; P2P group = "DIRECT-PP-group");
- *hostp2pd* configuration to use a persistent P2P group activated at process startup, with "keypad" authorization method;
- *hostp2pd* service setup to start at system boot time;
- read access protection of *wpa_suppicant* and *hostp2pd* configuration files to non-root users;
- *hostp2pd* logging set to root level WARNING (instead of DEBUG mode, which can be used for initial testing);
- for improved security, definition of a non-standard number of WPS digits (ref. `p2p_passphrase_len`in the *wpa_supplicant* configuration file).

# Limitations

The current *hostp2pd* implementation has the following limitations:

- tested with an Android 10 smartphone connecting to a Raspberry Pi 4 with Wi-Fi Direct protocol (and also using AP mode); all [use cases](#use-cases) are referred to this scenario.
- At the moment, *hostp2pd* is tested with only one station; two or more stations should concurrently connect to the same persistent group.
- At the moment, *hostp2pd* manages only one active P2P GO group for a specific P2P-Device, even if more instances of *hostp2pd* are allowed, each one referred to a specific P2P-Device (generally a specific wireless wlan board). This is because *wpa_supplicant* appears to announce the P2P-Device name to the Android clients (ref. "device_name" in the *wpa_supplicant* configuration, which is the same for all groups) and not the specific active P2P GO groups; likewise, it is not known how an Android client can inform *wpa_supplicant* to enrol a specific group of a known P2P-device through the default Wi-Fi Direct user interface. Notice also that some wireless drivers on UNIX systems only allow one P2P-GO group.
- The enrolment procedure (WPS authorization made by the *hostp2pd* Enroller subprocess) is activated in sync with the start of the P2P group made by *hostp2pd* (either *p2p_connect* or *p2p_group_add* commands) and remains active until the group is removed (reception of *P2P-GROUP-REMOVED* event); single connection requests by P2P Clients (controlled by respective *P2P-PROV-DISC-...* events) will not directly start the WPS authorization process, but will start a group formation (via *p2p_connect*) if a group is not active. While a P2P group is kept active by *hostp2pd*, any P2P Client requesting a P2P connection to the P2P-Device wireless interface will be part of the same active *hostp2pd* enrolment process to the active group.
- As hostp2pd is fully unattended, the following WPS credential methods are available: *pbc* and *keypad*. The *display* configuration method (much more secure than *keypad*) is not implemented and needs interaction (to insert the PIN presented by the Android handset). This means that at the moment the enrolment is done with either a static PIN saved in the *hostp2pd* configuration file or with no PIN at all (PBC mode). To protect PBC (no PIN), a list of enabled enrollees names can be defined. Notice that this is a weak authentication method, because the enrollees names are publicly announced. After all, MAC address filtering is not appropriate because, if a persistent group is not active, MAC adresses are randomized.
- When `dynamic_group` option is set to `True`, only a single station a time is accepted, because when a station disconnects, the group is removed by *hostp2pd* and any other connected station loses the session.

# Logging

Logging is configured in *hostp2pd.yaml*. This is in [Pyhton logging configuration format](https://docs.python.org/3/library/logging.config.html). By default, logs are saved in /var/log/hostp2pd.log, rolled into three files. Also, logs can be forced to a specific log level through the `force_logging` configuration attribute.

In interactive mode, logging can be changed using `loglevel`.

To browse the log files, [lnav](https://github.com/tstack/lnav) is suggested.

# Command-line arguments

Output of `hostp2pd -h`:

```
usage: hostp2pd [-h] [-V] [-v] [-vv] [-t] [-r] [-c CONFIG_FILE]
                           [-d] [-b FILE] [-i INTERFACE] [-p RUN_PROGRAM]

optional arguments:
  -h, --help            show this help message and exit
  -V, --version         print hostp2pd version and exit
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

hostp2pd v.0.1.0 - The Wi-Fi Direct Session Manager. wpa_cli controller of Wi-
Fi Direct connections handled by wpa_supplicant.
```

When running as a daemon, standard and error outputs are closed, but log file is always configurable (see Logging chapter).

# Python API

## Instantiating the class

All arguments are optional.

```python
from hostp2pd import HostP2pD

hostp2pd = HostP2pD(
    config_file="config_file",  # optional pathname of the hostp2pd.yaml configuration file
    interface="p2p-dev-wlan0",  # optional string defining the wlan interface (check it with iw dev)
    run_program="",             # optional run_program
    force_logging=None,         # optional logging mode
    pbc_white_list=[],          # optional name white list of allowed PBC station names
    password="00000000")        # optional PIN of keypad enrolment
```

Check [`__init__.py`](hostp2pd/__init__.py) for usage examples of the three allowed invocation methods: interactive, batch and daemon modes.

## Interactive mode

Interactive mode uses the Context Manager:

```python
import time

with hostp2pd as session:
    # do interactive monitoring while the process run
    time.sleep(40) # example
```

## Batch/daemon mode

Batch/daemon mode does not need the Context Manager:

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

When using the Context Manager, a thread is started: the current context, named "Main", is returned to the user. The created thread, named "Core", runs the *hostp2pd* engine in background.

With batch (selecting the option not to send input commands) and daemon modes, the "Core" does not run in a background thread.

The "Core" engine starts *wpa_cli* as [subprocess](https://docs.python.org/3/library/subprocess.html) connected to the P2P-Device, bidirectionally interfacing it via [pty](https://docs.python.org/3/library/pty.html), using no-echo mode. The internal "read" function gets one character a time mediated by a [select](https://docs.python.org/3/library/select.html) method which controls read timeout that is used to perform a number of periodic checks.

When a group is activated, a second [process](https://docs.python.org/3/library/multiprocessing.html#reference) is started, named Enroller, to manage WPS Enrolling. This process writes to the Core via the same pty and in turn starts another *wpa_cli* subprocess, connected to the P2P group, interfaced the same way as what done by the Core.

Example of process list when running as a daemon (p2p-dev-wlan0 is the P2P-Device and p2p-wlan0-0 is the group; the P2P-Device controller is the Core, the group controller is the Enroller):

```
UID        PID  PPID  C STIME TTY      STAT   TIME CMD
root     20452     1  4 08:36 ?        S      0:01 /usr/bin/python3 -m hostp2pd -c /etc/hostp2pd.yaml -d
root     20453 20452  0 08:36 ?        S      0:00  \_ wpa_cli -i p2p-dev-wlan0
root     20458 20452  0 08:36 ?        S      0:00  \_ /usr/bin/python3 -m hostp2pd -c /etc/hostp2pd.yaml -d
root     20460 20458  0 08:36 ?        S      0:00      \_ wpa_cli -i p2p-wlan0-0
```

[Signals](https://docs.python.org/3/library/signal.html) are configured among processes, so that termination is synced. Core sends SIGHUP to Enroller if a configuration needs to be reloaded.

## Interfacing wpa_supplicant

Currently, there seem to be two possibilities to interface *wpa_supplicant* on P2P (Wi-Fi Direct) sessions: using the UNIX sockets (like *wpa_cli* does) or by directly screenscraping the *wpa_cli* client via bidirectional pipe.

*wpa_supplicant* also allows the [dbus interface](https://w1.fi/wpa_supplicant/devel/dbus.html) when *wpa_supplicant* is run with the `-u` option; anyway, with the current *wpa_supplicant* version (v2.8-devel), the internal P2P objects do not seem to be registered to the *dbus* interface, so a Python request like the following one fails with message `dbus.exceptions.DBusException: fi.w1.wpa_supplicant1.InterfaceUnknown: wpa_supplicant knows nothing about this interface..`:

```python
python3 -c 'import dbus;\
dbus.Interface(dbus.SystemBus().get_object("fi.w1.wpa_supplicant1",\
"/fi/w1/wpa_supplicant1"), "fi.w1.wpa_supplicant1")\
.GetInterface("p2p-dev-wlan0")'
```

This is because *wpa_supplicant* does not expose *p2p-dev-wlan0* to *dbus*. It means that [the old Python test examples](http://w1.fi/cgit/hostap/tree/wpa_supplicant/examples/p2p) included in *wpa_supplicant* sources, which exploited *dbus*, are not usable. Notice also that if *p2p-dev-wlan0* in the above Python command is changed to *wlan0* (which is unrelated to P2P anyway), the command returns with no errors.

*hostp2pd* relises on *wpa_cli* considering that:

- it is natively integrated with *wpa_supplicant* via proven and roboust communication method,
- it allows easy P2P commands and in parallel it outputs all needed real time events,
- the consumed UNIX resources are very limited,
- the resulting Python program is very simple to maintain.

# Wi-Fi Direct configuration on a Raspberry Pi

To configure Wi-Fi Direct on a Raspberry Pi, follow [this link](https://raspberrypi.stackexchange.com/q/117238/126729).

Notice that with Raspberry Pi, running AP and P2P concurrently is not supported. Specifically, if a command like `iw dev wlan0 interface add uap0 type __ap` is issued to create a virtual Wi-Fi interface (in order for an access point to be managed for instance by *hostapd*), `wpa_cli -i p2p-dev-wlan0 p2p_connect <address> pbc` subsequently fails to create the *p2p-wlan0-0* interface and *wpa_supplicant* returns EBUSY error code -16 (Device or resource busy). Deleting the virtual interface (via `iw dev uap0 del`) restores the correct behavior.

# MAC Randomization

Some Linux and Android device drivers use by default randomized MAC addresses when starting network interfaces.

This might be probably checked with `iw list | grep 'randomizing MAC-addr'`; many devices, (including Raspberry Pi) return this:

```
Device supports randomizing MAC-addr in sched scans.
```

MAC randomization prevents listeners from using MAC addresses to build a history of device activity, thus increasing user privacy.

Anyway, when using persistent groups, MAC addresses shall not vary in order to avoid breaking the group restart: if a device supports MAC Randomization, restarting *wpa_supplicant* will change the local MAC address of the related virtual interface; a persistent group reinvoked with different MAC address denies the reuse of the saved group in the peer system.
[This appears to be appropriately managed by Android devices](https://source.android.com/devices/tech/connect/wifi-direct#mac_randomization).

The only configuration strategy that at the moment appears to already prevent MAC randomization with persistent groups might be the one mentioned [in a patch](http://w1.fi/cgit/hostap/commit/?id=9359cc8483eb84fbbb0a75cf64dcffd213fb412e) and it possibly only applicable to some nl80211 device drivers supporting it; so, for some devices, using `p2p_device_random_mac_addr=1` and `p2p_device_persistent_mac_addr=<mac address>` can do the job. Otherwise, a modification of the current version of *wpa_supplicant* might be needed.

The following is a workaround that implies modifying *wpa_supplicant* sources and recompiling them; it exploits the usage of `p2p_device_persistent_mac_addr`, but not `p2p_device_random_mac_addr`.

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

If usage of `p2p_device_persistent_mac_addr` is not available, as alternative, the MAC address can be hardcoded: edit *hostap/src/drivers/driver_nl80211.c*. In `nl80211_create_iface_once()`,  before `ret = send_and_recv_msgs(drv, msg, handler, arg, NULL, NULL);` add the following:

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

(C) Ircama 2021 - [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)

_______________

__Notes__

# wpa_supplicant issues

## wpa_cli does not connect to wpa_supplicant

Test *wpa_cli* using sudo. if it does not connect, check the configuration of the ctrl_interface socket used with your system (e.g., `-C` option of wpa_supplicant* or *ctrl_interface* in its configuration file).

If *wpa_cli* connects the network device (e.g., *wlan0*) but not the P2P-Device (e.g., *p2p-dev-wlan0*), use `iw dev` to check the presence of a P2P-Device. If not existing, then *wpa_supplicant* has configuration issues. Run *wpa_supplicant* with `-dd` options and verify the error messages:

```shell
kill <wpa supplicant process>
sudo /sbin/wpa_supplicant -c<configuration file> -Dnl80211,wext -i<network device> -dd
```

## Failed to create a P2P Device -22 (Invalid argument)

*wpa_supplicant* error message:

```
gen 10 20:07:20 ubuntu wpa_supplicant[46251]: Successfully initialized wpa_supplicant
gen 10 20:07:20 ubuntu wpa_supplicant[46251]: nl80211: kernel reports: Attribute failed policy validation
gen 10 20:07:20 ubuntu wpa_supplicant[46251]: Failed to create interface p2p-dev-wlp0s20f3: -22 (Invalid argument)
gen 10 20:07:20 ubuntu wpa_supplicant[46251]: nl80211: Failed to create a P2P Device interface p2p-dev-wlp0s20f3
gen 10 20:07:20 ubuntu wpa_supplicant[46251]: P2P: Failed to enable P2P Device interface
```

This might occur because the interface name could be too long for some internal procedures; for instance: `wlp0s20f3` should not work; change it to `wlan0`:

```shell
ip link set down wlp0s20f3 # this avoid error "RTNETLINK answers: Device or resource busy"
ip link set wlp0s20f3 name wlan0
ip link set up wlan0
```

# Other notes

The specifications of Wi-Fi Direct are developed and published by the [Wi-Fi Alliance consortium](https://www1.wi-fidev.org/discover-wi-fi/wi-fi-direct).

_Running wpa_supplicant from the command line_

Standard UNIX distributions already include a wpa_supplicant service. Anyway, for information, the following allows running it from the command line:

```bash
sudo /sbin/wpa_supplicant -c/etc/wpa_supplicant/wpa_supplicant-wlan0.conf -Dnl80211,wext -iwlan0
```

There is a relevant blog with [in-depth notes on Wi-Fi Direct](https://praneethwifi.in/).
