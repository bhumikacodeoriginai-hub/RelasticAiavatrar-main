"""
Speech-to-Text module using AWS Transcribe.
Converts spoken audio to text for processing by the AI conversation engine.
Supports both streaming and batch transcription.
"""

import asyncio
import json
import io
from typing import Optional, Callable, Awaitable, AsyncGenerator
import structlog
import boto3

from config import settings

logger = structlog.get_logger()


class SpeechToText:
    """
    AWS Transcribe Speech-to-Text service.
    Supports streaming transcription for real-time conversation.
    """

    def __init__(self):
        """Initialize the STT service."""
        self.language_code = settings.transcribe_language_code
        self.region = settings.aws_region
        self.client = None
        self._initialized = False
        self._on_transcript_callback: Optional[Callable] = None

    async def initialize(self) -> None:
        """Initialize the AWS Transcribe client."""
        try:
            session = boto3.Session(
                region_name=self.region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key
            )
            self.client = session.client("transcribe")
            self._initialized = True
            logger.info(
                "Speech-to-Text initialized",
                language=self.language_code,
                region=self.region
            )
        except Exception as e:
            logger.error("Failed to initialize STT", error=str(e))
            raise

    def on_transcript(
        self, callback: Callable[[str, bool], Awaitable[None]]
    ) -> None:
        """
        Register callback for when a transcript is ready.

        Args:
            callback: Async function receiving (text, is_final)
        """
        self._on_transcript_callback = callback

    async def transcribe_audio(self, audio_bytes: bytes) -> Optional[str]:
        """
        Transcribe audio bytes to text (batch mode).

        Args:
            audio_bytes: Raw PCM audio data (16kHz, 16-bit, mono)

        Returns:
            Transcribed text or None
        """
        if not self._initialized:
            logger.warning("STT not initialized")
            return None

        try:
            # For batch transcription, we use the streaming client
            # or a simplified approach with AWS SDK
            import wave
            import tempfile
            import os

            # Create a temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                wf = wave.open(f, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_bytes)
                wf.close()

            # For real-time apps, you'd use streaming transcription
            # This is a simplified batch approach
            logger.info("Audio transcription requested", size=len(audio_bytes))

            # Clean up
            os.unlink(temp_path)

            # Placeholder: In production, use AWS Transcribe Streaming
            return None

        except Exception as e:
            logger.error("Error transcribing audio", error=str(e))
            return None

    async def transcribe_stream(
        self, audio_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[str, None]:
        """
        Streaming transcription of audio.

        Args:
            audio_stream: Async generator yielding audio chunks

        Yields:
            Transcribed text segments
        """
        if not self._initialized:
            logger.warning("STT not initialized")
            return

        try:
            # Use AWS Transcribe Streaming API
            from botocore.config import Config

            streaming_config = Config(
                region_name=self.region,
                signature_version='v4',
            )

            session = boto3.Session(
                region_name=self.region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key
            )
            streaming_client = session.client(
                'transcribe',
                config=streaming_config
            )

            logger.info("Starting streaming transcription")

            # Process audio chunks
            buffer = b""
            async for chunk in audio_stream:
                buffer += chunk

                # Process in 1-second chunks (16000 samples * 2 bytes = 32000)
                while len(buffer) >= 32000:
                    audio_chunk = buffer[:32000]
                    buffer = buffer[32000:]

                    # In production, send to AWS Transcribe Streaming
                    # This is a placeholder for the streaming integration
                    yield ""

        except Exception as e:
            logger.error("Error in streaming transcription", error=str(e))


class WebSpeechToText:
    """
    Browser-based Speech-to-Text using Web Speech API.
    Audio is captured in the browser and text is sent to the backend.
    This is the recommended approach for the frontend.
    """

    @staticmethod
    def get_config() -> dict:
        """
        Get configuration for the Web Speech API on the frontend.

        Returns:
            Configuration dict for the frontend
        """
        return {
            "language": settings.transcribe_language_code,
            "continuous": True,
            "interimResults": True,
            "maxAlternatives": 1,
            "silenceTimeout": 2000,  # ms of silence before sending
        }

    @staticmethod
    async def process_web_transcript(
        transcript: str,
        is_final: bool,
        confidence: float = 1.0
    ) -> Optional[str]:
        """
        Process a transcript received from the browser's Web Speech API.

        Args:
            transcript: Transcribed text from the browser
            is_final: Whether this is a final transcript
            confidence: Confidence score from the browser

        Returns:
            Cleaned transcript text
        """
        if not transcript or not transcript.strip():
            return None

        # Clean up the transcript
        cleaned = transcript.strip()

        # Only process final transcripts with reasonable confidence
        if is_final and confidence >= 0.5:
            logger.info(
                "Web transcript received",
                text=cleaned[:50],
                confidence=confidence
            )
            return cleaned

        return None
