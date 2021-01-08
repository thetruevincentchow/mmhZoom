from meeting import Meeting
from typing import List
import datetime
import logging
import webbrowser

meeting_endpoint = "https://zoom.us/j/{meeting_id}"

def join_meeting(meeting: Meeting):
    url = meeting_endpoint.format(meeting_id = meeting.meeting_id)
    logging.info("Open URL %s" % url)
    webbrowser.open(url)

    # TODO: support password-protected meetings


class MeetingAutoJoin:
    def __init__(self):
        self.last_checked = None

    def process(self, meetings: List[Meeting]):
        now = datetime.datetime.now()
        assert (self.last_checked is None) or (self.last_checked < now)

        for meeting in meetings:
            if self.last_checked is None:
                continue
            if self.last_checked >= meeting.datetime:
                continue
            if meeting.datetime >= now:
                continue

            logging.info("Auto-join %s" % meeting)
            join_meeting(meeting)

        self.last_checked = now
