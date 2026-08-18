"""
Face Matching module.
Compares face embeddings against the database to identify visitors.
Implements the state machine logic for new vs returning persons.
"""

import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog

from database.visitors import VisitorRepository
from database.models import Person

logger = structlog.get_logger()


class MatchResult(str, Enum):
    """Result of face matching."""
    MATCH_FOUND = "match_found"
    NO_MATCH = "no_match"
    NO_FACE = "no_face"
    ERROR = "error"


@dataclass
class FaceMatchResult:
    """Result of a face match operation."""
    status: MatchResult
    person: Optional[Person] = None
    confidence: float = 0.0
    embedding: Optional[np.ndarray] = None
    message: str = ""


class FaceMatcher:
    """
    Face matching service.
    Compares face embeddings against the person database using
    cosine similarity through pgvector.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.6,
        high_confidence_threshold: float = 0.8
    ):
        """
        Initialize the face matcher.

        Args:
            similarity_threshold: Minimum cosine similarity for a match
            high_confidence_threshold: Threshold for high-confidence matches
        """
        self.similarity_threshold = similarity_threshold
        self.high_confidence_threshold = high_confidence_threshold

    async def match_face(
        self,
        embedding: np.ndarray,
        visitor_repo: VisitorRepository
    ) -> FaceMatchResult:
        """
        Match a face embedding against the database.

        Args:
            embedding: 512-dimensional face embedding
            visitor_repo: Database repository for visitor lookup

        Returns:
            FaceMatchResult with match status and person info
        """
        if embedding is None:
            return FaceMatchResult(
                status=MatchResult.NO_FACE,
                message="No face embedding provided"
            )

        try:
            # Search database for matching faces
            matches = await visitor_repo.search_by_face(
                embedding=embedding,
                threshold=self.similarity_threshold,
                limit=3
            )

            if not matches:
                logger.info("No face match found - new visitor")
                return FaceMatchResult(
                    status=MatchResult.NO_MATCH,
                    embedding=embedding,
                    message="No matching face found in database"
                )

            # Get the best match
            best_person, best_similarity = matches[0]

            # Determine confidence level
            if best_similarity >= self.high_confidence_threshold:
                confidence_msg = "high confidence"
            else:
                confidence_msg = "moderate confidence"

            logger.info(
                "Face match found",
                person_id=str(best_person.person_id),
                name=best_person.name,
                similarity=best_similarity,
                confidence=confidence_msg
            )

            # Update last seen
            await visitor_repo.update_last_seen(best_person.person_id)

            return FaceMatchResult(
                status=MatchResult.MATCH_FOUND,
                person=best_person,
                confidence=best_similarity,
                embedding=embedding,
                message=f"Matched with {confidence_msg}: {best_person.name}"
            )

        except Exception as e:
            logger.error("Error during face matching", error=str(e))
            return FaceMatchResult(
                status=MatchResult.ERROR,
                embedding=embedding,
                message=f"Error during matching: {str(e)}"
            )

    @staticmethod
    def compute_similarity(
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First face embedding
            embedding2: Second face embedding

        Returns:
            Cosine similarity score (0 to 1)
        """
        # Normalize embeddings
        norm1 = embedding1 / np.linalg.norm(embedding1)
        norm2 = embedding2 / np.linalg.norm(embedding2)

        # Cosine similarity
        similarity = float(np.dot(norm1, norm2))

        return max(0.0, min(1.0, similarity))

    @staticmethod
    def is_same_person(
        embedding1: np.ndarray,
        embedding2: np.ndarray,
        threshold: float = 0.6
    ) -> Tuple[bool, float]:
        """
        Quick check if two embeddings belong to the same person.

        Args:
            embedding1: First face embedding
            embedding2: Second face embedding
            threshold: Similarity threshold

        Returns:
            Tuple of (is_same_person, similarity_score)
        """
        similarity = FaceMatcher.compute_similarity(embedding1, embedding2)
        return similarity >= threshold, similarity
