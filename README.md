__WiFi-Direct Connection Manager__

This basic program interfaces [wpa_supplicant](https://en.wikipedia.org/wiki/Wpa_supplicant) via [wpa_cli](https://jlk.fjfi.cvut.cz/arch/manpages/man/wpa_cli.8), running *wpa_cli* in background and piping [p2p commands](https://w1.fi/cgit/hostap/plain/wpa_supplicant/README-P2P) to it, while reading events, in order to fully automate the workflow of a P2P AP server based on *wpa_supplicant* that manages connections of a single P2P client in [WiFi Direct](https://en.wikipedia.org/wiki/Wi-Fi_Direct) mode.

Run with `python3 wifip2p_monitor.py`.

Tested with an Android client connecting a Raspberry Pi with WiFi Direct protocol.

Related configuration is in the program configuration section.

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

Basic workflow performed by the program for pbc (virtual push button):

- send `set config_methods virtual_push_button`
- (the WiFi name is not yet visible to the client)
- send `p2p_find`
- (the WiFi name is visible to the client, which can select a connection setup)
- read `P2P-PROV-DISC-PBC-REQ <addr> or P2P-GO-NEG-REQUEST <addr>`
- send `p2p_connect <addr> pbc`
- read `P2P-GROUP-STARTED <group>`
- (the client receives connection confirmation)
- (the client disconnects)
- read `AP-STA-DISCONNECTED <addr>`
- send `p2p_group_remove <group>`
- send `p2p_find`

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
