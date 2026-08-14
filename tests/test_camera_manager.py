from app.camera.manager import CameraManager


def test_camera_manager_registers_and_removes_camera():
    manager = CameraManager()
    session = manager.add(
        name="Test Webcam",
        camera_type="webcam",
        source="0",
    )

    assert manager.get(session.config.id) is session
    assert session.snapshot()["type"] == "webcam"
    assert session.snapshot()["source"] == "0"

    assert manager.remove(session.config.id) is True
    assert manager.get(session.config.id) is None
