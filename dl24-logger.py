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

class dl24:
    def __init__(self):
        self.capacity_prev = -1
        self.first_json_line = True

    def get_int32(self, data, pos):
        return (data[pos] << 24) + (data[pos + 1] << 16) + (data[pos + 2] << 8) + data[pos + 3]

    def get_int24(self, data, pos):
        return (data[pos] << 16) + (data[pos + 1] << 8) + data[pos + 2]

    def get_int16(self, data, pos):
        return (data[pos] << 8) + data[pos + 1]

    def get_int8(self, data, pos):
        return data[pos]

    def get_voltage(self, data):
        return self.get_int24(data, POSITION_VOLTAGE) / 10  # V

    def get_current(self, data):
        return self.get_int24(data, POSITION_CURRENT)  # mA

    def get_capacity(self, data):
        return self.get_int24(data, POSITION_CAPACITY) * 10  # mAh

    def get_temp(self, data):
        return self.get_int16(data, POSITION_MOSFET_TEMP)  # C/F

    def get_power(self, voltage, current):
        return voltage * current / 1000  # W

    def get_resistance(self, voltage, current):
        return voltage / (current / 1000)  # Ohm

    def calc_crc(self, data):
        crc = 0
        for i in range(0, len(data)):
            crc += data[i]

        return (crc ^ 0x44) & 0xFF

    def send_command(self, serial_device, command):
        message = [0xFF, 0x55, 0x11, 0x02, command, 0x00, 0x00, 0x00, 0x00]
        byte_array = bytearray(message)
        crc = self.calc_crc(message[2:])
        byte_array += bytearray([crc])
        serial_device.write(byte_array)
        self.print_bin(byte_array, command)
        time.sleep(1)

    def print_bin(self, data, command = 0):
        for i in data:
            print(f'0x{i:02X}' + ' ', end='')
        if command == COMMAND_OK:
            print("COMMAND: OK")
        else:
            print('')

    def write_file(self, filename, mode, data):
        with open(filename, mode) as data_file:
            data_file.write(data)

    def print_json(self, timestamp, voltage, current, capacity, power, temp, resistance, args, filename):
        if args.fformat == "json":
            if self.first_json_line is False:
                # write comma to the end of the previous line
                data_json = ",\n"
            else:
                self.first_json_line = False
                data_json = ""

        data_json += f'  {{\"timestamp\": {timestamp}, \"voltage\": {voltage}, \"current\": {current}, \"capacity\": {capacity}, \"power\": {power:.2f}, \"temp\": {temp}'
        if resistance != -1:
            data_json += f', \"resistance\": {resistance:.1f}}}'
        else:
            data_json += '}'
        if args.sformat == "json":
            print(data_json, end='')
        if args.fformat == "json":
            self.write_file(filename, "a", data_json)

    def print_tab(self, timestamp, voltage, current, capacity, power, temp, resistance, args, filename):
        data_tab = f'[{timestamp}, {voltage}, {current}, {capacity}, {power:.2f}, {temp}'
        if resistance != -1:
            data_tab = data_tab  + f', {resistance:.1f}]\n'
        else:
            data_tab = data_tab  + ']\n'
        if args.sformat == "tab":
            print(data_tab, end='')
        if args.fformat == "tab":
            self.write_file(filename, "a", data_tab)

    def print_data(self, args, filename, data):
        timestamp = int(time.time())
        voltage = self.get_voltage(data)
        current = self.get_current(data)
        capacity = self.get_capacity(data)
        power = self.get_power(voltage, current)
        temp = self.get_temp(data)
        if current != 0:
            resistance = self.get_resistance(voltage, current)
        else:
            resistance = -1

        if args.capdiff and capacity == self.capacity_prev:
            return

        self.capacity_prev = capacity
        if args.sformat == "json" or args.fformat == "json":
            self.print_json(timestamp, voltage, current, capacity, power, temp, resistance, args, filename)
        if args.sformat == "tab" or args.fformat == "tab":
            self.print_tab(timestamp, voltage, current, capacity, power, temp, resistance, args, filename)
    
def main():
    parser = argparse.ArgumentParser(description='DL24 data logger')
    parser.add_argument('--onoff',  action='store_true',             help='Switch on or off DL24 output.')
    parser.add_argument('--sformat', choices=['bin', 'json', 'tab'], help='Set stdout data format.')
    parser.add_argument('--capdiff', action='store_true',            help='Show data when capacity changes.')

    file_group = parser.add_argument_group('File options')
    file_group.add_argument('--fformat', choices=['json', 'tab'],    help='Set file data format.')
    file_group.add_argument('--filename',                            help='Save data to file.')

    args = parser.parse_args()

    if args.filename and args.fformat is None:
        parser.error("--filename requires --fformat.")
    if args.fformat and args.filename is None:
        parser.error("--fformat requires --filename.")

    dl24obj = dl24()

    try:
        serial_device = serial.Serial(SERIAL_DEVICE, BAUD_RATE, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
    except Exception as exc:
        print('Serial error:', exc)
        sys.exit(1)

    if serial_device.isOpen():

        if args.onoff:
            dl24obj.send_command(serial_device, COMMAND_OK)

        # beginning of the file
        if args.filename:
            now = time.strftime("%y%m%d%H%M%S")
            filename = args.filename + "_" + now
            data = "[\n"
            if args.fformat == "json":
                filename += ".json"
            if args.sformat == "json":
                print(data, end='')
            if args.fformat == "tab":
                filename += ".tab"
                data = ""
            dl24obj.write_file(filename, "w", data)

        if args.sformat or args.fformat:
            try:
                while True:
                    data = serial_device.read(MESSAGE_SIZE)

                    if args.sformat == "bin":
                        dl24obj.print_bin(data)

                    if args.sformat == "json" or args.sformat == "tab" or args.fformat == "json" or args.fformat == "tab":
                        if data[0] == 0xFF and data[1] == 0x55 and data[2] == 0x01 and data[3] == 0x02:
                            dl24obj.print_data(args, filename, data)

            except KeyboardInterrupt:
                print(' exit...')

        # end of the file
        data = "\n]\n"
        if args.fformat == "json":
            dl24obj.write_file(filename, "a", data)
        if args.sformat == "json":
            print(data, end='')

        serial_device.close()

if __name__=="__main__":
    main()
