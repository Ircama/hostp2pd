__WiFi-Direct Connection Manager__

This basic program interfaces [wpa_supplicant](https://en.wikipedia.org/wiki/Wpa_supplicant) via [wpa_cli](https://jlk.fjfi.cvut.cz/arch/manpages/man/wpa_cli.8), running *wpa_cli* in background and piping [p2p commands](https://w1.fi/cgit/hostap/plain/wpa_supplicant/README-P2P) to it, while reading events, in order to fully automate the workflow of a P2P AP server based on *wpa_supplicant* that manages connections of a single P2P client in [WiFi Direct](https://en.wikipedia.org/wiki/Wi-Fi_Direct) mode.

Run with `python3 wifip2p_monitor.py`.

Tested with an Android client connecting a Raspberry Pi with WiFi Direct protocol.

Related configuration is in the program configuration section. The program allows two execution modes:

- Dynamic method: unset `use_conn_str`. With this method, if the client is whitelisted, the connection is performed via *pbc*, without asking a password. Otherwise, a password is asked.
- Static method: set `use_conn_str`. With this method, using or not *pbc* depends on the static configuration.

The default is to use *pbc* in static configuration. To convert the mode to dynamic process, unset `use_conn_str`.

Logging is controlled by `logging.basicConfig(level=...)`. Default is *logging.WARNING* for minimal logging. Set it to *logging.INFO* or *logging.DEBUG* to increase logging.

To configure WiFi Direct on a Raspberry Pi, follow [this link](https://raspberrypi.stackexchange.com/q/117238/126729).

Check that *wpa_supplicant-wlan0.conf* includes the following headers:

```
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
driver_param=p2p_device=6
update_config=1
device_name=DIRECT-<replace with the AP name>
device_type=6-0050F204-1
config_methods=virtual_push_button
p2p_go_intent=15
p2p_go_ht40=1
country=<replace with the country ID>
...
```

Notice that with Raspberry Pi, running AP and P2P concurrently does not appear to be supported. Specifically, if a command like `iw dev wlan0 interface add uap0 type __ap` is issued to create a virtual wifi interface (in order for an access point to be managed for instance by *hostapd*), `wpa_cli -i p2p-dev-wlan0 p2p_connect <address> pbc` subsequently fails to create the *p2p-wlan0-0* interface and *wpa_supplicant* returns EBUSY error code -16 (Device or resource busy). Deleting the virtual interface (via `iw dev uap0 del`) restores the correct behaviour.

Basic workflow performed by the program for *pbc* (virtual push button):

- send `set config_methods virtual_push_button`
- (the WiFi name is not yet visible to the client)
- send `p2p_find`
- (the WiFi name is visible to the client, which can select a connection setup)
- read event `P2P-PROV-DISC-PBC-REQ <addr>, or P2P-GO-NEG-REQUEST <addr>`, or `P2P-DEVICE-FOUND`
- (register the address of the client, checks that <addr> is referred to a name within a white list and allows connection only in this case)
- send `p2p_connect <addr> pbc`
- read event `P2P-GROUP-STARTED <group>` and register the name of the group in order to allow deleting it on client disconnection
- (the client receives connection confirmation; event `AP-STA-CONNECTED` is logged)
- (the client disconnects)
- read event `AP-STA-DISCONNECTED <addr>`
- send `p2p_group_remove <group>`
- send `p2p_find`

This process also supports the fixed password method (instead of using *pbc*):
- send `set config_methods keypad`
- (the WiFi name is not yet visible to the client)
- send `p2p_find`
- (the WiFi name is visible to the client, which can select a connection setup)
- read event `P2P-PROV-DISC-PBC-REQ <addr>, or P2P-GO-NEG-REQUEST <addr>`, or `P2P-DEVICE-FOUND`
- (register the address of the client)
- send `p2p_connect <addr> <8-digit password> display`
- read event `P2P-GROUP-STARTED <group>` and register the name of the group in order to allow deleting it on client disconnection
- (the client receives connection confirmation; event `AP-STA-CONNECTED` is logged)
- (the client disconnects)
- read event `AP-STA-DISCONNECTED <addr>`
- send `p2p_group_remove <group>`
- send `p2p_find`

In both cases, if the `p2p_connect` fails (`FAIL` event), perform `interface` to list the already registered groups and delete them one by one with `p2p_group_remove`.

In all cases, run `p2p_find` every 20 seconds (but delays it while connecting, because any command just after a *p2p_connect* disables the connection setup). Also a `P2P-DEVICE-LOST` event produces a `p2p_find` command (as well as `AP-STA-DISCONNECTED <addr>` event).

Event *CTRL-EVENT-TERMINATING* terminates the program.

Notice that *pbc* method does not ask a password to the client, and so needs whitelisting. With fixed password method, an Android client will not save the password (it has to be inserted on every connection). Notice also that any password different from eight digits is not accepted by *wpa_supplicant*.

Even if the process handles `P2P-PROV-DISC-SHOW-PIN` event, related configuration is not fully tested yet.

_______________

__Notes__

_Running wpa_supplicant from the command line_

Standard distribution already include a wpa_supplicant service. Anyway for information the following allows running it from the command line:

```bash
sudo /sbin/wpa_supplicant -c/etc/wpa_supplicant/wpa_supplicant-wlan0.conf -Dnl80211,wext -iwlan0
```

_Compiling *hostapd* and *wpa_supplicant* on a Raspberry Pi_

Standard distribution already include updated wpa_supplicant processes. Anyway for information the following steps allow compiling the latest version and obtaining *wpa_supplicanté,  *wpa_cli*, *hostapd*, *hostapd_cli*.

```bash
git clone git://w1.fi/srv/git/hostap.git
cd hostap
cp wpa_supplicant/defconfig wpa_supplicant/.config
cd wpa_supplicant
sudo apt-get install -y libnl-genl-3-dev libnl-route-3-dev
sudo apt install build-essential libdbus-glib-1-dev libgirepository1.0-dev
make
#sudo make install
cd ../
cd hostapd
cp defconfig .config
echo "CONFIG_P2P_MANAGER=y" >> .config
echo "CONFIG_LIBNL3_ROUTE=y" >> .config
make
#sudo make install
```
