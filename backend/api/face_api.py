"""
Face Recognition API.
Handles face capture, embedding generation, storage, and matching.
"""

import base64
import json
import numpy as np
import cv2
from typing import Optional
from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/api/face", tags=["face"])


class FaceFrame(BaseModel):
    """Base64 encoded camera frame."""
    image: str  # base64 JPEG


@router.post("/identify")
async def identify_face(data: FaceFrame, request: Request):
    """
    Identify visitor using InsightFace directly (skip OpenCV CascadeClassifier).
    """
    try:
        img_bytes = base64.b64decode(data.image)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return {"found": False, "no_face": True, "reason": "invalid_image"}
        
        # Use InsightFace directly (it does both detection + embedding)
        app = request.app
        embedding = None
        
        if hasattr(app.state, 'face_embedder') and app.state.face_embedder._initialized:
            embedding = app.state.face_embedder.get_embedding(frame)
        
        if embedding is None:
            # No face detected by InsightFace
            return {"found": False, "no_face": True, "reason": "no_face_detected"}
        
        # Face found + embedding generated! Search database
        from database.database import AsyncSessionLocal
        if not AsyncSessionLocal:
            return {"found": False, "no_face": False, "reason": "no_database"}
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("SELECT id, name, face_embedding, visit_count FROM visitor WHERE face_embedding IS NOT NULL AND consent_status='granted'")
            )
            rows = result.mappings().all()
            
            best_match = None
            best_similarity = 0.0
            
            for row in rows:
                try:
                    stored = json.loads(row['face_embedding'])
                    stored_arr = np.array(stored, dtype=np.float32)
                    if len(stored_arr) != 512:
                        continue
                    query_arr = np.array(embedding, dtype=np.float32)
                    query_arr = query_arr / (np.linalg.norm(query_arr) + 1e-8)
                    stored_arr = stored_arr / (np.linalg.norm(stored_arr) + 1e-8)
                    sim = float(np.dot(query_arr, stored_arr))
                    if sim > best_similarity:
                        best_similarity = sim
                        best_match = row
                except Exception:
                    continue
            
            if best_match and best_similarity >= 0.6:
                logger.info("Face MATCHED", name=best_match['name'], similarity=round(best_similarity, 3))
                return {"found": True, "name": best_match['name'], "visit_count": best_match['visit_count'], "confidence": round(best_similarity, 3)}
            else:
                # Face detected but not in DB (new person)
                logger.info("New face (not in DB)", similarity=round(best_similarity, 3))
                return {"found": False, "no_face": False, "reason": "unknown_face"}
    
    except Exception as e:
        logger.error("Face identify error", error=str(e))
        # If we got here, a face WAS detected but DB lookup failed
        # Return "unknown_face" so frontend still starts a new visitor conversation
        return {"found": False, "no_face": False, "reason": "unknown_face", "error": str(e)}


@router.post("/register")
async def register_face(data: FaceFrame, request: Request, name: str = ""):
    """Register face using InsightFace."""
    try:
        if not name:
            return {"success": False, "error": "Name required"}
        
        img_bytes = base64.b64decode(data.image)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return {"success": False, "error": "Invalid image"}
        
        # Generate embedding with InsightFace
        embedding = None
        app = request.app
        if hasattr(app.state, 'face_embedder') and app.state.face_embedder._initialized:
            embedding = app.state.face_embedder.get_embedding(frame)
        
        if embedding is None:
            # Save name only
            from database.database import AsyncSessionLocal
            if AsyncSessionLocal:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(text("SELECT id FROM visitor WHERE LOWER(name) = LOWER(:name)"), {"name": name.strip()})
                    if not result.mappings().first():
                        await db.execute(text("INSERT INTO visitor (name, consent_status, first_seen, last_seen) VALUES (:name, 'granted', NOW(), NOW())"), {"name": name.strip()})
                        await db.commit()
                        logger.info("Saved name only (no face embedding)", name=name)
            return {"success": True, "name": name, "face_saved": False}
        
        # Save InsightFace embedding
        embedding_json = json.dumps(embedding.tolist())
        
        from database.database import AsyncSessionLocal
        if not AsyncSessionLocal:
            return {"success": False, "error": "Database not available"}
        
        logger.info("Saving face to DB", name=name, embedding_size=len(embedding))
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(text("SELECT id FROM visitor WHERE LOWER(name) = LOWER(:name)"), {"name": name.strip()})
            existing = result.mappings().first()
            
            if existing:
                await db.execute(text("UPDATE visitor SET face_embedding=:emb, last_seen=NOW(), consent_status='granted' WHERE id=:id"), {"emb": embedding_json, "id": existing['id']})
                logger.info("✅ Updated face for existing visitor", name=name)
            else:
                await db.execute(text("INSERT INTO visitor (name, face_embedding, consent_status, first_seen, last_seen) VALUES (:name, :emb, 'granted', NOW(), NOW())"), {"name": name.strip(), "emb": embedding_json})
                logger.info("✅ NEW visitor saved with face", name=name)
            await db.commit()
        
        return {"success": True, "name": name, "face_saved": True}
    
    except Exception as e:
        logger.error("Face register error", error=str(e))
        return {"success": False, "error": str(e)}
