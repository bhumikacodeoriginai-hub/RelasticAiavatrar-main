"""
Person Detection using YOLO (You Only Look Once).
Detects whether the object in frame is actually a human/person,
filtering out chairs, bags, laptops, etc.
"""

import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class DetectedPerson:
    """Represents a detected person in a frame."""
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    class_id: int
    center: Tuple[int, int]
    area: int

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]


class PersonDetector:
    """
    YOLO-based person detector.
    Only detects humans/persons, ignoring other objects like chairs, bags, laptops.
    """

    # COCO class ID for "person" is 0
    PERSON_CLASS_ID = 0

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.5,
        device: str = "cpu"
    ):
        """
        Initialize the person detector.

        Args:
            model_path: Path to YOLO model weights
            confidence_threshold: Minimum confidence for detection
            device: Device to run inference on ('cpu' or 'cuda')
        """
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.model = None
        self.model_path = model_path
        self._initialized = False

    async def initialize(self) -> None:
        """Load the YOLO model."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            self._initialized = True
            logger.info(
                "Person detector initialized",
                model=self.model_path,
                device=self.device
            )
        except ImportError:
            logger.warning("ultralytics not installed - person detection disabled")
            logger.warning("Install with: pip install ultralytics")
            self._initialized = False
        except Exception as e:
            logger.error("Failed to initialize person detector", error=str(e))
            self._initialized = False

    def detect(self, frame: np.ndarray) -> List[DetectedPerson]:
        """
        Detect persons in a video frame.

        Args:
            frame: BGR image as numpy array (from OpenCV)

        Returns:
            List of DetectedPerson objects
        """
        if not self._initialized:
            logger.warning("Person detector not initialized")
            return []

        try:
            # Run YOLO inference
            results = self.model(
                frame,
                conf=self.confidence_threshold,
                classes=[self.PERSON_CLASS_ID],  # Only detect persons
                device=self.device,
                verbose=False
            )

            detections = []
            for result in results:
                if result.boxes is None:
                    continue

                for box in result.boxes:
                    # Extract bounding box coordinates
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    confidence = float(box.conf[0])
                    class_id = int(box.cls[0])

                    # Calculate center point
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2

                    # Calculate area
                    area = (x2 - x1) * (y2 - y1)

                    detection = DetectedPerson(
                        bbox=(x1, y1, x2, y2),
                        confidence=confidence,
                        class_id=class_id,
                        center=(center_x, center_y),
                        area=area
                    )
                    detections.append(detection)

            # Sort by area (largest person first - likely closest to camera)
            detections.sort(key=lambda d: d.area, reverse=True)

            if detections:
                logger.debug(
                    "Persons detected",
                    count=len(detections),
                    best_confidence=detections[0].confidence
                )

            return detections

        except Exception as e:
            logger.error("Error during person detection", error=str(e))
            return []

    def is_person_at_entrance(
        self,
        detections: List[DetectedPerson],
        frame_width: int,
        min_area_ratio: float = 0.02
    ) -> bool:
        """
        Determine if a person is standing at the entrance (close enough to camera).

        Args:
            detections: List of detected persons
            frame_width: Width of the frame
            min_area_ratio: Minimum bbox area relative to frame area

        Returns:
            True if a person is at the entrance
        """
        if not detections:
            return False

        frame_area = frame_width * frame_width  # approximate
        for det in detections:
            area_ratio = det.area / frame_area
            if area_ratio >= min_area_ratio:
                return True

        return False

    def get_closest_person(
        self, detections: List[DetectedPerson]
    ) -> Optional[DetectedPerson]:
        """Get the person closest to the camera (largest bounding box)."""
        if not detections:
            return None
        return detections[0]  # Already sorted by area
