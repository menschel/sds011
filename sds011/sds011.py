#file: sds011.py
#author: (C) Patrick Menschel  2018
#purpose: implement python3 interface to dust sensor inovafitness SDS011
#https://cdn.sparkfun.com/assets/parts/1/2/2/7/5/Laser_Dust_Sensor_Control_Protocol_V1.3.pdf


import serial
#import time
import threading
from queue import Queue#,Empty
import struct
import datetime

from collections import OrderedDict

from sds011.sockethandler import sockethandler
from sds011.databasehandler import databasehandler

MSG_HEAD = 0xAA
MSG_CMD_ID = 0xB4
MSG_TAIL = 0xAB
MSG_TYPE_MEASUREMENT = 0xC0
MSG_TYPE_CMD_RESP = 0xC5

MODE_OPTS = ["r","w"]
CMD_SET_DATA_REPORTING = 2
DATA_REPORTING_OPTS = ["active","query"]
CMD_QUERY_DATA = 4
CMD_SET_DEVICE_ID = 5
CMD_SLEEP_WORK = 6
SLEEP_OPTS = ["sleep","work"]
CMD_WORKING_PERIOD = 8
CMD_FIRMWARE_Version = 7


#The protocol has some similarities with early register access protocols,
# - 0xB4 seems to be a flag byte to listen for a command next every listed command starts with 0xB4, maybe it defines "register access"
# - The second data byte is the function selector 
# - The third data byte is a control byte that selects read = 0/write = 1
# - The fourth data byte is an option selector
#
# - The last two bytes define the device id that is addressed by the message


def calc_checksum(msg):
    return sum(msg) & 0xFF

def is_msg_valid(msg):
    return (len(msg)>0) and (msg[0] == MSG_HEAD) and (msg[-1] == MSG_TAIL) and (msg[-2] == calc_checksum(msg[2:-2]))

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


def concat_cmd_msg(cmd,mode="r",options={},devid=None):
    data = bytearray(15)
    data[0] = cmd
    if mode == "w":
        #write flag is 1, ignore if "r"
        data[1] = 1
    elif mode != "r":
        raise NotImplementedError("invalid mode {0}".format(mode))
    
    if cmd == CMD_SET_DATA_REPORTING:
        if options.get("modesel") == "query":
            data[2] = 1
            
    if cmd == CMD_SET_DEVICE_ID:
        new_devid = options.get("devid")
        if new_devid is not None and isinstance(new_devid,int):
            data[-4:-2] = new_devid.to_bytes(2,"big")
            
    if cmd == CMD_SLEEP_WORK:
        if options.get("modesel") == "work":
            data[2] = 1
    
    if cmd == CMD_WORKING_PERIOD:
        rate = options.get("rate")
        if isinstance(rate,int):
            data[2] = rate
    
    if devid is None:
        data[-2:] = (0xFF,0xFF)
    else:
        data[-2:] = devid.to_bytes(2,"big")
    return concat_msg(data)


class SDS011():
    
    
    def __init__(self,port,modesel="active",rate=0,devid=0xFFFF,
                use_socket=False,
                socket_portnum=9999,
                use_database=False,
                db3path="measurements.db3",
                 ):
        self.ser = serial.Serial(port=port,
                                 baudrate=9600,
                                 bytesize=serial.EIGHTBITS,
                                 parity=serial.PARITY_NONE,
                                 stopbits=serial.STOPBITS_ONE,
                                 timeout=1)
        self.rxhandler = None
#         if devid is None:
#             self.devid = 0xFFFF
        self.modesel = None
        self.rate = None 
        self.devid = devid
        self.firmware = "unknown"
        self.sleepworkstate = None
        self.datareportingmode = None
        self.serversocket = None
        self.databasehandler = None
        self.mutex = threading.Lock()
        self.rx_measurement_queue = Queue()
        self.rx_cmd_resp_queue = Queue()
        self.rx_queue_handler = threading.Thread(target = self.handle_rx)
        self.rx_queue_handler.setDaemon(True)
        self.rx_queue_handler.start()
        self.probe()
        if use_socket is True:
            self.serversocket = sockethandler(port=socket_portnum)
        if use_database is True:
            self.databasehandler = databasehandler(db3path=db3path)
        
    
    def probe(self):
        fwdata = self.get_firmware_version()
        sldata = self.get_sleep_work()
        drdata = self.get_data_reporting() 
        wpdata = self.get_working_period()
        with self.mutex:
            self.devid = fwdata.get("devid")
            self.firmware = fwdata.get("firmware_date")
            self.sleepworkstate = sldata.get("modesel")
            self.datareportingmode = drdata.get("modesel")
            self.rate = wpdata.get("rate")
        return

    def get_sensor_data(self):
        with self.mutex:
            data = {"devid":self.devid,
                    "firmware_date":self.firmware,
                    "sleepworkstate":self.sleepworkstate,
                    "datareportingmode":self.datareportingmode,
                    "rate":self.rate,
                    }
        return data
        
        
    def setup(self,modesel,rate):
        with self.mutex:
            self.modesel = modesel
            self.rate = rate 
        self.set_data_reporting(modesel=self.modesel)
        self.set_working_period(rate=self.rate)
        return
    
    def sleep(self):
        return self.set_sleep_work(modesel="sleep")
    
    def wakeup(self):
        return self.set_sleep_work(modesel="work")
    
    def set_data_reporting(self,modesel="query"):
        cmd = CMD_SET_DATA_REPORTING
        
        if modesel not in DATA_REPORTING_OPTS:
            raise ValueError("invalid mode {0}, use {1}".format(modesel," or ".join(DATA_REPORTING_OPTS)))
        return self.request(cmd, mode="w", options={"modesel":modesel})

    def get_data_reporting(self):
        cmd = CMD_SET_DATA_REPORTING
        return self.request(cmd)
    
    def query_data(self):
        cmd = CMD_QUERY_DATA
        return self.request(cmd)
    
    def set_devid(self,new_devid):
        cmd = CMD_SET_DEVICE_ID
        resp = self.request(cmd, options={"devid":new_devid})
        if resp.get("devid") != new_devid:
            raise NotImplementedError("New Dev Id not set by device")
        with self.mutex:
            self.devid = new_devid
        return resp
        
    
    def set_sleep_work(self,modesel="sleep"):
        cmd = CMD_SLEEP_WORK
        if modesel not in SLEEP_OPTS:
            raise ValueError("invalid mode {0}, use {1}".format(modesel," or ".join(SLEEP_OPTS)))
        return self.request(cmd, mode="w", options={"modesel":modesel})
    
    def get_sleep_work(self):
        cmd = CMD_SLEEP_WORK
        return self.request(cmd)
    
    def set_working_period(self,rate=0):
        #rate in minutes, 0 is continous
        cmd = CMD_WORKING_PERIOD
        if rate not in range(31):
            raise ValueError("Rate {0} is out of premitted range 0-30".format(rate)) 
        return self.request(cmd,mode="w", options={"rate":rate})
    
    def get_working_period(self):
        cmd = CMD_WORKING_PERIOD
        return self.request(cmd)
    
    def get_firmware_version(self):
        cmd = CMD_FIRMWARE_Version
        return self.request(cmd)
        
    def request(self,cmd,mode="r",options={}):
        msg = concat_cmd_msg(cmd=cmd, mode=mode, options=options, devid=self.devid)
        self.ser.write(msg)
        resp = self.rx_cmd_resp_queue.get(timeout=10)
        resp_cmd = resp.get("msg_cmd")
        if resp_cmd != cmd:
            raise NotImplementedError("waited for cmd {0} but got response to {1}".format(cmd,resp_cmd))
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
                    devid = struct.unpack(">H",msg[-4:-2])[0]
                    if msg_type == MSG_TYPE_MEASUREMENT:
                        #data msg
                        pm2_5,pm10 = (x/10 for x in struct.unpack("<HH",msg[2:6]))
                        item = OrderedDict([("timestamp",timestamp),
                                            ("pm2.5",pm2_5),
                                            ("pm10",pm10),
                                            ("devid",devid),
                                            ])
                        if self.serversocket is not None:
                            self.serversocket.queue_tx_message(item=item)
                        if self.databasehandler is not None:
                            self.databasehandler.add_measurement(measurement=item)

                        self.rx_measurement_queue.put(item=item)
                        
                    elif msg_type == MSG_TYPE_CMD_RESP:
                        #cmd response
                        item = {}
                        msg_cmd = msg[2]
                        item = OrderedDict([("timestamp",timestamp),
                                            ("msg_cmd",msg_cmd),
                                            ("devid",devid),
                                            ])
                                
                        if msg_cmd == CMD_SET_DATA_REPORTING:
                            mode = MODE_OPTS[msg[3]]
                            modesel = DATA_REPORTING_OPTS[msg[4]]
                            item.update(OrderedDict([("mode",mode),
                                                     ("modesel",modesel),
                                                     ]))
                                         
                        
                        elif msg_cmd == CMD_QUERY_DATA:
                            pass#do nothing as this produces a measurement message 
                        
                        elif msg_cmd == CMD_SET_DEVICE_ID:
                            pass#do nothing as the new device id is the reported device id
                        
                        elif msg_cmd == CMD_SLEEP_WORK:
                            mode = MODE_OPTS[msg[3]]
                            modesel = SLEEP_OPTS[msg[4]]
                            item.update(OrderedDict([("mode",mode),
                                                     ("modesel",modesel),
                                                     ]))
                        
                        elif msg_cmd == CMD_WORKING_PERIOD:
                            mode = MODE_OPTS[msg[3]]
                            rate = msg[4]
                            item.update(OrderedDict([("mode",mode),
                                                     ("rate",rate),
                                                     ]))
                            
                        
                        elif msg_cmd == CMD_FIRMWARE_Version:
                            year,month,day = msg[3:6]
                            item.update(OrderedDict([("firmware_date",datetime.date(year+2000,month,day)),
                                                     ]))
                        self.rx_cmd_resp_queue.put(item=item)#split by command type
                        
            
        raise NotImplementedError("NEVER TO HAPPEN")
    
    def read_measurement(self):
        return self.rx_measurement_queue.get()
    
    def __str__(self):
        msg = "SDS011 Device ID: {0:04X}\nFirmware Date: {1}\nSleepWorkState: {2}\nDataReportingMode {3}".format(self.devid,
                                                                                                                 self.firmware,
                                                                                                                 self.sleepworkstate,
                                                                                                                 self.datareportingmode)
        return msg

    def __del__(self):
        if self.serversocket is not None:
            self.serversocket.__del__()
            
        



if __name__ == "__main__":     
    port = "/dev/ttyUSB0"
    #port = "com10"
    #sds = SDS011(port=port,use_socket=True,socket_portnum=9999)
    sds = SDS011(port=port,use_database=True)
    sds.set_working_period(rate=5)#one measurment every 5 minutes offers decent granularity and at least a few years of lifetime to the sensor
    print(sds)
    import csv
    try:
        with open("measurments.csv","w") as csvfile:
            log = csv.writer(csvfile, delimiter=" ",
                       quotechar="|", quoting=csv.QUOTE_MINIMAL)
            logcols = ["timestamp","pm2.5","pm10","devid"]
            log.writerow(logcols)
            while True:
                meas = sds.read_measurement()
                vals = [str(meas.get(k)) for k in logcols]
                log.writerow(vals)
                print(vals)
            
            
    except KeyboardInterrupt:
        sds.sleep()
        sds.__del__()
