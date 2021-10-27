import base64
from collections.abc import Mapping
import dataclasses
import json
import logging
from typing import Any, Iterable
import xml.etree.ElementTree

import bs4
import requests


log = logging.getLogger(__name__)


class RESTResponse(Mapping):
    """Represents a REST response"""

    def __init__(self, response: requests.Response = requests.Response()) -> None:
        super().__init__()

        self._response = response

        try:
            self._data = response.json()
        except json.decoder.JSONDecodeError:
            self._data = {}

    @property
    def response(self):
        return self._response

    def __getitem__(self, k: str) -> Any:
        if k not in self._data:
            raise KeyError(k)
        return self._data[k]

    def __iter__(self) -> Iterable:
        return (k for k in self._data)

    def __len__(self) -> int:
        return len(list(self.__iter__()))

    def __str__(self) -> str:
        return self._response.content.decode()


class SAMLAssertion:
    """Represents a SAML assertion"""

    def __init__(self, saml_assertion: str) -> None:
        try:
            self._xml = base64.b64decode(saml_assertion).decode()
            self._b64encoded = saml_assertion
        except UnicodeDecodeError:
            self._xml = saml_assertion
            self._b64encoded = base64.b64encode(bytes(saml_assertion, "utf-8")).decode()

        self._attrs = SAMLAssertionAttributes(self._xml)

    @property
    def xml(self) -> str:
        return self._xml

    @property
    def b64encoded(self) -> str:
        return self._b64encoded

    @property
    def attrs(self) -> Mapping:
        return self._attrs

    def __str__(self) -> str:
        return self._xml

    def __eq__(self, other) -> bool:
        return str(self) == str(other)


class SAMLAssertionAttributes(Mapping):
    """Provides a simple dict-like interface for SAML assertion attributes"""

    def __init__(self, saml_assertion: str) -> None:
        self.ns = {
            "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
            "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
        }
        root = xml.etree.ElementTree.fromstring(saml_assertion)
        self.attribute_statement = root.find(".//saml:AttributeStatement", self.ns)

    def __getitem__(self, k: str) -> list:
        if not self.attribute_statement:
            return []

        attr = self.attribute_statement.find(f".//saml:Attribute[@Name='{k}']", self.ns)
        if not attr:
            raise KeyError(k)
        return [v.text for v in attr.findall(".//saml:AttributeValue", self.ns)]

    def __iter__(self) -> Iterable:
        if not self.attribute_statement:
            return []

        return (
            k.attrib["Name"]
            for k in self.attribute_statement.findall(".//saml:Attribute", self.ns)
        )

    def __len__(self) -> int:
        return len(list(self.__iter__()))


@dataclasses.dataclass
class SAMLApplication:
    """Represents a SAML application"""

    name: str
    url: str

    def __lt__(self, other):
        return self.name.casefold() < other.name.casefold()


class HTTPClient:
    """Simple HTTP client"""

    def __init__(self) -> None:
        self._client = requests.Session()

    def http_request(self, **kwargs) -> requests.Response:
        """Performs an HTTP request and returns the response"""
        if "method" not in kwargs:
            kwargs["method"] = "get"

        kwargs["headers"] = {
            **{
                "Accept": "text/html",
                "Content-Type": "text/html",
            },
            **kwargs.get("headers", {}),
        }

        response = self._client.request(**kwargs)
        log.debug(
            f"HTTP response ({response.status_code}): {response.content.decode()}"
        )

        return response

    def rest_request(self, **kwargs) -> RESTResponse:
        """Performs an API request and returns the response"""
        kwargs["headers"] = {
            **{
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            **kwargs.get("headers", {}),
        }

        response = self._client.request(**kwargs)
        log.debug(
            f"REST response ({response.status_code}): {response.content.decode()}"
        )

        return RESTResponse(response)

    def saml_request(self, **kwargs) -> SAMLAssertion:
        """Performs a SAML request and returns a SAML response"""
        if "method" not in kwargs:
            kwargs["method"] = "get"

        kwargs["headers"] = {
            **{
                "Accept": "text/html",
                "Content-Type": "text/html",
            },
            **kwargs.get("headers", {}),
        }

        response = self._client.request(**kwargs)

        parser = bs4.BeautifulSoup(response.content, "html.parser")
        try:
            response_saml = next(
                (
                    tag.get("value")
                    for tag in parser.find_all("input")
                    if tag.get("name") == "SAMLResponse"
                )
            )
        except StopIteration:
            raise Exception("SAML response not found")

        response_saml = SAMLAssertion(response_saml)
        log.debug(f"SAML response ({response.status_code}): {response_saml.xml}")

        return response_saml
