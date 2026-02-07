#!/usr/bin/python3

import sys
import serial # pyserial
import time
import os
import argparse

SERIAL_DEVICE = "/dev/rfcomm0"
ONE_WIRE_DEVICE = "/sys/bus/w1/devices"

BAUD_RATE = 9600
MESSAGE_SIZE = 36
NA = -9999

POSITION_VOLTAGE     = 0x04
POSITION_CURRENT     = 0x07
POSITION_CAPACITY    = 0x0A
POSITION_MOSFET_TEMP = 0x18

COMMAND_SETUP = 0x31
COMMAND_OK    = 0x32
COMMAND_PLUS  = 0x33
COMMAND_MINUS = 0x34

class ds18b20:
    def __init__(self, device, offset):
        self.device_addr = device
        self.offset = offset 

    def read_temp(self):
        try:
            with open(os.path.join(ONE_WIRE_DEVICE, self.device_addr, "w1_slave"), 'r') as raw_temp:
                lines = raw_temp.readlines()
        except FileNotFoundError:
            return NA

        if lines[0].strip()[-3:] != 'YES':
            return NA

        temp_pos = lines[1].find('t=')
        if temp_pos != -1:
            temp_str = lines[1][temp_pos + 2:]
            temp = float(temp_str) / 1000.0  # C
            return temp + self.offset
        return NA

class dl24:
    def __init__(self):
        self.capacity_prev = -1
        self.first_json_line = True
        self.curr_state = "started"
        self.avg_ext_temp_sum = 0
        self.avg_ext_temp_cnt = 0

    def get_int32(self, data, pos):
        return (data[pos] << 24) + (data[pos + 1] << 16) + (data[pos + 2] << 8) + data[pos + 3]

    def get_int24(self, data, pos):
        return (data[pos] << 16) + (data[pos + 1] << 8) + data[pos + 2]

    def get_int16(self, data, pos):
        return (data[pos] << 8) + data[pos + 1]

    def get_int8(self, data, pos):
        return data[pos]

    # readable values from dl24
    def get_voltage(self, data):
        return self.get_int24(data, POSITION_VOLTAGE) / 10  # V

    def get_current(self, data):
        return self.get_int24(data, POSITION_CURRENT)  # mA

    def get_capacity(self, data):
        return self.get_int24(data, POSITION_CAPACITY) * 10  # mAh

    def get_temp(self, data):
        return self.get_int16(data, POSITION_MOSFET_TEMP)  # C/F

    # calculated values
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
        self.print_cmd_header()
        self.print_bin(byte_array, command)
        time.sleep(1)

    def print_cmd_header(self):
        print('+------HEADER-------+CMD-+-------------------+CRC-+')

    def print_data_header(self):
        print('+------HEADER-------+---VOLTAGE----+---CURRENT----+---CAPACITY---+------------------------------------------------------+MOS-TEMP-+-------------------------------------------------+')

    def print_bin(self, data, command = 0):
        # header
        print(f'|0x{data[0]:02X} 0x{data[1]:02X} 0x{data[2]:02X} 0x{data[3]:02X}|', end='')
        if command == 0: # data
            # voltage, current, capacity
            print(f'0x{data[4]:02X} 0x{data[5]:02X} 0x{data[6]:02X}|0x{data[7]:02X} 0x{data[8]:02X} 0x{data[9]:02X}|0x{data[10]:02X} 0x{data[11]:02X} 0x{data[12]:02X}|', end='')
            print(f'0x{data[13]:02X} 0x{data[14]:02X} 0x{data[15]:02X} 0x{data[16]:02X} 0x{data[17]:02X} 0x{data[18]:02X} 0x{data[19]:02X} 0x{data[20]:02X} 0x{data[21]:02X} 0x{data[22]:02X} 0x{data[23]:02X}|', end='')
            # temp
            print(f'0x{data[24]:02X} 0x{data[25]:02X}|0x{data[26]:02X} 0x{data[27]:02X} 0x{data[28]:02X} 0x{data[29]:02X} 0x{data[30]:02X} 0x{data[31]:02X} 0x{data[32]:02X} 0x{data[33]:02X} 0x{data[34]:02X} 0x{data[35]:02X}|')
        else: # commands
            print(f'0x{data[4]:02X}|0x{data[5]:02X} 0x{data[6]:02X} 0x{data[7]:02X} 0x{data[8]:02X}|0x{data[9]:02X}| ', end='')
            if command == COMMAND_OK:
                print("COMMAND: OK")

    def write_file(self, filename, mode, data):
        with open(filename, mode) as data_file:
            data_file.write(data)

    def print_json(self, timestamp, voltage, current, capacity, power, temp, ext_temp, resistance, args, filename):
        if self.first_json_line is False:
            # write comma to the end of the previous line
            data_json = ",\n"
        else:
            self.first_json_line = False
            data_json = ""

        data_json += f'{{\"timestamp\": {timestamp}, \"voltage\": {voltage}, \"current\": {current}, \"capacity\": {capacity}, \"power\": {power:.2f}, \"mos_temp\": {temp}'

        if ext_temp != NA:
            data_json += f', \"ext_temp\": {ext_temp:.1f}'

        if resistance != NA:
            data_json += f', \"resistance\": {resistance:.1f}'

        data_json += '}'

        if args.sformat == "json":
            print(data_json, end='')
        if args.filename:
            self.write_file(filename, "a", data_json)

    def print_data(self, args, filename, data):
        timestamp = int(time.time())
        voltage = self.get_voltage(data)
        current = self.get_current(data)
        capacity = self.get_capacity(data)
        power = self.get_power(voltage, current)
        temp = self.get_temp(data)
        if current != 0:
            resistance = self.get_resistance(voltage, current)
            if self.curr_state == "started":
                self.curr_state = "working"
        else:
            if self.curr_state == "working":
                self.curr_state = "stopped"
            resistance = NA

        if args.autostop == False or (args.autostop == True and self.curr_state != "stopped"):
            if args.cdiff and capacity == self.capacity_prev:
                return

        if args.ds18b20:
            ds18b20obj = ds18b20('28-' + args.ds18b20, args.offset)
            ext_temp = ds18b20obj.read_temp()
            if ext_temp != NA:
                self.avg_ext_temp_sum += ext_temp
                self.avg_ext_temp_cnt += 1
        else:
            ext_temp = NA

        self.capacity_prev = capacity
        if args.filename or args.sformat == "json":
            self.print_json(timestamp, voltage, current, capacity, power, temp, ext_temp, resistance, args, filename)
        if args.sformat == "bin":
            self.print_bin(data)
    
def main():
    parser = argparse.ArgumentParser(description='DL24 data logger')
    parser.add_argument('--onoff',    action='store_true',     help='Switch on or off DL24 output.')
    parser.add_argument('--sformat',  choices=['bin', 'json'], help='Set stdout data format.')
    parser.add_argument('--cdiff',    action='store_true',     help='Show data when capacity changes.')
    parser.add_argument('--autostop', action='store_true',     help='Stop when current changes to zero.')
    parser.add_argument('--filename',                          help='Save data to json file.')
    parser.add_argument('--ds18b20',                           help='Set device address (28-<addr>) to read temperature from DS18B20 temperature sensor.')
    parser.add_argument('--offset', type=float, default=0.0,   help='Set DS18B20 temperature offset.')
    args = parser.parse_args()

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
            filename = args.filename + "_" + now + ".json"
            data = "{\n\"data\": [\n"
            dl24obj.write_file(filename, "w", data)
        else:
            filename = ""

        if args.sformat == "bin":
            dl24obj.print_data_header()

        if args.sformat or args.filename:
            try:
                while True:
                    data = serial_device.read(MESSAGE_SIZE)
                    if data[0] == 0xFF and data[1] == 0x55 and data[2] == 0x01 and data[3] == 0x02:
                        dl24obj.print_data(args, filename, data)
                        if args.autostop and dl24obj.curr_state == "stopped":
                             break

            except KeyboardInterrupt:
                print(' CTRL-C exit...')
            except serial.serialutil.SerialException:
                print(' Serial error, exit...')

        # end of the file
        if args.filename:
            if dl24obj.avg_ext_temp_sum != 0:
                avg_temp = dl24obj.avg_ext_temp_sum / dl24obj.avg_ext_temp_cnt
                data = f"\n], \"average_temp\": {avg_temp:.1f}\n}}\n"
            else:
                data = "\n]\n}\n"

            dl24obj.write_file(filename, "a", data)

        serial_device.close()

if __name__=="__main__":
    main()
