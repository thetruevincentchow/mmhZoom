#from PyQt5 import QtWidgets, QThreadPool, QRunnable, pyqtSlot, uic

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QTimer, QThread
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

# https://www.learnpyqt.com/tutorials/multithreading-pyqt-applications-qthreadpool/
# Bidirctonal callbacks:
#   https://stackoverflow.com/questions/61625043/threading-with-qrunnable-proper-manner-of-sending-bi-directional-callbacks

class Worker(QObject):
    callback_from_worker = pyqtSignal()

    def __init__(self, func, *args, **kwargs):
        super(Worker, self).__init__()
        self._func = func
        self.args = args
        self.kwargs = kwargs
        self.kwargs["signal"] = self.callback_from_worker

    def start_task(self):
        QTimer.singleShot(0, self.task)

    @pyqtSlot()
    def task(self):
        self._func(*self.args, **self.kwargs)

    @pyqtSlot()
    def acknowledge_callback_in_worker(self):
        print("Acknowledged Callback in Worker")
        print(threading.current_thread())

class Ui(QtWidgets.QMainWindow):
    mainthread_callback_to_worker = pyqtSignal()

    def __init__(self):
        super(Ui, self).__init__()
        uic.loadUi('mainWindow.ui', self)

        self.videoButton = self.findChild(QtWidgets.QPushButton, 'videoToggle')
        self.videoButton.clicked.connect(self.start_video)

        #self.input = self.findChild(QtWidgets.QLineEdit, 'input')

        self.timer_label = self.findChild(QtWidgets.QLabel, 'timer_label')

        self._worker = Worker(self.do_something)
        self._worker.callback_from_worker.connect(
            self.acknowledge_callback_in_mainthread_and_respond
        )

        self.worker_thread: QThread = QThread(self)
        self.worker_thread.start()
        self._worker.moveToThread(self.worker_thread)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.worker_thread.quit()
        self.worker_thread.wait()

    @pyqtSlot()
    def start_video(self, signal):
        # signal argument will be the callback_from_worker and it will emit to acknowledge_callback_in_mainthread
        print("do_something is sleeping briefly. Try to see if you get a locked widget...")
        with camera.RealCamera("/dev/video0") as input_cam:
            with camera.OutputCamera() as output_cam:
                camera.VideoLooper(input_cam, output_cam).loop()
        signal.emit()

    @pyqtSlot()
    def acknowledge_callback_in_mainthread_and_respond(self):
        # this function should respond to callback_from_worker and emit a response
        print("Acknowledged Callback in Main")
        self.mainthread_callback_to_worker.emit()

    def thread_example(self):
        print("Beginning thread example")
        worker = RespondedToWorker(self.do_something)
        worker.signals.callback_from_worker.connect(self.acknowledge_callback_in_mainthread_and_respond)
    # self.mainthread_callback_to_worker.connect(worker.acknowledge_callback_in_worker) # <-- causes crash

    def recurring_timer(self):
        self.counter += 1
        self.timer_label.setText(f"Counter: {self.counter}")


app = QtWidgets.QApplication(sys.argv)
with Ui() as window:
    window.show()
    app.exec()
