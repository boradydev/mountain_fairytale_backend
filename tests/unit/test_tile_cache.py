import asyncio
import sqlite3
from email.message import Message
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock
from urllib.error import HTTPError

import pytest

from src.feat.clients.domain.location_excs import GeoUnavailable, InvalidGeoResponse
from src.feat.clients.infra.geoapify import Geoapify
from src.feat.clients.infra.tile_cache import PNG_SIGNATURE, CachedTile, TileCache, TileStore


KEY = (17, 80826, 47098)
PNG = PNG_SIGNATURE + b"original"


async def settle(cache: TileCache) -> None:
    await asyncio.gather(*list(cache._flights.values()))
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_restart_reads_persisted_tile_without_provider(tmp_path: Path) -> None:
    loader = AsyncMock(return_value=(PNG, 'W/"one"'))
    store = TileStore(tmp_path, 1024**2)
    assert await TileCache(store).get(KEY, loader) == PNG
    loader.reset_mock()
    assert await TileCache(TileStore(tmp_path, 1024**2)).get(KEY, loader) == PNG
    loader.assert_not_awaited()


@pytest.mark.asyncio
async def test_30_day_check_serves_stale_then_304_renews_date(tmp_path: Path) -> None:
    now = [100.0]
    store = TileStore(tmp_path, 1024**2)
    loader = AsyncMock(return_value=(PNG, 'W/"one"'))
    cache = TileCache(store, clock=lambda: now[0])
    await cache.get(KEY, loader)
    now[0] += cache.fresh_seconds - 1
    await cache.get(KEY, loader)
    assert loader.await_count == 1
    now[0] += 1
    started, release = asyncio.Event(), asyncio.Event()

    async def unchanged(key, etag):
        assert key == KEY
        assert etag == 'W/"one"'
        started.set()
        await release.wait()
        return None, etag

    assert await cache.get(KEY, unchanged) == PNG
    await started.wait()
    # More requests do not wait for or duplicate the background request.
    assert await cache.get(KEY, unchanged) == PNG
    release.set()
    await settle(cache)
    tile = store.read(KEY, now[0])
    assert tile is not None
    assert tile.checked_at == now[0]
    assert tile.png == PNG
    assert await TileCache(store, clock=lambda: now[0]).get(KEY, loader) == PNG
    assert loader.await_count == 1


@pytest.mark.asyncio
async def test_changed_tile_replaces_image_and_etag(tmp_path: Path) -> None:
    store = TileStore(tmp_path, 1024**2)
    store.write(KEY, CachedTile(PNG, "old", 1), 1)
    cache = TileCache(store, clock=lambda: cache.fresh_seconds + 2)
    loader = AsyncMock(return_value=(PNG_SIGNATURE + b"new", "new"))
    assert await cache.get(KEY, loader) == PNG
    await settle(cache)
    loader.assert_awaited_once_with(KEY, "old")
    tile = store.read(KEY, cache._clock())
    assert tile is not None
    assert tile.png == PNG_SIGNATURE + b"new"
    assert tile.etag == "new"
    assert await cache.get(KEY, loader) == tile.png


@pytest.mark.asyncio
async def test_failure_keeps_tile_and_persists_retry_delay(tmp_path: Path) -> None:
    now = [TileCache.fresh_seconds + 2.0]
    store = TileStore(tmp_path, 1024**2)
    store.write(KEY, CachedTile(PNG, "old", 1), 1)
    loader = AsyncMock(side_effect=GeoUnavailable)
    cache = TileCache(store, clock=lambda: now[0])
    assert await cache.get(KEY, loader) == PNG
    await settle(cache)
    restarted = TileCache(store, clock=lambda: now[0])
    assert await restarted.get(KEY, loader) == PNG
    assert loader.await_count == 1
    now[0] += cache.retry_seconds
    assert await restarted.get(KEY, loader) == PNG
    await settle(restarted)
    assert loader.await_count == 2


@pytest.mark.asyncio
async def test_concurrent_misses_share_request_even_when_caller_cancelled(tmp_path: Path) -> None:
    cache = TileCache(TileStore(tmp_path, 1024**2))
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def load(key, etag):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return PNG, "one"

    first = asyncio.create_task(cache.get(KEY, load))
    await started.wait()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    others = [asyncio.create_task(cache.get(KEY, load)) for _ in range(8)]
    release.set()
    assert await asyncio.gather(*others) == [PNG] * 8
    assert calls == 1


@pytest.mark.asyncio
async def test_bad_png_not_saved_and_corrupt_entry_is_refetched(tmp_path: Path) -> None:
    store = TileStore(tmp_path, 1024**2)
    cache = TileCache(store)
    with pytest.raises(InvalidGeoResponse):
        await cache.get(KEY, AsyncMock(return_value=(b"not png", None)))
    assert store.read(KEY, 1) is None
    store.write(KEY, CachedTile(b"broken", None, 1), 1)
    assert await cache.get(KEY, AsyncMock(return_value=(PNG, None))) == PNG


@pytest.mark.asyncio
async def test_unwritable_directory_falls_back_to_memory(tmp_path: Path) -> None:
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    cache = TileCache(TileStore(blocked, 1024**2))
    loader = AsyncMock(return_value=(PNG, None))
    assert await cache.get(KEY, loader) == PNG
    assert await cache.get(KEY, loader) == PNG
    loader.assert_awaited_once()


def test_budget_reclaims_disk_and_evicts_least_recently_used(tmp_path: Path) -> None:
    store = TileStore(tmp_path, 1024**2)
    large_png = PNG_SIGNATURE + b"x" * 240_000
    for x in range(4):
        store.write((8, x, 0), CachedTile(large_png, None, 1), x)
    assert store.read((8, 0, 0), 10_000) is not None
    store.write((8, 4, 0), CachedTile(large_png, None, 1), 10_001)
    assert store.read((8, 1, 0), 10_002) is None
    assert store.read((8, 0, 0), 10_002) is not None
    assert store.read((8, 4, 0), 10_002) is not None
    assert store.path.stat().st_size <= store.max_bytes
    # No stale journal or worker-held connection prevents reopening the file.
    with sqlite3.connect(store.path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_geoapify_sends_etag_and_accepts_304(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-only")
    geo = Geoapify()

    def unchanged(request, timeout):
        assert request.get_header("If-none-match") == 'W/"one"'
        assert timeout == 10
        raise HTTPError(request.full_url, 304, "Not Modified", Message(), None)

    monkeypatch.setattr("src.feat.clients.infra.geoapify.urlopen", unchanged)
    assert geo._response("tile/osm-carto/17/1/1.png", {}, maps=True, etag='W/"one"') == (None, 'W/"one"')


def test_geoapify_reads_png_and_etag_from_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-only")
    geo = Geoapify()

    class Response(BytesIO):
        headers = Message()

    def changed(request, timeout):
        assert request.get_header("If-none-match") == "old"
        response = Response(PNG)
        response.headers["ETag"] = "new"
        return response

    monkeypatch.setattr("src.feat.clients.infra.geoapify.urlopen", changed)
    assert geo._response("tile/osm-carto/17/1/1.png", {}, maps=True, etag="old") == (PNG, "new")


@pytest.mark.asyncio
async def test_provider_failure_on_cache_miss_can_be_retried(tmp_path: Path) -> None:
    cache = TileCache(TileStore(tmp_path, 1024**2))
    with pytest.raises(GeoUnavailable):
        await cache.get(KEY, AsyncMock(side_effect=GeoUnavailable))
    await asyncio.sleep(0)
    assert await cache.get(KEY, AsyncMock(return_value=(PNG, None))) == PNG


@pytest.mark.asyncio
async def test_without_etag_stale_tile_uses_full_download(tmp_path: Path) -> None:
    store = TileStore(tmp_path, 1024**2)
    store.write(KEY, CachedTile(PNG, None, 1), 1)
    cache = TileCache(store, clock=lambda: TileCache.fresh_seconds + 2)
    loader = AsyncMock(return_value=(PNG_SIGNATURE + b"new", None))
    assert await cache.get(KEY, loader) == PNG
    await settle(cache)
    loader.assert_awaited_once_with(KEY, None)
    assert await cache.get(KEY, loader) == PNG_SIGNATURE + b"new"
