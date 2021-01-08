from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QTimer, QMutex, QThread, QModelIndex
from PyQt5 import QtWidgets, QtSvg, QtGui
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPalette

import sys
import contextlib
import logging
import string
import json
import pathlib
import xdg

class Meeting:
    @staticmethod
    def format_meeting_id(meeting_id):
        meeting_id = meeting_id.replace(" ", "")
        if not (set(meeting_id) <= set(string.digits)):
            raise ValueError("Incorrect meeting ID format")
        if len(meeting_id) == 0:
            raise ValueError("Meeting ID cannot be empty")
        return meeting_id

    @staticmethod
    def format_password(password):
        if not (set(password) <= set(string.ascii_letters + string.digits)):
            raise ValueError("Incorrect password format")

        return password

    def __init__(self, meeting_id: str, password: str, name: str):
        self.meeting_id = Meeting.format_meeting_id(meeting_id)
        self.password = Meeting.format_password(password)
        self.name = name

    def __str__(self):
        r = [("ID", self.meeting_id), ("password", self.password)]
        r = ", ".join("%s %s" % (k,v) for k,v in r if len(v))
        if self.name:
            r = "%s (%s)" % (self.name, r)
        return r

class MeetingEditDialog(QtWidgets.QDialog):
    def __init__(self, meeting: Meeting = None):
        super(MeetingEditDialog, self).__init__()
        uic.loadUi('meetingEditDialog.ui', self)

        self.meeting_id_input : QtWidgets.QLineEdit = self.findChild(QtWidgets.QLineEdit, 'meetingIdInput')
        self.password_input : QtWidgets.QLineEdit = self.findChild(QtWidgets.QLineEdit, 'passwordInput')
        self.name_input : QtWidgets.QLineEdit = self.findChild(QtWidgets.QLineEdit, 'nameInput')

        if meeting is not None:
            self.meeting_id_input.setText(meeting.meeting_id)
            self.password_input.setText(meeting.password)
            self.name_input.setText(meeting.name)

    def get_fields(self):
        meeting_id = self.meeting_id_input.text()
        password = self.password_input.text()
        name = self.name_input.text()
        return (meeting_id, password, name)

    def accept(self): # needs return value QDialogCode == int, also doesn't seem to work
        try:
            Meeting(*self.get_fields())
        except ValueError as e:
            return 0

        self.done(1) # close would return 0
        return 1

class MeetingList:
    def __init__(self, meetings = None):
        if meetings is None:
            meetings = []

        self.meetings = meetings

    @staticmethod
    def get_default_path() -> pathlib.Path:
        return xdg.XDG_CONFIG_HOME / 'mmhZoom' / 'meetings.json'

    @staticmethod
    def load_from_file(path = None):
        if path is None:
            path: pathlib.Path = MeetingList.get_default_path()

        with open(path, "r") as f:
            tree = json.load(f)

        return MeetingList([Meeting(*x) for x in tree])

    def save(self, path = None):
        if path is None:
            path = MeetingList.get_default_path()
            path.parent.mkdir(parents = True, exist_ok = True)

        tree = [(x.meeting_id, x.password, x.name) for x in self.meetings]
        tree = json.dumps(tree)
        with open(path, "w") as f:
            f.write(tree)

    def get_meetings(self):
        return self.meetings

    def get_index(self, index):
        return self.meetings[index]

    def add_meeting(self, meeting):
        self.meetings.append(meeting)

    def replace_index(self, index, meeting):
        self.meetings[index] = meeting

    def remove_index(self, index):
        del self.meetings[index]

    def __repr__(self):
        return "MeetingList<#%d>" % (len(self.meetings))

class MeetingUi:
    mainthread_callback_to_worker = pyqtSignal()
    
    def __init__(self, window: QtWidgets.QMainWindow, meeting_tab: QtWidgets.QWidget):

        self.add_meeting_button : QtWidgets.QPushButton = meeting_tab.findChild(QtWidgets.QPushButton, 'addMeeting')
        self.add_meeting_button.clicked.connect(self.add_meeting)

        self.remove_meeting_button : QtWidgets.QPushButton = meeting_tab.findChild(QtWidgets.QPushButton, 'removeMeeting')
        self.remove_meeting_button.clicked.connect(self.remove_meeting)

        self.meeting_list: QtWidgets.QListWidget = meeting_tab.findChild(QtWidgets.QListWidget, 'meetingList')
        self.meeting_list.itemActivated.connect(self.select_meeting_item)

        self.status_bar : QtWidgets.QStatusBar = window.findChild(QtWidgets.QStatusBar, 'statusBar')

        self.model = MeetingList.load_from_file()
        self.update_meeting_list()

    def update_meeting_list(self):
        self.meeting_list.clear()
        self.meeting_list.addItems(list(map(str, self.model.get_meetings())))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def add_meeting(self):
        dialog = MeetingEditDialog()
        if dialog.exec_():
            try:
                self.model.add_meeting(Meeting(*dialog.get_fields()))
                self.model.save()
                self.update_meeting_list()
            except ValueError as e:
                pass


    def remove_meeting(self):
        index = self.meeting_list.currentRow()
        if index < 0:
            return

        self.model.remove_index(index)
        self.model.save()
        self.update_meeting_list()

    def select_meeting_item(self):
        index = self.meeting_list.currentRow()
        if index < 0:
            return

        meeting = self.model.get_index(index)

        dialog = MeetingEditDialog(meeting)
        if dialog.exec_():
            try:
                new_meeting = Meeting(*dialog.get_fields())
                self.model.replace_index(index, new_meeting)
                self.model.save()
                self.update_meeting_list()
            except ValueError: pass

