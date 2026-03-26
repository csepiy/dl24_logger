### Atorch DL24/BW150 logger ###

Tested environment (HW + SW):
 - Raspberry Pi 4B + Raspberry Pi OS Lite (64-bit) - Debian Trixie 2025-12-04
 - Raspberry Pi Zero 2 W + Raspberry Pi OS Lite (64-bit) - Debian Trixie 2025-12-04
 - DL24 + firmware version 1.1.0
 - BW150 + firmware version 1.1.0

Install:
```
$ sudo apt-get update
$ sudo apt-get -y upgrade
$ sudo apt-get -y install git
$ git clone https://github.com/csepiy/dl24_logger
$ cd dl24_logger
$ ./install_environment
```

Get DL24/BW150 bluetooth device address:
```
$ bluetoothctl
bluetoothctl]> scan on
...
[NEW] Device <BD_ADDR> DL24_SPP (BW150_SPP)
...
bluetoothctl]> quit
```

If bluetooth not working, check rfkill:
```
$ rfkill list
0: hci0: Bluetooth
        Soft blocked: yes
        Hard blocked: no
1: phy0: Wireless LAN
        Soft blocked: no
        Hard blocked: no

$ sudo rfkill unblock all
```

Optionally connect DS18B20 1-wire temperature sensor to Raspberry Pi to measure environment temperature:
- black: GND (pin 6)
- red: 3.3V (pin 1)
- yellow: GPIO 4 (pin 7)

Enable 1-wire interface:
```
$ sudo raspi-config
  => 3 Interface Options
    => I7 1-Wire
      => Enable
  => Finish
  => Reboot
```

Get DS18B20 device address:
```
$ ls /sys/bus/w1/devices/
28-<address> w1_bus_master1
```

Run:
```
$ ./dl24_logger.sh <BD_ADDR> [-h]
```

Use screen manager for long runs:
```
$ screen
$ ./dl24_logger.sh ...
<CTRL-A + D> (Detach)
```
