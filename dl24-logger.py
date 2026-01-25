#!/usr/bin/python3

import sys
import serial # pyserial
import time
import argparse

SERIAL_DEVICE = "/dev/rfcomm0"
BAUD_RATE = 9600
MESSAGE_SIZE = 36

POSITION_VOLTAGE     = 0x04
POSITION_CURRENT     = 0x07
POSITION_CAPACITY    = 0x0A
POSITION_MOSFET_TEMP = 0x18

COMMAND_SETUP = 0x31
COMMAND_OK    = 0x32
COMMAND_PLUS  = 0x33
COMMAND_MINUS = 0x34

def get_int32(data, pos):
  return (data[pos] << 24) + (data[pos + 1] << 16) + (data[pos + 2] << 8) + data[pos + 3]

def get_int24(data, pos):
  return (data[pos] << 16) + (data[pos + 1] << 8) + data[pos + 2]

def get_int16(data, pos):
  return (data[pos] << 8) + data[pos + 1]

def get_int8(data, pos):
  return data[pos]

def get_voltage(data):
    return get_int24(data, POSITION_VOLTAGE) / 10  # V

def get_current(data):
    return get_int24(data, POSITION_CURRENT)  # mA

def get_capacity(data):
    return get_int24(data, POSITION_CAPACITY) * 10  # mAh

def get_temp(data):
    return get_int16(data, POSITION_MOSFET_TEMP)  # C/F

def get_power(voltage, current):
    return voltage * current / 1000  # W

def get_resistance(voltage, current):
    return voltage / (current / 1000)  # Ohm

def calc_crc(data):
    crc = 0
    for i in range(0, len(data)):
        crc += data[i]

    return (crc ^ 0x44) & 0xFF

def send_command(serial_device, command):
    message = [0xFF, 0x55, 0x11, 0x02, command, 0x00, 0x00, 0x00, 0x00]
    byte_array = bytearray(message)
    byte_array += bytearray([calc_crc(message[2:])])
    serial_device.write(byte_array)
    print_bin(byte_array)
    time.sleep(1)

def print_bin(data):
    for i in data:
        print(f'0x{i:02X}' + ' ', end='')
    print('')

def print_json(voltage, current, capacity, power, temp, resistance):
    data_json = f'{{\"voltage\": {voltage}, \"current\": {current}, \"capacity\": {capacity}, \"power\": {power:.2f}, \"temp\": {temp}'
    if resistance != -1:
        data_json = data_json + f', \"resistance\": {resistance:.1f}}}'
    else:
        data_json = data_json + '}'
    print(data_json)

def print_tab(voltage, current, capacity, power, temp, resistance):
    data_tab  = f'[{voltage}, {current}, {capacity}, {power:.2f}, {temp}'
    if resistance != -1:
        data_tab  = data_tab  + f', {resistance:.1f}]'
    else:
        data_tab  = data_tab  + ']'
    print(data_tab)

def print_data(args, data):
    voltage=get_voltage(data)
    current=get_current(data)
    capacity=get_capacity(data)
    power=get_power(voltage, current)
    temp=get_temp(data)
    if current != 0:
        resistance = get_resistance(voltage, current)
    else:
        resistance = -1

    if args.json:
        print_json(voltage, current, capacity, power, temp, resistance)
    if args.tab:
        print_tab(voltage, current, capacity, power, temp, resistance)
    
def main():
    parser = argparse.ArgumentParser(description='DL24 data logger')
    parser.add_argument('--onoff', action='store_true', help='Switch on or off DL24 output.')
    parser.add_argument('--json',  action='store_true', help='Print data in json format.')
    parser.add_argument('--tab',   action='store_true', help='Print data in tabular format.')
    parser.add_argument('--bin',   action='store_true', help='Print binary data.')

    args = parser.parse_args()

    try:
        serial_device = serial.Serial(SERIAL_DEVICE, BAUD_RATE, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
    except Exception as exc:
        print('Serial error:', exc)
        sys.exit(1)

    if serial_device.isOpen():

        if args.onoff:
            send_command(serial_device, COMMAND_OK)

        if args.bin or args.json or args.tab:
            try:
                while True:
                    data = serial_device.read(MESSAGE_SIZE)

                    if args.bin:
                        print_bin(data)

                    if args.json or args.tab:
                        if data[0]==0xFF and data[1]==0x55 and data[2]==0x01 and data[3]==0x02:
                            print_data(args, data)

            except KeyboardInterrupt:
                print(' exit...')

        serial_device.close()

if __name__=="__main__":
    main()
