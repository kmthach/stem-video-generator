"""Gemini API client for structured storyboards, Manim animation code, and self-healing repair."""

import json
import re
import threading
from typing import Optional
from generator.models import Storyboard, ScenePlan, AspectRatio, TokenUsage
from generator.config import settings
from generator.utils.logger import console, print_warning


class GeminiService:
    """Service wrapping Google Gemini API for structured generation and code repair."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.gemini_model

        if not self.api_key:
            raise ValueError(
                "Gemini API key is required! Set the GEMINI_API_KEY environment variable "
                "or pass it in .env file."
            )

        self._lock = threading.Lock()
        self.total_prompt_tokens = 0
        self.total_candidates_tokens = 0
        self.total_tokens = 0
        self.total_api_calls = 0

        self._init_client()

    def _record_usage(self, response):
        """Thread-safely records token consumption from Gemini API responses."""
        if not response:
            return
        metadata = getattr(response, "usage_metadata", None)
        if metadata:
            prompt = getattr(metadata, "prompt_token_count", 0) or 0
            candidates = getattr(metadata, "candidates_token_count", 0) or 0
            total = getattr(metadata, "total_token_count", 0) or (prompt + candidates)
            with self._lock:
                self.total_prompt_tokens += prompt
                self.total_candidates_tokens += candidates
                self.total_tokens += total
                self.total_api_calls += 1

    def get_token_usage(self) -> TokenUsage:
        """Returns aggregate token usage across all API requests."""
        with self._lock:
            return TokenUsage(
                prompt_tokens=self.total_prompt_tokens,
                candidates_tokens=self.total_candidates_tokens,
                total_tokens=self.total_tokens,
                api_calls=self.total_api_calls
            )

    def _init_client(self):
        """Initializes the official Google GenAI client."""
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.is_new_sdk = True
        except ImportError:
            try:
                import google.generativeai as legacy_genai
                legacy_genai.configure(api_key=self.api_key)
                self.client = legacy_genai.GenerativeModel(self.model_name)
                self.is_new_sdk = False
            except ImportError:
                raise ImportError(
                    "Neither google-genai nor google-generativeai package is installed. "
                    "Please run 'poetry install'."
                )

    def generate_storyboard(
        self,
        topic: str,
        target_audience: str = "Curious Minds & STEM Students (Kurzgesagt Style)",
        aspect_ratio: AspectRatio = AspectRatio.WIDESCREEN
    ) -> Storyboard:
        """
        Generates a pedagogical multi-scene storyboard using Gemini structured outputs,
        crafted in the iconic 'Kurzgesagt – In a Nutshell' narrative and visual style.
        """
        system_instruction = (
            "You are the lead science director and storytelling writer of 'Kurzgesagt – In a Nutshell'. "
            "Your mission is to transform complex scientific, mathematical, and technological concepts into "
            "captivating, visually stunning, and mind-bending educational stories. "
            "KURZGESAGT STORYTELLING PILLARS: "
            "1. THE HOOK: Start with an existential perspective, a fascinating thought experiment, or a microscopic/cosmic zoom-in ('Imagine for a moment...', 'At every second of your existence...'). "
            "2. VIVID ANALOGIES: Use tangible, intuitive visual metaphors to explain abstract physics, chemistry, biology, or math (e.g. chemical seesaws, cosmic clocks, cellular factories, particle dance). "
            "3. BITE-SIZED PACING: Break the journey into 4 to 8 focused, fast-paced micro-scenes (~10-20 seconds each). Never overload a single scene. "
            "4. AWE-INSPIRING SYNTHESIS: End with an uplifting, poetic takeaway connecting the fundamental mechanism to the broader universe or human reality. "
            "5. KURZGESAGT VISUAL MOTIFS: Specify rich flat-vector compositions, vibrant color contrasts, particle arrays, radial bursts, and scales of magnitude."
        )

        user_prompt = f"""
Create a Kurzgesagt-style educational storyboard for: "{topic}".
- Target Audience: {target_audience}
- Format Aspect Ratio: {aspect_ratio.value} ({"Horizontal 16:9 widescreen" if aspect_ratio == AspectRatio.WIDESCREEN else "Vertical 9:16 format (Shorts/TikTok)"})

Requirements:
1. Break this topic into an optimal sequence of 4 to 8 bite-sized, cinematic micro-scenes.
2. Voiceover narration must sound like Kurzgesagt: engaging, witty, awe-inspiring, and crystal-clear (~10-20s per scene).
3. Visuals must feature flat-vector style geometry, dynamic particle systems, scales of magnitude, and intuitive metaphors.
4. Use clean standard Unicode symbols (², ³, ⁺, ⁻, ⇌, →, ₁, ₂) for any equations or notation.
"""

        try:
            if self.is_new_sdk:
                from google.genai import types
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=Storyboard,
                        temperature=0.4,
                    )
                )
                self._record_usage(response)
                text = response.text
                return Storyboard.model_validate_json(text)
            else:
                prompt_full = f"{system_instruction}\n\nReturn JSON matching this schema:\n{Storyboard.model_json_schema()}\n\n{user_prompt}"
                response = self.client.generate_content(prompt_full)
                self._record_usage(response)
                cleaned = self._clean_json_markdown(response.text)
                return Storyboard.model_validate_json(cleaned)
        except Exception as e:
            console.print(f"[yellow]Structured generation encountered error: {e}. Attempting fallback parsing...[/yellow]")
            return self._fallback_storyboard_gen(topic, aspect_ratio)

    def _fallback_storyboard_gen(self, topic: str, aspect_ratio: AspectRatio) -> Storyboard:
        """Fallback method if SDK structured output schema fails."""
        prompt = f"""
Generate a valid JSON object describing a Kurzgesagt-style educational storyboard for: "{topic}".
Break the concept into 4 to 6 bite-sized scenes.
Aspect Ratio: {aspect_ratio.value}.

Output ONLY raw JSON with keys:
{{
  "topic": "{topic}",
  "target_audience": "Curious Minds (Kurzgesagt Style)",
  "overall_theme": "Captivating Kurzgesagt visual storytelling and intuitive metaphors",
  "learning_objectives": ["Understand core mechanism", "Appreciate cosmic/molecular perspective"],
  "scenes": [
    {{
      "scene_number": 1,
      "scene_title": "The Microscopic Reality",
      "narration": "Imagine zooming into a single drop of water...",
      "visuals": {{
        "description": "Vibrant flat-vector molecules splitting into glowing blue and teal ions against a deep dark background.",
        "math_formulas": ["pH = -log₁₀[H⁺]"],
        "geometric_elements": ["Stylized particle swarm", "Glowing equilibrium scale"],
        "color_palette": ["BLUE_B", "TEAL_B", "YELLOW_C", "WHITE"],
        "camera_and_focus": "Center with dynamic zoom"
      }},
      "estimated_duration_sec": 14.0
    }}
  ]
}}
"""
        if self.is_new_sdk:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            self._record_usage(response)
            raw = response.text
        else:
            response = self.client.generate_content(prompt)
            self._record_usage(response)
            raw = response.text

        cleaned = self._clean_json_markdown(raw)
        return Storyboard.model_validate_json(cleaned)

    def generate_manim_code(
        self,
        scene: ScenePlan,
        duration_sec: float,
        aspect_ratio: AspectRatio = AspectRatio.WIDESCREEN,
        topic: str = ""
    ) -> str:
        """
        Generates clean, simple, student-friendly, and ultra-reliable Manim CE code.
        """
        class_name = f"Scene{scene.scene_number}"
        is_vertical = (aspect_ratio == AspectRatio.VERTICAL)

        try:
            import manim
            manim_version = getattr(manim, "__version__", "0.21.0")
        except Exception:
            manim_version = "0.21.0"

        system_instruction = f"""
You are an expert educational animator creating simple, clean, and intuitive STEM videos for students.
Your target engine is Python Manim Community Edition (CE v{manim_version}).
Your goal is to write a single standalone, bug-free Python script containing class `{class_name}(Scene)`.

🎯 CORE PRINCIPLE: SIMPLE, CLEAN & STUDENT-FRIENDLY (AVOID OVERCOMPLICATION)
1. MANIM CE v{manim_version} COMPLIANCE:
   - Use only official Manim CE v{manim_version} APIs and classes.
   - Do NOT use deprecated methods or methods from other animation libraries.
2. DO NOT OVER-ANIMATE:
   - Keep animations calm, uncluttered, and easy to follow.
   - Limit each scene to ONLY 2 or 3 distinct, purposeful visual beats (e.g., Beat 1: Show concept -> Beat 2: Transform/Highlight -> Beat 3: Key takeaway).
   - Avoid chaotic particle loops, overly complex physics simulations, or dozens of simultaneous moving objects.
   - Never show more than 3 or 4 elements on screen at once.
3. CLEAN LAYOUT & VISUAL HIERARCHY:
   - Top Title: `title = Text("{scene.scene_title}", font_size=32, color=BLUE_B).to_edge(UP)`
   - Central Diagram: A simple, elegant geometric diagram, graph, or balance scale in the center.
   - Bottom / Highlight Takeaway: A clean formula or takeaway box (`SurroundingRectangle`, `Indicate`, `Circumscribe`).
   - Clean Transitions: When moving to a new concept, clean up previous objects with `self.play(FadeOut(...))` or `ReplacementTransform(...)`.
4. CALM & ABSORBING PACING:
   - Use comfortable animation speeds (`run_time=1.5` to `2.5`s).
   - Insert calm pauses (`self.wait(1.5)` to `self.wait(3.0)`) so students have ample time to read and digest every idea.
   - End with a restful final `self.wait(...)` that absorbs any remaining time.

STRICT RELIABILITY & ROBUSTNESS RULES:
1. TEXT & FORMULAS (NO LATEX DEPENDENCY):
   - CRITICAL: DO NOT use `MathTex` or `Tex` (LaTeX compiler is NOT installed on this machine).
   - ALWAYS use `Text("...", font_size=...)` for all titles, formulas, numbers, and labels.
   - Format math using standard Unicode symbols: ², ³, ⁴, ⁿ, ₀, ₁, ₂, ₇, ₁₄, ⁺, ⁻, ⁻⁷, ⁻¹⁴, ⇌, →, ×, ÷, ±, ≤, ≥, √, ∫, ∑, Δ, ≈, ≠, ∞ (e.g. `Text("pH = -log₁₀[H⁺]", font_size=34, color=YELLOW_C)`).
2. VALID COLOR CONSTANTS (STRICT MANIM CE NAMES):
   - Use ONLY built-in Manim color constants: `WHITE`, `BLACK`, `BLUE`, `BLUE_B`, `BLUE_C`, `TEAL`, `TEAL_B`, `GREEN`, `GREEN_B`, `YELLOW`, `YELLOW_C`, `GOLD`, `GOLD_A`, `RED`, `RED_B`, `LIGHT_GRAY`, `GRAY`, `ORANGE`, `PURPLE`, or hex codes (e.g. `"#FFFFFF"`, `"#3498db"`).
   - CRITICAL: DO NOT use `PURE_WHITE`, `PURE_RED`, `PURE_GREEN`, `PURE_BLUE`, or `CYAN`. Use `WHITE`, `RED`, `GREEN`, `BLUE`, `TEAL`.
3. STRICT RATE FUNCTIONS (NO CSS/WEB EASING NAMES):
   - CRITICAL: ONLY use official Manim CE rate functions: `smooth`, `linear`, `rush_into`, `slow_into`, `double_smooth`, `there_and_back`, `wiggle`.
   - CRITICAL: NEVER use web/CSS easing names like `ease_out_quad`, `ease_in_quad`, `ease_in_out_quad`, `ease_out_cubic`, `ease_in_cubic`, `ease_in_out_cubic`, `ease_out_sine`, `ease_in_sine`, `easeInOut`, `easeOut`, `easeIn`.
   - If in doubt, DO NOT pass `rate_func` (Manim defaults to `smooth`).
4. ANIMATION SYNTAX & METHODS:
   - Use `Create(...)` instead of `ShowCreation(...)`.
   - Use `ReplacementTransform(A, B)` or `Transform(A, B)` instead of deprecated transform variants.
   - For color changes in animations, use `obj.animate.set_color(...)` (e.g. `self.play(gear.animate.set_color(GRAY), run_time=1.5)`).
5. Layout & Positioning:
   - Position objects safely relative to each other using `.next_to()`, `.to_edge()`, `VGroup().arrange(DOWN, buff=0.4)`, or `.shift()`.
   {"- Vertical Format (9:16): Use smaller font sizes (24-30), arrange elements vertically, keep horizontal width <= 6." if is_vertical else "- Widescreen (16:9): Keep elements within 12 units width and 7 units height."}
6. Exact Timing Budget:
   - Total scene duration across all `self.play(...)` and `self.wait(...)` calls MUST equal EXACTLY ~{duration_sec:.2f} seconds.
7. Output format: Return ONLY runnable Python code with `from manim import *`.
"""

        user_prompt = f"""
Write the simple, clean, and student-friendly Manim CE v{manim_version} script for Scene {scene.scene_number}: "{scene.scene_title}".
Topic: {topic}
Target Duration: {duration_sec:.2f} seconds
Aspect Ratio: {aspect_ratio.value} ({"Vertical 9:16 Shorts" if is_vertical else "Widescreen 16:9"})

Scene Voiceover Script:
"{scene.narration}"

Visual Blueprint:
- Description: {scene.visuals.description}
- Math / Notation: {scene.visuals.math_formulas}
- Geometric Elements: {scene.visuals.geometric_elements}
- Color Palette: {scene.visuals.color_palette}
- Camera / Framing: {scene.visuals.camera_and_focus}

CRITICAL RULES TO AVOID ERRORS:
1. Rate Functions: ONLY use `smooth`, `linear`, `rush_into`, `slow_into` or omit `rate_func`. NEVER use `ease_out_quad`, `ease_in_quad`, `ease_out_cubic`, or any `ease_*` function!
2. Text/Formulas: ALWAYS use `Text(...)` with Unicode (e.g. `Text("pH = -log₁₀[H⁺]")`). NEVER use `MathTex` or `Tex`!
3. Colors: Use `WHITE` (never `PURE_WHITE`), `TEAL` (never `CYAN`), `RED`, `BLUE`, etc.
4. Simplicity: Keep visuals clean and student-friendly (maximum 2-3 visual beats, no visual clutter).
5. Pauses: Include gentle `self.wait(...)` pauses so students can comfortably absorb the concept.

Write complete, runnable Python code starting with `from manim import *` and `class {class_name}(Scene):`.
"""

        if self.is_new_sdk:
            from google.genai import types
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                )
            )
            self._record_usage(response)
            raw = response.text
        else:
            response = self.client.generate_content(f"{system_instruction}\n\n{user_prompt}")
            self._record_usage(response)
            raw = response.text

        return self._clean_python_markdown(raw)

    def repair_manim_code(
        self,
        scene: ScenePlan,
        duration_sec: float,
        failed_code: str,
        error_message: str,
        attempt: int,
        aspect_ratio: AspectRatio = AspectRatio.WIDESCREEN
    ) -> str:
        """
        Self-healing repair agent: analyzes Manim execution error tracebacks
        and provides corrected, simplified, and runnable code.
        """
        class_name = f"Scene{scene.scene_number}"
        try:
            import manim
            manim_version = getattr(manim, "__version__", "0.21.0")
        except Exception:
            manim_version = "0.21.0"

        prompt = f"""
You are debugging and auto-fixing a Python Manim Community Edition (v{manim_version}) script that failed to render.

Scene: {scene.scene_number} - {scene.scene_title}
Target Duration: {duration_sec:.2f} seconds
Class Name: {class_name}
Attempt: #{attempt}
Target Engine: Manim CE v{manim_version}

--- FAILED CODE ---
{failed_code}

--- ERROR LOG / TRACEBACK ---
{error_message}

--- CRITICAL REPAIR INSTRUCTIONS ---
1. Identify the exact root cause in the traceback:
   - If NameError for 'ease_out_quad', 'ease_in_quad', 'ease_out_cubic', or any easing name:
     Replace with standard `smooth` or `linear`, or remove `rate_func=...` entirely.
   - If NameError for 'PURE_WHITE', 'PURE_RED', 'PURE_GREEN', 'PURE_BLUE', 'CYAN', etc.:
     Replace with valid Manim constants (`WHITE`, `RED`, `GREEN`, `BLUE`, `TEAL`) or hex strings (`"#FFFFFF"`).
   - If error mentions 'latex' (FileNotFoundError: 'latex', pdflatex, etc.) or MathTex/Tex:
     CRITICAL: REPLACE ALL `MathTex(...)` and `Tex(...)` with `Text(...)` using Unicode characters (e.g. `Text("pH = -log₁₀[H⁺]", font_size=36, color=YELLOW_C)`, `Text("H₂O ⇌ H⁺ + OH⁻")`, `Text("a² + b² = c²")`). LaTeX is NOT installed on this machine!
   - If AttributeError or MethodNotFound: Use standard Manim CE v{manim_version} methods (`Create`, `Write`, `FadeIn`, `FadeOut`, `Transform`, `ReplacementTransform`, `Indicate`).
   - If SyntaxError / IndentationError: Fix Python syntax.
   - If Overlap / Dimension issue: Use `VGroup().arrange(DOWN, buff=0.4)` and `.to_edge(UP)`.
2. Keep the scene visual clean, elegant, and simple for students.
3. Ensure class name is `class {class_name}(Scene):` with `def construct(self):`.
4. Ensure animation durations (`run_time`) and `self.wait(...)` sum to ~{duration_sec:.2f} seconds.
5. Return ONLY the complete, corrected Python code.
"""

        if self.is_new_sdk:
            from google.genai import types
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                )
            )
            self._record_usage(response)
            raw = response.text
        else:
            response = self.client.generate_content(prompt)
            self._record_usage(response)
            raw = response.text

        return self._clean_python_markdown(raw)

    @staticmethod
    def _clean_json_markdown(text: str) -> str:
        """Strips markdown code blocks from JSON output."""
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

    @staticmethod
    def _clean_python_markdown(text: str) -> str:
        """Strips markdown code blocks from Python code output."""
        text = text.strip()
        match = re.search(r"```(?:python)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

