from collections.abc import MutableMapping
import json
import logging
from typing import Any, Iterable

import keyring
import keyring.errors
import yaml


log = logging.getLogger(__name__)


class KeyringItem(MutableMapping):
    """Provides a simple dict-like interface to an item in the system keyring
    service. Note that the keyring data can be dumped from the command line
    with: `keyring get authum <name>`
    """

    def __init__(self, name: str, initial: dict = {}) -> None:
        self._service = __package__
        self._name = name

        self._data = {}
        self.update(initial) if initial else self.load()

    @property
    def keyring_item_name(self) -> str:
        return self._name

    def __getitem__(self, k: Any) -> Any:
        return self._data[k]

    def __setitem__(self, k: Any, v: Any) -> None:
        self._data[k] = v

    def __delitem__(self, k: Any) -> None:
        del self._data[k]

    def __iter__(self) -> Iterable:
        return (k for k in self._data)

    def __len__(self) -> int:
        return len(self._data)

    def asyaml(self, masked_keys=[], hidden_keys=[]) -> str:
        """Return a naive (non-recursive) YAML representation of the item"""
        y = {}
        for k, v in self.items():
            if k in masked_keys:
                y[k] = "<masked>"
            elif k not in hidden_keys:
                y[k] = v

        return yaml.dump(y)

    def asdict(self) -> dict:
        """Return the item as a dict"""
        return dict(self)

    def load(self) -> None:
        """Loads data from a keyring item"""
        try:
            self._data = json.loads(
                str(keyring.get_password(self._service, self._name))
            )
            log.debug(
                f"Loaded keyring data from '{self._service}.{self._name}' with keys={list(self.keys())}"
            )
        except json.decoder.JSONDecodeError:
            pass

    def save(self) -> None:
        """Saves data to a keyring item"""
        log.debug(
            f"Saving keyring data to '{self._service}.{self._name}' with keys={list(self.keys())}"
        )
        keyring.set_password(
            self._service, self._name, json.dumps(self._data, default=str)
        )

    def delete(self) -> None:
        """Deletes a keyring item"""
        log.debug(f"Deleting keyring item: '{self._service}.{self._name}'")
        try:
            keyring.delete_password(self._service, self._name)
        except keyring.errors.PasswordDeleteError as e:
            if "not found" not in str(e):
                raise
