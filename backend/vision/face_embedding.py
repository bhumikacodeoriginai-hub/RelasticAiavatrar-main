"""
Face Embedding module using InsightFace ArcFace.
Generates 512-dimensional embeddings for face recognition.
"""

import numpy as np
from typing import Optional, List
import structlog

from vision.face_detection import DetectedFace

logger = structlog.get_logger()


class FaceEmbedder:
    """
    Generates face embeddings using InsightFace ArcFace model.
    Produces 512-dimensional normalized vectors for face comparison.
    """

    def __init__(self, model_name: str = "buffalo_l"):
        """
        Initialize the face embedder.

        Args:
            model_name: InsightFace model pack name
        """
        self.model_name = model_name
        self.app = None
        self._initialized = False
        self.embedding_size = 512

    async def initialize(self) -> None:
        """Load the embedding model."""
        try:
            import insightface
            from insightface.app import FaceAnalysis

            self.app = FaceAnalysis(
                name=self.model_name,
                providers=['CPUExecutionProvider']
            )
            self.app.prepare(ctx_id=0, det_size=(640, 640))
            self._initialized = True
            logger.info("Face embedder initialized", model=self.model_name)
        except ImportError:
            logger.warning("insightface not installed - face embedding disabled")
            self._initialized = False
        except Exception as e:
            logger.error("Failed to initialize face embedder", error=str(e))
            self._initialized = False

    def get_embedding(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Get face embedding from a frame containing a single face.

        Args:
            frame: BGR image containing a face

        Returns:
            512-dimensional numpy array (normalized) or None
        """
        if not self._initialized:
            logger.warning("Face embedder not initialized")
            return None

        try:
            faces = self.app.get(frame)

            if not faces:
                logger.debug("No face found for embedding extraction")
                return None

            # Get the best (highest confidence) face
            best_face = max(faces, key=lambda f: f.det_score)

            # Extract embedding (512-dimensional vector)
            embedding = best_face.normed_embedding

            if embedding is not None:
                # Ensure it's normalized
                embedding = embedding / np.linalg.norm(embedding)
                logger.debug(
                    "Embedding extracted",
                    shape=embedding.shape,
                    norm=float(np.linalg.norm(embedding))
                )

            return embedding

        except Exception as e:
            logger.error("Error extracting face embedding", error=str(e))
            return None

    def get_embedding_from_face(
        self,
        frame: np.ndarray,
        face: DetectedFace
    ) -> Optional[np.ndarray]:
        """
        Get face embedding using pre-detected face location.

        Args:
            frame: Full BGR frame
            face: DetectedFace object with bbox

        Returns:
            512-dimensional numpy array or None
        """
        if not self._initialized:
            return None

        try:
            # Use the full frame and let InsightFace find the face
            # This is more accurate than using a cropped region
            faces = self.app.get(frame)

            if not faces:
                return None

            # Find the detected face that best matches our face bbox
            best_match = None
            best_iou = 0.0

            for detected in faces:
                iou = self._calculate_iou(face.bbox, tuple(map(int, detected.bbox)))
                if iou > best_iou:
                    best_iou = iou
                    best_match = detected

            if best_match is not None and best_iou > 0.3:
                embedding = best_match.normed_embedding
                if embedding is not None:
                    embedding = embedding / np.linalg.norm(embedding)
                return embedding

            return None

        except Exception as e:
            logger.error("Error extracting embedding from face", error=str(e))
            return None

    def get_multiple_embeddings(
        self, frame: np.ndarray
    ) -> List[tuple]:
        """
        Get embeddings for all faces in a frame.

        Args:
            frame: BGR image

        Returns:
            List of (bbox, embedding) tuples
        """
        if not self._initialized:
            return []

        try:
            faces = self.app.get(frame)
            results = []

            for face in faces:
                embedding = face.normed_embedding
                if embedding is not None:
                    embedding = embedding / np.linalg.norm(embedding)
                    bbox = tuple(map(int, face.bbox))
                    results.append((bbox, embedding))

            return results

        except Exception as e:
            logger.error("Error extracting multiple embeddings", error=str(e))
            return []

    @staticmethod
    def _calculate_iou(
        bbox1: tuple, bbox2: tuple
    ) -> float:
        """Calculate Intersection over Union between two bounding boxes."""
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])

        intersection = max(0, x2 - x1) * max(0, y2 - y1)

        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])

        union = area1 + area2 - intersection

        if union == 0:
            return 0.0

        return intersection / union
