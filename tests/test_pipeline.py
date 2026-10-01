"""Unit tests for pipeline components and self-healing render logic."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from generator.models import ScenePlan, SceneVisualConcept, VideoQuality, AspectRatio, SceneRenderResult
from generator.services.manim_service import ManimService
from generator.services.video_service import VideoService


def test_manim_service_initialization():
    """Tests ManimService initialization with mocked gemini service."""
    mock_gemini = MagicMock()
    service = ManimService(gemini_service=mock_gemini, max_retries=2)
    assert service.max_retries == 2
    assert service.gemini is mock_gemini


def test_video_service_concatenation_empty():
    """Verify ValueError is raised if no clips are provided for concatenation."""
    video_service = VideoService()
    with pytest.raises(ValueError, match="No rendered scene video clips"):
        video_service.assemble_final_video(
            scene_results=[],
            output_path=Path("final.mp4"),
            temp_dir=Path("temp")
        )


def test_pipeline_worker_bounds():
    """Verify max_workers is properly bounded between 1 and 10."""
    from generator.pipeline import VideoGeneratorPipeline
    mock_gemini = MagicMock()
    
    # Check max worker clamping
    p = VideoGeneratorPipeline(api_key="dummy", max_workers=20)
    assert p.max_workers == 10

    p_low = VideoGeneratorPipeline(api_key="dummy", max_workers=0)
    assert p_low.max_workers == 1


def test_prepare_runnable_code_shims():
    """Verify _prepare_runnable_code injects shims and aliases at top."""
    code = """from manim import *

class Scene1(Scene):
    def construct(self):
        c = Circle(color=PURE_WHITE)
        self.play(Rotate(c, rate_func=ease_out_quad))
"""
    runnable = ManimService._prepare_runnable_code(code)
    assert "from manim import *" in runnable
    assert "ease_out_quad = smooth" in runnable
    assert "PURE_WHITE = WHITE" in runnable
    # Ensure shims appear before class Scene1
    shim_pos = runnable.find("ease_out_quad = smooth")
    class_pos = runnable.find("class Scene1")
    assert shim_pos != -1 and class_pos != -1
    assert shim_pos < class_pos


def test_pipeline_job_id_output_naming(tmp_path):
    """Verify that when job_id is provided, output folder and video use job_id."""
    from unittest.mock import patch
    from generator.pipeline import VideoGeneratorPipeline
    from generator.models import Storyboard

    p = VideoGeneratorPipeline(api_key="dummy", output_dir=tmp_path)
    mock_storyboard = Storyboard(topic="Quantum Physics", scenes=[])
    
    with patch.object(p.gemini, "generate_storyboard", return_value=mock_storyboard), \
         patch.object(p.gemini, "get_token_usage", return_value=None), \
         patch("generator.pipeline.check_ffmpeg_installed", return_value=True), \
         patch.object(p.video, "assemble_final_video") as mock_assemble, \
         patch("generator.pipeline.get_media_duration", return_value=60.0):
        
        job_uuid = "a1b2c3d4-e5f6-7890-1234-56789abcdef0"
        expected_video_file = tmp_path / job_uuid / f"{job_uuid}.mp4"
        mock_assemble.return_value = expected_video_file

        res = p.run(topic="Quantum Physics", job_id=job_uuid)

        assert res.output_dir == tmp_path / job_uuid
        assert res.final_video_path == expected_video_file


