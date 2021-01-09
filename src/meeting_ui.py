from PyQt5 import uic
from PyQt5.QtCore import QTimer, QModelIndex, QDate, QDateTime
from PyQt5 import QtWidgets

import logging
import datetime

from meeting import Meeting, MeetingList
from meeting_join import MeetingAutoJoin

class MeetingEditDialog(QtWidgets.QDialog):
    def __init__(self, meeting: Meeting = None):
        super(MeetingEditDialog, self).__init__()
        uic.loadUi('./layout/meetingEditDialog.ui', self)

        self.meeting_id_input : QtWidgets.QLineEdit = self.findChild(QtWidgets.QLineEdit, 'meetingIdInput')
        self.password_input : QtWidgets.QLineEdit = self.findChild(QtWidgets.QLineEdit, 'passwordInput')
        self.name_input : QtWidgets.QLineEdit = self.findChild(QtWidgets.QLineEdit, 'nameInput')

        self.date_time_input : QtWidgets.QDateTimeEdit = self.findChild(QtWidgets.QDateTimeEdit, 'dateTimeEdit')

        if meeting is not None:
            self.meeting_id_input.setText(meeting.meeting_id)
            self.password_input.setText(meeting.password)
            self.name_input.setText(meeting.name)
            datetime = QDateTime(meeting.datetime)
        else:
            datetime = QDateTime.currentDateTime()

        self.date_time_input.setDateTime(datetime)

    def get_fields(self):
        meeting_id = self.meeting_id_input.text()
        password = self.password_input.text()
        name = self.name_input.text()
        datetime = self.date_time_input.dateTime().toPyDateTime()
        return (meeting_id, password, name, datetime)

    def date_time_change(self):
        datetime = self.date_time_input.dateTime()

    def accept(self): # needs return value QDialogCode == int, also doesn't seem to work
        try:
            Meeting(*self.get_fields())
        except ValueError as e:
            return 0

        self.done(1) # close would return 0
        return 1

class MeetingUi:
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

        self.auto_join = MeetingAutoJoin()

        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.auto_join_meeting)
        self.timer.start()

    def auto_join_meeting(self):
        self.auto_join.process(self.model.get_meetings())

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

