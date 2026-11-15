"""Nominatim / OpenStreetMap geocoder (contract §3.5).

- Coordinates come only from Nominatim, never from the language model.
- Usage policy of the public instance: at most 1 request per second (enforced
  process-wide with a lock), an identifying User-Agent from
  ``INGESTION_USER_AGENT`` (no personal data), results cached (Django cache
  framework; with the default ``LocMemCache`` the cache is in memory, with a
  database/file cache it persists) and ODbL attribution on every location.
- ``NOMINATIM_URL`` is the full search endpoint (default
  ``https://nominatim.openstreetmap.org/search``). It is operator configuration,
  not user input; redirects are not followed.
"""
import hashlib
import math
import threading
import time
from dataclasses import dataclass

import httpx
from django.conf import settings
from django.core.cache import cache

DEFAULT_URL = 'https://nominatim.openstreetmap.org/search'
CACHE_SECONDS = 30 * 24 * 3600
MIN_INTERVAL_SECONDS = 1.0
OSM_TYPES = {'node', 'way', 'relation'}
ATTRIBUTION = ('Datos © colaboradores de OpenStreetMap, disponibles bajo la licencia ODbL 1.0 '
               '(https://www.openstreetmap.org/copyright). Geocodificación mediante Nominatim.')

_lock = threading.Lock()
_last_request = [0.0]


@dataclass
class Place:
    query: str
    latitude: float
    longitude: float
    osm_type: str
    osm_id: int
    display_name: str

    @property
    def osm_url(self):
        return f'https://www.openstreetmap.org/{self.osm_type}/{self.osm_id}'

    @property
    def locator(self):
        return f'OSM {self.osm_type} {self.osm_id}'


def _parse(query, payload):
    if not isinstance(payload, list) or not payload:
        return None
    item = payload[0]
    if not isinstance(item, dict):
        return None
    try:
        latitude, longitude = float(item['lat']), float(item['lon'])
        osm_type, osm_id = str(item['osm_type']).lower(), int(item['osm_id'])
    except (KeyError, TypeError, ValueError):
        return None
    if osm_type not in OSM_TYPES or not (math.isfinite(latitude) and math.isfinite(longitude)):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return Place(query=query, latitude=latitude, longitude=longitude, osm_type=osm_type, osm_id=osm_id,
                 display_name=str(item.get('display_name', ''))[:400])


class NominatimGeocoder:
    def __init__(self, *, url=None, user_agent=None, transport=None, sleep=time.sleep, clock=time.monotonic,
                 timeout=10.0, min_interval=MIN_INTERVAL_SECONDS):
        self.url = url or getattr(settings, 'NOMINATIM_URL', '') or DEFAULT_URL
        self.user_agent = user_agent or getattr(settings, 'INGESTION_USER_AGENT', '') or 'GeoObservatorio/0.1'
        self.transport = transport
        self.sleep = sleep
        self.clock = clock
        self.timeout = timeout
        self.min_interval = min_interval
        self.requests_made = 0

    def _cache_key(self, query, country_code):
        digest = hashlib.sha256(f'{self.url}|{query.casefold()}|{country_code or ""}'.encode()).hexdigest()
        return f'ingestion:nominatim:{digest}'

    def search(self, query, country_code=None):
        """First result for ``query`` or ``None``. Network errors also return ``None`` (no location)."""
        query = (query or '').strip()[:200]
        if not query:
            return None
        country_code = (country_code or '').strip().lower()
        if len(country_code) != 2 or not country_code.isalpha():
            country_code = ''
        key = self._cache_key(query, country_code)
        cached = cache.get(key)
        if cached is not None:
            return _parse(query, cached)
        params = {'q': query, 'format': 'jsonv2', 'limit': 1, 'accept-language': 'es'}
        if country_code:
            params['countrycodes'] = country_code
        with _lock:
            wait = self.min_interval - (self.clock() - _last_request[0])
            if wait > 0:
                self.sleep(wait)
            try:
                with httpx.Client(transport=self.transport, trust_env=False, follow_redirects=False,
                                  timeout=self.timeout) as client:
                    response = client.get(self.url, params=params, headers={'User-Agent': self.user_agent})
                payload = response.json() if response.status_code == 200 else None
            except (httpx.HTTPError, ValueError):
                payload = None
            finally:
                _last_request[0] = self.clock()
                self.requests_made += 1
        if payload is None:
            return None
        cache.set(key, payload[:1] if isinstance(payload, list) else [], CACHE_SECONDS)
        return _parse(query, payload)
