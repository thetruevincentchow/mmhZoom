#from PyQt5 import QtWidgets, QThreadPool, QRunnable, pyqtSlot, uic

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QTimer, QMutex, QThread
from PyQt5 import QtWidgets, QtSvg, QtGui
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPalette

#from PyQt%.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton)

import sys
import contextlib
import logging

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

import camera
import audio

# https://www.learnpyqt.com/tutorials/multithreading-pyqt-applications-qthreadpool/
# Bidirctonal callbacks:
#   https://stackoverflow.com/questions/61625043/threading-with-qrunnable-proper-manner-of-sending-bi-directional-callbacks

class VideoWorker(QObject):
    signalFinished = pyqtSignal()
    signalLoopStatus = pyqtSignal([bool])

    def __init__(self, looper: camera.VideoLooper):
        super(QObject, self).__init__()
        self._mutex = QMutex()
        self._running = True
        self.looper = looper
        self.can_loop = looper.can_loop

    @pyqtSlot()
    def work(self):
        while self._running:
            logging.debug('Loop')
            self.looper.loop()

            if self.looper.can_loop != self.can_loop:
                self.can_loop = self.looper.can_loop
                self.signalLoopStatus.emit(self.can_loop)

        self.signalFinished.emit()

    def set_looping(self, value: bool):
        self.looper.is_looping = value

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
    def __init__(self, input_device: str, output_device: str, ui: 'Ui'):
        self.ui = ui

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
            self.worker.signalLoopStatus.connect(self.update_loop_button)

            self.worker_thread = QThread()
            self.worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(self.worker.work)
            self.worker_thread.start()
        except Exception as e:
            self.release()
            raise e

    def update_loop_button(self, can_loop):
        self.ui.update_loop_button() #can_loop)

    def set_looping(self, value: bool):
        self.worker.set_looping(value)

    def can_loop(self):
        return self.worker.can_loop

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


class VideoUi:
    mainthread_callback_to_worker = pyqtSignal()
    
    preview_fps = 5.0

    def __init__(self, window: QtWidgets.QMainWindow, video_tab: QtWidgets.QWidget):
        self.video_button : QtWidgets.QPushButton = video_tab.findChild(QtWidgets.QPushButton, 'videoToggle')
        self.video_button.clicked.connect(self.toggle_video)

        self.speak_button : QtWidgets.QPushButton = video_tab.findChild(QtWidgets.QPushButton, 'speakToggle')
        self.speak_button.clicked.connect(self.toggle_speak)

        self.loop_button : QtWidgets.QPushButton = video_tab.findChild(QtWidgets.QPushButton, 'loopToggle')
        self.loop_button.clicked.connect(self.toggle_loop)

        self.video_source : QtWidgets.QComboBox = video_tab.findChild(QtWidgets.QComboBox, 'videoSource')
        self.video_source.activated.connect(self.select_video_source)

        self.status_bar : QtWidgets.QStatusBar = window.findChild(QtWidgets.QStatusBar, 'statusBar')

        self.worker = None

        self.timer = QTimer()
        self.timer.setInterval(1000 // self.preview_fps)
        self.timer.timeout.connect(self.render_preview_frame)
        self.timer.start()

        #self.preview : QtWidgets.QGraphicsView = video_tab.findChild(QtWidgets.QGraphicsView, 'previewView')
        self.preview : QtWidgets.QLabel = video_tab.findChild(QtWidgets.QLabel, 'previewView')

        self.video_helper = None

        self.input_device_id, self.input_cam = None, None
        self.update_device_list()

        self.set_input_device(camera.RealCamera.get_default_device())

        self.audio : audio.Audio = audio.Audio()

        self.update_loop_button()

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
        if self.video_helper:
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
            self.status_bar.showMessage('Ending video feed')
        else:
            try:
                if self.input_cam and self.input_device_id == self.input_cam.device_id:
                    self.input_cam.release()
                    self.input_cam = None

                self.video_helper = VideoHelper(self.input_device_id, None, self)

                logging.info('Input camera: ' + self.video_helper.input_cam.device_id)
                logging.info('Output camera: ' + self.video_helper.output_cam.device_id)

                self.input_cam = self.video_helper.input_cam
                self.status_bar.showMessage('Starting video feed')
            except ValueError:
                logging.error('Cannot find cameras')
                self.status_bar.showMessage('Error: Cannot find cameras')
            except SystemError:
                logging.error('Cannot allocate selected camera')
                self.status_bar.showMessage('Error: Cannot allocate selected camera')

        self.video_source.setEnabled(not self.video_helper)
        self.video_button.setText("Start video" if self.video_helper is None else "Stop video")
        self.video_button.setChecked(self.video_helper is not None)

    def set_capture(self, value: bool):
        self.audio.set_capture(value)
        self.speak_button.setChecked(value)

    def toggle_speak(self):
        #is_capturing = not self.audio.is_capturing()
        is_capturing = not self.audio.should_capture
        self.set_capture(is_capturing)

        if is_capturing:
            self.status_bar.showMessage('Enabled microphone, disabled capturing')
            self.set_looping(False)
        else:
            self.status_bar.showMessage('Disbaled microphone')

    def update_loop_button(self):
        if self.video_helper and self.video_helper.can_loop():
            self.loop_button.setEnabled(True)
        else:
            self.loop_button.setEnabled(False)
            self.loop_button.setChecked(False)

    def set_looping(self, value: bool):
        self.loop_button.setChecked(value)
        self.update_loop_button()

        if self.video_helper:
            self.video_helper.set_looping(self.loop_button.isChecked())

    def toggle_loop(self):
        if self.video_helper is None:
            self.loop_button.setChecked(False)
            return

        # TODO: clean up
        is_looping = self.loop_button.isChecked()
        if is_looping:
            self.status_bar.showMessage('Enabled looping, disabled microphone')
            self.set_capture(False)
        else:
            self.status_bar.showMessage('Disabled looping')

        self.set_looping(is_looping)


    def render_preview_frame(self):
        if self.input_cam is None:
            widget = self.preview
            #widget.setGeometry(50,200,500,500)
            #renderer =  QtSvg.QSvgRenderer('./assets/no-video.svg')
            #widget.resize(renderer.defaultSize())
            #painter = QPainter(widget)
            #painter.restore()
            #renderer.render(painter)
            #widget.show()

            image = QImage(100, 100, QImage.Format_RGB888)
            image.fill(0)
            pix = QPixmap(image)
            self.preview.setPixmap(pix)

            # https://wiki.qt.io/How_to_Change_the_Background_Color_of_QWidget

            # No border
            #pal = QPalette()
            #pal.setColor(QPalette.Background, QtGui.QColor(0, 0, 0, 0))
            #self.video_button.setPalette(pal)
            return

        if self.video_helper:
            data = self.input_cam.read_recent_frame() # ugly hack
        else:
            data = self.input_cam.read()

        if data is None:
            return

        # Red border
        #pal = QPalette()
        #pal.setColor(QPalette.Background, QtGui.QColor(255, 0, 0))
        #self.video_button.setPalette(pal)

        # https://pythonbasics.org/pyqt-qpixmap/
        # https://stackoverflow.com/questions/45018926/how-to-properly-setpixmap-scaled-on-pyqt5#45019730
        # https://stackoverflow.com/questions/40391901/getting-webcam-footage-from-opencv-to-pyqt/42844998
        data = data[::2, ::2, :] # downscale
        data = data.transpose((1,0,2)).copy() # bad for performance
        height, width, channels = data.shape
        bpl = 3 * width 
        image = QImage(data, width, height, bpl, QImage.Format_RGB888)
        pix = QPixmap(image)
        self.preview.setPixmap(pix)

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
