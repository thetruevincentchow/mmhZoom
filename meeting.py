import string
import datetime
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

    def __iter__(self):
        return iter((self.meeting_id, self.password, self.name, self.datetime.isoformat()))

    def __init__(self, meeting_id: str, password: str, name: str, _datetime: datetime.datetime):
        if type(_datetime) is str:
            _datetime = datetime.datetime.fromisoformat(_datetime)

        self.meeting_id = Meeting.format_meeting_id(meeting_id)
        self.password = Meeting.format_password(password)
        self.name = name
        self.datetime = _datetime

    def __str__(self):
        r = [("ID", self.meeting_id), ("password", self.password)]
        r = ", ".join("%s %s" % (k,v) for k,v in r if len(v))
        if self.name:
            r = "%s (%s)" % (self.name, r)
        return r

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

        try:
            with open(path, "r") as f:
                tree = json.load(f)
            return MeetingList([Meeting(*x) for x in tree])
        except (FileNotFoundError, json.JSONDecodeError):
            return MeetingList()
        except ValueError:
            return MeetingList()

    def save(self, path = None):
        if path is None:
            path = MeetingList.get_default_path()
            path.parent.mkdir(parents = True, exist_ok = True)

        tree = [tuple(x) for x in self.meetings]
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
