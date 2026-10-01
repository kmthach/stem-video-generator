"""Edge-TTS neural voice synthesis service with millisecond-accurate duration calculation."""

import asyncio
from pathlib import Path
from typing import List, Dict, Optional
import edge_tts
from generator.models import SceneAudioResult
from generator.config import settings, POPULAR_VOICES
from generator.utils.ffmpeg_utils import get_media_duration
from generator.utils.logger import console, print_success


class TTSService:
    """Handles neural text-to-speech synthesis using Microsoft Edge TTS."""

    def __init__(self, voice: Optional[str] = None):
        self.voice = voice or settings.default_voice

    async def generate_scene_audio_async(
        self,
        scene_number: int,
        narration: str,
        output_dir: Path,
        voice: Optional[str] = None
    ) -> SceneAudioResult:
        """
        Synthesizes narration audio for a single scene and returns the file path and duration.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        selected_voice = voice or self.voice
        audio_file = output_dir / f"scene_{scene_number:02d}_narration.mp3"

        # Edge-TTS communicate
        communicate = edge_tts.Communicate(text=narration, voice=selected_voice)
        await communicate.save(str(audio_file))

        # Measure duration accurately
        duration = get_media_duration(audio_file)
        if duration <= 0.0:
            # Fallback estimation if ffprobe/mutagen couldn't read (rough ~150 words per minute)
            words = len(narration.split())
            duration = max(3.0, (words / 150.0) * 60.0)

        return SceneAudioResult(
            scene_number=scene_number,
            audio_path=audio_file,
            duration_sec=duration,
            voice=selected_voice
        )

    def generate_scene_audio(
        self,
        scene_number: int,
        narration: str,
        output_dir: Path,
        voice: Optional[str] = None
    ) -> SceneAudioResult:
        """Synchronous wrapper for generate_scene_audio_async."""
        return asyncio.run(
            self.generate_scene_audio_async(
                scene_number=scene_number,
                narration=narration,
                output_dir=output_dir,
                voice=voice
            )
        )

    @staticmethod
    async def list_available_voices(filter_locale: Optional[str] = None) -> List[Dict[str, str]]:
        """Lists available Edge-TTS voices, optionally filtered by locale (e.g. 'en-US')."""
        voices = await edge_tts.list_voices()
        results = []
        for v in voices:
            short_name = v.get("ShortName", "")
            locale = v.get("Locale", "")
            gender = v.get("Gender", "")
            if not filter_locale or filter_locale.lower() in locale.lower() or filter_locale.lower() in short_name.lower():
                results.append({
                    "ShortName": short_name,
                    "Locale": locale,
                    "Gender": gender,
                    "FriendlyName": v.get("FriendlyName", "")
                })
        return results
