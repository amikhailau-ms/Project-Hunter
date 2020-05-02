import re
import sys
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QListWidgetItem, QMessageBox
from astropy.io import fits

from WindowUI import Ui_MainWindow
import utils


class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.maxTransitLines = 32
        self.fileLoaded = False
        self.folded_all_time = []
        self.detrended_all_flux = []
        self.all_time = []
        self.all_flux = []
        self.kepID = ""
        self.hashFile = ""
        self.hashDir = "cache\\"
        transitLine = pg.InfiniteLine()
        transitLine.setPen(utils.get_transit_pen())
        self.firstTransitLine = transitLine
        self.transitLines = []
        self.presentLines = []
        self.firstTransitSet = False
        self.firstLineAdded = False
        self.secondLinesSet = False
        self.isFolded = False
        self.init_open()

    def init_open(self):

        pen = utils.get_transit_pen()
        for i in range(self.maxTransitLines):
            transitLine = pg.InfiniteLine()
            transitLine.setPen(pen)
            self.transitLines.append(transitLine)
            self.presentLines.append(False)

        self.foldButton.setVisible(False)
        self.foldButton.clicked.connect(self.click_fold_graph)

        self.detrendCheck.setVisible(False)
        self.detrendCheck.clicked.connect(self.detrend_data)

        self.deleteButton.setVisible(False)
        self.deleteButton.clicked.connect(self.delete_entry)

        self.actionOpen.setShortcut("Ctrl+O")
        self.actionOpen.setStatusTip("Open .fits file.")
        self.actionOpen.triggered.connect(self.open_file)

        self.actionDetrend.setEnabled(False)
        self.actionDetrend.setShortcut("Ctrl+D")
        self.actionDetrend.setStatusTip("Detrend graph")
        self.actionDetrend.triggered.connect(self.menu_detrend)

        self.actionExit.setShortcut("Ctrl+Q")
        self.actionExit.setStatusTip("Exit the application.")
        self.actionExit.triggered.connect(self.exit_app)

        self.actionAbout.setShortcut("Ctrl+I")
        self.actionAbout.setStatusTip("About the application.")
        self.actionAbout.triggered.connect(self.show_about)

        self.offsetText.setValidator(QDoubleValidator())
        self.periodText.setValidator(QDoubleValidator())
        self.offsetText.textChanged.connect(self.text_changed)
        self.offsetText.setStatusTip("Offset of first transit in days.")
        self.periodText.textChanged.connect(self.text_changed)
        self.periodText.setStatusTip("Period of transits in days.")

        self.listOfTransits.itemClicked.connect(self.selection_changed)
        self.listOfTransits.itemDoubleClicked.connect(self.get_saved_transit)
        self.listOfTransits.setStatusTip("Double click on transit entry to load it. " +
                                         "Select entry and click Delete entry to remove.")

        self.clearButton.setVisible(False)
        self.clearButton.clicked.connect(self.click_clear_graph)
        self.clearButton.setStatusTip("Click to clear graph from transit lines.")
        self.saveButton.setVisible(False)
        self.saveButton.clicked.connect(self.save_transit_entry)
        self.saveButton.setStatusTip("Click to save transit entry.")

        self.graphViewer.sceneObj.sigMouseMoved.connect(self.show_transit_line)
        self.graphViewer.sceneObj.sigMouseClicked.connect(self.set_transit_line)

    def open_file(self):
        if self.hashFile != "":
            self.save_transits_to_file()
        self.clear_graph(rebuild=False)
        fileName, _ = QFileDialog.getOpenFileName(self, "Open light curve file",
                                               "c:\\", "Fits kepler files (*.fits)")
        if fileName:
            with fits.open(fileName) as hdu_list:
                light_curve = hdu_list["LIGHTCURVE"].data

            match = re.search("kplr[0-9]{9}", fileName)
            self.kepID = ""
            if match:
                self.kepID = match[0][4:]

            self.all_time = light_curve.TIME
            self.all_flux = light_curve.PDCSAP_FLUX

            flux_and_time_finite = np.logical_and(np.isfinite(self.all_flux), np.isfinite(self.all_time))
            self.all_time = self.all_time[flux_and_time_finite]
            self.all_flux = self.all_flux[flux_and_time_finite]

            self.all_flux /= np.median(self.all_flux)

            self.hashFile = utils.hash_file(fileName)
            try:
                with open(self.hashDir + self.hashFile, "r") as transitFile:
                    for line in transitFile.readlines():
                        item = QListWidgetItem()
                        item.setText(line)
                        self.listOfTransits.addItem(item)
            except OSError:
                pass

            self.rebuild_plot()
            self.fileLoaded = True
            self.saveButton.setVisible(True)
            self.clearButton.setVisible(True)
            self.detrendCheck.setVisible(True)
            self.actionDetrend.setEnabled(True)

    def text_changed(self):
        if not self.isFolded:
            if self.offsetText.text().strip(" ") != "":
                xpos = float(self.offsetText.text())
                p = QPointF(xpos, 1.0)
                self.show_first_line(p)
                if self.periodText.text().strip(" ") != "":
                    period = float(self.periodText.text())
                    p2 = QPointF(xpos + period, 1.0)
                    self.show_secondary_lines(p2)
        if self.isFolded:
            if self.offsetText.text().strip(" ") != "" and self.periodText.text().strip(" ") != "":
                self.recalculate_fold_graph(float(self.offsetText.text()), float(self.periodText.text()))
            else:
                self.clear_graph(rebuild=True)
                self.text_changed()

    def get_saved_transit(self, item):
        self.clear_graph(rebuild=True)
        epoch, period = item.text().split("|")
        epoch = epoch[7:].strip(" ")
        period = period[9:].strip(" ")
        self.offsetText.setText(epoch)
        if period != "-":
            self.periodText.setText(period)
            self.secondLinesSet = True
        self.firstTransitSet = True
        self.isFolded = False
        self.foldButton.setVisible(True)

    def save_transit_entry(self):
        item = QListWidgetItem()
        offset = self.offsetText.text().strip(" ")
        period = self.periodText.text().strip(" ")
        if offset == "" or not self.firstTransitSet:
            QMessageBox.warning(self, "Save transit", "Offset of the first transit should be selected.")
            return
        if period == "" or not self.secondLinesSet:
            period = "-"
        item.setText("Epoch: {0} | Period: {1}\n".format(offset, period))
        self.listOfTransits.addItem(item)
        self.clear_graph(rebuild=True)

    def selection_changed(self):
        if len(self.listOfTransits.selectedItems()) == 0:
            self.deleteButton.setVisible(False)
            return
        self.deleteButton.setVisible(True)

    def delete_entry(self):
        self.listOfTransits.takeItem(self.listOfTransits.currentRow())
        self.deleteButton.setVisible(False)

    def save_transits_to_file(self):
        if self.listOfTransits.count() == 0:
            return
        with open(self.hashDir + self.hashFile, "w") as transitFile:
            for i in range(self.listOfTransits.count()):
                transitFile.write(self.listOfTransits.item(i).text())
            self.listOfTransits.clear()
            self.deleteButton.setVisible(False)

    def click_clear_graph(self):
        self.clear_graph(rebuild=True)

    def clear_graph(self, rebuild=False):
        self.graphViewer.getPlotItem().clear()
        self.isFolded = False
        self.offsetText.setText("")
        self.periodText.setText("")
        for index in range(self.maxTransitLines):
            self.presentLines[index] = False
        self.firstTransitSet = False
        self.firstLineAdded = False
        self.secondLinesSet = False
        self.foldButton.setVisible(False)
        if rebuild:
            self.rebuild_plot()

    def rebuild_graph_with_transits(self):
        self.graphViewer.getPlotItem().clear()
        self.rebuild_plot()
        self.graphViewer.addItem(self.firstTransitLine)
        for index, item in enumerate(self.transitLines):
            if self.presentLines[index]:
                self.graphViewer.addItem(item)

    def rebuild_plot(self):
        x_data = self.all_time
        y_data = self.all_flux
        if self.kepID != "":
            self.graphViewer.getPlotItem().setTitle("Kepler ID - {0}".format(self.kepID))
        if self.detrendCheck.isChecked():
            y_data = self.detrended_all_flux
        if self.isFolded:
            x_data = self.folded_all_time
            self.graphViewer.getPlotItem().plot(x_data, y_data, pen=None, symbol='+', symbolPen=utils.get_fold_qpen())
        else:
            self.graphViewer.getPlotItem().plot(x_data, y_data, pen=utils.get_qpen())
        self.graphViewer.getPlotItem().vb.setLimits(yMin=np.min(y_data), yMax=np.max(y_data),
                                                    xMin=np.min(x_data), xMax=np.max(x_data))

    def exit_app(self):
        choice = QMessageBox.question(self, 'Exit',
                                      "Exit the application?",
                                      QMessageBox.Yes | QMessageBox.No)
        if choice == QMessageBox.Yes:
            sys.exit()
        else:
            pass

    def show_about(self):
        QMessageBox.information(self, 'About', "Application for analyzing light curves provided by Kepler telescope.\n" +
                                               "Wrote on PyQt5 and pyqtgraph.\n" +
                                               "Mikhailau Anton. 2020.", )

    def show_transit_line(self):
        if not self.fileLoaded:
            return
        if self.isFolded:
            return
        pos = self.graphViewer.lastMousePos
        p = self.graphViewer.getPlotItem().vb.mapSceneToView(pos)
        if not self.firstTransitSet:
            self.offsetText.setText("%.2f" % p.x())
        elif not self.secondLinesSet:
            offset = self.firstTransitLine.pos().x()
            period = np.abs(offset - p.x())
            self.periodText.setText("%.2f" % period)

    def show_first_line(self, p):
        if not self.firstLineAdded:
            self.graphViewer.addItem(self.firstTransitLine)
            self.firstLineAdded = True
        self.firstTransitLine.setPos(p)

    def show_secondary_lines(self, p):
        offset = self.firstTransitLine.pos().x()
        period = np.abs(offset - p.x())
        if period == 0:
            return
        left_transit = offset - period
        right_transit = offset + period
        last_point = self.all_time[len(self.all_time) - 1]
        for index, item in enumerate(self.transitLines):
            if index % 2 == 0:
                if left_transit < self.all_time[0]:
                    self.graphViewer.removeItem(item)
                    self.presentLines[index] = False
                    continue
                item.setPos(left_transit)
                left_transit -= period
                if not self.presentLines[index]:
                    self.presentLines[index] = True
                    self.graphViewer.addItem(item)
            else:
                if right_transit > last_point:
                    self.graphViewer.removeItem(item)
                    self.presentLines[index] = False
                    continue
                item.setPos(right_transit)
                right_transit += period
                if not self.presentLines[index]:
                    self.presentLines[index] = True
                    self.graphViewer.addItem(item)

    def set_transit_line(self):
        if self.isFolded:
            return
        if not self.firstTransitSet:
            self.firstTransitSet = True
        else:
            self.secondLinesSet = True
            self.foldButton.setVisible(True)

    def click_fold_graph(self):
        xpos = float(self.offsetText.text())
        period = float(self.periodText.text())
        self.fold_graph(xpos, period)

    def fold_graph(self, xpos, period):
        if self.isFolded:
            self.foldButton.setText("Fold graph")
            self.isFolded = False
            self.firstTransitLine.setPos(xpos)
            self.rebuild_graph_with_transits()
        else:
            self.foldButton.setText("Unfold graph")
            self.isFolded = True
            self.recalculate_fold_graph(xpos, period)

    def recalculate_fold_graph(self, xpos, period):
        self.folded_all_time = []
        for point in self.all_time:
            self.folded_all_time.append(point - (xpos + np.round((point - xpos) / period) * period))
        self.graphViewer.getPlotItem().clear()
        self.rebuild_plot()
        self.firstTransitLine.setPos(0.0)
        self.graphViewer.addItem(self.firstTransitLine)

    def menu_detrend(self):
        if self.actionDetrend.isChecked():
            self.detrendCheck.setChecked(True)
            self.detrend_data()
        else:
            self.detrendCheck.setChecked(False)
            self.detrend_data()

    def detrend_data(self):
        if self.detrendCheck.isChecked():
            self.actionDetrend.setChecked(True)
            dataSize = len(self.all_time)
            windowSize = int(np.sqrt(dataSize))
            if windowSize % 2 == 0:
                windowSize -= 1
            self.detrended_all_flux = []
            self.detrended_all_flux.extend(self.all_flux[:int(windowSize / 2)])
            window = []
            window.extend(self.all_flux[:windowSize])
            for i in range(dataSize - windowSize + 1):
                movingAverage = np.average(window)
                self.detrended_all_flux.append(self.all_flux[int(windowSize / 2) + i] - movingAverage + 1.0)
                if i != dataSize - windowSize:
                    window = window[1:]
                    window.append(self.all_flux[windowSize + i])
            self.detrended_all_flux.extend(self.all_flux[-int(windowSize / 2):])
        else:
            self.actionDetrend.setChecked(False)
        self.rebuild_graph_with_transits()


def main():
    app = QApplication(sys.argv)
    GUI = MainWindow()
    app.aboutToQuit.connect(GUI.save_transits_to_file)
    GUI.show()
    sys.exit(app.exec_())


main()
