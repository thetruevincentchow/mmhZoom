from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QTimer, QMutex, QThread
from PyQt5 import QtWidgets, QtSvg, QtGui
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPalette

import sys
import contextlib
import logging

from video_ui import VideoUi

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()
        uic.loadUi('mainWindow.ui', self)

        self.video_tab : QtWidgets.QWidget = self.findChild(QtWidgets.QWidget, 'videoTab')
        self.video_ui = VideoUi(self, self.video_tab)

    def __enter__(self):
        self._ctx_stack: contextlib.ExitStack = contextlib.ExitStack()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._ctx_stack.close()


app = QtWidgets.QApplication(sys.argv)
with Ui() as window:
    window.show()
    app.exec()
