import threading
import time

import cv2

from app.rtsp.face_detector import detect_faces


class WebcamCamera:
    def __init__(self, device_index=0, use_face_detection=False):
        self.device_index = device_index
        self.use_face_detection = use_face_detection
        self.capture = cv2.VideoCapture(device_index)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.capture.set(cv2.CAP_PROP_FPS, 30)
        self.lock = threading.Lock()
        self.frame = None
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return
        if not self.capture.isOpened():
            raise RuntimeError(f"Unable to open webcam device {self.device_index}")
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _capture_loop(self):
        while self.running:
            success, frame = self.capture.read()
            if not success:
                time.sleep(0.05)
                continue

            if self.use_face_detection:
                frame = detect_faces(frame)

            success, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if success:
                with self.lock:
                    self.frame = jpeg.tobytes()

    def get_frame(self):
        with self.lock:
            return self.frame

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)
        self.capture.release()
