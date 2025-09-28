import asyncio
import contextlib
import logging
import socket
from typing import Any, Awaitable, Callable

import asgineer
import uvicorn


class CaptureRequestMiddlware:
    _previous_request_url: str | None

    def __init__(self, next: Callable[..., Any]):
        self._next = next
        self._previous_request_url = None
        self._request_event = asyncio.Event()

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ):
        if scope["type"] == "http":
            request = asgineer.HttpRequest(scope, receive, send)
            self._previous_request_url = request.url
            self._request_event.set()
        return await self._next(scope, receive, send)

    async def next_request_url(self) -> str:
        self._request_event.clear()
        await self._request_event.wait()
        assert self._previous_request_url is not None
        return self._previous_request_url


class LocalServer:
    def __init__(
        self, app_with_captures: CaptureRequestMiddlware, host: str, sock: socket.socket
    ):
        self._app_with_captures = app_with_captures
        port = sock.getsockname()[1]
        self.base_url = f"http://{host}:{port}"

    async def next_request_url(self) -> str:
        return await self._app_with_captures.next_request_url()

    @classmethod
    @contextlib.asynccontextmanager
    async def serve(cls, app: Callable[..., Any]):
        family = socket.AF_INET
        host = "127.0.0.1"
        sock = socket.socket(family=family)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(
            (
                host,
                0,  # Pick any available port.
            )
        )

        app_with_captures = CaptureRequestMiddlware(app)
        config = uvicorn.Config(
            app_with_captures, fd=sock.fileno(), log_level=logging.INFO
        )
        server = uvicorn.Server(config)

        async with asyncio.TaskGroup() as tg:
            tg.create_task(server.serve())
            yield cls(app_with_captures, host, sock)

            # For reasons I don't grok, `server.shutdown()` does not actually shut down a
            # `uvicorn` server without first setting `should_exit` to `True`.
            # See <https://github.com/Kludex/uvicorn/issues/742>
            server.should_exit = True
            await server.shutdown()
