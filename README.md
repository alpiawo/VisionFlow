# VisionFlow

VisionFlow is a FastAPI + OpenCV video streaming service that can receive frames from a laptop webcam, an external USB webcam, or an RTSP camera and expose them as browser-compatible MJPEG streams.

## Features

- Laptop webcam streaming
- External USB webcam streaming
- RTSP camera streaming
- Optional real-time face detection
- Configurable webcam device index
- Browser-compatible MJPEG output

## Project Structure

```text
project-root/
├── app/
│   ├── rtsp/
│   │   ├── camera_rtsp.py
│   │   ├── face_detector.py
│   │   └── main.py
│   └── webcam/
│       ├── __init__.py
│       └── camera.py
├── models/
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.9+
- OpenCV
- FastAPI
- Uvicorn
- A laptop webcam or USB webcam

Create a virtual environment and install dependencies:

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

```bash
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.rtsp.main:app --host 0.0.0.0 --port 8000
```

Open the stream in a browser or use it as an MJPEG source:

- Laptop/default webcam: `http://127.0.0.1:8000/webcam_feed?device=0`
- External webcam: `http://127.0.0.1:8000/webcam_feed?device=1`
- Webcam + face detection: `http://127.0.0.1:8000/webcam_feed_faces?device=0`
- RTSP stream: `http://127.0.0.1:8000/video_feed`
- RTSP + face detection: `http://127.0.0.1:8000/video_feed_faces`

## Webcam Device Index

OpenCV normally exposes the integrated laptop camera as device `0`. An external USB camera is commonly device `1`, but the actual index depends on the operating system and connected devices.

If the external camera is not available at index `1`, try another index such as `2` or `3`.

## Architecture

The webcam is captured directly by OpenCV on the machine running VisionFlow. Frames are encoded as JPEG and continuously returned by FastAPI using `multipart/x-mixed-replace`. This makes the stream directly viewable in a browser without a separate frontend or WebSocket client.

Face detection can be enabled by using the `_faces` endpoint. The existing OpenCV SSD face detection model in `models/` is reused for this processing pipeline.
