# Based on:
# https://github.com/pimutils/vdirsyncer/blob/v0.20.0/vdirsyncer/storage/google.py
import json
import logging
import webbrowser
import wsgiref.simple_server
from importlib.metadata import version
from pathlib import Path
from threading import Thread
from typing import cast

import click
from aiohttp_oauthlib import OAuth2Session
from pydantic import BaseModel

from .redirect_app import RedirectWSGIApp, WSGIRequestHandler
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


class GoogleSession:
    def __init__(self, creds_file: Path, token_file: Path, scope: list[str]):
        self._creds = GoogleCreds.model_validate_json(creds_file.read_text()).installed
        self._scope = scope
        self._token_file = token_file
        self._token = None

    async def request(self, method, url, data=None, headers=None):
        if not self._token:
            await self._init_token()

        if headers is None:
            headers = self.get_default_headers()

        async with self._session(
            redirect_uri=None  # Unnecessary because we just init-ed the token.
        ) as session:
            return await session.request(method, url, data=data, headers=headers)

    def get_default_headers(self):
        return {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/xml; charset=UTF-8",
        }

    def _session(self, redirect_uri: str | None):
        return OAuth2Session(
            client_id=self._creds.client_id,
            redirect_uri=redirect_uri,
            scope=self._scope,
            token=self._token,
            auto_refresh_url=self._creds.token_uri,
            auto_refresh_kwargs={
                "client_id": self._creds.client_id,
                "client_secret": self._creds.client_secret,
            },
            token_updater=self._save_token,
        )

    async def _init_token(self):
        try:
            with self._token_file.open() as f:
                self._token = json.load(f)
        except FileNotFoundError:
            pass

        if not self._token:
            # Some times a task stops at this `async`, and another continues the flow.
            # At this point, the user has already completed the flow, but is prompted
            # for a second one.
            wsgi_app = RedirectWSGIApp("Successfully obtained token.")
            wsgiref.simple_server.WSGIServer.allow_reuse_address = False
            host = "127.0.0.1"
            local_server = wsgiref.simple_server.make_server(
                host, 0, wsgi_app, handler_class=WSGIRequestHandler
            )
            thread = Thread(target=local_server.handle_request, daemon=True)
            thread.start()
            redirect_uri = f"http://{host}:{local_server.server_port}"
            async with self._session(redirect_uri=redirect_uri) as session:
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
                thread.join()
                logger.debug("server handled request!")

                # Note: using https here because oauthlib is very picky that
                # OAuth 2.0 should only occur over https.
                assert wsgi_app.last_request_uri is not None
                authorization_response = wsgi_app.last_request_uri.replace(
                    "http", "https", 1
                )
                logger.debug(f"authorization_response: {authorization_response}")
                self._token = await session.fetch_token(
                    self._creds.token_uri,
                    authorization_response=authorization_response,
                    # Google specific extra param used for client authentication:
                    client_secret=self._creds.client_secret,
                )
                logger.debug(f"token: {self._token}")
                local_server.server_close()

            await self._save_token(self._token)

    async def _save_token(self, token):
        """Helper function called by OAuth2Session when a token is updated."""
        with atomic_write(self._token_file, mode="w", overwrite=True) as f:
            json.dump(token, f)
