### Atorch DL24 logger ###

Environment hw&sw:
 - Raspberry Pi 4B, Raspberry Pi OS Lite (64-bit) - Debian Trixie 2025-12-04
 - DL24, firmware version 1.1.0

Install:
```
$ sudo apt-get update
$ sudo apt-get install git
$ git clone https://github.com/csepiy/dl24_logger
$ cd dl24_logger
$ ./install_environment
```

Get DL24 bluetooth device address:
```
$ bluetoothctl
bluetoothctl]> scan on
...
[NEW] Device <BD_ADDR> DL24_SPP
...
bluetoothctl]> quit
```

Run:
```
$ ./dl24_logger.sh <BD_ADDR> [-h]
```
