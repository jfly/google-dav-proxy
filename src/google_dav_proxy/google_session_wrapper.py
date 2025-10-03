import contextlib
import json
import logging
import webbrowser
from importlib.metadata import version
from pathlib import Path
from typing import cast

import click
from aiohttp_oauthlib import OAuth2Session
from pydantic import BaseModel

from .hello_app import HelloASGIApp
from .local_server import LocalServer
from .utils import atomic_write

logger = logging.getLogger(__name__)

assert __package__ is not None
USER_AGENT = f"google-dav-proxy/{version(__package__)}"


class GoogleInstalledCreds(BaseModel):
    project_id: str

    auth_uri: str
    token_uri: str

    client_id: str
    client_secret: str


class GoogleCreds(BaseModel):
    installed: GoogleInstalledCreds


class GoogleSessionWrapper:
    """
    A wrapper around Google's WebDAV APIs. We construct a new `OAuth2Session` for every single request.

    This is not great. Consider the scenario where a bunch of requests are simultaneously coming in and
    we have an expired token. Currently we construct a bunch of `OAuth2Session`s, which all race to
    refresh the token in parallel. Perhaps we should instead grab a lock and ensure that we only
    do a single token refresh at a time?
    """

    def __init__(self, creds_file: Path, token_file: Path, scope: list[str]):
        self._creds = GoogleCreds.model_validate_json(creds_file.read_text()).installed
        self._scope = scope
        self._token_file = token_file
        self._token = None

    @contextlib.asynccontextmanager
    async def session(self):
        if self._token is None:
            await self._init_token()

        assert self._token is not None

        async with self._build_session(
            # Unnecessary as we just init-ed `self._token` above.
            redirect_uri=None,
        ) as session:
            yield session

    def _build_session(self, redirect_uri: str | None):
        return OAuth2Session(
            client_id=self._creds.client_id,
            scope=self._scope,
            token=self._token,
            redirect_uri=redirect_uri,
            auto_refresh_url=self._creds.token_uri,
            auto_refresh_kwargs={
                "client_id": self._creds.client_id,
                "client_secret": self._creds.client_secret,
            },
            token_updater=self._save_token,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/xml; charset=UTF-8",
            },
        )

    async def _init_token(self):
        """
        Based on <https://github.com/pimutils/vdirsyncer/blob/v0.20.0/vdirsyncer/storage/google.py>
        """
        try:
            with self._token_file.open() as f:
                self._token = json.load(f)
        except FileNotFoundError:
            pass

        if self._token is not None:
            return

        async with (
            LocalServer.serve(
                HelloASGIApp("Successfully obtained token.")
            ) as running_server,
            self._build_session(
                redirect_uri=running_server.base_url,
            ) as session,
        ):
            session = cast(OAuth2Session, session)

            authorization_url, state = session.authorization_url(
                self._creds.auth_uri,
                # `access_type` and `approval_prompt` are Google specific
                # extra parameters.
                access_type="offline",
                approval_prompt="force",
            )
            click.echo(f"Opening {authorization_url} ...")
            try:
                webbrowser.open(authorization_url)
            except Exception as e:
                logger.warning(str(e))

            click.echo("Follow the instructions on the page.")

            next_request_url = await running_server.next_request_url()
            logger.debug("server handled request!")

            # Note: using https here because oauthlib is very picky that
            # OAuth 2.0 should only occur over https.
            authorization_response = next_request_url.replace("http", "https", 1)
            logger.debug(f"authorization_response: {authorization_response}")
            self._token = await session.fetch_token(
                self._creds.token_uri,
                authorization_response=authorization_response,
                # Google specific extra param used for client authentication:
                client_secret=self._creds.client_secret,
            )
            logger.debug(f"token: {self._token}")

        await self._save_token(self._token)

    async def _save_token(self, token):
        """Helper function called by OAuth2Session when a token is updated."""
        with atomic_write(self._token_file, mode="w", overwrite=True) as f:
            json.dump(token, f)
