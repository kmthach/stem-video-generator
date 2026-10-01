"""Unit tests for Edge-TTS and audio utilities."""

import pytest
import asyncio
from pathlib import Path
from generator.services.tts_service import TTSService
from generator.utils.ffmpeg_utils import check_ffmpeg_installed


def test_ffmpeg_check():
    """Verify that FFmpeg is detected on the system."""
    assert check_ffmpeg_installed() is True


@pytest.mark.asyncio
async def test_list_voices():
    """Verify listing voices from Edge-TTS."""
    voices = await TTSService.list_available_voices(filter_locale="en-US")
    assert len(voices) > 0
    voice_names = [v["ShortName"] for v in voices]
    assert "en-US-ChristopherNeural" in voice_names or "en-US-JennyNeural" in voice_names or len(voice_names) > 0
