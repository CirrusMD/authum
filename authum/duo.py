import contextlib
import logging
import socket
import threading
import time
from typing import Union
import webbrowser

import flask
import flask.cli

import authum
import authum.http


flask.cli.show_server_banner = lambda *args: None
logging.getLogger("werkzeug").disabled = True
log = logging.getLogger(__name__)


class DuoWebV2:
    """Implements Duo Web v2 SDK.

    See: https://duo.com/docs/duoweb-v2
    """

    POST_ACTION_PROXY_ROUTE = "/post_action"

    def __init__(
        self,
        name: str,
        http_client: authum.http.HTTPClient,
        host: str,
        sig_request: str,
        post_action: str,
        post_action_proxy: bool = False,
        post_argument: str = "sig_response",
        duo_form_args: dict = {},
        script_url: str = "https://api.duosecurity.com/frame/hosted/Duo-Web-v2.min.js",
        poll_interval: float = 0.25,
    ) -> None:
        self._app = flask.Flask(__name__)
        self._post_action_proxy = post_action_proxy
        self._post_action_event = threading.Event()
        self._post_action_response = authum.http.RESTResponse()
        self._poll_interval = poll_interval

        @self._app.route("/")
        def index():
            template_vars = {
                "app_name": authum.metadata["Name"].capitalize(),
                "name": name,
                "host": host,
                "sig_request": sig_request,
                "post_action": self.POST_ACTION_PROXY_ROUTE
                if post_action_proxy
                else post_action,
                "post_argument": post_argument,
                "duo_form_args": duo_form_args,
                "script_url": script_url,
            }
            return flask.render_template("duo_web_v2.html", **template_vars)

        @self._app.route(self.POST_ACTION_PROXY_ROUTE, methods=["POST"])
        def post_action_handler():
            self._post_action_response = http_client.rest_request(
                url=post_action,
                method="post",
                data=flask.request.form.to_dict(),
            )

            self._post_action_event.set()

            response = flask.make_response(self._post_action_response.response.text)
            response.headers[
                "Content-Type"
            ] = self._post_action_response.response.headers["Content-Type"]

            return response

    @property
    def server_url(self) -> str:
        try:
            return f"http://{self._server_host}:{self._server_port}"
        except AttributeError:
            return ""

    def start_server(self) -> None:
        """Starts the local web server"""
        self._server_host = "127.0.0.1"
        with contextlib.closing(
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ) as sock:
            sock.bind((self._server_host, 0))
            self._server_port = sock.getsockname()[1]

        log.debug(f"Starting web server: {self._server_host}:{self._server_port}")
        thread = threading.Thread(
            target=lambda: self._app.run(
                host=self._server_host,
                port=self._server_port,
                debug=True,
                use_reloader=False,
            )
        )
        thread.daemon = True
        thread.start()

        while True:
            with contextlib.closing(
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ) as sock:
                if sock.connect_ex((self._server_host, self._server_port)) == 0:
                    break
            time.sleep(self._poll_interval)

    def prompt(self) -> authum.http.RESTResponse:
        """Opens a web browser and displays the Duo prompt"""
        self.start_server()

        log.debug(f"Opening URL: {self.server_url}")
        webbrowser.open(self.server_url)

        if self._post_action_proxy:
            log.debug("Waiting for post_action event...")
            while not self._post_action_event.is_set():
                time.sleep(self._poll_interval)

        return self._post_action_response
