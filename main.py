#from PyQt5 import QtWidgets, QThreadPool, QRunnable, pyqtSlot, uic

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QTimer, QMutex, QThread
from PyQt5 import QtWidgets
from PyQt5.QtGui import QPixmap, QImage

#from PyQt%.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton)

import sys
import camera
import contextlib

import logging

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

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
            logging.debug('Loop')
            self.looper.loop(self)

        self.signalFinished.emit()

    def __enter__(self):
        self._mutex.lock()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._mutex.unlock()

    @pyqtSlot()
    def stop(self):
        logging.info('Stopping')
        with self:
            self._running = False

class VideoHelper:
    def __init__(self, input_device: str, output_device: str):
        if input_device is None:
            input_device = camera.RealCamera.get_default_device()

        if output_device is None:
            output_device = camera.OutputCamera.get_default_device()

        if input_device == output_device:
            raise ValueError

        try:
            self.worker, self.worker_thread = None, None
            self.input_cam, self.output_cam = None, None

            if isinstance(input_device, camera.InputCamera):
                self.input_cam = input_device
            else:
                logging.info("Create input camera")
                self.input_cam = camera.RealCamera(input_device).init()

            if isinstance(output_device, camera.OutputCamera):
                self.output_cam = output_device
            else:
                logging.info("Create output camera")
                self.output_cam = camera.OutputCamera(output_device).init()

            looper = camera.VideoLooper(self.input_cam, self.output_cam)
            self.worker = VideoWorker(looper)
            self.worker_thread = QThread()
            self.worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(self.worker.work)
            self.worker_thread.start()
        except Exception as e:
            self.release()
            raise e

    def release(self):
        if self.worker:
            logging.info("Stop worker")
            self.worker.stop()

        if self.worker_thread:
            logging.info("Quit worker thread")
            self.worker_thread.quit()
            logging.info("Wait on worker thread")
            self.worker_thread.wait()

        if self.input_cam:
            logging.info("Release input camera")
            self.input_cam.release()

        if self.output_cam:
            logging.info("Release output camera")
            self.output_cam.release()

class Ui(QtWidgets.QMainWindow):
    mainthread_callback_to_worker = pyqtSignal()

    def __init__(self):
        super(Ui, self).__init__()
        uic.loadUi('mainWindow.ui', self)

        self.video_button : QtWidgets.QPushButton = self.findChild(QtWidgets.QPushButton, 'videoToggle')
        self.video_button.clicked.connect(self.toggle_video)
        self.video_source : QtWidgets.QComboBox = self.findChild(QtWidgets.QComboBox, 'videoSource')
        self.video_source.activated.connect(self.select_video_source)

        self.worker = None

        self.timer = QTimer()
        self.timer.setInterval(1000. / 5)
        self.timer.timeout.connect(self.render_preview_frame)
        self.timer.start()

        #self.preview : QtWidgets.QGraphicsView = self.findChild(QtWidgets.QGraphicsView, 'previewView')
        self.preview : QtWidgets.QLabel = self.findChild(QtWidgets.QLabel, 'previewView')

        self.video_helper = None

        self.input_device_id, self.input_cam = None, None
        self.update_device_list()

        self.set_input_device(camera.RealCamera.get_default_device())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.video_helper:
            self.video_helper.release()

    def update_device_list(self):
        devices = camera.RealCamera.get_devices()
        default_device = camera.RealCamera.get_default_device()

        self.video_source.addItems(devices)
        if self.video_source.currentIndex() < 0 and default_device in devices:
            self.video_source.setCurrentIndex(devices.index(default_device))

    # https://stackoverflow.com/questions/39235687/when-qcombobox-is-set-editable#39236399
    def select_video_source(self, index = None):
        if self.video_source:
            return

        if index is None:
            self.set_input_device(None)
        else:
            self.set_input_device(self.video_source.itemText(index))

    def set_input_device(self, device_id):
        self.input_device_id = device_id

        if self.input_cam:
            self.input_cam.release()
            self.input_cam = None

        try:
            self.input_cam = camera.RealCamera(self.input_device_id).init()
        except SystemError:
            self.input_cam = None

    def toggle_video(self):
        if self.video_helper:
            if self.input_device_id == self.video_helper.input_cam.device_id:
                self.input_cam = self.video_helper.input_cam
                self.video_helper.input_cam = None

            self.video_helper.release()
            self.video_helper = None
        else:
            try:
                if self.input_cam and self.input_device_id == self.input_cam.device_id:
                    self.input_cam.release()
                    self.input_cam = None

                self.video_helper = VideoHelper(self.input_device_id, None)

                logging.info('Input camera: ' + self.video_helper.input_cam.device_id)
                logging.info('Output camera: ' + self.video_helper.output_cam.device_id)

                self.input_cam = self.video_helper.input_cam
            except ValueError:
                logging.error('Cannot find cameras')
            except SystemError:
                logging.error('Cannot allocate selected camera')

        self.video_button.setText("Start video" if self.video_helper is None else "Stop video")

    def render_preview_frame(self):
        if self.input_cam is None:
            return

        mutex = self.video_helper.worker if self.video_helper else contextlib.nullcontext()
        with mutex:
            data = self.input_cam.read()

        # https://pythonbasics.org/pyqt-qpixmap/
        # https://stackoverflow.com/questions/45018926/how-to-properly-setpixmap-scaled-on-pyqt5#45019730
        # https://stackoverflow.com/questions/40391901/getting-webcam-footage-from-opencv-to-pyqt/42844998
        data = data.transpose((1,0,2)).copy() # bad for performance
        height, width, channels = data.shape
        bpl = 3 * width 
        image = QImage(data, width, height, bpl, QImage.Format_RGB888)
        pix = QPixmap(image)
        self.preview.setPixmap(pix)

app = QtWidgets.QApplication(sys.argv)
with Ui() as window:
    window.show()
    app.exec()
