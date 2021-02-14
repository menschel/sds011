#!/usr/bin/python3
# file: sds011_pyqt5app.pyw
# author: (C) Patrick Menschel 2018
# purpose: a simple gui to play with the sds011 sensor

import sys

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QApplication, QSizePolicy, QLabel, QGridLayout, \
    QLineEdit, QPushButton, QRadioButton, QDialog, QDialogButtonBox
from PyQt5.QtCore import QThread, pyqtSignal, Qt

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.dates as mdates

from sds011 import SDS011

from datetime import timedelta

from serial.tools.list_ports import comports
# from matplotlib.axis import XAxis

import os
import pickle

DEFAULT_OPTS = {"port": "/dev/ttyUSB0",
                "autolookup_ch341": True,
                "autoconnect": True,
                "rate": 5,
                "interval": timedelta(hours=1),
                }

SETTINGS_FILENAME = "settings.pkl"


class OptionsDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.selection = None
        self.init_user_interface()

    def init_user_interface(self):
        self.setWindowTitle("Select Com Port")
        self.setGeometry(10, 10, 640, 400)
        layout = QVBoxLayout()
        ports = [p for p in comports()]
        for idx, p in enumerate(ports):
            btn = QRadioButton()
            btn.setText(p.device)
            btn.toggled.connect(lambda: self.on_toggle(p.device))
            layout.addWidget(btn)
            if idx == 0:
                # self.selection = p.device
                btn.toggle()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self.show()

    def on_toggle(self, b):
        self.selection = b
        return

    def on_ok(self):
        print(self.selection)
        return self.done()
        # return self.selection

    def get_selection(self):
        ret = DEFAULT_OPTS
        ret.update({"port": self.selection})
        return ret


class App(QWidget):

    def __init__(self):
        super().__init__()
        self.left = 10
        self.top = 10
        self.title = "sds011 dust sensor"
        self.width = 640
        self.height = 400
        self.settings = DEFAULT_OPTS
        self.read_settings()
        self.init_user_interface()
        if self.settings.get("autoconnect") is True:
            self.setup_port()

    def init_user_interface(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        self.pm25 = QLabel()
        pm25label = QLabel()
        pm25label.setText("pm 2.5")

        self.pm10 = QLabel()
        pm10label = QLabel()
        pm10label.setText("pm 10")

        grid = QGridLayout()

        device_id_label = QLabel()
        device_id_label.setText("Device ID")
        self.device_id = QLabel()
        firmwarelabel = QLabel()
        firmwarelabel.setText("Firmware date")
        self.firmware_date = QLabel()
        sleepworkstatelabel = QLabel()
        sleepworkstatelabel.setText("Sleep work state")
        sleepworkstatelabel.setToolTip("'sleep' (equal to waiting) or 'active'")
        self.sleepworkstate = QLabel()
        datareportinglabel = QLabel()
        datareportinglabel.setText("Data reporting mode")
        datareportinglabel.setToolTip("'active' by sensor or 'query' by user (tbd)")
        self.datareportingmode = QLabel()
        ratelabel = QLabel()
        ratelabel.setText("Rate")
        ratelabel.setToolTip("Working period of the sensor in minutes")
        self.rate = QLabel()

        self.rateedit = QLineEdit()
        ratebutton = QPushButton()
        ratebutton.setText("set rate")
        ratebutton.clicked.connect(self.set_rate)

        optionsbutton = QPushButton()
        optionsbutton.setText("select Options")
        optionsbutton.clicked.connect(self.select_options)

        self.portedit = QLineEdit()

        grid.addWidget(pm25label, 0, 0)
        grid.addWidget(self.pm25, 0, 1)
        grid.addWidget(pm10label, 1, 0)
        grid.addWidget(self.pm10, 1, 1)

        grid.addWidget(device_id_label, 2, 0)
        grid.addWidget(self.device_id, 2, 1)
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
        grid.addWidget(optionsbutton, 8, 1)

        hbox = QHBoxLayout()
        hbox.addLayout(grid)
        vbox2 = QVBoxLayout()
        self.plot = PlotCanvas(interval=self.settings.get("interval"))
        self.toolbar = NavigationToolbar(self.plot, parent=self)
        vbox2.addWidget(self.toolbar)
        vbox2.addWidget(self.plot)
        hbox.addLayout(vbox2)
        self.setLayout(hbox)
        self.show()

    def select_options(self):
        od = OptionsDialog()
        if od.exec_():
            self.settings.update(od.get_selection())
        self.save_settings()
        return

    def setup_port(self):
        if self.settings.get("autolookup_ch341") is True:
            ports = [p for p in comports()]
            for p in ports:
                if (0x1A86, 0x7523) == (p.vid, p.pid):
                    self.settings.update({"port": p.device})
                    break
            if self.settings.get("port") is None:
                raise NotImplementedError("Could not determine the port with CH341")
        self.portedit.setText(self.settings.get("port"))
        self.val_updater = MeasurementGetter(settings=self.settings)
        self.val_updater.update_event.connect(self.update_vals)
        self.val_updater.start()
        self.get_sensor_data()
        return

    def get_sensor_data(self):
        data = self.val_updater.sds011.get_sensor_data()
        self.device_id.setText("0x{0:X}".format(data.get("device_id")))
        self.firmware_date.setText(str(data.get("firmware_date")))
        self.sleepworkstate.setText(str(data.get("sleep_work_state")))
        self.datareportingmode.setText(str(data.get("data_reporting_mode")))
        self.rate.setText(str(data.get("rate")))
        self.rateedit.setText(str(data.get("rate")))
        return

    def set_rate(self):
        try:
            rate = int(self.rateedit.text())
        except (TypeError, ValueError):
            rate = 5
        self.settings.update({"rate": rate})
        self.val_updater.sds011.set_working_period(rate=rate)
        self.rate.setText(str(rate))
        return

    def read_settings(self, settingsfile="settings.pkl"):
        settings = DEFAULT_OPTS
        if os.path.exists(settingsfile):
            with open(settingsfile, "rb") as f:
                settings = pickle.load(f)
            if isinstance(settings, dict):
                self.settings.update({key: settings.get(key) for key in settings})
        return

    def save_settings(self, settingsfile="settings.pkl"):
        with open(settingsfile, "wb") as f:
            pickle.dump(self.settings, f)
        return

    def update_vals(self):
        values = self.val_updater.meas
        if values:
            self.pm25.setText("{0:.1f} µg/m³".format(values.get("pm2.5")))
            self.pm10.setText("{0:.1f} µg/m³".format(values.get("pm10")))
            self.plot.update_plot(timestamp=values.get("timestamp"), pm2_5=values.get("pm2.5"), pm10=values.get("pm10"))
        status = self.val_updater.sensor_status
        if status:
            self.sleepworkstate.setText(str(status))
        return


class MeasurementGetter(QThread):
    update_event = pyqtSignal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.sds011 = SDS011(port=self.settings.get("port"))
        self.sensor_status = None
        self.meas = {}

    def run(self):
        while True:
            sensor_measurement = self.sds011.read_measurement(timeout=5)
            self.meas = sensor_measurement
            self.sensor_status = self.sds011.get_sleep_work_status()
            self.update_event.emit()


class PlotCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=4, dpi=100, interval=timedelta(minutes=10)):
        fig = Figure(figsize=(width, height), dpi=dpi)
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
        self.ax.format_xdata = mdates.DateFormatter("%H:%M:%S")
        fig.autofmt_xdate()
        self.plot(init_legend=True)

    def plot(self, init_legend=False):
        if len(self.timestamps) > 2:
            mt = max(self.timestamps)
            self.ax.set_xlim(mt - self.interval, mt)
        self.ax.plot(self.timestamps, self.pm2_5vals, 'r-', label="pm2.5 µg/m³")
        self.ax.plot(self.timestamps, self.pm10vals, 'g-', label="pm10 µg/m³")

        if init_legend is True:  # quick hack to counter multiple instances of legend
            self.ax.legend()
        self.draw()
        return

    def update_plot(self, timestamp, pm2_5, pm10):
        self.timestamps.append(timestamp)
        self.pm2_5vals.append(pm2_5)
        self.pm10vals.append(pm10)
        self.plot()
        return


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())
