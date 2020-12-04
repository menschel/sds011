# file: sds011.py
# author: (C) Patrick Menschel  2018
# purpose: implement python3 interface to dust sensor Inovafitness SDS011
# https://cdn.sparkfun.com/assets/parts/1/2/2/7/5/Laser_Dust_Sensor_Control_Protocol_V1.3.pdf


import serial
# import time
import threading
from queue import Queue, Empty
import struct
import datetime

from collections import OrderedDict

from sds011.utils.sockethandler import sockethandler
from sds011.utils.databasehandler import databasehandler

MSG_HEAD = 0xAA
MSG_CMD_ID = 0xB4
MSG_TAIL = 0xAB
MSG_TYPE_MEASUREMENT = 0xC0
MSG_TYPE_CMD_RESP = 0xC5

MODE_OPTS = ["r", "w"]
CMD_SET_DATA_REPORTING = 2
DATA_REPORTING_OPTS = ["active", "query"]
CMD_QUERY_DATA = 4
CMD_SET_DEVICE_ID = 5
CMD_SLEEP_WORK = 6
SLEEP_OPTS = ["sleep", "work"]
CMD_WORKING_PERIOD = 8
CMD_FIRMWARE_Version = 7


# The protocol has some similarities with early register access protocols,
# - 0xB4 seems to be a flag byte to listen for a command next every listed command starts with 0xB4,
#   maybe it defines "register access"
# - The second data byte is the function selector
# - The third data byte is a control byte that selects read = 0/write = 1
# - The fourth data byte is an option selector
#
# - The last two bytes define the device id that is addressed by the message


def calc_checksum(msg):
    return sum(msg) & 0xFF


def is_msg_valid(msg):
    return (len(msg) > 0) and (msg[0] == MSG_HEAD) and (msg[-1] == MSG_TAIL) and (msg[-2] == calc_checksum(msg[2:-2]))


def concat_msg(data):
    if len(data) != 15:
        raise ValueError("Data length incorrect {0}".format(len(data)))
    msg = bytearray()
    msg.append(MSG_HEAD)
    msg.append(MSG_CMD_ID)
    msg.extend(data)
    msg.append(calc_checksum(data))
    msg.append(MSG_TAIL)
    #    assert(len(msg) == 19)
    return msg


def concat_cmd_msg(cmd, mode="r", options=None, device_id=None):
    if options is None:
        options = {}
    data = bytearray(15)
    data[0] = cmd
    if mode == "w":
        # write flag is 1, ignore if "r"
        data[1] = 1
    elif mode != "r":
        raise NotImplementedError("invalid mode {0}".format(mode))

    if cmd == CMD_SET_DATA_REPORTING:
        if options.get("mode_select") == "query":
            data[2] = 1

    if cmd == CMD_SET_DEVICE_ID:
        new_device_id = options.get("new_device_id")
        if new_device_id is not None and isinstance(new_device_id, int):
            data[-4:-2] = new_device_id.to_bytes(2, "big")

    if cmd == CMD_SLEEP_WORK:
        if options.get("mode_select") == "work":
            data[2] = 1

    if cmd == CMD_WORKING_PERIOD:
        rate = options.get("rate")
        if isinstance(rate, int):
            data[2] = rate

    if device_id is None:
        data[-2:] = (0xFF, 0xFF)
    else:
        data[-2:] = device_id.to_bytes(2, "big")
    return concat_msg(data)


class SDS011:

    def __init__(self, port, mode_select="active", rate=0, device_id=0xFFFF,
                 use_socket=False,
                 socket_port_number=9999,
                 use_database=False,
                 db3path="measurements.db3",
                 ):
        self.ser = serial.Serial(port=port,
                                 baudrate=9600,
                                 bytesize=serial.EIGHTBITS,
                                 parity=serial.PARITY_NONE,
                                 stopbits=serial.STOPBITS_ONE,
                                 timeout=1)
        self.mode_select = mode_select
        self.rate = rate
        self.device_id = device_id
        self.firmware = "unknown"
        self.sleep_work_state = None
        self.data_reporting_mode = None
        self.server_socket = None
        self.database_handler = None
        self.mutex = threading.Lock()
        self.request_mutex = threading.Lock()
        self.rx_measurement_queue = Queue()
        self.rx_cmd_resp_queue = Queue()
        self.rx_queue_handler = threading.Thread(target=self.handle_rx)
        self.rx_queue_handler.setDaemon(True)
        self.rx_queue_handler.start()
        self.probe()
        if use_socket is True:
            self.server_socket = sockethandler(port=socket_port_number)
        if use_database is True:
            self.database_handler = databasehandler(db3path=db3path)

    def probe(self):
        firmware_version_data = self.get_firmware_version()
        sleep_work_data = self.get_sleep_work()
        data_reporting_data = self.get_data_reporting()
        working_period_data = self.get_working_period()
        with self.mutex:
            self.device_id = firmware_version_data.get("device_id")
            self.firmware = firmware_version_data.get("firmware_date")
            self.sleep_work_state = sleep_work_data.get("mode_select")
            self.data_reporting_mode = data_reporting_data.get("mode_select")
            self.rate = working_period_data.get("rate")
        return

    def get_sensor_data(self):
        with self.mutex:
            data = {"device_id": self.device_id,
                    "firmware_date": self.firmware,
                    "sleep_work_state": self.sleep_work_state,
                    "data_reporting_mode": self.data_reporting_mode,
                    "rate": self.rate,
                    }
        return data

    def setup(self, mode_select, rate):
        with self.mutex:
            self.mode_select = mode_select
            self.rate = rate
        self.set_data_reporting(mode_select=self.mode_select)
        self.set_working_period(rate=self.rate)
        return

    def sleep(self):
        return self.set_sleep_work(mode_select="sleep")

    def wakeup(self):
        return self.set_sleep_work(mode_select="work")

    def set_data_reporting(self, mode_select="query"):
        cmd = CMD_SET_DATA_REPORTING

        if mode_select not in DATA_REPORTING_OPTS:
            raise ValueError("invalid mode {0}, use {1}".format(mode_select, " or ".join(DATA_REPORTING_OPTS)))
        return self.request(cmd, mode="w", options={"mode_select": mode_select})

    def get_data_reporting(self):
        cmd = CMD_SET_DATA_REPORTING
        return self.request(cmd)

    def query_data(self):
        cmd = CMD_QUERY_DATA
        return self.request(cmd)

    def set_device_id(self, new_device_id):
        cmd = CMD_SET_DEVICE_ID
        resp = self.request(cmd, options={"new_device_id": new_device_id})
        if resp.get("device_id") != new_device_id:
            raise NotImplementedError("New Dev Id not set by device")
        else:
            with self.mutex:
                self.device_id = new_device_id
        return resp

    def set_sleep_work(self, mode_select="sleep"):
        cmd = CMD_SLEEP_WORK
        if mode_select not in SLEEP_OPTS:
            raise ValueError("invalid mode {0}, use {1}".format(mode_select, " or ".join(SLEEP_OPTS)))
        return self.request(cmd, mode="w", options={"mode_select": mode_select})

    def get_sleep_work(self):
        cmd = CMD_SLEEP_WORK
        return self.request(cmd)

    def get_sleep_work_status(self):
        return self.get_sleep_work().get("mode_select")

    def set_working_period(self, rate=0):
        # rate in minutes, 0 is continuous
        cmd = CMD_WORKING_PERIOD
        if rate not in range(31):
            raise ValueError("Rate {0} is out of permitted range 0-30".format(rate))
        return self.request(cmd, mode="w", options={"rate": rate})

    def get_working_period(self):
        cmd = CMD_WORKING_PERIOD
        return self.request(cmd)

    def get_firmware_version(self):
        cmd = CMD_FIRMWARE_Version
        return self.request(cmd)

    def request(self, cmd, mode="r", options=None):
        if options is None:
            options = {}
        with self.request_mutex:
            msg = concat_cmd_msg(cmd=cmd, mode=mode, options=options, device_id=self.device_id)
            self.ser.write(msg)        
            resp = self.rx_cmd_resp_queue.get(timeout=10)
            resp_cmd = resp.get("msg_cmd")
            if resp_cmd != cmd:
                raise NotImplementedError("waited for cmd {0} but got response to {1}".format(cmd, resp_cmd))
        return resp

    def handle_rx(self):
        self.ser.flush()
        while True:
            msg = bytearray()
            data = self.ser.read(1)
            if len(data) > 0:
                msg.extend(data)
                msg.extend(self.ser.read(self.ser.inWaiting()))

                if is_msg_valid(msg):
                    msg_type = msg[1]
                    timestamp = datetime.datetime.now()
                    device_id = struct.unpack(">H", msg[-4:-2])[0]
                    if msg_type == MSG_TYPE_MEASUREMENT:
                        # data msg
                        pm2_5, pm10 = (x / 10 for x in struct.unpack("<HH", msg[2:6]))
                        item = OrderedDict([("timestamp", timestamp),
                                            ("pm2.5", pm2_5),
                                            ("pm10", pm10),
                                            ("device_id", device_id),
                                            ])
                        if self.server_socket is not None:
                            self.server_socket.queue_tx_message(item=item)
                        if self.database_handler is not None:
                            self.database_handler.add_measurement(measurement=item)

                        self.rx_measurement_queue.put(item=item)

                    elif msg_type == MSG_TYPE_CMD_RESP:
                        # cmd response
                        msg_cmd = msg[2]
                        item = OrderedDict([("timestamp", timestamp),
                                            ("msg_cmd", msg_cmd),
                                            ("device_id", device_id),
                                            ])

                        if msg_cmd == CMD_SET_DATA_REPORTING:
                            mode = MODE_OPTS[msg[3]]
                            mode_select = DATA_REPORTING_OPTS[msg[4]]
                            item.update(OrderedDict([("mode", mode),
                                                     ("mode_select", mode_select),
                                                     ]))

                        elif msg_cmd == CMD_QUERY_DATA:
                            pass  # do nothing as this produces a measurement message

                        elif msg_cmd == CMD_SET_DEVICE_ID:
                            pass  # do nothing as the new device id is the reported device id

                        elif msg_cmd == CMD_SLEEP_WORK:
                            mode = MODE_OPTS[msg[3]]
                            mode_select = SLEEP_OPTS[msg[4]]
                            item.update(OrderedDict([("mode", mode),
                                                     ("mode_select", mode_select),
                                                     ]))

                        elif msg_cmd == CMD_WORKING_PERIOD:
                            mode = MODE_OPTS[msg[3]]
                            rate = msg[4]
                            item.update(OrderedDict([("mode", mode),
                                                     ("rate", rate),
                                                     ]))

                        elif msg_cmd == CMD_FIRMWARE_Version:
                            year, month, day = msg[3:6]
                            item.update(OrderedDict([("firmware_date", datetime.date(year + 2000, month, day)),
                                                     ]))
                        self.rx_cmd_resp_queue.put(item=item)  # split by command type

    def read_measurement(self,timeout=None):
        if timeout is not None:
            try:
                meas = self.rx_measurement_queue.get(timeout=timeout)
            except Empty:
                return None
            else:
                return meas
        else:
            return self.rx_measurement_queue.get()

    def __str__(self):
        msg = "SDS011 Device ID: {0:04X}\nFirmware Date: {1}\nSleepWorkState: {2}\nDataReportingMode {3}".format(
            self.device_id,
            self.firmware,
            self.sleep_work_state,
            self.data_reporting_mode)
        return msg

    def __del__(self):
        if self.server_socket is not None:
            self.server_socket.__del__()
