import urllib.parse

import rich.console

rich_stdout = rich.console.Console(soft_wrap=True)
rich_stderr = rich.console.Console(stderr=True)


def url_has_domain(url: str, domain: str) -> bool:
    """Checks whether the URL contains the specified domain"""
    o = urllib.parse.urlparse(url)
    return o.hostname == domain
