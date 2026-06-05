# TESTING.md — Test Strategy

## Philosophy

This is a hackathon project. Tests exist to:
1. Prevent regressions on the pipeline data contracts
2. Verify prompt outputs meet acceptance criteria
3. Catch import errors and wiring mistakes before demo day

We do NOT test Modal endpoints directly in CI (too slow, costs money).
We mock all Modal calls in unit tests.

---

## Test structure

```
tests/
├── __init__.py
├── test_orchestrator.py       # Pipeline integration (mocked Modal)
├── test_prompt_builder.py     # Prompt output validation
├── test_pdf_builder.py        # PDF assembly (no Modal)
├── test_session_store.py      # Storage logic (mocked HF API)
├── test_validation.py         # Input validation logic
└── fixtures/
    ├── sample_memory.json     # Margaret's car story
    ├── sample_photo.jpg       # 64x64 solid colour test image
    ├── sample_photo_analysis.json  # Pre-computed PhotoAnalysis
    └── sample_scenes.json     # Pre-computed list[SceneDict]
```

---

## Fixture data

### tests/fixtures/sample_memory.json
```json
{
    "person_name": "Margaret",
    "event": "Buying her first car",
    "memory_text": "When she was young, she saved money for nearly three years to buy her first car. Her mother thought she was wasting her savings, but when she finally bought it, she couldn't stop smiling. The next weekend they drove to the coast together.",
    "expected_scene_count": 5
}
```

### tests/fixtures/sample_photo_analysis.json
```json
{
    "era": "1960s",
    "people_descriptions": [
        "A woman in her late 20s, smiling broadly, holding car keys",
        "An older woman, her mother, standing beside her laughing"
    ],
    "locations": ["Outside a small car dealership", "A 1960s high street"],
    "emotional_register": "joyful and triumphant",
    "key_objects": ["A small red car", "Car keys"],
    "style_period": "mid-century warm film tones"
}
```

### tests/fixtures/sample_scenes.json
```json
[
    {
        "scene_number": 1,
        "text": "You count the coins in the tin one more time, Margaret. Three years of careful saving, and today is the day.",
        "illustration_prompt": "A young woman counting coins at a kitchen table, warm 1960s kitchen, focused expression",
        "emotional_beat": "anticipation"
    },
    {
        "scene_number": 2,
        "text": "The salesman hands you the keys and they are heavier than you expected. Your mother stands beside you, shaking her head and smiling at the same time.",
        "illustration_prompt": "A young woman receiving car keys from a suited salesman, elderly mother beside her smiling, 1960s car lot",
        "emotional_beat": "triumph"
    },
    {
        "scene_number": 3,
        "text": "You sit behind the wheel for a full minute before starting the engine. It smells like new carpet and possibility.",
        "illustration_prompt": "Close-up of a young woman in the driver's seat of a small red car, hands on wheel, 1960s interior",
        "emotional_beat": "wonder"
    },
    {
        "scene_number": 4,
        "text": "The coast road opens up ahead of you and your mother reaches over and squeezes your hand. Neither of you says anything.",
        "illustration_prompt": "Two women in a small red car on a coastal road, sea visible, warm golden afternoon light, 1960s",
        "emotional_beat": "tenderness"
    },
    {
        "scene_number": 5,
        "text": "You park on the cliff top and look out at the sea. It is wide and blue and entirely yours. Margaret, you think. You actually did it.",
        "illustration_prompt": "A small red car parked on a coastal cliff, woman standing beside it looking at the sea, 1960s, golden hour",
        "emotional_beat": "quiet pride"
    }
]
```

---

## Key tests to write

### test_orchestrator.py

```python
from unittest.mock import patch, MagicMock
from app.pipeline.orchestrator import generate_storybook
from tests.fixtures import load_fixtures

@patch("app.pipeline.photo_analyzer.MiniCPMVision")
@patch("app.pipeline.story_generator.StoryGenerator")
@patch("app.pipeline.illustrator.Illustrator")
@patch("app.pipeline.narrator.Narrator")
@patch("app.pipeline.adapter.Adapter")
def test_full_pipeline_success(mock_adapter, mock_narrator, mock_illustrator,
                                mock_story, mock_vision):
    """Pipeline runs all 5 stages in order and returns StoryResult."""
    # Setup mocks to return fixture data
    mock_vision.return_value.analyze.remote.return_value = load_fixtures("sample_photo_analysis.json")
    mock_story.return_value.generate.remote.return_value = load_fixtures("sample_scenes.json")
    mock_illustrator.return_value.illustrate.remote.return_value = b"fake_png_bytes"
    mock_narrator.return_value.narrate.remote.return_value = b"fake_wav_bytes"

    result = generate_storybook(
        person_name="Margaret",
        event="Buying her first car",
        memory_text="She saved for three years...",
        photos=[Path("tests/fixtures/sample_photo.jpg")],
        session_id="test-session-id",
        progress=MagicMock(),
    )

    assert result.person_name == "Margaret"
    assert len(result.scenes) == 5
    assert len(result.images) == 5
    assert result.audio_path.exists()
    assert result.pdf_path.exists()


def test_pipeline_vision_failure_raises_pipeline_error():
    """Vision endpoint failure returns user-friendly error."""
    with patch("app.pipeline.photo_analyzer.MiniCPMVision") as mock:
        mock.return_value.analyze.remote.side_effect = Exception("Connection timeout")
        result = generate_storybook(...)
        assert isinstance(result, str)
        assert "try again" in result.lower()


def test_illustration_partial_failure_continues():
    """One illustration failing should not fail the whole pipeline."""
    # Mock one illustration to fail, others to succeed
    call_count = 0
    def illustrate_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 3:  # Scene 3 fails
            raise Exception("GPU OOM")
        return b"fake_png_bytes"
    ...
    # Verify: result.images has 5 entries, scene 3 is a placeholder
    assert len(result.images) == 5
```

### test_prompt_builder.py

```python
def test_story_prompt_contains_person_name():
    prompt = build_story_prompt(sample_analysis, "She saved for years...", "Margaret", "car")
    assert "Margaret" in prompt

def test_story_prompt_with_adaptation_weights():
    weights = {"professional_identity": 0.9, "family_relationships": 0.2}
    prompt = build_story_prompt(sample_analysis, "...", "Margaret", "car", weights)
    assert "professional_identity" in prompt
    assert "emphasise" in prompt.lower()

def test_illustration_prompt_includes_era_style():
    scene = {"illustration_prompt": "A woman at a car dealership", "emotional_beat": "triumph", "scene_number": 1, "text": "..."}
    prompt = build_illustration_prompt(scene, "mid-century warm film tones", "1960s")
    assert "watercolour" in prompt
    assert "1960s" in prompt or "mid-century" in prompt

def test_adaptation_prompt_format():
    log = [
        {"date": "2026-06-10", "scene_number": 2, "reaction": "smiled", "notes": ""},
        {"date": "2026-06-10", "scene_number": 4, "reaction": "unsettled", "notes": ""},
    ]
    prompt = build_adaptation_prompt(log)
    assert "smiled" in prompt
    assert "unsettled" in prompt
    assert "professional_identity" in prompt
```

### test_pdf_builder.py

```python
def test_pdf_generates_successfully():
    pdf_path = build_pdf(
        scenes=load_fixtures("sample_scenes.json"),
        images=[create_test_image() for _ in range(5)],
        person_name="Margaret",
        event="Buying her first car",
        first_photo=create_test_image(),
        output_path=Path("/tmp/test_storybook.pdf"),
    )
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 10000  # Non-trivial PDF

def test_pdf_always_has_final_page():
    """The hardcoded final page must always be present."""
    pdf_path = build_pdf(...)
    # Read PDF and verify final page text
    # Use PyPDF2 or similar to extract text
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    last_page_text = reader.pages[-1].extract_text()
    assert "looked out at everything she had made" in last_page_text
    assert "Margaret" in last_page_text

def test_pdf_has_correct_page_count():
    """Cover + 5 scenes + final page = 7 pages."""
    pdf_path = build_pdf(...)
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 7
```

---

## Running tests

```bash
# All tests
pytest tests/ -v

# Just pipeline tests
pytest tests/test_orchestrator.py -v

# Just prompt tests
pytest tests/test_prompt_builder.py -v

# With coverage
pytest tests/ --cov=app --cov-report=term-missing
```

---

## Pre-demo checklist

Run this before every demo:

```bash
# 1. All tests pass
pytest tests/ -v

# 2. App imports cleanly
python -c "from app.main import demo; print('Import OK')"

# 3. Gradio launches
python app/main.py
# Open http://localhost:7860 — verify three tabs visible, no console errors

# 4. Modal endpoints live
modal app list
# All 5 should show "deployed"

# 5. End-to-end test with fixture data
# (manual — upload sample_photo.jpg, enter Margaret fixture data, generate)
```
