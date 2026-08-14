from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.camera.manager import CameraManager, CameraType, camera_manager

DEFAULT_RTSP_URL = "rtsp://10.208.88.36:8554/cam"


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: CameraType
    source: str = Field(min_length=1)
    width: int = Field(default=1280, ge=160, le=3840)
    height: int = Field(default=720, ge=120, le=2160)
    fps: int = Field(default=30, ge=1, le=120)
    face_detection: bool = False
    reconnect_delay: float = Field(default=2.0, ge=0.5, le=30.0)


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    width: int | None = Field(default=None, ge=160, le=3840)
    height: int | None = Field(default=None, ge=120, le=2160)
    fps: int | None = Field(default=None, ge=1, le=120)
    face_detection: bool | None = None
    reconnect_delay: float | None = Field(default=None, ge=0.5, le=30.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    camera_manager.shutdown()


app = FastAPI(title="VisionFlow", version="0.2.0", lifespan=lifespan)


def frame_stream(camera_id: str):
    session = camera_manager.get(camera_id)
    if session is None:
        return

    session.start()
    try:
        while session.running:
            frame = session.get_frame(timeout=2.0)
            if frame is None:
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Cache-Control: no-cache\r\n\r\n" + frame + b"\r\n"
            )
    finally:
        session.stop()


@app.get("/")
def root():
    return {
        "name": "VisionFlow",
        "version": app.version,
        "message": "Video streaming server aktif",
        "docs": "/docs",
        "cameras": "/api/cameras",
    }


@app.get("/api/cameras")
def list_cameras():
    return [session.snapshot() for session in camera_manager.list()]


@app.post("/api/cameras", status_code=201)
def create_camera(payload: CameraCreate):
    if payload.type == "webcam":
        try:
            device_index = int(payload.source)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Webcam source harus berupa device index") from exc
        if device_index < 0:
            raise HTTPException(status_code=400, detail="Webcam device index tidak boleh negatif")

    session = camera_manager.add(**payload.model_dump())
    return session.snapshot()


@app.get("/api/cameras/discover")
def discover_cameras():
    return {"webcams": camera_manager.discover_webcams()}


@app.get("/api/cameras/{camera_id}")
def get_camera(camera_id: str):
    session = camera_manager.get(camera_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Camera tidak ditemukan")
    return session.snapshot()


@app.patch("/api/cameras/{camera_id}")
def update_camera(camera_id: str, payload: CameraUpdate):
    session = camera_manager.get(camera_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Camera tidak ditemukan")

    updates = payload.model_dump(exclude_unset=True)
    if updates:
        was_running = session.running
        if was_running:
            session.stop()
        for key, value in updates.items():
            setattr(session.config, key, value)
        if was_running:
            session.start()
    return session.snapshot()


@app.delete("/api/cameras/{camera_id}", status_code=204)
def delete_camera(camera_id: str):
    if not camera_manager.remove(camera_id):
        raise HTTPException(status_code=404, detail="Camera tidak ditemukan")


@app.post("/api/cameras/{camera_id}/start")
def start_camera(camera_id: str):
    session = camera_manager.get(camera_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Camera tidak ditemukan")
    session.start()
    return session.snapshot()


@app.post("/api/cameras/{camera_id}/stop")
def stop_camera(camera_id: str):
    session = camera_manager.get(camera_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Camera tidak ditemukan")
    session.stop()
    return session.snapshot()


@app.get("/api/cameras/{camera_id}/stream")
def camera_stream(camera_id: str):
    session = camera_manager.get(camera_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Camera tidak ditemukan")
    return StreamingResponse(
        frame_stream(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/webcam_feed")
def webcam_feed(device: int = 0):
    camera_id = "legacy-webcam"
    session = camera_manager.get(camera_id)
    if session is None:
        session = camera_manager.add(
            name=f"Webcam {device}",
            camera_type="webcam",
            source=str(device),
        )
        session.config.id = camera_id
        camera_manager._sessions[camera_id] = camera_manager._sessions.pop(session.config.id, session)
    return StreamingResponse(
        frame_stream(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/webcam_feed_faces")
def webcam_feed_faces(device: int = 0):
    camera_id = f"legacy-webcam-face-{device}"
    session = camera_manager.get(camera_id)
    if session is None:
        session = camera_manager.add(
            name=f"Webcam {device} Face Detection",
            camera_type="webcam",
            source=str(device),
            face_detection=True,
        )
        camera_manager._sessions[camera_id] = camera_manager._sessions.pop(session.config.id, session)
    return StreamingResponse(
        frame_stream(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/video_feed")
def video_feed():
    camera_id = "legacy-rtsp"
    session = camera_manager.get(camera_id)
    if session is None:
        session = camera_manager.add(
            name="Default RTSP Camera",
            camera_type="rtsp",
            source=DEFAULT_RTSP_URL,
        )
        camera_manager._sessions[camera_id] = camera_manager._sessions.pop(session.config.id, session)
    return StreamingResponse(
        frame_stream(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/video_feed_faces")
def video_feed_faces():
    camera_id = "legacy-rtsp-face"
    session = camera_manager.get(camera_id)
    if session is None:
        session = camera_manager.add(
            name="Default RTSP Face Detection",
            camera_type="rtsp",
            source=DEFAULT_RTSP_URL,
            face_detection=True,
        )
        camera_manager._sessions[camera_id] = camera_manager._sessions.pop(session.config.id, session)
    return StreamingResponse(
        frame_stream(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
