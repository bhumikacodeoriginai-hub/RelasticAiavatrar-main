"""
Face Detection module using InsightFace.
Detects faces within person bounding boxes and extracts face regions.
"""

import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class DetectedFace:
    """Represents a detected face in a frame."""
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    landmarks: Optional[np.ndarray] = None  # 5 facial landmarks
    face_image: Optional[np.ndarray] = None  # Cropped face region
    aligned_face: Optional[np.ndarray] = None  # Aligned face for embedding
    age: Optional[int] = None
    gender: Optional[str] = None

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]

    @property
    def center(self) -> Tuple[int, int]:
        return (
            (self.bbox[0] + self.bbox[2]) // 2,
            (self.bbox[1] + self.bbox[3]) // 2
        )


class FaceDetector:
    """
    Face detection using InsightFace (RetinaFace backbone).
    Provides high-accuracy face detection with landmark extraction.
    """

    def __init__(
        self,
        model_name: str = "buffalo_l",
        det_size: Tuple[int, int] = (640, 640),
        det_threshold: float = 0.5,
        max_faces: int = 10
    ):
        """
        Initialize the face detector.

        Args:
            model_name: InsightFace model pack name
            det_size: Detection input size
            det_threshold: Detection confidence threshold
            max_faces: Maximum number of faces to detect
        """
        self.model_name = model_name
        self.det_size = det_size
        self.det_threshold = det_threshold
        self.max_faces = max_faces
        self.app = None
        self._initialized = False

    async def initialize(self) -> None:
        """Load the InsightFace model."""
        try:
            import insightface
            from insightface.app import FaceAnalysis

            self.app = FaceAnalysis(
                name=self.model_name,
                providers=['CPUExecutionProvider']
            )
            self.app.prepare(
                ctx_id=0,
                det_size=self.det_size,
                det_thresh=self.det_threshold
            )
            self._initialized = True
            logger.info(
                "Face detector initialized",
                model=self.model_name,
                det_size=self.det_size
            )
        except ImportError:
            logger.warning("insightface not installed - face detection disabled")
            self._initialized = False
        except Exception as e:
            logger.error("Failed to initialize face detector", error=str(e))
            self._initialized = False

    def detect_faces(self, frame: np.ndarray) -> List[DetectedFace]:
        """
        Detect all faces in a frame.

        Args:
            frame: BGR image as numpy array

        Returns:
            List of DetectedFace objects
        """
        if not self._initialized:
            logger.warning("Face detector not initialized")
            return []

        try:
            # InsightFace expects BGR format (OpenCV default)
            faces = self.app.get(frame)

            # Limit number of faces
            faces = faces[:self.max_faces]

            detections = []
            for face in faces:
                bbox = tuple(map(int, face.bbox))
                x1, y1, x2, y2 = bbox

                # Ensure coordinates are within frame
                h, w = frame.shape[:2]
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(w, x2)
                y2 = min(h, y2)

                # Crop face region
                face_image = frame[y1:y2, x1:x2].copy()

                detected = DetectedFace(
                    bbox=(x1, y1, x2, y2),
                    confidence=float(face.det_score),
                    landmarks=face.kps if hasattr(face, 'kps') else None,
                    face_image=face_image,
                    age=int(face.age) if hasattr(face, 'age') else None,
                    gender="male" if hasattr(face, 'gender') and face.gender == 1 else "female" if hasattr(face, 'gender') else None
                )
                detections.append(detected)

            # Sort by confidence
            detections.sort(key=lambda d: d.confidence, reverse=True)

            if detections:
                logger.debug(
                    "Faces detected",
                    count=len(detections),
                    best_confidence=detections[0].confidence
                )

            return detections

        except Exception as e:
            logger.error("Error during face detection", error=str(e))
            return []

    def detect_faces_in_region(
        self,
        frame: np.ndarray,
        region: Tuple[int, int, int, int]
    ) -> List[DetectedFace]:
        """
        Detect faces within a specific region (e.g., person bounding box).

        Args:
            frame: Full frame
            region: (x1, y1, x2, y2) region to search

        Returns:
            List of DetectedFace objects with coordinates in full frame space
        """
        x1, y1, x2, y2 = region

        # Crop the region
        roi = frame[y1:y2, x1:x2]

        if roi.size == 0:
            return []

        # Detect faces in region
        faces = self.detect_faces(roi)

        # Adjust coordinates back to full frame space
        adjusted_faces = []
        for face in faces:
            adj_bbox = (
                face.bbox[0] + x1,
                face.bbox[1] + y1,
                face.bbox[2] + x1,
                face.bbox[3] + y1,
            )
            adjusted = DetectedFace(
                bbox=adj_bbox,
                confidence=face.confidence,
                landmarks=face.landmarks + np.array([x1, y1]) if face.landmarks is not None else None,
                face_image=face.face_image,
                age=face.age,
                gender=face.gender
            )
            adjusted_faces.append(adjusted)

        return adjusted_faces

    def get_best_face(self, faces: List[DetectedFace]) -> Optional[DetectedFace]:
        """Get the face with highest confidence."""
        if not faces:
            return None
        return faces[0]  # Already sorted by confidence
