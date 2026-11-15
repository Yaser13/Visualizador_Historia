"""Exceptions of the ingestion pipeline. Messages are user-facing (Spanish) and never contain secrets."""


class PipelineError(Exception):
    """A step failed; ``str(error)`` is shown to the user in ``NewsSubmission.error``."""


class FetchError(PipelineError):
    """Download rejected or failed. ``http_status`` is set when the server answered."""

    def __init__(self, message, http_status=None, content_type=''):
        super().__init__(message)
        self.http_status = http_status
        self.content_type = content_type


class UnsafeURLError(FetchError):
    """URL rejected by the SSRF policy (scheme, port, credentials or non-public address)."""


class LLMError(PipelineError):
    """The language model call failed or returned unusable output."""


class ConfigurationError(PipelineError):
    """Missing or invalid configuration (e.g. ``OPENAI_API_KEY``)."""
