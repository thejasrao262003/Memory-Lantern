"""Modal inference backends.

Each module defines a standalone Modal ``App`` wrapping one model. Deploy them
individually with ``modal deploy modal_backends/<name>.py``. They are not
imported by the Gradio app — the app reaches them over HTTPS.
"""
