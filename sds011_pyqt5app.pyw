#!/usr/bin/python3
#file: sds011_pyqt5app.pyw
#author: (C) Patrick Menschel 2018
#purpose: a simple gui to play with the sds011 sensor

import sys
 
from PyQt5.QtWidgets import QWidget,   QHBoxLayout, QApplication, QSizePolicy, QLabel, QGridLayout, QLineEdit, QPushButton
from PyQt5.QtCore import QThread, pyqtSignal
 
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


from sds011 import SDS011

from datetime import timedelta

from serial.tools.list_ports import comports

 
class App(QWidget):
 
    def __init__(self):
        super().__init__()
        self.left = 10
        self.top = 10
        self.title = "sds011 dust sensor"
        self.width = 640
        self.height = 400
        self.initUI()
        self.setup_port()
 
    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        
        self.pm25 = QLabel()#QLCDNumber(self)
        pm25label = QLabel()
        pm25label.setText("pm 2.5")
        
        self.pm10 = QLabel()#QLCDNumber(self)
        pm10label = QLabel()
        pm10label.setText("pm 10")
        
        grid = QGridLayout()
#         self.setLayout(grid)
        

        
        devidlabel = QLabel()
        devidlabel.setText("Device ID")
        self.devid = QLabel()
        firmwarelabel = QLabel()
        firmwarelabel.setText("Firmware date")
        self.firmware_date = QLabel()
        sleepworkstatelabel = QLabel()
        sleepworkstatelabel.setText("Sleep work state")
        self.sleepworkstate = QLabel()
        datareportinglabel = QLabel()
        datareportinglabel.setText("Data reporting mode")
        self.datareportingmode = QLabel()
        ratelabel = QLabel()
        ratelabel.setText("Rate")       
        self.rate = QLabel()
        
        self.rateedit = QLineEdit()
        ratebutton = QPushButton()
        ratebutton.setText("set rate")
        ratebutton.clicked.connect(self.setRate)   


        self.portedit = QLineEdit()

        grid.addWidget(pm25label, 0, 0)
        grid.addWidget(self.pm25, 0, 1)
        grid.addWidget(pm10label, 1, 0)
        grid.addWidget(self.pm10, 1, 1)

        grid.addWidget(devidlabel, 2, 0)
        grid.addWidget(self.devid, 2, 1)
        grid.addWidget(firmwarelabel, 3, 0)
        grid.addWidget(self.firmware_date, 3, 1)
        grid.addWidget(sleepworkstatelabel, 4, 0)
        grid.addWidget(self.sleepworkstate, 4, 1)
        grid.addWidget(datareportinglabel, 5, 0)
        grid.addWidget(self.datareportingmode, 5, 1)
        grid.addWidget(ratelabel, 6, 0)
        grid.addWidget(self.rate, 6, 1)
        grid.addWidget(self.rateedit, 7, 0)
        grid.addWidget(ratebutton, 7, 1)
        grid.addWidget(self.portedit, 8, 0)


        hbox = QHBoxLayout()
        hbox.addLayout(grid)
        self.plot = PlotCanvas()        
        hbox.addWidget(self.plot)                
        self.setLayout(hbox)
        self.show()

    def setup_port(self):
        self.port = None
        ports = [p for p in comports()]
        for p in ports:
            if (0x1A86,0x7523) == (p.vid,p.pid):
                self.port = p.device
                break
        if self.port is None:
            raise NotImplementedError("Could not determine the port with CH341")
        self.portedit.setText(self.port)
        self.val_updater = measurement_getter(self.port)
        self.val_updater.update_event.connect(self.update_vals)
        self.val_updater.start()
        self.get_sensor_data()
        return
        
    def get_sensor_data(self):
        data = self.val_updater.sds011.get_sensor_data()
        self.devid.setText("0x{0:X}".format(data.get("devid")))
        self.firmware_date.setText(str(data.get("firmware_date")))
        self.sleepworkstate.setText(str(data.get("sleepworkstate")))
        self.datareportingmode.setText(str(data.get("datareportingmode")))
        self.rate.setText(str(data.get("rate")))
        self.rateedit.setText(str(data.get("rate")))
        return
    
    def setRate(self):
        try:
            rate = int(self.rateedit.text())        
        except:
            rate = 5
        self.val_updater.sds011.set_working_period(rate=rate)
        self.rate.setText(str(rate))
        return

        
    def update_vals(self):
        vals = self.val_updater.meas
        #self.lcdpm25.display("{0:.1f}".format(vals.get("pm2.5")))
        #self.lcdpm10.display("{0:.1f}".format(vals.get("pm10")))
        
        self.pm25.setText("{0:.1f}".format(vals.get("pm2.5")))
        self.pm10.setText("{0:.1f}".format(vals.get("pm10")))
        
        self.plot.update_plot(timestamp=vals.get("timestamp"),pm2_5=vals.get("pm2.5"),pm10=vals.get("pm10"))
        return
        
class measurement_getter(QThread):
    
    update_event = pyqtSignal()
    
    def __init__(self,port="/dev/ttyUSB0"):
        super().__init__()    
        #port = "/dev/ttyUSB0"
        #port = "com12"
        self.sds011 = SDS011(port=port,use_database=True)
#        self.sds011.set_working_period(rate=5)
        self.meas = {}
        
    def run(self):
        while True:
            self.meas = self.sds011.read_measurement()
            self.update_event.emit()



class PlotCanvas(FigureCanvas):
 
    def __init__(self, parent=None, width=5, height=4, dpi=100, interval=timedelta(hours=1)):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
 
        FigureCanvas.__init__(self, fig)
        self.setParent(parent)
 
        FigureCanvas.setSizePolicy(self,
                QSizePolicy.Expanding,
                QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.timestamps = []
        self.pm2_5vals = []
        self.pm10vals = []
        self.interval = interval
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title('SDS011 Data Plot')
        
        self.plot(init_legend=True)
 
 
    def plot(self,init_legend=False):
        self.ax.plot(self.timestamps,self.pm2_5vals, 'r-',label="pm2.5")
        self.ax.plot(self.timestamps,self.pm10vals, 'g-',label="pm10")
        if init_legend is True:#quick hack to counter multiple instances of legend
            self.ax.legend()
        self.draw()
        return
        
    def update_plot(self,timestamp,pm2_5,pm10):
        if len(self.timestamps)>0:
            while (timestamp-self.timestamps[0]) > self.interval:
                self.timestamps.pop(0)
                self.pm2_5vals.pop(0)
                self.pm10vals.pop(0)
        self.timestamps.append(timestamp)
        self.pm2_5vals.append(pm2_5)
        self.pm10vals.append(pm10)
        self.plot()
        return
        

 
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())
