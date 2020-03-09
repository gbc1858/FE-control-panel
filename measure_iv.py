import shutil
from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import QTimer

from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QTableWidget, QTextBrowser, QVBoxLayout, \
    QTableWidgetItem
import pyqtgraph as pg
import pyvisa

import matplotlib.pyplot as plt

import logging
import os
import subprocess
import time
import sys
import settings
from exceptions import *

import gphoto2 as gp

qtCreatorFile = "FE_control.ui"

# Loading UI
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)


class UIClass(QMainWindow, Ui_MainWindow):

    def __init__(self, parent=None, *args, **kwargs):
        QMainWindow.__init__(self, parent, *args, **kwargs)
        Ui_MainWindow.__init__(self, *args, **kwargs)
        self.title = 'FE control panel'
        self.setupUi(self)
        self.tableWidget_iv_results.setColumnCount(4)

        self.power_supply = None
        self.v_min = None
        self.v_step = None
        self.v_max = None
        self.i_compliance = None
        self.delay_between_pts = None
        self.delay_aftr_v_changes = None

        self.i_reading = None
        self.v_setting = None

        self.current_list = []
        self.voltage_list = []

        self.iso = None
        self.aperture = None
        self.shutter_speed = None

        self.pushButton_scan.clicked.connect(self.measure_iv)
        self.pushButton_abort.clicked.connect(self.disconnect_dc_power)
        self.pushButton_take_pic.clicked.connect(self.image_cap)
        self.pushButton_conct_canon.clicked.connect(self.camera_test)
        self.pushButton_sync_to_camera.clicked.connect(self.camera_settings)

    def clear(self):
        self.v_min = None
        self.v_step = None
        self.v_max = None
        self.i_compliance = None
        self.delay_between_pts = None
        self.delay_aftr_v_changes = None
        self.current_list = []
        self.voltage_list = []

    def connect_dc_power(self):
        dc_power = pyvisa.ResourceManager()
        self.power_supply = dc_power.open_resource(settings.KEITHLEY_GPIB_ADDRESS)
        self.power_supply.write(":SYST:BEEP:STAT OFF")  # disable keithley "beep" sound
        self.power_supply.write(":OUTP ON")

    def disconnect_dc_power(self):
        self.power_supply.write("*RST")  # restore GPIB defaults
        self.power_supply.write("*CLS")  # clear the error queue, status registers
        self.power_supply.write(":OUTP OFF")

    def select_file(self):
        self.lineEdit_folder.setText(QFileDialog.getExistingDirectory(
            directory='/Users/chen/Desktop/github/fe_control_panel'))

    def save_iv(self):
        filename = os.path.join(self.lineEdit_folder.text(),
                                self.lineEdit_filename.text())
        self.data_iv.to_csv(filename + '.csv')
        shutil.copy('measurement_iv.png', filename + '_iv.png')
        self.textBrowser.append('I-V data saved')

    def measure_iv(self):
        # Get input parameters.
        self.v_min = self.doubleSpinBox_v_min.value()
        self.v_step = self.doubleSpinBox_v_step.value()
        self.v_max = self.doubleSpinBox_v_max.value()

        # Get current compliance.
        self.i_compliance = self.doubleSpinBox_current_limit.value()

        # Get delay.
        self.delay_between_pts = self.doubleSpinBox_time_delay.value()
        self.delay_aftr_v_changes = self.doubleSpinBox_wait_after_v.value()

        self.connect_dc_power()
        self.power_supply.write(f":SOUR:VOLT:RANG {str(self.v_max)}")
        self.power_supply.write(f":SENS:CURR:PROT {str(self.i_compliance)}")  # current compliance [A]
        self.power_supply.write(f":SOUR:DEL {str(self.delay_aftr_v_changes / 1000)}")  # source delay [s]

        self.v_ramping(ramp_up=True)
        self.v_ramping(ramp_down=True)

        self.disconnect_dc_power()

    def v_ramping(self, ramp_up=False, ramp_down=False):
        # self.textBrowser.append(f"IV scan from {str(self.v_min)} V to {str(self.v_max)} V.")
        if (self.v_max - self.v_min) % self.v_step == 0:
            if ramp_up:
                self.textBrowser.append(f"IV scan from {str(self.v_min)} V to {str(self.v_max)} V.")
                self.textBrowser.append("Voltage ramping up.")
            if ramp_down:
                self.textBrowser.append(f"IV scan from {str(self.v_max)} V to {str(self.v_min)} V.")
                self.textBrowser.append("Voltage ramping down.")

            step_num = (self.v_max - self.v_min) / self.v_step
            for i in range(int(step_num) + 1):
                if ramp_up:
                    self.v_setting = self.v_min + self.v_step * i
                if ramp_down:
                    self.v_setting = self.v_max - self.v_step * i
                self.power_supply.write(f":SOUR:VOLT {self.v_setting}")
                self.power_supply.write(":READ?")

                self.i_reading = self.power_supply.read(termination='\n').split(',')[1]
                self.v_setting = round(self.v_setting, 2)

                self.update_table()

                self.voltage_list.append(self.v_setting)
                self.current_list.append(self.i_reading)

                # self.image_cap()
                # self.plot_iv_scan()
                # time.sleep(self.delay_aftr_v_changes / 1000)
        else:
            self.textBrowser.append("***STEP SIZE ERROR. Please re-enter.***")


    def update_table(self):
        num_rows = self.tableWidget_iv_results.rowCount()
        self.tableWidget_iv_results.insertRow(num_rows)
        self.tableWidget_iv_results.setItem(num_rows, 0, QTableWidgetItem(str(self.v_setting)))
        self.tableWidget_iv_results.setItem(num_rows, 1, QTableWidgetItem(str(self.i_reading)))

    def save_iv_data(self):
        # TODO:
        pass

    def plot_iv_scan(self):
        # TODO:
        pg.plot(self.voltage_list, self.current_list, pen=None, symbol='o')

    def camera_settings(self):
        self.iso = self.comboBox_ISO.currentIndex()
        os.system('gphoto2 --set-config-index /main/imgsettings/iso=' + str(self.iso))
        self.aperture = self.comboBox_aperture.currentIndex()
        os.system('gphoto2 --set-config-index /main/capturesettings/aperture=' + str(self.aperture))
        self.shutter_speed = self.comboBox_exposure.currentIndex()
        os.system('gphoto2 --set-config-index /main/capturesettings/shutterspeed=' + str(self.shutter_speed))
        self.textBrowser.append("Camera synced successfully.")

    def image_cap(self):
        t = time.localtime()
        current_t = time.strftime("%H:%M:%S", t)
        current_time = str(current_t)
        logging.basicConfig(
            format='%(levelname)s: %(name)s: %(message)s', level=logging.WARNING)
        camera = gp.Camera()
        camera.init()
        print('Capturing image')
        file_path = camera.capture(gp.GP_CAPTURE_IMAGE)
        file_location = os.path.join('/Users/chen/Desktop/github/fe_control_pane/test_img', current_time + ".jpg")
        camera_file = camera.file_get(
            file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL)
        camera_file.save(file_location)
        # subprocess.call(['open', file_location])
        camera.exit()

    def camera_test(self):
        camera = gp.Camera()
        camera.init()
        print('Shutter test, without image saving.')
        camera.capture(gp.GP_CAPTURE_IMAGE)
        camera.exit()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    myWindow = UIClass()
    myWindow.show()
    app.exec_()
