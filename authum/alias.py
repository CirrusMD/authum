import urllib.parse

import authum.persistence
import authum.util


class Aliases(authum.persistence.KeyringItem):
    """Provides an interface to manage and resolve URL aliases"""

    def __init__(self, name="alias") -> None:
        super().__init__(name=name)

    def add(self, name: str, url: str) -> None:
        """Add an alias"""
        if not authum.util.is_url(url):
            raise AliasError(f"Invalid URL: {url}")

        self[name] = url
        self.save()

    def resolve(self, name_or_url: str) -> str:
        """Resolve an alias to a URL"""
        if authum.util.is_url(name_or_url):
            return name_or_url

        try:
            return self[name_or_url]
        except KeyError:
            raise AliasError(f"No such alias: {name_or_url}")

    def aliases_for(self, url: str) -> list:
        """Return aliases for a URL"""
        return sorted(k for k, v in self.items() if v == url)

    def mv(self, cur: str, new: str) -> None:
        """Rename an alias"""
        try:
            self[new] = self[cur]
        except KeyError:
            raise AliasError(f"No such alias: {cur}")

        del self[cur]
        self.save()

    def rm(self, name: str) -> None:
        """Remove an alias"""
        try:
            del self[name]
        except KeyError:
            raise AliasError(f"No such alias: {name}")
        self.save()


class AliasError(KeyError):
    """Represents general alias errors"""

    pass


aliases = Aliases()
