#from PyQt5 import QtWidgets, QThreadPool, QRunnable, pyqtSlot, uic

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QTimer, QMutex, QThread
from PyQt5 import QtWidgets
#import (
#    QApplication,
#    QMainWindow,
#    QWidget,
#    QVBoxLayout,
#    QLabel,
#    QPushButton,
#)

import sys
import camera

import logging

#logging.basicConfig()
#logging.getLogger().setLevel(logging.DEBUG)

# https://www.learnpyqt.com/tutorials/multithreading-pyqt-applications-qthreadpool/
# Bidirctonal callbacks:
#   https://stackoverflow.com/questions/61625043/threading-with-qrunnable-proper-manner-of-sending-bi-directional-callbacks

class VideoWorker(QObject):
    signalFinished = pyqtSignal()

    def __init__(self, looper: camera.VideoLooper):
        QObject.__init__(self)
        self._mutex = QMutex()
        self._running = True

        self.looper = looper

    @pyqtSlot()
    def work(self):
        while self._running:
            print("Loop")
            self.looper.loop()
        self.signalFinished.emit()

    @pyqtSlot()
    def stop(self):
        print('Stopping')
        self._mutex.lock()
        self._running = False
        self._mutex.unlock()

class VideoHelper:
    def __init__(self, input_device: str, output_device: str):
        logging.info("Create input camera")
        self.input_cam = camera.RealCamera(input_device)
        self.input_cam.init()
        logging.info("Create output camera")
        self.output_cam = camera.OutputCamera(output_device)
        self.output_cam.init()

        looper = camera.VideoLooper(self.input_cam, self.output_cam)
        self.worker = VideoWorker(looper)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.work)
        self.worker_thread.start()

    def release(self):
        logging.info("Stop worker")
        self.worker.stop()
        logging.info("Quit worker thread")
        self.worker_thread.quit()
        logging.info("Wait on worker thread")
        self.worker_thread.wait()

        logging.info("Release input camera")
        self.input_cam.release()
        logging.info("Release output camera")
        self.output_cam.release()

class Ui(QtWidgets.QMainWindow):
    mainthread_callback_to_worker = pyqtSignal()

    def __init__(self):
        super(Ui, self).__init__()
        uic.loadUi('mainWindow.ui', self)

        self.videoButton = self.findChild(QtWidgets.QPushButton, 'videoToggle')
        self.videoButton.clicked.connect(self.toggle_video)

        self.timer_label = self.findChild(QtWidgets.QLabel, 'timer_label')

        self.worker = None

        self.counter = 0
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.recurring_timer)
        self.timer.start()

        self.video_helper = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.video_helper:
            self.video_helper.release()

    def toggle_video(self):
        if self.video_helper:
            self.video_helper.release()
            self.video_helper = None
        else:
            self.video_helper = VideoHelper(None, None)

    def recurring_timer(self):
        self.counter += 1
        self.timer_label.setText(f"Counter: {self.counter}")


app = QtWidgets.QApplication(sys.argv)
with Ui() as window:
    window.show()
    app.exec()
