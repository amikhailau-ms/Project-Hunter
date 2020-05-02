import hashlib

import numpy as np
from PyQt5 import QtCore
from PyQt5.QtGui import QPen, QColor


def reject_outliers(data, m=3):
    mean = np.mean(data)
    sigma = np.std(data)
    new_data = []
    rejected = []
    for it in range(len(data)):
        if (data[it] - mean) >= m * sigma:
            rejected.append(it)
        else:
            new_data.append(data[it])
    return new_data, rejected


def get_qpen():
    pen = QPen()
    pen.setWidth(0.5)
    pen.setStyle(QtCore.Qt.SolidLine)
    pen.setColor(QColor(51, 204, 255))
    pen.setCapStyle(QtCore.Qt.SquareCap)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)
    return pen


def get_fold_qpen():
    pen = QPen()
    pen.setWidth(0.1)
    pen.setStyle(QtCore.Qt.SolidLine)
    pen.setColor(QColor(51, 204, 255))
    pen.setCapStyle(QtCore.Qt.SquareCap)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)
    return pen


def get_transit_pen():
    pen = QPen()
    pen.setWidth(0.3)
    pen.setStyle(QtCore.Qt.DashLine)
    pen.setColor(QColor(168, 50, 153))
    return pen


def hash_file(filename):
    h = hashlib.sha1()
    with open(filename, 'rb') as file:
        chunk = 0
        while chunk != b'':
            chunk = file.read(1024)
            h.update(chunk)
    return h.hexdigest()
