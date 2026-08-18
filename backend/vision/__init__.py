"""
Vision module for AI Avatar Receptionist.
Handles person detection, face detection, face embedding, and face matching.
"""

from vision.person_detection import PersonDetector
from vision.face_detection import FaceDetector
from vision.face_embedding import FaceEmbedder
from vision.face_matching import FaceMatcher
from vision.camera import CameraService

__all__ = [
    "PersonDetector",
    "FaceDetector",
    "FaceEmbedder",
    "FaceMatcher",
    "CameraService",
]
