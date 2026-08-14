import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

import cv2

CameraType = Literal["webcam", "rtsp"]
CameraState = Literal["stopped", "starting", "running", "reconnecting", "error"]


@dataclass
class CameraConfig:
    id: str
    name: str
    type: CameraType
    source: str
    width: int = 1280
    height: int = 720
    fps: int = 30
    face_detection: bool = False
    reconnect_delay: float = 2.0


@dataclass
class CameraSession:
    config: CameraConfig
    state: CameraState = "stopped"
    capture: cv2.VideoCapture | None = None
    latest_frame: bytes | None = None
    fps: float = 0.0
    frames: int = 0
    started_at: float | None = None
    last_error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    condition: threading.Condition = field(init=False)
    running: bool = False
    thread: threading.Thread | None = None

    def __post_init__(self):
        self.condition = threading.Condition(self.lock)

    def start(self):
        with self.lock:
            if self.running:
                return
            self.running = True
            self.state = "starting"
            self.last_error = None
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def stop(self):
        with self.lock:
            self.running = False
            self.state = "stopped"
            self.condition.notify_all()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self._release_capture()

    def get_frame(self, timeout: float = 1.0) -> bytes | None:
        deadline = time.monotonic() + timeout
        with self.condition:
            while self.latest_frame is None and self.running:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.condition.wait(timeout=remaining)
            return self.latest_frame

    def _open_capture(self) -> cv2.VideoCapture:
        source = int(self.config.source) if self.config.type == "webcam" else self.config.source
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Unable to open camera source: {self.config.source}")

        if self.config.type == "webcam":
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
            capture.set(cv2.CAP_PROP_FPS, self.config.fps)
        return capture

    def _run(self):
        previous = time.monotonic()
        interval_frames = 0

        while self.running:
            try:
                if self.capture is None or not self.capture.isOpened():
                    self._release_capture()
                    with self.lock:
                        self.state = "reconnecting"
                    self.capture = self._open_capture()
                    with self.lock:
                        self.state = "running"
                        self.started_at = time.time()
                        self.last_error = None

                success, frame = self.capture.read()
                if not success:
                    raise RuntimeError("Camera frame read failed")

                if self.config.face_detection:
                    from app.rtsp.face_detector import detect_faces

                    frame = detect_faces(frame)

                encoded, jpeg = cv2.imencode(
                    ".jpg",
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 85],
                )
                if not encoded:
                    continue

                now = time.monotonic()
                interval_frames += 1
                elapsed = now - previous
                if elapsed >= 1.0:
                    with self.lock:
                        self.fps = interval_frames / elapsed
                    interval_frames = 0
                    previous = now

                with self.condition:
                    self.latest_frame = jpeg.tobytes()
                    self.frames += 1
                    self.state = "running"
                    self.condition.notify_all()
            except Exception as exc:
                with self.lock:
                    self.last_error = str(exc)
                    self.state = "reconnecting"
                self._release_capture()
                if self.running:
                    time.sleep(self.config.reconnect_delay)

        self._release_capture()

    def _release_capture(self):
        capture = self.capture
        self.capture = None
        if capture is not None:
            capture.release()

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "id": self.config.id,
                "name": self.config.name,
                "type": self.config.type,
                "source": self.config.source,
                "state": self.state,
                "width": self.config.width,
                "height": self.config.height,
                "target_fps": self.config.fps,
                "fps": round(self.fps, 2),
                "frames": self.frames,
                "face_detection": self.config.face_detection,
                "started_at": self.started_at,
                "last_error": self.last_error,
            }


class CameraManager:
    def __init__(self):
        self._sessions: dict[str, CameraSession] = {}
        self._lock = threading.RLock()

    def add(
        self,
        name: str,
        camera_type: CameraType,
        source: str,
        camera_id: str | None = None,
        **kwargs,
    ) -> CameraSession:
        camera_id = camera_id or str(uuid.uuid4())
        config = CameraConfig(
            id=camera_id,
            name=name,
            type=camera_type,
            source=source,
            **kwargs,
        )
        session = CameraSession(config)
        with self._lock:
            self._sessions[camera_id] = session
        return session

    def get(self, camera_id: str) -> CameraSession | None:
        with self._lock:
            return self._sessions.get(camera_id)

    def list(self) -> list[CameraSession]:
        with self._lock:
            return list(self._sessions.values())

    def remove(self, camera_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(camera_id, None)
        if session is None:
            return False
        session.stop()
        return True

    def discover_webcams(self, max_devices: int = 10) -> list[dict]:
        devices = []
        for index in range(max_devices):
            capture = cv2.VideoCapture(index)
            try:
                if capture.isOpened():
                    devices.append({"index": index, "name": f"Webcam {index}"})
            finally:
                capture.release()
        return devices

    def shutdown(self):
        for session in self.list():
            session.stop()


camera_manager = CameraManager()
