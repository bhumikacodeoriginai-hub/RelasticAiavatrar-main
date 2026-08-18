"""
Camera Service for continuous video capture.
Manages the webcam/IP camera connection and frame processing pipeline.
"""

import asyncio
import time
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np
import structlog

from config import settings

logger = structlog.get_logger()


class CameraStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    CAPTURING = "capturing"
    ERROR = "error"


@dataclass
class FrameData:
    """Represents a captured frame with metadata."""
    frame: np.ndarray
    timestamp: float
    frame_number: int
    width: int
    height: int

    def to_jpeg(self, quality: int = 85) -> bytes:
        """Convert frame to JPEG bytes."""
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        _, buffer = cv2.imencode('.jpg', self.frame, encode_params)
        return buffer.tobytes()

    def to_base64(self) -> str:
        """Convert frame to base64 string."""
        import base64
        jpeg_bytes = self.to_jpeg()
        return base64.b64encode(jpeg_bytes).decode('utf-8')


class CameraService:
    """
    Manages camera capture and frame distribution.
    Supports both USB webcams and IP cameras.
    """

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30
    ):
        """
        Initialize the camera service.

        Args:
            camera_index: Camera device index (0 for default webcam)
            width: Capture width
            height: Capture height
            fps: Target frames per second
        """
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.cap: Optional[cv2.VideoCapture] = None
        self.status = CameraStatus.DISCONNECTED
        self.frame_count = 0
        self._running = False
        self._latest_frame: Optional[FrameData] = None
        self._frame_callbacks: list = []

    async def start(self) -> bool:
        """Start the camera capture."""
        try:
            self.cap = cv2.VideoCapture(self.camera_index)

            if not self.cap.isOpened():
                logger.error("Failed to open camera", index=self.camera_index)
                self.status = CameraStatus.ERROR
                return False

            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)

            # Read actual properties (camera might not support requested values)
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))

            self.status = CameraStatus.CONNECTED
            self._running = True

            logger.info(
                "Camera started",
                width=actual_width,
                height=actual_height,
                fps=actual_fps
            )
            return True

        except Exception as e:
            logger.error("Error starting camera", error=str(e))
            self.status = CameraStatus.ERROR
            return False

    async def stop(self) -> None:
        """Stop the camera capture."""
        self._running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.status = CameraStatus.DISCONNECTED
        logger.info("Camera stopped")

    async def capture_frame(self) -> Optional[FrameData]:
        """
        Capture a single frame from the camera.

        Returns:
            FrameData object or None if capture failed
        """
        if self.cap is None or not self.cap.isOpened():
            return None

        ret, frame = self.cap.read()
        if not ret:
            logger.warning("Failed to capture frame")
            return None

        self.frame_count += 1
        h, w = frame.shape[:2]

        frame_data = FrameData(
            frame=frame,
            timestamp=time.time(),
            frame_number=self.frame_count,
            width=w,
            height=h
        )

        self._latest_frame = frame_data
        return frame_data

    async def capture_loop(
        self,
        process_interval: float = 0.5
    ) -> None:
        """
        Continuous capture loop that processes frames at specified intervals.
        For real-time processing, set interval based on processing speed.

        Args:
            process_interval: Seconds between processed frames
        """
        self.status = CameraStatus.CAPTURING
        last_process_time = 0

        logger.info("Starting capture loop", interval=process_interval)

        while self._running:
            frame_data = await self.capture_frame()

            if frame_data is None:
                await asyncio.sleep(0.1)
                continue

            current_time = time.time()

            # Process frame at specified interval
            if current_time - last_process_time >= process_interval:
                last_process_time = current_time

                # Notify all registered callbacks
                for callback in self._frame_callbacks:
                    try:
                        await callback(frame_data)
                    except Exception as e:
                        logger.error("Frame callback error", error=str(e))

            # Small sleep to prevent CPU overload
            await asyncio.sleep(1.0 / self.fps)

    def register_callback(
        self, callback: Callable[[FrameData], Awaitable[None]]
    ) -> None:
        """Register a callback for processed frames."""
        self._frame_callbacks.append(callback)

    def get_latest_frame(self) -> Optional[FrameData]:
        """Get the most recently captured frame."""
        return self._latest_frame

    @property
    def is_running(self) -> bool:
        return self._running

    async def capture_single_image(self) -> Optional[np.ndarray]:
        """Capture a single high-quality image (for face registration)."""
        if self.cap is None or not self.cap.isOpened():
            return None

        # Capture multiple frames and use the last one (auto-exposure)
        for _ in range(5):
            ret, frame = self.cap.read()
            await asyncio.sleep(0.05)

        if ret:
            return frame
        return None


class MockCameraService(CameraService):
    """
    Mock camera service for testing without a physical camera.
    Generates synthetic frames or reads from a video file.
    """

    def __init__(self, video_path: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.video_path = video_path

    async def start(self) -> bool:
        """Start with a video file or generate mock frames."""
        if self.video_path:
            self.cap = cv2.VideoCapture(self.video_path)
            if self.cap.isOpened():
                self.status = CameraStatus.CONNECTED
                self._running = True
                logger.info("Mock camera started with video", path=self.video_path)
                return True

        # Generate blank frames for testing
        self.status = CameraStatus.CONNECTED
        self._running = True
        logger.info("Mock camera started (blank frames)")
        return True

    async def capture_frame(self) -> Optional[FrameData]:
        """Capture from video file or generate blank frame."""
        if self.cap and self.cap.isOpened():
            return await super().capture_frame()

        # Generate a blank frame for testing
        self.frame_count += 1
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        return FrameData(
            frame=frame,
            timestamp=time.time(),
            frame_number=self.frame_count,
            width=self.width,
            height=self.height
        )
