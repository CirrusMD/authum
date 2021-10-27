import pytest

import authum.util


@pytest.mark.parametrize(
    "url, domain, result",
    [
        ["http://test.example.com", "test", False],
        ["http://test.example.com", "example.com", False],
        ["http://test.example.com", "test.example.com", True],
    ],
)
def test_url_has_domain(url, domain, result):
    assert authum.util.url_has_domain(url, domain) == result
