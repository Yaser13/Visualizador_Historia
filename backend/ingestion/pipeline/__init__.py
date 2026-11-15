"""Agent pipeline that turns a user-submitted URL into a draft observation.

Contract: docs/api/CONTRATO_USUARIOS_INGESTA.md §3. Technical notes:
docs/architecture/PIPELINE_AGENTES.md.

Modules:
- ``fetcher``: SSRF-safe download and main-text extraction.
- ``llm``: thin, injectable OpenAI Responses client (structured outputs, web search).
- ``agents``: versioned prompts and JSON schemas for researcher, extractor,
  verifier, geolocator and analyst.
- ``verification``: deterministic quote/date checks and corroboration (the main
  guarantee against invented content).
- ``geocoding``: Nominatim/OpenStreetMap geocoder (the LLM never gives coordinates).
- ``runner``: orchestration, ``AgentRun`` tracing and transactional persistence.
"""
from .errors import PipelineError

__all__ = ['PipelineError']
