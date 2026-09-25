"""
Vercel Python entrypoint for NCOF Platform API.

This file intentionally exposes the FastAPI application as a
top-level variable named `app` so Vercel can detect it.
"""

from app.main import app
