import sys
 
#from PyQt5.QtWidgets import QApplication, QMainWindow, QSizePolicy, QPushButton, QWidget, QLCDNumber, QSlider, QVBoxLayout, QApplication
from PyQt5.QtWidgets import QWidget, QMainWindow, QLCDNumber, QVBoxLayout, QApplication, QPushButton, QHBoxLayout
from PyQt5.QtCore import QThread, pyqtSignal# QObject
 
# from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
# from matplotlib.figure import Figure
# 
# import threading

from sds011 import SDS011
 
class App(QWidget):
 
    def __init__(self):
        super().__init__()
        self.left = 10
        self.top = 10
        self.title = "sds011 dust sensor"
        self.width = 640
        self.height = 400
        self.initUI()
        self.val_updater = measurement_getter()
        self.val_updater.start()
        self.val_updater.update_event.connect(self.update_vals)
        
 
    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        
        self.lcdpm25 = QLCDNumber(self)
        self.lcdpm10 = QLCDNumber(self)
        
        hbox = QHBoxLayout()
        hbox.addWidget(self.lcdpm25)
        hbox.addWidget(self.lcdpm10)
        self.setLayout(hbox)
        
        #FIXME: somehow all widgets are stacked over each other in the layout, why is that so?!
        self.show()
        
        
    def update_vals(self):
        vals = self.val_updater.meas
        self.lcdpm25.display(vals.get("pm2.5"))
        self.lcdpm10.display(vals.get("pm10"))
        return
        
class measurement_getter(QThread):
    
    update_event = pyqtSignal()
    
    def __init__(self):
        super().__init__()    
        port = "/dev/ttyUSB0"
        self.sds011 = SDS011(port=port)
        self.sds011.set_working_period(rate=0)
        self.meas = {}
        
    def run(self):
        while True:
            self.meas = self.sds011.read_measurement()
            self.update_event.emit()

 
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())
