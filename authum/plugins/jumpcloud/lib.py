import dataclasses
import logging
from typing import Type, Union

import authum.duo
import authum.http
import authum.persistence

log = logging.getLogger(__name__)

JUMPCLOUD_SSO_DOMAIN = "sso.jumpcloud.com"
JUMPCLOUD_SESSION_COOKIE = "_jumpcloud_user_console_"


@dataclasses.dataclass
class JumpCloudClientSession:
    """Represents a JumpCloud client session"""

    cookie: str = ""
    xsrf: str = ""


class JumpCloudClient(authum.http.HTTPClient):
    """Handles communication with the JumpCloud API"""

    def __init__(
        self,
        email: str,
        password: str,
        session: JumpCloudClientSession = JumpCloudClientSession(),
    ) -> None:
        super().__init__()

        self._email = email
        self._password = password
        self._session = session

        self.urls = {
            k: f"https://console.jumpcloud.com{v}"
            for k, v in {
                "applications": "/userconsole/api/applications",
                "auth": "/userconsole/auth",
                "auth_totp": "/userconsole/auth/totp",
                "auth_duo": "/userconsole/auth/duo",
                "self": "/userconsole/api/self",
                "xsrf": "/userconsole/xsrf",
            }.items()
        }

    @property
    def session(self) -> JumpCloudClientSession:
        return self._session

    def rest_request(
        self, url: str, method: str, data: dict = {}
    ) -> authum.http.RESTResponse:
        """Performs an API request and returns the response"""
        return super().rest_request(
            url=url,
            method=method,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "X-Xsrftoken": self._session.xsrf,
            },
            cookies={JUMPCLOUD_SESSION_COOKIE: self._session.cookie},
            json=data,
            allow_redirects=False,
        )

    def saml_request(self, url: str) -> authum.http.SAMLAssertion:
        """Performs a SAML request and returns the response"""
        if url not in [app["ssoUrl"] for app in list(self.applications())]:
            raise JumpCloudError(f"Unknown SSO URL: {url}")

        return super().saml_request(
            url=url,
            # https://developer.okta.com/docs/guides/session-cookie/overview/
            cookies={JUMPCLOUD_SESSION_COOKIE: self._session.cookie},
        )

    def auth(self, lazy: bool = False) -> authum.http.RESTResponse:
        """Authenticates a user"""
        if lazy:
            response = self.self()
            if response.response.ok and "/login" not in response.response.headers.get(
                "Location", ""
            ):
                log.debug(f"Reusing existing session")
                return response

        self.xsrf()

        log.debug(f"Authenticating '{self._email}'")
        data = {"email": self._email, "password": self._password}
        response = self.rest_request(url=self.urls["auth"], method="post", data=data)

        if response.response.status_code == 401 and "factors" in response:
            log.debug("MFA required")
            raise JumpCloudMFARequired(self, response)
        elif not response.response.ok:
            raise JumpCloudError(response.get("message"))

        return response

    def xsrf(self) -> authum.http.RESTResponse:
        """Requests an XSRF token, updates the session, and returns the response"""
        log.debug(f"Requesting XSRF token")
        response = self.rest_request(url=self.urls["xsrf"], method="get")

        log.debug("Saving session data")
        self._session.xsrf = response["xsrf"]
        self._session.cookie = response.response.cookies[JUMPCLOUD_SESSION_COOKIE]

        return response

    def auth_totp(self, otp: str) -> Union[authum.http.RESTResponse, None]:
        """Performs MFA factor verification for the "totp" factor type"""
        response = self.rest_request(
            url=self.urls["auth_totp"], method="post", data={"otp": str(otp)}
        )
        if not response.response.ok:
            raise JumpCloudError(f"MFA verification failed: {response.get('message')}")

        return response

    def auth_duo(self) -> Union[authum.http.RESTResponse, None]:
        """Performs MFA factor verification for the "duo" factor type"""
        response = self.rest_request(url=self.urls["auth_duo"], method="get")
        duo = authum.duo.DuoWebV2(
            name=f"JumpCloud ({self._email})",
            http_client=self,
            host=response["api_host"],
            sig_request=response["sig_request"],
            post_action=self.urls["auth_duo"],
            post_action_proxy=True,
            duo_form_args={"token": response["token"]},
        )

        response = duo.prompt()
        if not response.response.ok:
            raise JumpCloudError(f"MFA verification failed: {response.get('message')}")

        return response

    def applications(self) -> authum.http.RESTResponse:
        """Returns a list of the current user's applications"""
        log.debug("Requesting applications")
        return self.rest_request(url=self.urls["applications"], method="get")

    def self(self):
        """Returns information about the current authenticated user"""
        return self.rest_request(url=self.urls["self"], method="get")


class JumpCloudMFARequired(Exception):
    """Raised when multi-factor authentication is required"""

    def __init__(
        self, client: JumpCloudClient, response: authum.http.RESTResponse
    ) -> None:
        self.client = client
        self.response = response


class JumpCloudError(Exception):
    """Represents JumpCloud errors"""


class JumpCloudData(authum.persistence.KeyringItem):
    """Represents persistent JumpCloud data"""

    def __init__(self) -> None:
        super().__init__("jumpcloud")

    @property
    def email(self) -> str:
        return self.get("email", "")

    @property
    def password(self) -> str:
        return self.get("password", "")

    @property
    def session(self) -> Type:
        return JumpCloudClientSession(**self.get("session", {}))

    @email.setter
    def email(self, v: str) -> None:
        self["email"] = v
        self.save()

    @password.setter
    def password(self, v: str) -> None:
        self["password"] = v
        self.save()

    @session.setter
    def session(self, v: Type) -> None:
        if v:
            self["session"] = dataclasses.asdict(v)
        elif "session" in self:
            del self["session"]
        self.save()


jumpcloud_data = JumpCloudData()
