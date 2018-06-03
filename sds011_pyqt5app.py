import sys
 
from PyQt5.QtWidgets import QWidget,  QLCDNumber, QVBoxLayout, QApplication, QSizePolicy, QLabel, QGridLayout
from PyQt5.QtCore import QThread, pyqtSignal
 
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


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
        self.val_updater.update_event.connect(self.update_vals)
        self.val_updater.start()
        
 
    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        
        self.lcdpm25 = QLCDNumber(self)
        pm25label = QLabel()
        pm25label.setText("pm 2.5")
        
        self.lcdpm10 = QLCDNumber(self)
        pm10label = QLabel()
        pm10label.setText("pm 10")
        
        grid = QGridLayout()
#         self.setLayout(grid)
        
        grid.addWidget(pm25label, 0, 0)
        grid.addWidget(self.lcdpm25, 0, 1)
        grid.addWidget(pm10label, 1, 0)
        grid.addWidget(self.lcdpm10, 1, 1)
        
        vbox = QVBoxLayout()
        vbox.addLayout(grid)
        self.plot = PlotCanvas()        
        vbox.addWidget(self.plot)                
        self.setLayout(vbox)
        self.show()
        
        
    def update_vals(self):
        vals = self.val_updater.meas
        self.lcdpm25.display("{0:.1f}".format(vals.get("pm2.5")))
        self.lcdpm10.display("{0:.1f}".format(vals.get("pm10")))
        
        self.plot.update_plot(timestamp=vals.get("timestamp"),pm2_5=vals.get("pm2.5"),pm10=vals.get("pm10"))
        return
        
class measurement_getter(QThread):
    
    update_event = pyqtSignal()
    
    def __init__(self):
        super().__init__()    
        port = "/dev/ttyUSB0"
        self.sds011 = SDS011(port=port)
        self.sds011.set_working_period(rate=1)
        self.meas = {}
        
    def run(self):
        while True:
            self.meas = self.sds011.read_measurement()
            self.update_event.emit()



class PlotCanvas(FigureCanvas):
 
    def __init__(self, parent=None, width=5, height=4, dpi=100):
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
        self.timestamps.append(timestamp)
        self.pm2_5vals.append(pm2_5)
        self.pm10vals.append(pm10)
        self.plot()
        return
        

 
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())
