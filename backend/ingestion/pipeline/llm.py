"""Thin, injectable client for the OpenAI Responses API.

Two operations are used by the agents:

- ``structured``: ``responses.create`` with ``text.format`` = strict JSON Schema
  (Structured Outputs). The returned JSON is parsed and still re-validated by the
  deterministic checks of ``verification``/``runner``.
- ``web_search``: ``responses.create`` with the hosted ``web_search`` tool. Only
  the ``url_citation`` annotations attached by the tool to the output text are
  returned as candidate URLs; URLs written by the model in the text itself are
  ignored.

``store=False`` so the downloaded material is not kept as a stored response.
Transient errors (timeouts, connection, 408/409/429/5xx) are retried a limited
number of times by the official SDK (``max_retries``). The API key is never
logged nor included in error messages.

Tests inject any object exposing ``structured(...)`` and ``web_search(...)``
returning ``LLMResult``.
"""
import json
import logging
from dataclasses import dataclass, field

from django.conf import settings

from .errors import ConfigurationError, LLMError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'gpt-5-mini'
DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_MAX_OUTPUT_TOKENS = 16_000
MISSING_KEY_MESSAGE = 'Falta OPENAI_API_KEY: configúrala en .env (o como variable de entorno) y vuelve a intentarlo.'


@dataclass
class Citation:
    url: str
    title: str = ''


@dataclass
class LLMResult:
    data: dict | None = None
    text: str = ''
    citations: list = field(default_factory=list)
    model: str = ''
    tokens_in: int | None = None
    tokens_out: int | None = None
    response_id: str = ''


def _usage(response):
    usage = getattr(response, 'usage', None)
    if usage is None:
        return None, None
    return getattr(usage, 'input_tokens', None), getattr(usage, 'output_tokens', None)


def _check_complete(response):
    status = getattr(response, 'status', None)
    if status == 'incomplete':
        details = getattr(response, 'incomplete_details', None)
        reason = getattr(details, 'reason', None) or 'desconocido'
        raise LLMError(f'La respuesta del modelo quedó incompleta ({reason}).')
    if status == 'failed':
        raise LLMError('El modelo no pudo completar la respuesta.')


def _message_parts(response):
    for item in getattr(response, 'output', None) or []:
        if getattr(item, 'type', None) != 'message':
            continue
        for content in getattr(item, 'content', None) or []:
            yield content


class OpenAIClient:
    def __init__(self, *, api_key, model=None, search_model=None, timeout=None, max_retries=None,
                 reasoning_effort=None, max_output_tokens=None, sdk_client=None):
        if not api_key and sdk_client is None:
            raise ConfigurationError(MISSING_KEY_MESSAGE)
        self.model = model or DEFAULT_MODEL
        self.search_model = search_model or self.model
        self.reasoning_effort = reasoning_effort or None
        self.max_output_tokens = max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS
        if sdk_client is None:
            from openai import OpenAI  # imported lazily: tests never need the SDK
            sdk_client = OpenAI(api_key=api_key, timeout=timeout or DEFAULT_TIMEOUT,
                                max_retries=DEFAULT_MAX_RETRIES if max_retries is None else max_retries)
        self._client = sdk_client

    def _create(self, **kwargs):
        from openai import OpenAIError
        if self.reasoning_effort:
            kwargs['reasoning'] = {'effort': self.reasoning_effort}
        try:
            return self._client.responses.create(store=False, max_output_tokens=self.max_output_tokens, **kwargs)
        except OpenAIError as error:
            # Status code and class only: SDK messages may echo request details.
            status = getattr(error, 'status_code', None)
            logger.warning('OpenAI error %s (status %s)', type(error).__name__, status)
            if status == 401:
                raise ConfigurationError('OPENAI_API_KEY no es válida o no tiene acceso al modelo configurado.') from error
            label = f' (código {status})' if status else ''
            raise LLMError(f'Error al llamar a la API de OpenAI: {type(error).__name__}{label}.') from error

    def structured(self, *, instructions, input, schema_name, schema, model=None):
        model = model or self.model
        response = self._create(
            model=model, instructions=instructions, input=input,
            text={'format': {'type': 'json_schema', 'name': schema_name, 'schema': schema, 'strict': True}},
        )
        _check_complete(response)
        text = ''
        for content in _message_parts(response):
            if getattr(content, 'type', None) == 'refusal':
                raise LLMError('El modelo rechazó la tarea.')
            if getattr(content, 'type', None) == 'output_text':
                text += content.text
        try:
            data = json.loads(text)
        except (TypeError, ValueError) as error:
            raise LLMError('El modelo no devolvió JSON válido.') from error
        if not isinstance(data, dict):
            raise LLMError('El modelo no devolvió un objeto JSON.')
        tokens_in, tokens_out = _usage(response)
        return LLMResult(data=data, text=text, model=getattr(response, 'model', model) or model,
                         tokens_in=tokens_in, tokens_out=tokens_out, response_id=getattr(response, 'id', '') or '')

    def web_search(self, *, instructions, input, model=None):
        model = model or self.search_model
        response = self._create(model=model, instructions=instructions, input=input,
                                tools=[{'type': 'web_search', 'search_context_size': 'medium'}], tool_choice='auto')
        _check_complete(response)
        text, citations = '', []
        for content in _message_parts(response):
            if getattr(content, 'type', None) != 'output_text':
                continue
            text += content.text
            for annotation in getattr(content, 'annotations', None) or []:
                if getattr(annotation, 'type', None) == 'url_citation' and getattr(annotation, 'url', None):
                    citations.append(Citation(url=annotation.url, title=getattr(annotation, 'title', '') or ''))
        tokens_in, tokens_out = _usage(response)
        return LLMResult(text=text, citations=citations, model=getattr(response, 'model', model) or model,
                         tokens_in=tokens_in, tokens_out=tokens_out, response_id=getattr(response, 'id', '') or '')


def build_client():
    """Client configured from ``settings``; raises ``ConfigurationError`` without ``OPENAI_API_KEY``."""
    api_key = (getattr(settings, 'OPENAI_API_KEY', '') or '').strip()
    if not api_key:
        raise ConfigurationError(MISSING_KEY_MESSAGE)
    return OpenAIClient(
        api_key=api_key,
        model=getattr(settings, 'OPENAI_MODEL', '') or DEFAULT_MODEL,
        search_model=getattr(settings, 'OPENAI_SEARCH_MODEL', '') or None,
        timeout=getattr(settings, 'OPENAI_TIMEOUT', None),
        max_retries=getattr(settings, 'OPENAI_MAX_RETRIES', None),
        reasoning_effort=getattr(settings, 'OPENAI_REASONING_EFFORT', None),
        max_output_tokens=getattr(settings, 'OPENAI_MAX_OUTPUT_TOKENS', None),
    )
