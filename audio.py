import alsaaudio

class Audio:
    def __init__(self):
        self.recording_mixer = self.get_default_mixer()
        self.should_capture = False

    def set_capture(self, rec = True):
        self.recording_mixer.setrec(rec)
        self.should_capture = rec

    def is_capturing(self):
        return self.recording_mixer.getrec()[0] != 0

    @staticmethod
    def test_mixer(name):
        mixer = alsaaudio.Mixer(name)
        try:
            mixer.getrec()
            return mixer
        except:
            return

    def get_recording_mixers(self):
        all_mixers = alsaaudio.mixers()
        mixers = [(name, Audio.test_mixer(name)) for name in all_mixers]
        mixers = [(name, mixer) for name, mixer in mixers if mixer]
        return dict(mixers)

    def get_default_mixer(self):
        mixers = self.get_recording_mixers()
        m = mixers.get('Capture')
        if m is not None: return m
        return next(iter(mixers.values()))
