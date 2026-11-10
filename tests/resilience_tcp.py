"""Owned native API process and one-request fault proxy for stage 5."""

import asyncio
import os
import socket
import subprocess
import sys

import httpx


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class NativeAPI:
    def __init__(self, directory):
        self.port = free_port()
        self.gate = directory / "commit.gate"
        self.log = (directory / "api.log").open("ab")
        self.process = None

    async def start(self):
        self.process = subprocess.Popen(
            [sys.executable, "-m", "tests.resilience_server"],
            env={**os.environ, "RESILIENCE_PORT": str(self.port), "RESILIENCE_GATE": str(self.gate)},
            stdout=self.log,
            stderr=self.log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        async with httpx.AsyncClient(trust_env=False) as client:
            for _ in range(150):
                assert self.process.poll() is None, "Owned API exited; inspect api.log"
                try:
                    if (await client.get(f"http://127.0.0.1:{self.port}/health/ready")).status_code == 200:
                        return
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.1)
        raise AssertionError("Owned API readiness timeout")

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=10)


class FaultProxy:
    def __init__(self, upstream):
        self.upstream = upstream
        self.mode = "pass"
        self.arrived = asyncio.Event()
        self.release = asyncio.Event()
        self.tasks = set()

    async def start(self):
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def close(self):
        self.server.close()
        await self.server.wait_closed()
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        upstream = None
        mode, self.mode = self.mode, "pass"
        try:
            if mode == "offline":
                return
            header = await reader.readuntil(b"\r\n\r\n")
            length = next(
                (
                    int(line.split(b":", 1)[1])
                    for line in header.split(b"\r\n")
                    if line.lower().startswith(b"content-length:")
                ),
                0,
            )
            body = await reader.readexactly(length)
            remote, upstream = await asyncio.open_connection("127.0.0.1", self.upstream)
            header = (
                b"\r\n".join(
                    line for line in header.split(b"\r\n") if line and not line.lower().startswith(b"connection:")
                )
                + b"\r\nConnection: close\r\n\r\n"
            )
            if mode == "partial":
                upstream.write(header + body[: max(1, len(body) // 2)])
                await upstream.drain()
                return
            upstream.write(header + body)
            await upstream.drain()
            response = await remote.read()
            if mode in ("lost", "delay"):
                self.arrived.set()
                await self.release.wait()
                if mode == "lost":
                    return
            writer.write(response)
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            if upstream:
                upstream.close()
                await upstream.wait_closed()
            writer.close()
            await writer.wait_closed()
            self.tasks.discard(task)
