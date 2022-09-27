from typing import Any
import urllib.parse

import rich.box
import rich.console
import rich.table


rich_stdout = rich.console.Console(soft_wrap=True)
rich_stderr = rich.console.Console(stderr=True)

rich_table_horizontal_opts = {"box": rich.box.DOUBLE_EDGE}
rich_table_vertical_opts = {
    "box": rich.box.SIMPLE,
    "title_style": "bold",
    "title_justify": "left",
    "show_header": False,
}


def sensitive_value(v: Any) -> str:
    """Hide a sensitive value"""
    return "<sensitive>" if v else ""


def is_url(url: str) -> bool:
    """Checks whether the string is a URL"""
    o = urllib.parse.urlparse(url)
    return all([o.scheme, o.netloc])


def url_has_domain(url: str, domain: str) -> bool:
    """Checks whether the URL contains the specified domain"""
    o = urllib.parse.urlparse(url)
    return o.hostname == domain
