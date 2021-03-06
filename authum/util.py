import urllib.parse


def url_has_domain(url: str, domain: str) -> bool:
    """Checks whether the URL contains the specified domain"""
    o = urllib.parse.urlparse(url)
    return o.hostname == domain
