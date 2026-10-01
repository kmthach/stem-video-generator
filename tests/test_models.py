"""Unit tests for Pydantic models and schemas."""

import pytest
from pathlib import Path
from generator.models import (
    Storyboard,
    ScenePlan,
    SceneVisualConcept,
    VideoQuality,
    AspectRatio,
    SceneAudioResult,
    RenderAttempt,
    SceneRenderResult,
    PipelineResult,
    TokenUsage,
)


def test_storyboard_serialization():
    """Tests Storyboard model parsing and serialization."""
    scene1 = ScenePlan(
        scene_number=1,
        scene_title="Pythagorean Theorem Statement",
        narration="In any right-angled triangle, the square of the hypotenuse equals the sum of the squares of the other two sides.",
        visuals=SceneVisualConcept(
            description="Draw a right triangle with labeled sides a, b, and c.",
            math_formulas=[r"a^2 + b^2 = c^2"],
            geometric_elements=["Right triangle", "Squares on each side"],
            color_palette=["BLUE", "YELLOW", "RED"],
            camera_and_focus="Center"
        ),
        estimated_duration_sec=12.0
    )

    storyboard = Storyboard(
        topic="Pythagorean Theorem",
        target_audience="High School / College Geometry",
        overall_theme="Geometric proof by rearrangement",
        learning_objectives=["Understand geometric interpretation of a^2 + b^2 = c^2"],
        scenes=[scene1]
    )

    json_str = storyboard.model_dump_json()
    assert "Pythagorean Theorem" in json_str
    assert "a^2 + b^2 = c^2" in json_str

    # Test roundtrip parsing
    loaded = Storyboard.model_validate_json(json_str)
    assert len(loaded.scenes) == 1
    assert loaded.scenes[0].scene_number == 1
    assert loaded.scenes[0].visuals.math_formulas == [r"a^2 + b^2 = c^2"]


def test_scene_render_result_model():
    """Tests SceneRenderResult model creation."""
    result = SceneRenderResult(
        scene_number=1,
        scene_title="Intro",
        scene_class_name="Scene1",
        code_path=Path("scene1.py"),
        raw_video_path=Path("scene1.mp4"),
        target_duration_sec=10.0,
        actual_duration_sec=10.2,
        attempts=1,
        is_success=True
    )
    assert result.is_success is True
    assert result.attempts == 1
    assert result.actual_duration_sec == 10.2


def test_token_usage_model():
    """Tests TokenUsage model creation and aggregation."""
    usage = TokenUsage(
        prompt_tokens=4000,
        candidates_tokens=5000,
        total_tokens=9000,
        api_calls=8
    )
    assert usage.prompt_tokens == 4000
    assert usage.candidates_tokens == 5000
    assert usage.total_tokens == 9000
    assert usage.api_calls == 8
