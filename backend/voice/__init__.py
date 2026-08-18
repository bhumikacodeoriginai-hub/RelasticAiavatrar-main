"""
Voice module for speech-to-text, text-to-speech, and voice activity detection.
"""

from voice.speech_to_text import SpeechToText
from voice.text_to_speech import TextToSpeech
from voice.vad import VoiceActivityDetector

__all__ = ["SpeechToText", "TextToSpeech", "VoiceActivityDetector"]
