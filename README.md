hostp2pd
========

__The Wi-Fi Direct Session Manager__

*hostp2pd* implements a soft host [Access Point](https://en.wikipedia.org/wiki/Wireless_access_point) (AP) software in [Wi-Fi Direct](https://en.wikipedia.org/wiki/Wi-Fi_Direct) mode, enabling a [wireless network interface card](https://en.wikipedia.org/wiki/Wireless_network_interface_controller) to act as *Ad hoc* access point and [Wi-Fi Protected Setup](https://en.wikipedia.org/wiki/Wi-Fi_Protected_Setup) (WPS) [authentication server](https://en.wikipedia.org/wiki/Authentication_server). It features basic functionalities roughly similar to [hostapd](https://en.wikipedia.org/wiki/Hostapd) (with its [hostapd.conf](https://w1.fi/cgit/hostap/plain/hostapd/hostapd.conf) configuration file), which is the common AP software integrated with *wpa_supplicant*, generally used for [infrastructure mode networking](https://en.wikipedia.org/wiki/Service_set_(802.11_network)#Infrastructure_mode). When implementing a [P2P persistent group](https://praneethwifi.in/2019/11/23/p2p-group-formation-procedure-persistent-method/), [wpa_supplicant](https://en.wikipedia.org/wiki/Wpa_supplicant) offers the [P2P-GO](https://en.wikipedia.org/wiki/Wireless_LAN#Peer-to-peer) features enabled by *hostp2pd* to connect P2P Clients like Android smartphones, as well as provide the standard infrastructure AP mode to the same P2P-GO group, without the need of *hostapd*.

In order to accept [Wi-Fi Direct](https://www.wi-fi.org/discover-wi-fi/wi-fi-direct) connections from P2P Clients, to activate a local [P2P-GO](https://w1.fi/wpa_supplicant/devel/p2p.html) (Wi-Fi Direct Group Owner) and to perform WPS authentication, *hostp2pd* fully relies on *wpa_supplicant*, interfacing it through the [wpa_cli](https://manpages.debian.org/stretch/wpasupplicant/wpa_cli.8.en.html) command-line interface ([CLI](https://en.wikipedia.org/wiki/Command-line_interface)): *wpa_cli* is run in background and [p2p commands](https://w1.fi/cgit/hostap/plain/wpa_supplicant/README-P2P) are piped via pseudo-tty communication, while events returned by *wpa_cli* are read and processed.

*hostp2pd* includes a command-line interface mode for monitoring and controlling; it can be executed as a batch or as a daemon and provides an API for integration into other Python programs.

# Connecting via Wi-Fi Direct with Android devices

Wi-Fi Direct (formerly named Wi-Fi Peer-to-Peer, or *P2P*) allows devices to connect directly to each other, without the need for a traditional Wireless Access Point (AP). The role of the access point is replaced by the so-called Group Owner (GO), either negotiated during the connection setup, or autonomously created.

An advantage of Wi-Fi Direct with Android is that it can coexist with a traditional Wi-Fi connection as well as with a cellular connection: it means that an Android smartphone can be connected to a mobile network, or to an infrastructure-mode Wi-Fi AP with internet access and at the same time connect to a UNIX device via Wi-Fi Direct, without losing the routing to the mobile (or AP) network. This is because with Android, differently from the standard infrastructure-mode Wi-Fi AP connection where an active Wi-Fi session always takes routing priority to the mobile network for its internal Android routing configuration that disables mobile routing, Wi-Fi Direct does not interfere with the routing table.

Apple iOS devices do not support Wi-Fi Direct, but can concurrently connect to a P2P persistent group in AP mode the same way as for traditional infrastructure-mode Access Points managed by *hostapd*. Differently from Android phones, if the persistent group does not configure a default router, iOS does not change the routing tables of the cellular network, which is by consequence not lost.

# Installation

Check that the Python version is 3.6 or higher (`python3 -V`), then install *hostp2pd* with the following command:

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

The above command uses the automatically detected P2P-Device interface and the internal default configuration file.

Using a P2P-Device interface and a configuration file:

```shell
hostp2pd -i p2p-dev-wlan0 -c /etc/hostp2pd.yaml
```

- `-i` option: The P2P-Device interface used by hostp2pd is created by *wpa_supplicant* over the physical wlan interface (if default options are used). Use `iw dev` to list the available wlan interfaces. An *unnamed/non-netdev* interface with *type P2P-device* should be found. If no P2P-Device is shown (e.g., only the physical *phy#0* Interface *wlan0* is present), either *wpa_supplicant* is not active or it is not appropriately compiled/configured. With *wlan0* as physical interface (ref. `iw dev`), to get the name of the P2P-Interface use the command `wpa_cli -i wlan0 interface`: it should return the interface device *wlan0* and the P2P-device (e.g., *p2p-dev-wlan0*). Use this name as argument to the `-i` option of *hostp2pd*. Notice also that, if a P2P-Device is configured, `wpa_cli` without option should automatically point to this interface. If `-i` option is not used, *hostp2pd* tries to automatically detect the right interface.
- `-c` option: a [YAML](https://en.wikipedia.org/wiki/YAML) configuration file ([here](hostp2pd/hostp2pd.yaml) an example) is not strictly necessary to start a first test; a minimum parameter would be the PIN, which can be alternatively defined using a shell [Here Document](https://en.wikipedia.org/wiki/Here_document) expression:
  ```shell
  hostp2pd -i p2p-dev-wlan0 -c - <<\eof
  pin: "00000000"
  eof
  ```

In this documentation, the UNIX system is where *hostp2pd* is installed and run, generally acting as P2P-GO. The P2P device is generally an Android smartphone (or another Linux/Windows system).

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

Optionally, *hostp2pd* allows the `-p` option, which defines an external program to be run with specific arguments each time preconfigured events occur, like activating or deactivating a group; this for instance allows controlling external AP resources before groups are created or after groups are removed.

Preconfigured events:

- "started": executed at *hostp2pd* startup
- "terminated": executed at *hostp2pd* termination
- "start_group": executed before creating a P2P GO group
- "stop_group": executed after removing a P2P GO group
- "connect": executed after a station connects to a group
- "disconnect": executed after a station disconnects from a group

Events might have additional arguments, which are used to add related attributes.

This is an example of RUN_PROGRAM (/tmp/run_program_sample):

```bash
#!/bin/bash
# /tmp/run_program_sample
set -o errexit -o nounset -o pipefail -o functrace -o errtrace -eE
case "$1" in
started) echo "hpstp2pd startup - $@";;
terminated) echo "hpstp2pd terminated - $@";;
start_group) echo "P2P-GO group creation - $@";;
stop_group) echo "P2P-GO group removal - $@";;
connect) echo "Station connected - $@";;
disconnect) echo "Station disconnected - $@";;
*) echo "Unknown command - $@";;
esac
```

Related test case:

```shell
hostp2pd -i p2p-dev-wlan0 -c /etc/hostp2pd.yaml -p /tmp/run_program_sample
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
device_type=6-0050F204-1                                # (Optional: Microsoft wireless device, Network Infrastructure, AP)
config_methods=keypad                                   # "keypad" uses a fixed PIN on UNIX, which is asked from a keypad popped up on the Android devices
p2p_go_intent=15                                        # Optional, only to be used in case of negotiation. Force UNIX to become a P2P-GO (Group Owner)
persistent_reconnect=1                                  # Allow reconnecting to a persistent group without user acknowledgement
p2p_go_ht40=1                                           # Optional: use HT40 channel bandwidth (300 Mbps) when operating as GO (instead of 144.5Mbps).
country=<country ID>                                    # Use your country code here
p2p_device_persistent_mac_addr=<mac address>            # Fixed MAC address overcoming MAC Randomization, to be used with persistent group
p2p_device_random_mac_addr=<mode>                       # MAC address management to create the P2P Device interface

# This is an example of P2P persistent group:
network={                                               # Network profile
        ssid="DIRECT-PP-group"                          # Name of the persistent group saved on the Android phone and shown within the AP names;
                                                        # use any name in place of "PP-group" and keep the "DIRECT-xx-" prefix.
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

-	The SSID of the P2P-GO shall begin with the `DIRECT-xx-...` prefix (P2P_WILDCARD_SSID), otherwise the group is not appropriately announced to the network as a P2P group; any alphanumeric string can be used after `DIRECT-` prefix; the format `DIRECT-<random two octets>[-<optional postfix>]` is suggested.
-	A `mode=3` directive shall be present, meaning [WPAS_MODE_P2P_GO](https://w1.fi/wpa_supplicant/devel/structwpa__ssid.html), otherwise the related `p2p_group_add` command fails for unproper group specification.
-	A `disabled=2` directive shall be present, meaning persistent P2P group, otherwise the stanza is not even recognized and listed as persistent (`disabled=0` indicates normal network; `disabled=1` will announce a disabled network).

If no persistent group is predefined in *wpa_supplicant.conf* and if `activate_persistent_group` is set to `True`, then *hostp2pd* asks *wpa_supplicant* to create a generic persistent group, giving it a name with format `DIRECT-<random two octets>`.

If *update_config* is set to 1, the configuration file is automatically updated by *wpa_supplicant* in the following cases:

- a new network block is added
- a password is changed
- a P2P group is created

Notice that, whenever the configuration file is automatically updated

- all comments are stripped,
- all parameters set to default values are removed from the configuration file.

The *p2p_go_intent* parameter is a number between 0 and 15 which controls the default group owner intent: higher numbers indicate preference to become the GO. It is not needed in case of autonomous or persistent groups (in these cases the UNIX system is always a GO) and it is used only when the GO role is negotiated.

The optional parameter `ssid_postfix` in the *hostp2pd* configuration file allows adding a fixed postfix string to the SSID whenever a group is created by *wpa_supplicant*  (the form `DIRECT-<random two octets>-<ssid_postfix string>` is used).

Other parameters (like `freq_list`) can be used.

See below for the usage of `p2p_device_random_mac_addr`; in summary, if the device driver uses persistent MAC addresses by default, this option shall be set to 0 (usage of the default persistent MAC address) or to 1 (usage of random MAC addresses only if a group is not set, otherwise, the MAC address is changed to `p2p_device_persistent_mac_addr`); some 802.11 device drivers do not allow `p2p_device_random_mac_addr=1` and need a modification of the *wpa_supplicant* code to use `p2p_device_random_mac_addr=2`.

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
stations
eof
```

## Device Identification Parameters

The *wpa_supplicant* configuration file allows including optional parameters identifying the UNIX system when presenting itself on the network.

*device_type* represents the primary device type with information of category, sub-category, and a manufacturer specific [OUI (Organization ID)](https://en.wikipedia.org/wiki/Organizationally_unique_identifier) conforming to "Annex B P2P Specific WSC IE Attributes" in "Wi-Fi Peer-to-Peer (P2P) Technical Specification".

Used format from the [hostapd.conf manual](https://w1.fi/cgit/hostap/plain/hostapd/hostapd.conf) related to the *Primary Device Type* parameter:

*categ*-*OUI*-*subcateg*

- categ = Category as an integer value: "Category ID" defined in the Annex B format of the Wi-Fi Direct specification.
- OUI = A four-byte subdivided "OUI and type" field, consisting of a 4-octet hex-encoded value which identifies a product from a specific company and is basically the first three octets of a MAC address with the addition of a type subfield. [As documented by Microsoft](https://docs.microsoft.com/en-us/windows/win32/api/wcntypes/ns-wcntypes-wcn_value_type_primary_device_type), the 0050F204 CDI-32 OUI is a Vendor­Specific IE referred to Microsoft (00:50:f2), with subtype 4 (wireless device). Anyway, as reported in the Wi-Fi Peer-to-Peer (P2P) Technical Specification, 0050F204 is the predefined value for a default OUI for a generic vendor.
- subcateg = OUI-specific Sub Category: "Sub Category ID" defined in the Annex B format of the Wi-Fi Direct specification

The following table reports some commented examples:

device_type|Device Type|Description
-----------|-----------|-----------
1-0050F204-1|Computer / PC|Category 1 = Computer, Sub Category 1 = PC
1-0050F204-2|Computer / Server|Category 1 = Computer, Sub Category 2 = Server
5-0050F204-1|Storage / NAS|Category 5 = Storage, Sub Category 1 = NAS
6-0050F204-1|Network Infrastructure / AP|Category 6 = Network Infrastructure, Sub Category 1 = AP
10-0050F204-5|Telephone / Smartphone – dual mode|Category 10 = Telephone, Sub Category 5 = Smartphone – dual mode (typical Android device_type)
3-0050F204-1|Printer|Category 3 = Printers, Scanners, Faxes and Copiers, Sub Category 1 = Printer or Print Server
3-0050F204-5|All-in-one Printer|Category 3 = Printers, Scanners, Faxes and Copiers, Sub Category 1 = All-in-one (Printer, Scanner, Fax, Copier)

The *Primary Device Type* parameter is for instance used to identify the device with the "pri_dev_type" field of "P2P-DEVICE-FOUND", "P2P-PROV-DISC-ENTER-PIN", "P2P-PROV-DISC-PBC-REQ", "P2P-PROV-DISC-SHOW-PIN" (or in WPS-ENROLLEE-SEEN).

Suggested device type for *hostp2pd*:

```ini
device_type=6-0050F204-1
```

Other possible elements that can be declared in *wpa_supplicant.conf*:

```ini
# Manufacturer
# The manufacturer of the device (up to 64 ASCII characters)
manufacturer=my_manufacturer_name

# Model Name
# Model of the device (up to 32 ASCII characters)
model_name=my_model_name

# Model Number
# Additional device description (up to 32 ASCII characters)
model_number=my_model_number

# Serial Number
# Serial number of the device (up to 32 characters)
serial_number=12345

# OS Version
# 4-octet operating system version number (hex string)
os_version=01020300
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
- `pbc_in_use: False`: force the *keypad* configuration method, performing the enrolment with configured PIN;
- `pbc_in_use: True`: force the *virtual_push_button* configuration method, performing the enrolment without PIN.

Configuration methods:
- *keypad*: the Android phone prompts a soft keypad; the user has to enter a fixed passkey compliant to the one set in the *hostp2pd.yaml* configuration file.
- *virtual_push_button* (pbc): no PIN is used. Anyway, a whitelist of client names can be defined (`pbc_white_list`).

The *keypad* configuration method needs a PIN configured in *hostp2pd.yaml* through the `pin` directive (e.g., `pin: "12345678"`; notice also that any PIN different from eight digits is not accepted by *wpa_supplicant*, unless differently specified by `p2p_passphrase_len`).

Using *virtual_push_button* is extremely weak and discovering the P2P client names can be easily made by any user.

# Use cases

In summary, with the standard group formation technique negotiated on demand, when a P2P Client starts a connection, the UNIX device will always become a GO (Group Owner) if `p2p_go_intent` in *wpa_supplicant.conf* is set to 15. In autonomous and persistent group formation technique, the UNIX device becomes a group owner by itself without any client request. Persistent groups are saved in the *wpa_supplicant* configuration file and can be reused after restarting *wpa_supplicant* or rebooting the UNIX system (and after rebooting the Android device). While Wi-Fi MAC addresses are generally randomized, with persistent groups both the Android device and the UNIX system keep the same wireless MAC address (see note below on *wpa_supplicant*).

The following table details the use cases:

Group Formation technique|Configuration|Description
-------------------------|-------------|-----------
Negotiated on demand|`activate_persistent_group: False`, `activate_autonomous_group: False`, `dynamic_group: True`|Non-persistent P2P Group formation method using non-autonomous negotiation technique; groups are dynamically created and removed by *hostp2pd* via `p2p_connect` and `p2p_group_remove`; in other terms, no group is created at startup and the first client connection performs the P2P group formation. Subsequent sessions are enrolled to the same group. Only a single P2P-GO group is kept active. The group is removed when the last client session is disconnected. The related virtual network interface is activated only on demand and the related device driver resource is released when not in use. The P2P Client enrolment with its authorization process is slow (especially when forming the group) and always needed.
Autonomous on demand|`activate_persistent_group: False`, `activate_autonomous_group: False`, `dynamic_group: False`|P2P Group Formation using on-demand Autonomous GO Method, configuring a non-persistent autonomous group activated upon the first connection: *hostp2pd* uses `p2p_connect` to setup the first session, while all subsequent connections are managed through WPS enrolment. Once created, the related virtual network interface will be kept active. Authorization process is always needed and generally slow (especially the first time, when the group formation is required on the GO).
Autonomous|`activate_persistent_group: False`, `activate_autonomous_group: True`, `dynamic_group: False`|P2P Group Formation using Autonomous GO Method, configuring a non-persistent autonomous group at startup (using `p2p_group_create`); all connections are managed through WPS enrolment. The related virtual network interface will always be active. Authorization process is always needed.
Persistent on demand|`activate_persistent_group: True`, `activate_autonomous_group: False`, `dynamic_group: True`|Negotiated persistent group. To setup the first session, *hostp2pd* uses `p2p_connect ... persistent or persistent=<network id>`, depending on the existence of a valid persistent group in *wpa_supplicant* configuration file). The authorization process is only performed the first time (slow), than all reconnections are pretty fast and fully automated by *wpa_supplicant*. With this setting, the P2P Client is able on demand to automatically restart the P2P-GO group on the UNIX system and then connect to this group without WPS enrolment. So, after the P2P-GO group is saved to the P2P Client, any subsequent reconnection of the same client is not mediated by *hostp2pd*; the only task of *hostp2pd* is to enrol new clients, in order to allow them to locally save the persistent group. The related virtual network interface is activated only on demand and then kept active.
Persistent|`activate_persistent_group: True`, `activate_autonomous_group: False`, `dynamic_group: False`|The persistent group is autonomously activated at program startup. If the persistent group is predefined in *wpa_supplicant.conf*, it is restarted, otherwise a new persistent group is created. The virtual network interface is kept constantly active. The authorization process of a P2P Device is only performed the first time (if the persistent group is not saved in the peer), through WPS enrolment technique; after the persistent group data is saved to the P2P Device, all reconnections of the same device are fast and automatically done without WPS enrolment (so not mediated by *hostp2pd*). The creation of the persistent group is done via *p2p_group_add persistent*. If a persistent group is already (e.g., manually) defined in *wpa_supplicant* (and this is the suggested method), it is re-invoked via *p2p_group_add persistent=n*. If a persistent group is not defined in *wpa_supplicant* and if the *network_parms* list exists in the *hostp2pd* configuration, the persistent group is created with the parameters set in the *network_parms* list, that is used to automatically create and save the network profile (`mode=3` and `disabled=2` are automatically added and so they are not required in the *network_parms* list); if also this configuration parameter is not set, the persistent group is created with the default parameters set by *wpa_supplicant*. 

Using an autonomous GO for a non-persistent group, the passphrase and SSID are automatically created by *wpa_supplicant* (using random strings) and the related settings should not be modified. A persistent group can be either manually or automatically created.

Using the standard group negotiation method with fixed PIN, an Android client (at least, up to Android 11) will not save the PIN (the authorization has to be performed on every connection). Using persistent groups, with newer Android releases a local group information element is permanently stored in the Android handset (until it is deleted by hand) and this enables to directly perform all subsequent reconnections without separate authorization (e.g., without user interaction). Ref. also [Compatibility](#Compatibility)

In all cases that foresee a negotiation (usage of `p2p_connect`), the UNIX System will always become GO (ref. `p2p_go_intent=15` in *wpa_supplicant.conf*).

If a whitelist (`pbc_white_list: ...`) is configured with push button mode/PBC (`pbc_in_use: True` or `config_methods=virtual_push_button`) and if the client name does not correspond to any whitelisted names, then the configuration method is changed from *pbc* to *keypad*.

Internally, connections to Autonomous/Persistent Groups are managed by a subprocess named Enroller, which does `wps_pin` or `wps_pbc` over the group interface. The `interface` and `list_networks` commands of *wpa_cli* are used to check groups. `p2p_find` is periodically executed to ensure that announcements are performed (especially when [P2P group beacons](https://en.wikipedia.org/wiki/Beacon_frame) are not active). A number of events are managed.

If different P2P-GO persistent groups are defined in the *wpa_supplicant* configuration file, by default the first one in the configuration file is used (e.g., the first group listed by the *wpa_cli* `list_networks` command including `[P2P-PERSISTENT]`); use `persistent_network_id` to force a specific network id instead of the first one (provided that it is correctly configured in the *wpa_supplicant* configuration file, so that it is recognized as persistent group).

Invitation (`p2p_invite`) is not used by the current version of *hostp2pd*, which is at the moment designed to enable integration of the Wi-Fi Direct Android connection panel with a P2P-GO group on the UNIX system running *wpa_supplicant*; in such use case, invitation is not actually needed, because the Android user must manually form the connection and in some cases Android P2P clients announce themselves (*P2P-DEVICE-FOUND* event) only at connection time.

# Compatibility

Only UNIX operating systems running *wpa_supplicant* and *wpa_cli* are allowed.

_Important Note: with the current *hostp2pd* version, the only working Operating System is Raspberry Pi 4 Model B with Raspbian Buster O.S. - Other Linux O.S. like Ubuntu are not supported at the moment._

Current Ubuntu 20.04.1 LTS issues with *wpa_cli* (which make *hostp2pd* useless with that O.S.):

- *wpa_cli* is not automatically terminated when *hostp2pd* exits.
- Always occurring error *Invalid negotiation request from station with address "fe:c1:3f:1c:b1:b7".* while performing a session connection from an Android phone.

Current Ubuntu 20.04.2 LTS issues with *wpa_supplicant* v2.9:

- *wpa_supplicant* dies when *hostp2pd* updates the configuration without configuration file in the parameter and with NetworkManager integration (through `-u`) (disable `update_config: 1` config_parms to avoid the problem).
- *wpa_supplicant* does not support `p2p_device_random_mac_addr=1` and `p2p_device_random_mac_addr=2`
- *wpa_supplicant* v2.9 included in Ubuntu 20.04.2 LTS crashes when creating persistent groups. See previous point on disabling `update_config: 1`, or recompile the program with the latest sources and install the compiled version.

*hostp2pd* has been tested with:

- Raspberry Pi 4 Model B hw
- Raspberry Pi OS Buster O.S.
- UNIX wpa_cli and wpa_supplicant version v2.8-devel (Debian Buster); it is suggested to use the latest [*wpa_supplicant* development version](http://w1.fi/cgit/hostap) to take advantage of *p2p_device_random_mac_addr* which overcomes the [MAC randomization issue with persistent groups](#mac-randomization).
- Python 3.7.3 on Debian (Raspberry Pi OS Buster). Python 2 and Python versions older than 3.6 are not supported.
- P2P Clients including Android 11, Android 10, Android 9, Android 8, Android 7 and Android 6 smartphones.

Wi-Fi Direct is present in most smartphones with at least Android 4.0 (API level 14); notice anyway that only recent Android versions support the local saving of persistent groups. With some Android 6 and 7 devices (depending on the ROM), the enrolment is always needed when connecting a persistent group. Some devices have a slower notification of announced groups; generally if the UNIX system device does not appear after a P2P-GO is created, try exiting from the Android Wi-Fi Direct panel and then and re-entering. Some devices also show the AP icon. Sometimes the enrolling might fail, often depending on the Android version (this is possibly due to timeout issues, especially correlated to missing *WPS-ENROLLEE-SEEN* events sent by the Android device).

## Built-in keywords

At the `CMD> ` prompt in interactive mode, *hostp2pd* accepts the following commands:

- `version` = Print hostp2pd version.
- `loglevel` = If an argument is given, set the logging level, otherwise show the current one. Valid numbers: CRITICAL=50, ERROR=40, WARNING=30, INFO=20, DEBUG=10.
- `reload` = Reload configuration from the latest valid configuration file. Optional argument is a new configuration file; to load defaults use `reset` as argument.
- `reset` = Reset the hostp2pd statistics.
- `stations` = Print all discovered stations. Besides, the following variables can be used at prompt level:
  - `hostp2pd.addr_register`: peer name for each discovered peer
  - `hostp2pd.dev_type_register`: peer type for each discovered peer
- `stats` = Print execution statistics. Besides, the following variable can be used at prompt level:
  - `hostp2pd.statistics`: list of all commands issued by wpa_supplicant
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
- predefinition of a persistent P2P group in the *wpa_supplicant* configuration file;
- appropriate configuration of *wpa_supplicant* so that the persistent P2P group will not randomize the MAC address of the related virtual wireless interface;
- usage of appropriate group name and related WPA configuration in the *wpa_supplicant* configuration file (e.g., WPA2 password), so that this P2P group can also act as AP (instead of using *hostapd*); defining a secret WPA2 password is a workaround to deny AP connections;
- for better usage of Wi-Fi Direct naming, differentiate the name of the P2P device and the P2P group in the *wpa_supplicant* configuration file (e.g., P2P-Device = "DIRECT-Host"; P2P group = "DIRECT-PP-group");
- *hostp2pd* configuration to use a persistent P2P group activated at process startup, with "keypad" authorization method;
- *hostp2pd* service setup to start at system boot time;
- read access protection of *wpa_supplicant* and *hostp2pd* configuration files to non-root users;
- *hostp2pd* logging set to root level WARNING (instead of DEBUG mode, which can be used for initial testing);
- for improved security, definition of a non-standard number of WPS digits (ref. `p2p_passphrase_len`in the *wpa_supplicant* configuration file).

# Limitations

The current *hostp2pd* implementation has the following limitations:

- tested with an Android 10 smartphone connecting to a Raspberry Pi 4 with Wi-Fi Direct protocol (and also using AP mode); all [use cases](#use-cases) are referred to this scenario.
- At the moment, *hostp2pd* is tested with only one station; two or more stations should concurrently connect to the same persistent group.
- At the moment, *hostp2pd* manages only one active P2P GO group for a specific P2P-Device, even if more instances of *hostp2pd* are allowed, each one referred to a specific P2P-Device (generally a specific wireless wlan board). This is because *wpa_supplicant* appears to announce the P2P-Device name to the Android clients (ref. "device_name" in the *wpa_supplicant* configuration, which is the same for all groups) and not the specific active P2P GO groups; likewise, it is not known how an Android client can inform *wpa_supplicant* to enrol a specific group of a known P2P-device through the default Wi-Fi Direct user interface. Notice also that some wireless drivers on UNIX systems only allow one P2P-GO group.
- The enrolment procedure (WPS authorization made by the *hostp2pd* Enroller subprocess) is activated in sync with the start of the P2P group made by *hostp2pd* (either *p2p_connect* or *p2p_group_add* commands) and remains active until the group is removed (reception of *P2P-GROUP-REMOVED* event); single connection requests by P2P Clients (controlled by respective *P2P-PROV-DISC-...* events) will not directly start the WPS authorization process, but will start a group formation (via *p2p_connect*) if a group is not active. While a P2P group is kept active by *hostp2pd*, any P2P Client requesting a P2P connection to the P2P-Device wireless interface will be part of the same active *hostp2pd* enrolment process to the active group.
- As hostp2pd is fully unattended, the following WPS credential methods are available: *pbc* and *keypad*. The *display* configuration method (much more secure than *keypad*) is not implemented and needs interaction (to insert the PIN presented by the Android handset). This means that at the moment the enrolment is done with either a static PIN saved in the *hostp2pd* configuration file or with no PIN at all (PBC mode). To protect PBC (no PIN), a list of enabled enrollees names can be defined. Notice that this is a weak authentication method, because the enrollees names are publicly announced. After all, MAC address filtering is not appropriate because, if a persistent group is not active, MAC addresses are randomized.
- When `dynamic_group` option is set to `True`, only a single station a time is accepted, because when a station disconnects, the group is removed by *hostp2pd* and any other connected station loses the session.

# Logging

Logging is configured in *hostp2pd.yaml*. This is in [Python logging configuration format](https://docs.python.org/3/library/logging.config.html). By default, logs are saved in /var/log/hostp2pd.log, rolled into three files. Also, logs can be forced to a specific log level through the `force_logging` configuration attribute.

In interactive mode, logging can be changed using `loglevel`.

To browse the log files, [lnav](https://github.com/tstack/lnav) is suggested.

If the following error message occurs: `CRITICAL:root:Wrong "logging" section in YAML configuration file "/etc/hostp2pd.yaml": Unable to configure handler 'file'.`, it means that 
the current *hostp2pd* permissions do not allow updating the log file; try `sudo chmod a+rw /var/log/hostp2pd.log*`.

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
    pin="00000000")             # optional PIN of keypad enrolment
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

The following example browses the registered Wi-Fi Direct stations after collecting information for 40 seconds.

```python
from hostp2pd import HostP2pD
import time

with HostP2pD() as hostp2pd:
    time.sleep(40)
    if hostp2pd.addr_register:
        print("Station addresses:")
        for i in hostp2pd.addr_register:
            print("  {} = {:35s} ({})".format(i,
                    hostp2pd.addr_register[i],
                    (hostp2pd.dev_type_register[i]
                        if i in hostp2pd.dev_type_register
                        else "(unknown device type)")
                )
            )

print("Completed.")
```

Example of output:

```ini
Station addresses:
  ae:e2:d3:41:27:14 = DIRECT-14-HP ENVY 5000 series       (Printer)
  ee:11:6c:59:a3:d4 = DIRECT-Example                      (AP Network Infrastructure device)
Completed.
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

```bash
python3 -c 'import dbus;\
dbus.Interface(dbus.SystemBus().get_object("fi.w1.wpa_supplicant1",\
"/fi/w1/wpa_supplicant1"), "fi.w1.wpa_supplicant1")\
.GetInterface("p2p-dev-wlan0")'
```

This is because *wpa_supplicant* does not expose *p2p-dev-wlan0* to *dbus*. It means that [the old Python test examples](http://w1.fi/cgit/hostap/tree/wpa_supplicant/examples/p2p) included in *wpa_supplicant* sources, which exploited *dbus*, are not usable. Notice also that if *p2p-dev-wlan0* in the above Python command is changed to *wlan0* (which is unrelated to P2P anyway), the command returns with no errors.

If [NetworkManager](https://en.wikipedia.org/wiki/NetworkManager) is used to configure the network interfaces, it connects *wpa_supplicant* via *dbus* and the `-u` option is needed for appropriate interaction between the two programs. Anyway, NetworkManager does not manage P2P functions.

*hostp2pd* relies on *wpa_cli* considering that:

- it is natively integrated with *wpa_supplicant* via proven and robust communication method,
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

Anyway, when using persistent groups, MAC addresses shall not vary in order to avoid breaking the group restart: if a device supports MAC Randomization, restarting *wpa_supplicant* will change the local MAC address of the related virtual interface; a persistent group re-invoked with different MAC address denies the reuse of the saved group in the peer system.
[This appears to be appropriately managed by Android devices](https://source.android.com/devices/tech/connect/wifi-direct#mac_randomization).

A configuration strategy that appears to prevent MAC randomization with persistent groups might be the one mentioned [in a patch](http://w1.fi/cgit/hostap/commit/?id=9359cc8483eb84fbbb0a75cf64dcffd213fb412e) and it possibly only applicable to some nl80211 device drivers supporting it; so, for some devices, using `p2p_device_random_mac_addr=1` and `p2p_device_persistent_mac_addr=<mac address>` can do the job. Otherwise, the latest *wpa_supplicant* version might be needed, which [includes another patch](http://w1.fi/cgit/hostap/commit/?id=e79febb3f5b516f4027fba0a8a35be359c38cf9f) exploiting the usage of the `p2p_device_persistent_mac_addr` parameter with option `p2p_device_random_mac_addr=2`. Notice that also `update_config=1` is required.

The following commands allow downloading the latest version of the *wpa_supplicant* sources, preparing the environment on Ubuntu, compiling the code and installing:

```bash
sudo apt-get update
sudo apt-get install -y git libnl-genl-3-dev libnl-route-3-dev build-essential libdbus-glib-1-dev libgirepository1.0-dev libssl-dev libdbus-1-dev

git clone git://w1.fi/srv/git/hostap.git
cd hostap
cp wpa_supplicant/defconfig wpa_supplicant/.config
cd wpa_supplicant
make -j$(($(nproc)+1))

# Example of installation:
sudo mv /sbin/wpa_supplicant /sbin/wpa_supplicant-org
sudo systemctl stop dhcpcd # in case wpa_supplicant is managed by dhcpcd (Debian, Raspberry)
# sudo systemctl stop NetworkManager # in case wpa_supplicant is managed by the NetworkManager (Ubuntu)
# sudo systemctl stop wpa_supplicant.service # in case wpa_supplicant is managed by a specific service (NetworkManager or custom setup)
sudo killall wpa_supplicant # in other cases
sudo cp wpa_supplicant /sbin
sudo systemctl start dhcpcd # in case wpa_supplicant is managed by dhcpcd
# sudo systemctl start NetworkManager # in case wpa_supplicant is managed by the NetworkManager
# sudo systemctl start wpa_supplicant.service # in case wpa_supplicant is managed by a specific service (NetworkManager or custom setup)
pgrep -l wpa_supplicant

# Alternative standard installation example:
#sudo make install
```

Add the following in *wpa_supplicant.conf*:

```ini
p2p_device_random_mac_addr=2
```

A description of the `p2p_device_random_mac_addr` configuration settings obtained with this patch follows.

```ini
p2p_device_random_mac_addr=0
```

This is the default option and uses the MAC address set by the device driver.
If the default is a static MAC address, this address is kept unaltered.
If the device driver is configured by default to always use random MAC addresses,
this flag breaks reinvoking a persistent group (which needs reusing the same MAC
address used during the group creation phase), so flags 1 or 2 should be used
instead.

```ini
p2p_device_random_mac_addr=1
```

On creating the interface, if there is no persistent group, this option changes
the interface MAC address using random numbers computed by wpa_supplicant.
Besides, if a persistent group is created, p2p_device_persistent_mac_addr is set
to the MAC address of the P2P Device interface, so that this address will be
subsequently reused to change the MAC address of the P2P Device interface.
This option relies on SIOCGIFFLAGS/SIOCSIFFLAGS ioctl interface control
operations to change the MAC address, which implies that the device driver shall
support this mode.

```ini
p2p_device_random_mac_addr=2
```

This flag should be used when the device driver uses internally generated random
MAC addresses by default when a P2P Device interface is created. If
p2p_device_persistent_mac_addr is set, this MAC address is used on creating the
P2P Device interface (in place of the one produced by the device driver).
If not set, the default method adopted by the device driver (e.g., random
MAC address) is used. Besides, if a persistent group is created,
p2p_device_persistent_mac_addr is set to the MAC address of the P2P Device
interface, so that this address will be subsequently used in place of the
default address set by the device driver. (This option does not need
support of SIOCGIFFLAGS/SIOCSIFFLAGS ioctl interface control operations to
change the MAC address and uses the NL80211_ATTR_MAC attribute).

Notice that the default *wpa_supplicant* code manages `p2p_device_random_mac_addr=2` the same as `p2p_device_random_mac_addr=1`. So, if returning back to the original code and if the device driver does not support SIOCGIFFLAGS/SIOCSIFFLAGS ioctl interface control operations to change the MAC address, also remove *p2p_device_random_mac_addr* or set it to 0.

## Compiling wpa_gui

```shell
cd hostap/wpa_supplicant
sudo apt-get install -y qt5-default qttools5-dev-tools
make wpa_gui-qt4
cd wpa_gui-qt4
./wpa_gui
```

Notice that *wpa_gui* connects the wireless interface, but not P2P devices and P2P Groups.

_______________

__Notes__
=========

# wpa_supplicant issues

## wpa_cli does not connect to wpa_supplicant

Example of error messagge: *Could not connect to wpa_supplicant: (nil) - re-trying*.

Check the existence of the UNIX sockets (generally under */var/run/wpa_supplicant*, see the *ctrl_interface* parameter in the *wpa_supplicant* configuration file, or the *wpa_supplicant* command line arguments):

```
ls -l /var/run/wpa_supplicant
```

If one or more UNIX socket special files exist, generally this error means that *wpa_cli* has not permissions enough to access the *wpa_supplicant* UNIX socket. Try running *wpa_cli* and *hostp2pd* with *root* or *netdev* permissions.

If the connection succeeds with *root* permission, follow these steps to configure a non-root user to connect:
- create a group (say "netdev", which should already exist in most distributions; if not existing: `sudo groupadd netdev`);
- associate the user to that group (e.g., for the user "*my_user*": `sudo usermod -a -G netdev my_user`);
- check how *wpa_supplicant* is started (`ps -ef | grep wpa_supplicant`):
  - if the `-O` option is used, like `-O /run/wpa_supplicant`, change it to a string including *DIR* and *GROUP* attributes, assigning *GROUP* to *netdev*, like in `-O "DIR=/run/wpa_supplicant GROUP=netdev"`;
  - if `-O` and `-i` are not used, while `-s` is used, then you need to set the `-O` option like before; notice that any setting included in the *wpa_supplicant* configuration file (e.g., `-c` option) will not be used in this case; example of correct configuration: `/sbin/wpa_supplicant -u -s -O "DIR=/run/wpa_supplicant GROUP=netdev"`;
  - if `-O` is not used, while `-i` and `-c` are used, then you can set the *GROUP* attribute in the *wpa_supplicant* configuration file (e.g., specified with `-c` option); example: `ctrl_interface=DIR=/run/wpa_supplicant GROUP=netdev`.

  You can use `/var/run` in place of `/run` in the above examples, as generally `/var/run` is a symbolic link of `/run`.

If the *ctrl_interface* directory does not exist (also checked with root user), either *wpa_supplicant* is not running, or it is running with not appropriate configuration.

If *wpa_cli* connects the network device (e.g., *wlan0*, like `wpa_cli -i wlan0`) but not the P2P-Device (e.g., *p2p-dev-wlan0*), use `iw dev` to check the presence of a P2P-Device. If not existing, then *wpa_supplicant* has configuration issues. Run *wpa_supplicant* with `-dd` options and verify the error messages:

```shell
kill <wpa supplicant process>
sudo /sbin/wpa_supplicant -c<configuration file> -Dnl80211,wext -i<network device> -dd
```

## Android device never browsing the UNIX system running wpa_supplicant

Check that the Android device supports both 2.4 GHz and 5 GHz bands: *wpa_supplicant* might have used a 5 GHz channel for the P2P-GO group, which will not be received by an Android device only supporting the 2.4 GHz band.

To force *wpa_supplicant* to use the 2.4 GHz band for the P2P-GO group, set `p2p_group_add_opts: freq=2` in *hostp2pd.yaml*. Anyway, on some devices (Raspberry Pi) after some time the band might be autonomously moved to the 5 GHz band (by the wireless device driver); in such cases, the only possible method to force the permanent usage of 2.4 GHz band is by setting a [country code](https://en.wikipedia.org/wiki/List_of_WLAN_channels) that denies the allocation of 5 GHz frequencies according to the related regulatory domain; for instance, depending on the device driver setup, adding `country=RU` to the *wpa_supplicant* configuration file should only allow Wi-Fi channels 1 to 13.

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

## wpa_supplicant crash

If no configuration file is set with *wpa_supplicant*, old versions of this program will crash (segmentation fault) when the `save_config` command is issued by *wpa_cli*, or when the internal functions of *wpa_supplicant* require to save the configuration file (e.g., following a P2P Group creation). This is typical of Ubuntu versions where *wpa_supplicant* is started by the *NetworkManager* via *dbus* (`-u` option), without any need of configuration file. Example: `wpa_supplicant -u -s -O /run/wpa_supplicant`. To fix this issue, either upgrade *wpa_supplicant* (e.g., recompiling it from sources) or ensure that the *hostp2pd* configuration file (*hostp2pd.yaml*) does not configure a *config_parms* with `update_config: 1`.

# Other notes

The specifications of Wi-Fi Direct are developed and published by the [Wi-Fi Alliance consortium](https://www1.wi-fidev.org/discover-wi-fi/wi-fi-direct).

_Running wpa_supplicant from the command line_

Standard UNIX distributions already include a wpa_supplicant service. Anyway, for information, the following allows running it from the command line:

```bash
sudo /sbin/wpa_supplicant -c/etc/wpa_supplicant/wpa_supplicant-wlan0.conf -Dnl80211,wext -iwlan0
```

There is a relevant blog with [in-depth notes on Wi-Fi Direct](https://praneethwifi.in/).

_______________

# License
=========

Copyright (c) Ircama 2021 - [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
