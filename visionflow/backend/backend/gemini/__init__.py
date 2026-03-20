"""Gemini AI integration for VisionFlow.

Modules:
    client              — Gemini API client singleton
    schemas             — Structured Output response schemas (Phase 2)
    tools               — Function Calling tool definitions (Phase 3)
    workflow_generator  — AI-powered workflow generation (Phase 2)
    replay_agent        — AI-powered replay with tool use (Phase 3)
    verifier            — Result verification + failure diagnosis (Phase 3)
    screen_analyzer     — Screen anomaly detection (Phase 3)
    computer_use        — Computer Use autonomous agent (Phase 3.5)
    reverse_generator   — CU action log → deterministic workflow conversion (Phase 3.5)
"""
