import asyncio
import logging
from pathlib import Path
from typing import Annotated

import aiohttp
import asgineer
import typer
import uvicorn

from .google_session_wrapper import GoogleSessionWrapper

logger = logging.getLogger(__name__)

app = typer.Typer()


async def proxy(
    bind: str,
    port: int,
    creds_file: Path,
    token_file: Path,
):
    # TODO: make this work with both CalDAV and CardDAV.
    scope = ["https://www.googleapis.com/auth/calendar"]
    proxy_url = "https://apidata.googleusercontent.com/"

    session_wrapper = GoogleSessionWrapper(
        scope=scope,
        creds_file=creds_file,
        token_file=token_file,
    )

    @asgineer.to_asgi
    async def proxy_app(request: asgineer.HttpRequest):
        url = proxy_url + request.path.removeprefix("/")
        if request.querylist:
            url += "?" + "&".join(f"{key}={val}" for key, val in request.querylist)

        # Remove the Host header so the underlying request has the
        # appropriate Host for the url we're proxying to.
        request.headers.pop("host")

        logger.info("Proxying %s request onto %s", request.method, url)
        async with (
            session_wrapper.session() as session,
            session.request(
                method=request.method,
                url=url,
                data=await request.get_body(),
                headers=request.headers,
                # aiohttp does some useful stuff like requesting compressed content.
                # We're just a dumb proxy, so don't let that happen.
                skip_auto_headers=aiohttp.ClientRequest.DEFAULT_HEADERS.keys(),
                # Furthermore, if the client *did* request compressed data, don't
                # mangle it by decompressing it, just send it along unchanged.
                auto_decompress=False,
            ) as response,
        ):
            return (
                response.status,
                # Workaround for <https://github.com/almarklein/asgineer/issues/47>.
                { k.lower(): v for k, v in response.headers.items() },
                await response.read(),
            )

    config = uvicorn.Config(proxy_app, host=bind, port=port)
    server = uvicorn.Server(config)
    await server.serve()


@app.command()
def main(
    creds_file: Annotated[
        Path,
        typer.Option(
            help="Google Cloud credentials JSON file (read-only). See https://vdirsyncer.pimutils.org/en/stable/config.html#google for instructions on how to obtain one."
        ),
    ],
    token_file: Annotated[
        Path,
        typer.Option(
            help="Google Cloud token file (read-write). Will be created if it does not exist yet."
        ),
    ],
    bind: Annotated[
        str,
        typer.Option(help="Bind to this address"),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(help="Bind to this port"),
    ] = 8080,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
):
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level)

    asyncio.run(proxy(bind, port, creds_file, token_file))
