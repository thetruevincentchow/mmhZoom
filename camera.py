import math
import logging
import numpy as np
import time
import abc

# unfortunately, OpenCV is incompatible with PyQt5, so pyfakewebcam will suffer degraded performance
#import cv2
import pygame
import pygame.camera

pygame.init()
pygame.camera.init()

import pyfakewebcam

import contextlib
import threading

import itertools as it

class InputCamera(abc.ABC):
    pass

class RealCamera(InputCamera):
    def __init__(self, device_id, size = (640,480)):
        #if device_id is None:
        #    device_id = RealCamera.get_default_device()

        self.size = size
        self.device_id = device_id

        # create a display surface. standard pygame stuff
        #self.display = pygame.display.set_mode(self.size, 0)
        self._mutex = threading.Lock()
        self.last_frame = None

    @staticmethod
    def get_devices():
        devices = pygame.camera.list_cameras()
        fake_device_id = OutputCamera.get_default_device()
        return [device_id for device_id in devices if device_id != fake_device_id]

    @staticmethod
    def get_default_device():
        devices = RealCamera.get_devices()
        if len(devices) == 0:
            raise ValueError("No camera available")
        return devices[0]

    def read(self):
        with self._mutex:
            # https://stackoverflow.com/questions/39003106/python-access-camera-without-opencv?noredirect=1&lq=1
            frame : pygame.Surface = self.vid.get_image()
            frame : np.array = pygame.surfarray.array3d(frame) # slow :(

            #ret, frame = self.vid.read()
            #if not ret: return None

            self.last_frame = frame

            return frame

            #rgb_frame = frame[:,:,[2,1,0]] # BGR to RGB color conversion
            #return rgb_frame

    def read_transposed(self):
        return np.transpose(self.read(), (1,0,2))

    def read_recent_frame(self):
        with self._mutex:
            if self.last_frame is None:
                ret = None
            else:
                ret = self.last_frame.copy()
        return ret

    def skip(self, n_frames):
        for i in range(n_frames):
            self.vid.read()

    def init(self):
        self.vid = pygame.camera.Camera(self.device_id, self.size)
        self.vid.start()

        # create a surface to capture to.  for performance purposes
        # bit depth is the same as that of the display surface.
        #self.snapshot = pygame.surface.Surface(self.size, 0, self.display)

        #self.vid: VideoCapture = cv2.VideoCapture(self.device_id)
        return self

    def __enter__(self): 
        self.init()
        return self

    def release(self):
        self.vid.stop()
        #self.vid.release() # OpenCV

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def __repr__(self):
        return "RealCamera(%r)" % (self.device_id, )

class OutputCamera:
    @staticmethod
    def get_default_device():
        return '/dev/video2' # TODO: dynamically allocate device

    def __init__(self, device_id = None, size = (640,480)):
        #if device_id is None:
        #    device_id = OutputCamera.find_output_video_device()

        self.size = size
        self.device_id = device_id

    def init(self):
        self.vid = pyfakewebcam.FakeWebcam(self.device_id, self.size[0], self.size[1])
        return self

    def __enter__(self):
        self.init()
        return self

    def release(self):
        del self.vid
        #self.vid.release()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def write(self, frame: np.array):
        self.vid.schedule_frame(np.transpose(frame, (1,0,2)))

class CycleLoop:
    def __init__(self, n):
        self.n = n
    def __len__(self):
        return self.n
    def __iter__(self):
        return it.cycle(range(self.n))

class VideoLooper:
    num_seconds = 2
    fps = 15.0
    frame_delay = 1 / fps

    buffer_capacity = math.ceil(fps * num_seconds)
    #skip_frames = 10
    #freeze_frames = round(fps * 1)

    def __init__(self, input_camera: InputCamera, output_camera: OutputCamera):
        self.input_camera = input_camera
        self.output_camera = output_camera
        self.buffer = []

        self._can_gather = True
        self._looping = False

        self._generator = iter(CycleLoop(self.buffer_capacity))

    def get_gather(self):
        return self._can_gather

    def set_gather(self, value: bool):
        self._can_gather = value

    def get_looping(self):
        if not self.can_loop:
            self._looping = False
        return self._looping

    def set_looping(self, value: bool):
        value = value and self.can_loop
        self._looping = value

    can_gather: bool = property(get_gather, set_gather) # unused, is_looping excludes frame gathering
    is_looping: bool = property(get_looping, set_looping)

    @property
    def can_loop(self):
        return len(self.buffer) >= self.buffer_capacity

    def read_frames(self):
        start_time = time.time()
        frame = self.input_camera.read()
        end_time = time.time()
        yield frame, end_time - start_time

    def add_frame(self, frame):
        self.buffer.append(frame)
        if len(self.buffer) > self.buffer_capacity:
            del self.buffer[0] # TODO: replace with deque

        logging.debug("Gather frame %d / %d" % (len(self.buffer), self.buffer_capacity))

    def loop(self):
        if self.is_looping:
            frame_index = next(self._generator)
            frame = self.buffer[frame_index]
            self.output_camera.write(frame)
            time.sleep(self.frame_delay)
        else:
            for frame, capture_delay in self.read_frames():
                if frame is not None:
                    self.output_camera.write(frame)
                    if self.can_gather:
                        self.add_frame(frame)

                delay = max(0., self.frame_delay - capture_delay)
                logging.debug("%r %r %r" % (delay, self.frame_delay, capture_delay))
                time.sleep(delay)


if __name__ == "__main__":
    with RealCamera("/dev/video0") as input_cam:
        with OutputCamera() as output_cam:
            VideoLooper(input_cam, output_cam).loop()
