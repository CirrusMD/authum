import dataclasses
import itertools
import logging
import time
from typing import Type, Union

import authum.duo
import authum.persistence
import authum.http


log = logging.getLogger(__name__)


@dataclasses.dataclass
class OktaClientSession:
    """Represents an Okta client session"""

    id: str = ""
    refresh_url: str = ""


class OktaClient(authum.http.HTTPClient):
    """Handles communication with the Okta API.

    See: https://developer.okta.com/docs/reference/api/
    """

    def __init__(
        self,
        domain: str,
        username: str,
        password: str,
        session: OktaClientSession = OktaClientSession(),
        poll_interval: float = 2.0,
    ) -> None:
        super().__init__()

        self._domain = domain
        self._username = username
        self._password = password
        self._session = session
        self._poll_interval = poll_interval

        self.urls = {
            k: f"https://{self._domain}/api/v1{v}"
            for k, v in {
                "app_links": "/users/me/appLinks",
                "authn": "/authn",
                "sessions": "/sessions",
            }.items()
        }

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def session(self) -> OktaClientSession:
        return self._session

    def rest_request(
        self, url: str, method: str, data: dict = {}
    ) -> authum.http.RESTResponse:
        """Performs an API request and returns the response"""
        return super().rest_request(
            url=url,
            method=method,
            # https://developer.okta.com/docs/guides/session-cookie/overview/
            cookies={"sid": self._session.id},
            json=data,
        )

    def saml_request(self, url: str) -> authum.http.SAMLAssertion:
        """Performs a SAML request and returns the response"""
        return super().saml_request(
            url=url,
            # https://developer.okta.com/docs/guides/session-cookie/overview/
            cookies={"sid": self._session.id},
        )

    def authn(self, lazy: bool = False) -> authum.http.RESTResponse:
        """Authenticates a user.

        See: https://developer.okta.com/docs/reference/api/authn/
        """
        if lazy:
            try:
                response = self.session_refresh()
                if response.response.ok:
                    log.debug(f"Reusing existing session")
                    return response
            except OktaError:
                pass

        log.debug(f"Authenticating '{self._username}' at '{self._domain}'")
        data = {"username": self._username, "password": self._password}
        response = self.rest_request(url=self.urls["authn"], method="post", data=data)

        # https://developer.okta.com/docs/reference/api/authn/#transaction-state
        status = response.get("status")
        if status == "MFA_REQUIRED":
            log.debug("MFA required")
            raise OktaMFARequired(self, response)
        elif status == "SUCCESS":
            self.session_create(response["sessionToken"])
        elif response.get("errorCode"):
            raise OktaError(
                f"{response.get('errorCode')} - {response.get('errorSummary')}"
            )

        return response

    def verify(
        self,
        mfa_response: authum.http.RESTResponse,
        factor_id: str,
        factor_args: dict = {},
    ) -> Union[authum.http.RESTResponse, None]:
        """Performs MFA factor verification.

        See: https://developer.okta.com/docs/reference/api/factors/
        """
        factor = factor_by_id(mfa_response, factor_id)
        url = factor["_links"]["verify"]["href"]
        data = {**{"stateToken": mfa_response["stateToken"]}, **factor_args}

        response = None
        for i in itertools.count(1):
            log.debug(f"Checking MFA verification status (try: {i})")
            response = self.rest_request(url=url, method="post", data=data)

            if factor["factorType"] == "web" and i == 1:
                self.verify_web(response)

            factor_result = response.get("factorResult", "")
            if factor_result == "WAITING":
                time.sleep(self._poll_interval)

            elif response["status"] == "SUCCESS":
                self.session_create(response["sessionToken"])
                break

            else:
                raise OktaError(f"MFA verification failed: {factor_result}")

        return response

    def verify_web(
        self,
        response: authum.http.RESTResponse,
    ) -> None:
        """Performs MFA factor verification for the "web" factor type.

        See: https://developer.okta.com/docs/reference/api/authn/#verify-duo-factor
        """
        verification = response["_embedded"]["factor"]["_embedded"]["verification"]
        duo = authum.duo.DuoWebV2(
            name=f"Okta ({self._username})",
            http_client=self,
            host=verification["host"],
            sig_request=verification["signature"],
            post_action=verification["_links"]["complete"]["href"],
            duo_form_args={"stateToken": response["stateToken"]},
            script_url=verification["_links"]["script"]["href"],
        )

        duo.prompt()

    def session_create(self, session_token: str) -> authum.http.RESTResponse:
        """Creates a new session.

        See: https://developer.okta.com/docs/reference/api/sessions/
        """
        log.debug(f"Creating session")
        response = self.rest_request(
            url=self.urls["sessions"],
            method="post",
            data={"sessionToken": session_token},
        )
        if response["status"] == "ACTIVE":
            log.debug("Saving session data")
            self._session.id = response["id"]
            self._session.refresh_url = response["_links"]["refresh"]["href"]

        return response

    def session_refresh(self) -> authum.http.RESTResponse:
        """Refreshes the current session.

        See: https://developer.okta.com/docs/reference/api/sessions/#refresh-current-session
        """
        if not self._session.refresh_url:
            raise OktaError("No session refresh URL found")

        log.debug(f"Refreshing session")
        return self.rest_request(url=self._session.refresh_url, method="post")

    def app_links(self) -> authum.http.RESTResponse:
        """Returns a list of the current user's app links.

        See: https://developer.okta.com/docs/reference/api/users/#get-assigned-app-links
        """
        log.debug("Requesting app links")
        return self.rest_request(url=self.urls["app_links"], method="get")


class OktaMFARequired(Exception):
    """Raised when multi-factor authentication is required"""

    def __init__(self, client: OktaClient, response: authum.http.RESTResponse) -> None:
        self.client = client
        self.response = response


class OktaError(Exception):
    """Represents Okta errors"""


def factor_ids_by_type(response: authum.http.RESTResponse, factor_type: str) -> list:
    """Returns all the factor ids of a given type from a response"""
    factors = response["_embedded"]["factors"]
    return [f["id"] for f in factors if f["factorType"] == factor_type]


def factor_by_id(response: authum.http.RESTResponse, id: str) -> dict:
    """Returns the factor with the given id from a response"""
    factors = response["_embedded"]["factors"]
    return next((f for f in factors if f["id"] == id), {})


class OktaData(authum.persistence.KeyringItem):
    """Represents persistent Okta data"""

    def __init__(self) -> None:
        super().__init__("okta")

    @property
    def domain(self) -> str:
        return self.get("domain", "")

    @property
    def username(self) -> str:
        return self.get("username", "")

    @property
    def password(self) -> str:
        return self.get("password", "")

    @property
    def session(self) -> Type:
        return OktaClientSession(**self.get("session", {}))

    @domain.setter
    def domain(self, v: str) -> None:
        self["domain"] = v
        self.save()

    @username.setter
    def username(self, v: str) -> None:
        self["username"] = v
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


okta_data = OktaData()
