"""
Voice interface for GNOME AI Assistant.

This module provides speech recognition and text-to-speech functionality
for hands-free interaction with the AI assistant.
"""

import asyncio
import logging
import threading
import tempfile
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import wave
import pyaudio
import speech_recognition as sr
from dataclasses import dataclass

from ..utils.logger import get_logger
from ..core.config import VoiceConfig

logger = get_logger(__name__)


@dataclass
class VoiceCommand:
    """Represents a voice command."""
    text: str
    confidence: float
    language: str
    timestamp: float


class VoiceInterface:
    """Voice interface for speech recognition and text-to-speech."""
    
    def __init__(self, config: VoiceConfig, message_callback: Optional[Callable] = None):
        """
        Initialize voice interface.
        
        Args:
            config: Voice configuration
            message_callback: Callback for processing recognized speech
        """
        self.config = config
        self.message_callback = message_callback
        
        # Speech recognition
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.is_listening = False
        self.listen_thread = None
        
        # Audio settings
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk_size = 1024
        
        # Wake word detection
        self.wake_word_active = False
        self.wake_word = config.wake_word.lower()
        
        # TTS settings
        self.tts_enabled = config.enabled
        
    async def initialize(self) -> None:
        """Initialize the voice interface."""
        try:
            if not self.config.enabled:
                logger.info("Voice interface disabled in configuration")
                return
            
            # Initialize microphone
            self.microphone = sr.Microphone()
            
            # Adjust for ambient noise
            logger.info("Adjusting for ambient noise...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
            
            logger.info("Voice interface initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize voice interface: {e}")
            self.config.enabled = False
            raise
    
    async def start_listening(self) -> None:
        """Start continuous voice recognition."""
        if not self.config.enabled or self.is_listening:
            return
        
        self.is_listening = True
        self.wake_word_active = True
        
        # Start listening in a separate thread
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        
        logger.info("Voice recognition started")
    
    async def stop_listening(self) -> None:
        """Stop voice recognition."""
        self.is_listening = False
        self.wake_word_active = False
        
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=2)
        
        logger.info("Voice recognition stopped")
    
    def _listen_loop(self) -> None:
        """Main listening loop running in separate thread."""
        while self.is_listening:
            try:
                # Listen for audio
                with self.microphone as source:
                    # Short timeout for responsiveness
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                
                # Process audio in background
                threading.Thread(
                    target=self._process_audio,
                    args=(audio,),
                    daemon=True
                ).start()
                
            except sr.WaitTimeoutError:
                # Normal timeout, continue listening
                continue
            except Exception as e:
                logger.error(f"Error in listen loop: {e}")
                # Short pause before retrying
                threading.Event().wait(1)
    
    def _process_audio(self, audio: sr.AudioData) -> None:
        """Process recognized audio."""
        try:
            # Use Google Speech Recognition (free tier)
            text = self.recognizer.recognize_google(
                audio, 
                language=self.config.language
            )
            
            logger.debug(f"Recognized: {text}")
            
            # Check for wake word
            if self.wake_word_active:
                if self.wake_word in text.lower():
                    logger.info("Wake word detected")
                    self.wake_word_active = False
                    
                    # Extract command after wake word
                    wake_word_index = text.lower().find(self.wake_word)
                    command_text = text[wake_word_index + len(self.wake_word):].strip()
                    
                    if command_text:
                        self._handle_command(command_text)
                    else:
                        # Just wake word, wait for next command
                        threading.Timer(10.0, self._reactivate_wake_word).start()
                else:
                    # No wake word, ignore
                    return
            else:
                # Wake word already detected, process as command
                self._handle_command(text)
                # Reactivate wake word after processing
                threading.Timer(2.0, self._reactivate_wake_word).start()
                
        except sr.UnknownValueError:
            # Could not understand audio
            pass
        except sr.RequestError as e:
            logger.error(f"Speech recognition error: {e}")
    
    def _handle_command(self, text: str) -> None:
        """Handle recognized voice command."""
        command = VoiceCommand(
            text=text,
            confidence=0.8,  # Google API doesn't provide confidence
            language=self.config.language,
            timestamp=asyncio.get_event_loop().time()
        )
        
        logger.info(f"Voice command: {text}")
        
        # Call message callback if provided
        if self.message_callback:
            try:
                # Run async callback in event loop
                asyncio.run_coroutine_threadsafe(
                    self.message_callback(command),
                    asyncio.get_event_loop()
                )
            except Exception as e:
                logger.error(f"Error processing voice command: {e}")
    
    def _reactivate_wake_word(self) -> None:
        """Reactivate wake word detection."""
        self.wake_word_active = True
        logger.debug("Wake word detection reactivated")
    
    async def speak(self, text: str) -> None:
        """Convert text to speech and play it."""
        if not self.tts_enabled:
            return
        
        try:
            # Use festival for TTS (simple and available on most Linux systems)
            process = await asyncio.create_subprocess_exec(
                'festival', '--tts',
                input=text.encode(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.debug(f"Spoke: {text}")
            else:
                logger.error(f"TTS error: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Error in text-to-speech: {e}")
    
    async def test_voice_recognition(self) -> bool:
        """Test voice recognition functionality."""
        try:
            if not self.config.enabled:
                return False
            
            logger.info("Testing voice recognition... Say something!")
            
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=3)
            
            text = self.recognizer.recognize_google(audio, language=self.config.language)
            logger.info(f"Test recognition successful: {text}")
            return True
            
        except Exception as e:
            logger.error(f"Voice recognition test failed: {e}")
            return False
    
    async def cleanup(self) -> None:
        """Cleanup voice interface resources."""
        await self.stop_listening()
        logger.info("Voice interface cleanup completed")


class WakeWordDetector:
    """Simple wake word detector using keyword matching."""
    
    def __init__(self, wake_word: str, sensitivity: float = 0.8):
        """
        Initialize wake word detector.
        
        Args:
            wake_word: Wake word to detect
            sensitivity: Detection sensitivity (0.0 to 1.0)
        """
        self.wake_word = wake_word.lower()
        self.sensitivity = sensitivity
    
    def detect(self, text: str) -> bool:
        """
        Detect wake word in text.
        
        Args:
            text: Text to search in
            
        Returns:
            True if wake word detected
        """
        text_lower = text.lower()
        
        # Simple keyword matching
        if self.wake_word in text_lower:
            return True
        
        # TODO: Implement more sophisticated detection
        # - Fuzzy matching for similar sounding words
        # - Phonetic matching
        # - Machine learning based detection
        
        return False


# Voice command processors
class VoiceCommandProcessor:
    """Process voice commands and extract intents."""
    
    def __init__(self):
        """Initialize command processor."""
        self.command_patterns = {
            'assistant': ['hey assistant', 'assistant', 'ai'],
            'stop': ['stop', 'cancel', 'quit'],
            'help': ['help', 'what can you do'],
            'status': ['status', 'how are you'],
            'system': ['system', 'computer'],
            'files': ['files', 'file', 'documents'],
            'music': ['music', 'spotify', 'play'],
            'weather': ['weather', 'temperature'],
            'time': ['time', 'date', 'clock'],
        }
    
    def process_command(self, command: VoiceCommand) -> Dict[str, Any]:
        """
        Process voice command and extract intent.
        
        Args:
            command: Voice command to process
            
        Returns:
            Dictionary with intent and parameters
        """
        text_lower = command.text.lower()
        
        # Extract intent
        intent = 'general'
        confidence = command.confidence
        
        for intent_name, patterns in self.command_patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    intent = intent_name
                    break
            if intent != 'general':
                break
        
        # Extract parameters (simple keyword extraction)
        parameters = self._extract_parameters(text_lower, intent)
        
        return {
            'intent': intent,
            'confidence': confidence,
            'parameters': parameters,
            'original_text': command.text,
            'language': command.language,
            'timestamp': command.timestamp
        }
    
    def _extract_parameters(self, text: str, intent: str) -> Dict[str, Any]:
        """Extract parameters from command text."""
        parameters = {}
        
        if intent == 'system':
            if 'shutdown' in text or 'power off' in text:
                parameters['action'] = 'shutdown'
            elif 'restart' in text or 'reboot' in text:
                parameters['action'] = 'restart'
            elif 'sleep' in text or 'suspend' in text:
                parameters['action'] = 'suspend'
            elif 'lock' in text:
                parameters['action'] = 'lock'
        
        elif intent == 'music':
            if 'play' in text:
                parameters['action'] = 'play'
            elif 'pause' in text or 'stop' in text:
                parameters['action'] = 'pause'
            elif 'next' in text:
                parameters['action'] = 'next'
            elif 'previous' in text or 'back' in text:
                parameters['action'] = 'previous'
        
        elif intent == 'files':
            if 'open' in text:
                parameters['action'] = 'open'
            elif 'search' in text or 'find' in text:
                parameters['action'] = 'search'
            elif 'create' in text or 'new' in text:
                parameters['action'] = 'create'
        
        return parameters
