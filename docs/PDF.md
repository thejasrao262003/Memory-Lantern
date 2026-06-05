# PDF.md — Storybook PDF Specification

## Overview

The PDF is assembled on the HF Space CPU using WeasyPrint + Jinja2.
No GPU required. No Modal call. Pure Python.

The PDF is the artifact the family keeps. Polish matters here.

---

## Page structure

| Page | Content |
|---|---|
| Cover | Person's name, event name, decorative border |
| Scene 1 | Illustration (top 60%), scene text (bottom 40%) |
| Scene 2 | Same layout |
| Scene 3 | Same layout |
| Scene 4 | Same layout |
| Scene 5 | Same layout |
| Final page | First uploaded photo (full page), single line at bottom |

Total pages: 7

---

## Final page rule — HARDCODED

The final page is ALWAYS:

```
[First uploaded photo, filling the full page]

[Bottom of page, centred, italic serif font]
[person_name] looked out at everything she had made, and it was good.
```

This is not optional. It is not configurable. It does not change.
The Jinja2 template always renders this page regardless of story content.
Do not remove it. Do not make it conditional. Do not generate it dynamically.

---

## Typography

| Element | Font | Size | Colour |
|---|---|---|---|
| Person's name (cover) | Lora Bold | 36px | #3D2B1F |
| Event name (cover) | Lora Italic | 24px | #6B4226 |
| Scene text | Lora Regular | 18px | #3D2B1F |
| Final page line | Lora Italic | 22px | #3D2B1F |

Font source: Google Fonts — `https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,700;1,400`

WeasyPrint fetches this at PDF generation time. Requires internet access on the HF Space.

---

## Colour palette

| Role | Hex |
|---|---|
| Page background | #FDF6EC (warm cream) |
| Text | #3D2B1F (dark brown) |
| Accent border | #C4956A (warm tan) |
| Scene card background | #F5EBD8 (lighter cream) |

---

## Image handling in PDF

- Illustrations: resize to 1024×1024 max before embedding (WeasyPrint handles display)
- Cover photo: resize to 800px on longest side
- Final page photo: embed at full resolution (WeasyPrint fills the page)
- Format: PNG for illustrations, JPEG for photos
- Convert all images to base64 and embed inline in the HTML template
  (avoids file path issues in WeasyPrint)

---

## Jinja2 template structure

File: `app/pdf/templates/storybook.html`

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
    <style>
        @page {
            size: A5;
            margin: 0;
        }
        body {
            font-family: 'Lora', Georgia, serif;
            background-color: #FDF6EC;
            color: #3D2B1F;
            margin: 0;
            padding: 0;
        }
        .page {
            width: 148mm;   /* A5 width */
            height: 210mm;  /* A5 height */
            page-break-after: always;
            overflow: hidden;
        }
        .cover {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 40px;
            border: 8px solid #C4956A;
            margin: 20px;
            height: calc(210mm - 40px);
            box-sizing: border-box;
        }
        .scene-page {
            display: flex;
            flex-direction: column;
        }
        .scene-illustration {
            width: 100%;
            height: 60%;
            object-fit: cover;
        }
        .scene-text {
            padding: 24px 32px;
            font-size: 14pt;
            line-height: 1.8;
        }
        .final-page {
            position: relative;
        }
        .final-photo {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .final-text {
            position: absolute;
            bottom: 32px;
            left: 0;
            right: 0;
            text-align: center;
            font-style: italic;
            font-size: 16pt;
            color: #FDF6EC;
            text-shadow: 1px 1px 3px rgba(0,0,0,0.8);
            padding: 0 32px;
        }
    </style>
</head>
<body>

<!-- Cover page -->
<div class="page cover">
    <h1 style="font-size: 28pt; margin: 0;">{{ person_name }}</h1>
    <p style="font-size: 18pt; font-style: italic; color: #6B4226;">{{ event }}</p>
</div>

<!-- Scene pages -->
{% for scene in scenes %}
<div class="page scene-page">
    <img class="scene-illustration" src="data:image/png;base64,{{ images_b64[loop.index0] }}" alt="Illustration for scene {{ scene.scene_number }}">
    <div class="scene-text">{{ scene.text }}</div>
</div>
{% endfor %}

<!-- Final page — HARDCODED — DO NOT MODIFY -->
<div class="page final-page">
    <img class="final-photo" src="data:image/jpeg;base64,{{ first_photo_b64 }}" alt="{{ person_name }}">
    <div class="final-text">{{ person_name }} looked out at everything she had made, and it was good.</div>
</div>

</body>
</html>
```

---

## builder.py function signature

```python
def build_pdf(
    scenes: list[SceneDict],
    images: list[Image.Image],
    person_name: str,
    event: str,
    first_photo: Image.Image,
    output_path: Path,
) -> Path:
    """
    Assemble storybook PDF.

    Args:
        scenes: 5 SceneDict objects in order
        images: 5 PIL images in scene order
        person_name: Used in cover and final page
        event: Used in cover subtitle
        first_photo: Original uploaded photo — used on final page
        output_path: Where to save the PDF

    Returns:
        output_path (same as input, confirmed written)

    Note:
        The final page is ALWAYS appended. It is not conditional.
        The final page text is ALWAYS the hardcoded sentence.
        This is not a parameter.
    """
```

---

## WeasyPrint dependencies

WeasyPrint requires system libraries. Add to HF Space `packages.txt`:

```
libpango-1.0-0
libcairo2
libgdk-pixbuf2.0-0
libffi-dev
shared-mime-info
```

These are pre-installed on most HF Space base images but list them explicitly
to prevent breakage on image updates.
