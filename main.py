from PyQt5 import uic, QtWidgets

import sys
import contextlib
import logging

from video_ui import VideoUi
from meeting_ui import MeetingUi

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()
        uic.loadUi('mainWindow.ui', self)

        self.video_tab : QtWidgets.QWidget = self.findChild(QtWidgets.QWidget, 'videoTab')
        self.meeting_tab : QtWidgets.QWidget = self.findChild(QtWidgets.QWidget, 'meetingTab')

        self.video_ui = VideoUi(self, self.video_tab)
        self.meeting_ui = MeetingUi(self, self.meeting_tab)

    def __enter__(self):
        self._ctx_stack: contextlib.ExitStack = contextlib.ExitStack()
        self._ctx_stack.enter_context(self.video_ui)
        self._ctx_stack.enter_context(self.meeting_ui)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._ctx_stack.close()


app = QtWidgets.QApplication(sys.argv)
with Ui() as window:
    window.show()
    app.exec()
