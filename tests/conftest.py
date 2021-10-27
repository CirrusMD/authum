import os
import pathlib
from typing import Any
import uuid

import keyring
import keyring.backend
import mako.template
import pytest


class TestKeyring(keyring.backend.KeyringBackend):
    priority = 0

    def __init__(self):
        super().__init__()
        self._data = {}

    def set_password(self, servicename: str, username: str, password: str) -> None:
        self._data.setdefault(servicename, {})[username] = password

    def get_password(self, servicename: str, username: str) -> Any:
        return self._data.get(servicename, {}).get(username)

    def delete_password(self, servicename: str, username: str) -> None:
        del self._data.get(servicename, {})[username]


keyring.set_keyring(TestKeyring())


@pytest.fixture(scope="session")
def random_string():
    rand = str(uuid.uuid4()).split("-")[0]
    return f"authum-test-{rand}"


@pytest.fixture(scope="session")
def random_url(random_string):
    return f"http://{random_string}"


@pytest.fixture
def response_data():
    def _response_data(name: str, **data):
        path = os.path.join(pathlib.Path(__file__).parent, "response_data", name)
        with open(path, "r") as f:
            return mako.template.Template(f.read()).render(**data)

    return _response_data
