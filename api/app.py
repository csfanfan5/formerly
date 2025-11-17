"""
Flask entrypoint for Vercel.

Vercel looks for a module (e.g., api/app.py) that exports a Flask
application named `app`. We re-export the `app` defined in page_answers.
"""

from page_answers import app  # noqa: F401


