import pytest

import authum.util


@pytest.mark.parametrize(
    "value, result",
    [
        [None, ""],
        ["", ""],
        ["test", "<sensitive>"],
        [" ", "<sensitive>"],
    ],
)
def test_sensitive_value(value, result):
    assert authum.util.sensitive_value(value) == result


@pytest.mark.parametrize(
    "url, result",
    [["127.0.0.1", False], ["http://", False], ["http://127.0.0.1", True]],
)
def test_is_url(url, result):
    assert authum.util.is_url(url) == result


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
