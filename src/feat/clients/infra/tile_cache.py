import asyncio
import logging
import os
import sqlite3
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from src.core.paths import PROJECT_DIR
from src.feat.clients.domain.location_excs import InvalidGeoResponse


logger = logging.getLogger(__name__)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
TileKey = tuple[int, int, int]
TileLoader = Callable[[TileKey, str | None], Awaitable[tuple[bytes | None, str | None]]]


@dataclass(frozen=True)
class CachedTile:
    png: bytes
    etag: str | None
    checked_at: float
    retry_at: float = 0


class TileStore:
    """Atomic filesystem storage; SQLite transactions also serialize multiple workers."""

    def __init__(self, directory: Path, max_bytes: int) -> None:
        self.path = directory / "osm-carto-v1.sqlite3"
        self.max_bytes = max_bytes

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        try:
            # Reclaim evicted pages at commit instead of leaving a growing file.
            db.execute("PRAGMA auto_vacuum = FULL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS tiles ("
                "z INTEGER, x INTEGER, y INTEGER, png BLOB NOT NULL, etag TEXT, "
                "checked_at REAL NOT NULL, retry_at REAL NOT NULL, used_at REAL NOT NULL, "
                "PRIMARY KEY (z, x, y))"
            )
            db.execute("CREATE INDEX IF NOT EXISTS tiles_used ON tiles(used_at)")
            return db
        except BaseException:
            db.close()
            raise

    def read(self, key: TileKey, now: float) -> CachedTile | None:
        with closing(self._connect()) as db, db:
            row = db.execute(
                "SELECT png, etag, checked_at, retry_at FROM tiles WHERE z=? AND x=? AND y=?", key
            ).fetchone()
            if row is None:
                return None
            png = bytes(row[0])
            if not png.startswith(PNG_SIGNATURE):
                db.execute("DELETE FROM tiles WHERE z=? AND x=? AND y=?", key)
                return None
            # Touch at most once an hour to avoid a disk write for every map frame.
            db.execute(
                "UPDATE tiles SET used_at=? WHERE z=? AND x=? AND y=? AND used_at<?",
                (now, *key, now - 3600),
            )
            return CachedTile(png, row[1], row[2], row[3])

    def write(self, key: TileKey, tile: CachedTile, now: float, *, unchanged: bool = False) -> None:
        with closing(self._connect()) as db, db:
            if unchanged:
                updated = db.execute(
                    "UPDATE tiles SET etag=?, checked_at=?, retry_at=?, used_at=? WHERE z=? AND x=? AND y=?",
                    (tile.etag, tile.checked_at, tile.retry_at, now, *key),
                ).rowcount
                if updated:
                    self._prune(db)
                    return
            db.execute(
                "INSERT INTO tiles VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(z,x,y) DO UPDATE SET png=excluded.png, etag=excluded.etag, "
                "checked_at=excluded.checked_at, retry_at=excluded.retry_at, used_at=excluded.used_at",
                (*key, tile.png, tile.etag, tile.checked_at, tile.retry_at, now),
            )
            self._prune(db)

    def retry(self, key: TileKey, retry_at: float) -> None:
        with closing(self._connect()) as db, db:
            db.execute("UPDATE tiles SET retry_at=? WHERE z=? AND x=? AND y=?", (retry_at, *key))

    def _prune(self, db: sqlite3.Connection) -> None:
        # Include indexes/metadata in the size budget. Journal files are transient.
        page_size = db.execute("PRAGMA page_size").fetchone()[0]
        while True:
            pages = db.execute("PRAGMA page_count").fetchone()[0]
            free = db.execute("PRAGMA freelist_count").fetchone()[0]
            if (pages - free) * page_size <= self.max_bytes:
                break
            removed = db.execute(
                "DELETE FROM tiles WHERE rowid IN (SELECT rowid FROM tiles ORDER BY used_at LIMIT 1)"
            ).rowcount
            if not removed:
                break


class TileCache:
    fresh_seconds = 30 * 24 * 3600
    retry_seconds = 3600

    def __init__(
        self,
        store: TileStore | None = None,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.store = store or TileStore(
            Path(os.environ.get("GEOAPIFY_TILE_CACHE_DIR", str(PROJECT_DIR / ".cache" / "geoapify-tiles"))),
            int(os.environ.get("GEOAPIFY_TILE_CACHE_MAX_BYTES", str(20 * 1024**3))),
        )
        if self.store.max_bytes < 1024 * 1024:
            raise ValueError("GEOAPIFY_TILE_CACHE_MAX_BYTES must be at least 1048576")
        self._clock = clock
        # Small fallback when the filesystem is unavailable; disk remains authoritative.
        self._memory: OrderedDict[TileKey, CachedTile] = OrderedDict()
        self._memory_bytes = 0
        self._flights: dict[TileKey, asyncio.Task[bytes]] = {}
        self._disk_warning = False

    async def _disk(self, operation: Callable[[], object]) -> object:
        try:
            return await asyncio.to_thread(operation)
        except (OSError, sqlite3.Error):
            if not self._disk_warning:
                logger.warning("Tile filesystem cache unavailable; using memory and provider fallback")
                self._disk_warning = True
            return None

    def _remember(self, key: TileKey, tile: CachedTile) -> None:
        previous = self._memory.pop(key, None)
        if previous is not None:
            self._memory_bytes -= len(previous.png)
        self._memory[key] = tile
        self._memory_bytes += len(tile.png)
        while len(self._memory) > 128 or self._memory_bytes > 16 * 1024**2:
            self._memory_bytes -= len(self._memory.popitem(last=False)[1].png)

    async def get(self, key: TileKey, loader: TileLoader) -> bytes:
        now = self._clock()
        stored = await self._disk(lambda: self.store.read(key, now))
        tile = stored if isinstance(stored, CachedTile) else self._memory.get(key)
        if tile is not None:
            self._remember(key, tile)
            if now - tile.checked_at >= self.fresh_seconds and now >= tile.retry_at:
                self._start(key, tile, loader)
            return tile.png
        return await asyncio.shield(self._start(key, None, loader))

    def _start(self, key: TileKey, old: CachedTile | None, loader: TileLoader) -> asyncio.Task[bytes]:
        if key not in self._flights:
            task = asyncio.create_task(self._refresh(key, old, loader))
            self._flights[key] = task

            def finished(done: asyncio.Task[bytes]) -> None:
                self._flights.pop(key, None)
                # Retrieve errors even if every HTTP caller disconnected.
                if not done.cancelled():
                    done.exception()

            task.add_done_callback(finished)
        return self._flights[key]

    async def _refresh(self, key: TileKey, old: CachedTile | None, loader: TileLoader) -> bytes:
        # Persist a short delay to reduce repeat checks after a restart or by another worker.
        if old is not None:
            lease = self._clock() + 300
            self._remember(key, CachedTile(old.png, old.etag, old.checked_at, lease))
            await self._disk(lambda: self.store.retry(key, lease))
        try:
            png, etag = await loader(key, old.etag if old else None)
            unchanged = png is None
            if png is None:
                if old is None:
                    raise InvalidGeoResponse
                png = old.png
                etag = etag or old.etag
            if not png.startswith(PNG_SIGNATURE):
                raise InvalidGeoResponse
            tile = CachedTile(png, etag, self._clock())
            await self._disk(lambda: self.store.write(key, tile, self._clock(), unchanged=unchanged))
            self._remember(key, tile)
            return png
        except Exception:
            if old is None:
                raise
            tile = CachedTile(old.png, old.etag, old.checked_at, self._clock() + self.retry_seconds)
            self._remember(key, tile)
            await self._disk(lambda: self.store.retry(key, tile.retry_at))
            logger.warning("Tile update unavailable; retaining cached image and retrying later")
            return old.png
