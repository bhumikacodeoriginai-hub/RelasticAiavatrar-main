"""
Voice Activity Detection (VAD) module.
Detects when a person is speaking vs. silence.
Uses WebRTC VAD for efficient real-time detection.
"""

import asyncio
from typing import Optional, Callable, Awaitable, List
from dataclasses import dataclass
from enum import Enum
import struct
import time
import numpy as np
import structlog

logger = structlog.get_logger()


class VoiceState(str, Enum):
    """Current state of voice detection."""
    SILENCE = "silence"
    SPEAKING = "speaking"
    PAUSE = "pause"  # Brief pause during speech


@dataclass
class VoiceSegment:
    """A detected speech segment."""
    audio_data: bytes
    start_time: float
    end_time: float
    duration: float
    sample_rate: int = 16000


class VoiceActivityDetector:
    """
    WebRTC VAD-based voice activity detector.
    Determines when the user starts and stops speaking.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        aggressiveness: int = 2,
        silence_threshold_ms: int = 1500,
        min_speech_ms: int = 300
    ):
        """
        Initialize the VAD.

        Args:
            sample_rate: Audio sample rate (8000, 16000, 32000, 48000)
            frame_duration_ms: Frame duration (10, 20, or 30 ms)
            aggressiveness: VAD aggressiveness (0-3). Higher = more aggressive filtering
            silence_threshold_ms: How long silence triggers end of speech
            min_speech_ms: Minimum speech duration to consider valid
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.aggressiveness = aggressiveness
        self.silence_threshold_ms = silence_threshold_ms
        self.min_speech_ms = min_speech_ms
        self.vad = None
        self._initialized = False

        # State tracking
        self.state = VoiceState.SILENCE
        self._speech_buffer: List[bytes] = []
        self._speech_start_time: float = 0
        self._last_speech_time: float = 0
        self._silence_frames: int = 0
        self._speech_frames: int = 0

        # Callbacks
        self._on_speech_start: Optional[Callable] = None
        self._on_speech_end: Optional[Callable[[VoiceSegment], Awaitable[None]]] = None

        # Calculate frame size in bytes (16-bit PCM)
        self.frame_size = int(sample_rate * frame_duration_ms / 1000) * 2

    async def initialize(self) -> None:
        """Initialize the WebRTC VAD."""
        try:
            import webrtcvad
            self.vad = webrtcvad.Vad(self.aggressiveness)
            self._initialized = True
            logger.info(
                "VAD initialized",
                sample_rate=self.sample_rate,
                frame_duration=self.frame_duration_ms,
                aggressiveness=self.aggressiveness
            )
        except ImportError:
            logger.error("webrtcvad not installed")
            raise
        except Exception as e:
            logger.error("Failed to initialize VAD", error=str(e))
            raise

    def on_speech_start(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register callback for when speech starts."""
        self._on_speech_start = callback

    def on_speech_end(
        self, callback: Callable[[VoiceSegment], Awaitable[None]]
    ) -> None:
        """Register callback for when speech ends (with audio data)."""
        self._on_speech_end = callback

    async def process_audio(self, audio_chunk: bytes) -> Optional[VoiceState]:
        """
        Process an audio chunk and detect voice activity.

        Args:
            audio_chunk: Raw PCM audio data (16-bit, mono)

        Returns:
            Current voice state
        """
        if not self._initialized:
            return None

        # Process in frame-sized chunks
        offset = 0
        while offset + self.frame_size <= len(audio_chunk):
            frame = audio_chunk[offset:offset + self.frame_size]
            await self._process_frame(frame)
            offset += self.frame_size

        return self.state

    async def _process_frame(self, frame: bytes) -> None:
        """Process a single audio frame."""
        is_speech = self.vad.is_speech(frame, self.sample_rate)
        current_time = time.time()

        if is_speech:
            self._speech_frames += 1
            self._silence_frames = 0
            self._last_speech_time = current_time

            if self.state == VoiceState.SILENCE:
                # Speech just started
                self.state = VoiceState.SPEAKING
                self._speech_start_time = current_time
                self._speech_buffer = [frame]

                if self._on_speech_start:
                    await self._on_speech_start()

                logger.debug("Speech started")
            else:
                # Continuing speech
                self._speech_buffer.append(frame)

        else:
            self._silence_frames += 1

            if self.state == VoiceState.SPEAKING:
                # Add frame to buffer (might be a brief pause)
                self._speech_buffer.append(frame)

                # Check if silence duration exceeds threshold
                silence_duration_ms = (
                    self._silence_frames * self.frame_duration_ms
                )

                if silence_duration_ms >= self.silence_threshold_ms:
                    # Speech has ended
                    await self._end_speech(current_time)

    async def _end_speech(self, end_time: float) -> None:
        """Handle end of speech segment."""
        duration = end_time - self._speech_start_time
        duration_ms = duration * 1000

        self.state = VoiceState.SILENCE

        # Only emit if speech was long enough
        if duration_ms >= self.min_speech_ms:
            audio_data = b"".join(self._speech_buffer)

            segment = VoiceSegment(
                audio_data=audio_data,
                start_time=self._speech_start_time,
                end_time=end_time,
                duration=duration,
                sample_rate=self.sample_rate
            )

            logger.info(
                "Speech segment detected",
                duration_ms=int(duration_ms),
                buffer_size=len(audio_data)
            )

            if self._on_speech_end:
                await self._on_speech_end(segment)
        else:
            logger.debug(
                "Speech too short, ignoring",
                duration_ms=int(duration_ms)
            )

        # Reset buffers
        self._speech_buffer = []
        self._speech_frames = 0
        self._silence_frames = 0

    def reset(self) -> None:
        """Reset the VAD state."""
        self.state = VoiceState.SILENCE
        self._speech_buffer = []
        self._speech_frames = 0
        self._silence_frames = 0
        self._speech_start_time = 0
        self._last_speech_time = 0

    @staticmethod
    def audio_level(audio_chunk: bytes) -> float:
        """
        Calculate the RMS audio level of a chunk.
        Useful for visual feedback on the frontend.

        Args:
            audio_chunk: Raw PCM audio data

        Returns:
            RMS level (0.0 to 1.0)
        """
        if not audio_chunk:
            return 0.0

        # Convert bytes to int16 samples
        num_samples = len(audio_chunk) // 2
        if num_samples == 0:
            return 0.0

        samples = struct.unpack(f"{num_samples}h", audio_chunk[:num_samples * 2])
        arr = np.array(samples, dtype=np.float32)

        # Calculate RMS
        rms = np.sqrt(np.mean(arr ** 2))

        # Normalize to 0-1 range (int16 max is 32767)
        level = min(1.0, rms / 32767.0)

        return float(level)
