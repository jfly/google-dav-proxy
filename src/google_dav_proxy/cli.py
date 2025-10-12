import asyncio
import logging
import subprocess
import typing
from typing import Annotated, NotRequired

import aiohttp
import asgineer
import typer
import uvicorn

logger = logging.getLogger(__name__)

app = typer.Typer()


def get_access_token(oama_email):
    cp = subprocess.run(
        ["oama", "access", oama_email],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return cp.stdout.removesuffix("\n")


class ParsedBindForUvicorn(typing.TypedDict):
    host: NotRequired[str]
    port: NotRequired[int]
    uds: NotRequired[str]


def parse_bind_for_uvicorn(bind: str) -> ParsedBindForUvicorn:
    parsed: ParsedBindForUvicorn = {}
    unix_prefix = "unix:"
    if bind.startswith(unix_prefix):
        parsed["uds"] = bind.removeprefix(unix_prefix)
    else:
        host_port = bind.rsplit(":", 1)
        if len(host_port) != 2:
            raise typer.BadParameter("must include a port")

        host, port = host_port
        port = int(port)
        parsed["host"] = host
        parsed["port"] = port

    return parsed


async def proxy(
    bind: ParsedBindForUvicorn,
    oama_email: str,
):
    proxy_url = "https://apidata.googleusercontent.com/"
    session = aiohttp.ClientSession()

    @asgineer.to_asgi
    async def proxy_app(request: asgineer.HttpRequest):
        url = proxy_url + request.path.removeprefix("/")
        if request.querylist:
            url += "?" + "&".join(f"{key}={val}" for key, val in request.querylist)

        # Remove the Host header so the underlying request has the
        # appropriate Host for the url we're proxying to.
        request.headers.pop("host")

        logger.info("Proxying %s request onto %s", request.method, url)
        token = get_access_token(oama_email)
        async with (
            session.request(
                method=request.method,
                url=url,
                data=await request.get_body(),
                headers={
                    **request.headers,
                    "Authorization": f"Bearer {token}",
                },
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
                {k.lower(): v for k, v in response.headers.items()},
                await response.read(),
            )

    config = uvicorn.Config(proxy_app, **bind)
    server = uvicorn.Server(config)
    await server.serve()


@app.command()
def main(
    oama_email: Annotated[
        str,
        typer.Argument(help="Email address of an email configured with `oama`"),
    ],
    bind: Annotated[
        ParsedBindForUvicorn,
        typer.Option(
            help="Bind to this address/socket. Examples: '127.0.0.1:8080' or 'unix:/path/to/socket.sock'",
            parser=parse_bind_for_uvicorn,
        ),
    ] = {"host": "127.0.0.1", "port": 8080},
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
):
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level)

    asyncio.run(proxy(bind, oama_email))
