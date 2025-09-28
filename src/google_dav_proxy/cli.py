import asyncio
import logging
from pathlib import Path
from typing import Annotated

import typer

from .google_session import GoogleSession

logger = logging.getLogger(__name__)

app = typer.Typer()


async def proxy(creds_file: Path, token_file: Path):
    session = GoogleSession(
        scope=["https://www.googleapis.com/auth/calendar"],
        creds_file=creds_file,
        token_file=token_file,
    )

    cal_url = "https://apidata.googleusercontent.com/caldav/v2/"

    print(session, cal_url)  # TODO: actually proxy!


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
):
    asyncio.run(proxy(creds_file, token_file))
