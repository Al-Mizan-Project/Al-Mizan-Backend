import hashlib

from django.conf import settings
from django.core.cache import cache


CACHE_VERSION_KEY = "appels:api-cache-version"


def get_cache_version():
    version = cache.get(CACHE_VERSION_KEY)
    if version is None:
        cache.add(CACHE_VERSION_KEY, 1, None)
        version = cache.get(CACHE_VERSION_KEY) or 1
    return int(version)


def build_cache_key(namespace, identifier="", query_string=""):
    version = get_cache_version()
    payload = f"{version}:{namespace}:{identifier}:{query_string}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"appels:cache:{digest}"


def read_cached(namespace, identifier="", query_string=""):
    return cache.get(build_cache_key(namespace, identifier, query_string))


def write_cached(payload, namespace, identifier="", query_string=""):
    timeout = int(getattr(settings, "CACHE_TTL", 60))
    cache.set(build_cache_key(namespace, identifier, query_string), payload, timeout=timeout)


def bump_cache_version():
    try:
        cache.incr(CACHE_VERSION_KEY)
    except ValueError:
        cache.set(CACHE_VERSION_KEY, 2, None)
