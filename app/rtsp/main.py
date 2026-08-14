import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.rtsp.camera_rtsp import CameraRTSP
from app.webcam.camera import WebcamCamera

app = FastAPI(title="VisionFlow")

camera_url = "rtsp://10.208.88.36:8554/cam"


def generate_rtsp_frames(use_face_detection=False):
    cam = CameraRTSP(camera_url, use_face_detection=use_face_detection)
    try:
        while True:
            frame = cam.get_frame()
            if frame is None:
                break
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
    finally:
        cam.cap.release()


def get_webcam(device: int, use_face_detection: bool):
    cam = WebcamCamera(device, use_face_detection=use_face_detection)
    cam.start()
    return cam


def generate_webcam_frames(device: int, use_face_detection=False):
    cam = get_webcam(device, use_face_detection)
    try:
        while True:
            frame = cam.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Cache-Control: no-cache\r\n\r\n" + frame + b"\r\n"
            )
    finally:
        cam.stop()


@app.get("/")
def root():
    return {
        "name": "VisionFlow",
        "message": "Video streaming server aktif",
        "webcam": "/webcam_feed?device=0",
        "webcam_face_detection": "/webcam_feed_faces?device=0",
        "rtsp": "/video_feed",
    }


@app.get("/webcam_feed")
def webcam_feed(device: int = Query(0, ge=0, le=10)):
    try:
        camera = WebcamCamera(device)
        if not camera.capture.isOpened():
            camera.stop()
            raise HTTPException(status_code=404, detail=f"Webcam device {device} tidak dapat dibuka")
        camera.stop()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return StreamingResponse(
        generate_webcam_frames(device),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/webcam_feed_faces")
def webcam_feed_faces(device: int = Query(0, ge=0, le=10)):
    return StreamingResponse(
        generate_webcam_frames(device, use_face_detection=True),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/video_feed")
def video_feed():
    return StreamingResponse(
        generate_rtsp_frames(False),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/video_feed_faces")
def video_feed_faces():
    return StreamingResponse(
        generate_rtsp_frames(True),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
