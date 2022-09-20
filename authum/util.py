import urllib.parse

import rich.console

rich_stdout = rich.console.Console(soft_wrap=True)
rich_stderr = rich.console.Console(stderr=True)


def is_url(url: str) -> bool:
    """Checks whether the string is a URL"""
    o = urllib.parse.urlparse(url)
    return all([o.scheme, o.netloc])


def url_has_domain(url: str, domain: str) -> bool:
    """Checks whether the URL contains the specified domain"""
    o = urllib.parse.urlparse(url)
    return o.hostname == domain
