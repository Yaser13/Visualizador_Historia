"""SSRF-safe download of news pages and main-text extraction (contract §3.1).

Policy, applied to the submitted URL and to every redirect hop:
- only ``http``/``https``, ports 80/443, no credentials in the URL;
- the host name is resolved and **every** address must be public (no private,
  loopback, link-local, reserved, multicast, unspecified, CGNAT or IPv4 embedded
  in IPv6 pointing to those); the connection is then pinned to the checked
  address (``Host`` header and TLS SNI keep the original name, so certificates
  are still verified) which closes the DNS-rebinding window;
- at most 5 redirects, 15 s in total, 3 MB of decoded body read in streaming
  (also protects against compression bombs), only HTML or plain text;
- environment proxies are ignored (``trust_env=False``).

Extraction: ``trafilatura`` for the main text (fallback: ``<p>`` elements) and
``lxml`` for metadata (``og:title``, ``og:site_name``, ``article:published_time``,
``<title>``, ``<html lang>``). ``published_at`` is only taken from metadata,
never guessed.
"""
import codecs
import hashlib
import ipaddress
import re
import socket
import time
import unicodedata
from dataclasses import dataclass
from datetime import date
from urllib.parse import unquote_plus, urljoin, urlsplit, urlunsplit

import httpx
import lxml.html
import trafilatura
from django.conf import settings

from .errors import FetchError, UnsafeURLError

ALLOWED_SCHEMES = {'http', 'https'}
ALLOWED_PORTS = {80, 443}
DEFAULT_PORTS = {'http': 80, 'https': 443}
ALLOWED_CONTENT_TYPES = {'text/html', 'application/xhtml+xml', 'text/plain'}
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 15.0
MAX_BYTES = 3 * 1024 * 1024
MAX_TEXT_CHARS = 200_000
MIN_MAIN_TEXT_CHARS = 200
DEFAULT_USER_AGENT = 'GeoObservatorio/0.1'
_NAT64 = ipaddress.ip_network('64:ff9b::/96')
_META_CHARSET = re.compile(rb'<meta[^>]+charset\s*=\s*["\']?\s*([A-Za-z0-9_\-:.]+)', re.IGNORECASE)
_XML_DECLARATION = re.compile(r'^\s*<\?xml[^>]*\?>', re.IGNORECASE)


def canonical_url(url):
    """Comparable form of a URL: lowercase scheme/host, no default port, fragment or ``utm_*`` parameters."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or '').lower()
    if ':' in host:
        host = f'[{host}]'
    try:
        port = parts.port
    except ValueError:
        port = None
    netloc = host if port in (None, DEFAULT_PORTS.get(scheme)) else f'{host}:{port}'
    # Raw ``key=value`` pairs are kept with their original encoding (as ``ingestion.services.normalize_url``).
    query = '&'.join(pair for pair in parts.query.split('&')
                     if pair and not unquote_plus(pair.split('=', 1)[0]).lower().startswith('utm_'))
    return urlunsplit((scheme, netloc, parts.path or '/', query, ''))


def is_public_address(address):
    """True only for globally routable unicast addresses."""
    try:
        ip = ipaddress.ip_address(address.split('%', 1)[0])
    except ValueError:
        return False
    candidates = [ip]
    if ip.version == 6:
        if ip.ipv4_mapped:
            candidates.append(ip.ipv4_mapped)
        if ip.sixtofour:
            candidates.append(ip.sixtofour)
        if ip.teredo:
            candidates.extend(ip.teredo)
        if ip in _NAT64:
            candidates.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    for item in candidates:
        if (not item.is_global or item.is_private or item.is_loopback or item.is_link_local or item.is_reserved
                or item.is_multicast or item.is_unspecified):
            return False
    return True


def default_resolver(host, port):
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as error:
        raise FetchError(f'No se pudo resolver el dominio «{host}».') from error
    return [info[4][0] for info in infos]


@dataclass
class Target:
    url: str
    scheme: str
    host: str
    port: int
    address: str


def check_url(url, resolver=default_resolver):
    """Validate ``url`` against the SSRF policy and return the pinned ``Target``."""
    if not isinstance(url, str) or len(url) > 2000:
        raise UnsafeURLError('URL no válida.')
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f'Esquema no permitido «{scheme or "(ninguno)"}»: solo se admiten http y https.')
    if parts.username is not None or parts.password is not None:
        raise UnsafeURLError('La URL no puede incluir credenciales.')
    host = (parts.hostname or '').rstrip('.')
    if not host:
        raise UnsafeURLError('La URL no tiene dominio.')
    try:
        port = parts.port or DEFAULT_PORTS[scheme]
    except ValueError as error:
        raise UnsafeURLError('Puerto no válido.') from error
    if port not in ALLOWED_PORTS:
        raise UnsafeURLError(f'Puerto no permitido ({port}): solo 80 y 443.')
    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        try:
            ascii_host = host.encode('idna').decode('ascii')
        except UnicodeError as error:
            raise UnsafeURLError('Dominio no válido.') from error
        if ascii_host in ('localhost',) or ascii_host.endswith(('.localhost', '.local', '.internal', '.home.arpa')):
            raise UnsafeURLError('El dominio apunta a una red local.')
        addresses = list(dict.fromkeys(resolver(ascii_host, port)))
        host = ascii_host
    if not addresses:
        raise FetchError(f'No se pudo resolver el dominio «{host}».')
    unsafe = [address for address in addresses if not is_public_address(address)]
    if unsafe:
        raise UnsafeURLError('La URL apunta a una dirección de red privada o reservada; no se descarga.')
    return Target(url=urlunsplit((scheme, parts.netloc, parts.path or '/', parts.query, '')),
                  scheme=scheme, host=host, port=port, address=addresses[0])


@dataclass
class Download:
    url: str
    final_url: str
    http_status: int
    content_type: str
    body: bytes
    encoding: str | None


@dataclass
class Page:
    """Downloaded and extracted document (fields of ``FetchedDocument``)."""
    url: str
    final_url: str
    http_status: int
    content_type: str
    title: str
    publisher: str
    published_at: date | None
    language: str
    text: str

    @property
    def content_hash(self):
        return hashlib.sha256(self.text.encode('utf-8')).hexdigest()


class SafeFetcher:
    """Downloader with the SSRF policy above. ``transport`` and ``resolver`` are injectable for tests."""

    def __init__(self, *, user_agent=None, resolver=default_resolver, transport=None, timeout=TIMEOUT_SECONDS,
                 max_bytes=MAX_BYTES, max_redirects=MAX_REDIRECTS, clock=time.monotonic):
        self.user_agent = user_agent or getattr(settings, 'INGESTION_USER_AGENT', '') or DEFAULT_USER_AGENT
        self.resolver = resolver
        self.transport = transport
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.clock = clock

    def fetch(self, url):
        """Download and extract ``url``; raises ``FetchError``/``UnsafeURLError``."""
        return extract_page(self.download(url))

    def download(self, url):
        deadline = self.clock() + self.timeout
        current = url
        with httpx.Client(transport=self.transport, trust_env=False, follow_redirects=False, verify=True) as client:
            for _hop in range(self.max_redirects + 1):
                target = check_url(current, self.resolver)
                response = self._send(client, target, deadline)
                try:
                    if response.status_code in REDIRECT_STATUSES:
                        location = response.headers.get('location')
                        if not location:
                            raise FetchError('Redirección sin destino.', http_status=response.status_code)
                        current = urljoin(target.url, location.strip())
                        continue
                    return self._read(response, url, target.url, deadline)
                finally:
                    response.close()
        raise FetchError(f'Demasiadas redirecciones (máximo {self.max_redirects}).')

    def _remaining(self, deadline):
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise FetchError(f'Tiempo de descarga agotado ({int(self.timeout)} s).')
        return remaining

    def _send(self, client, target, deadline):
        parts = urlsplit(target.url)
        address = f'[{target.address}]' if ':' in target.address else target.address
        pinned = urlunsplit((target.scheme, f'{address}:{target.port}', parts.path or '/', parts.query, ''))
        host_header = target.host if target.port == DEFAULT_PORTS[target.scheme] else f'{target.host}:{target.port}'
        remaining = self._remaining(deadline)
        request = client.build_request(
            'GET', pinned,
            headers={'Host': host_header, 'User-Agent': self.user_agent,
                     'Accept': 'text/html,application/xhtml+xml,text/plain;q=0.9',
                     'Accept-Language': 'es,en;q=0.8,*;q=0.5'},
            timeout=httpx.Timeout(remaining),
            extensions={'sni_hostname': target.host},
        )
        try:
            return client.send(request, stream=True)
        except httpx.TimeoutException as error:
            raise FetchError(f'Tiempo de descarga agotado ({int(self.timeout)} s).') from error
        except httpx.HTTPError as error:
            raise FetchError(f'No se pudo conectar con «{target.host}».') from error

    def _read(self, response, requested_url, final_url, deadline):
        status = response.status_code
        content_type_header = response.headers.get('content-type', '')
        media_type = content_type_header.split(';', 1)[0].strip().lower()
        if not 200 <= status < 300:
            raise FetchError(f'El servidor respondió con el código {status}.', http_status=status, content_type=media_type)
        if media_type not in ALLOWED_CONTENT_TYPES:
            raise FetchError(f'Tipo de contenido no admitido «{media_type or "desconocido"}»: solo HTML o texto.',
                             http_status=status, content_type=media_type)
        declared = response.headers.get('content-length', '')
        if declared.isdigit() and int(declared) > self.max_bytes:
            raise FetchError(self._too_large(), http_status=status, content_type=media_type)
        chunks, size = [], 0
        try:
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > self.max_bytes:
                    raise FetchError(self._too_large(), http_status=status, content_type=media_type)
                chunks.append(chunk)
                self._remaining(deadline)
        except httpx.TimeoutException as error:
            raise FetchError(f'Tiempo de descarga agotado ({int(self.timeout)} s).', http_status=status) from error
        except httpx.HTTPError as error:
            raise FetchError('La descarga se interrumpió.', http_status=status) from error
        return Download(url=requested_url, final_url=final_url, http_status=status, content_type=media_type,
                        body=b''.join(chunks), encoding=response.charset_encoding)

    def _too_large(self):
        return f'El documento supera el tamaño máximo ({self.max_bytes // (1024 * 1024)} MB).'


def _codec(name):
    if not name:
        return None
    try:
        return codecs.lookup(name.strip()).name
    except LookupError:
        return None


def decode_body(body, declared=None):
    if body.startswith(codecs.BOM_UTF8):
        return body[len(codecs.BOM_UTF8):].decode('utf-8', errors='replace')
    encoding = _codec(declared)
    if encoding is None:
        match = _META_CHARSET.search(body[:4096])
        encoding = _codec(match.group(1).decode('ascii', 'ignore')) if match else None
    if encoding is None:
        try:
            return body.decode('utf-8')
        except UnicodeDecodeError:
            encoding = 'cp1252'
    return body.decode(encoding, errors='replace')


def _clean_text(text):
    """NFC text, one paragraph per line, without empty lines; NFC keeps excerpts exact substrings."""
    text = unicodedata.normalize('NFC', text)
    lines = [re.sub(r'[ \t ]+', ' ', line).strip() for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n')]
    return '\n'.join(line for line in lines if line)[:MAX_TEXT_CHARS]


def _parse_date(value):
    match = re.match(r'\s*(\d{4}-\d{2}-\d{2})', value or '')
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def html_metadata(tree):
    meta = {}
    for element in tree.iter('meta'):
        key = (element.get('property') or element.get('name') or element.get('itemprop') or '').strip().lower()
        content = (element.get('content') or '').strip()
        if key and content and key not in meta:
            meta[key] = content
    title_element = tree.find('.//title')
    page_title = title_element.text_content().strip() if title_element is not None else ''
    html_element = tree if tree.tag == 'html' else tree.getroottree().getroot()
    language = (html_element.get('lang') or meta.get('og:locale') or '').strip().replace('_', '-')[:16]
    return {
        'title': (meta.get('og:title') or page_title)[:500],
        'publisher': meta.get('og:site_name', '')[:255],
        'published_at': _parse_date(meta.get('article:published_time')),
        'language': language,
    }


def extract_page(download):
    text = decode_body(download.body, download.encoding)
    base = dict(url=download.url, final_url=download.final_url, http_status=download.http_status,
                content_type=download.content_type)
    if download.content_type == 'text/plain':
        return Page(**base, title='', publisher='', published_at=None, language='', text=_clean_text(text))
    markup = _XML_DECLARATION.sub('', text)
    try:
        tree = lxml.html.document_fromstring(markup)
    except (lxml.etree.ParserError, ValueError) as error:
        raise FetchError('No se pudo interpretar el HTML descargado.', http_status=download.http_status) from error
    metadata = html_metadata(tree)
    main = trafilatura.extract(markup, url=download.final_url, output_format='txt', include_comments=False,
                               include_tables=False, include_images=False, include_links=False,
                               favor_precision=True, with_metadata=False) or ''
    if len(main) < MIN_MAIN_TEXT_CHARS:
        paragraphs = [p.text_content() for p in tree.iter('p')]
        fallback = '\n'.join(item for item in paragraphs if item.strip())
        if len(fallback) > len(main):
            main = fallback
    return Page(**base, **metadata, text=_clean_text(main))
