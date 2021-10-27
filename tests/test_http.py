import pytest
import responses

import authum.http


@pytest.fixture()
def a(response_data):
    return authum.http.SAMLAssertion(response_data("saml/response.xml"))


def test_saml_assertion_attrs_getitem_error(a):
    with pytest.raises(KeyError):
        a.attrs["invalid"]


def test_saml_assertion_attrs_getitem_ok(a):
    assert a.attrs["uid"] == ["test"]
    assert a.attrs["mail"] == ["test@example.com"]
    assert a.attrs["eduPersonAffiliation"] == ["users", "examplerole1"]


def test_saml_assertion_attrs_iter(a):
    assert {n: v for n, v in a.attrs.items()} == {
        "eduPersonAffiliation": ["users", "examplerole1"],
        "mail": ["test@example.com"],
        "uid": ["test"],
    }


def test_saml_assertion_attrs_len(a):
    assert len(a.attrs) == 3


@responses.activate
def test_saml_request_error():
    url = "https://example.com/"
    responses.add(method=responses.GET, url=url)
    with pytest.raises(Exception):
        authum.http.HTTPClient().saml_request(url=url)


@responses.activate
def test_saml_request_ok(response_data):
    saml_assertion = authum.http.SAMLAssertion(response_data("saml/response.xml"))
    html = response_data("saml/response.html", SAMLResponse=saml_assertion.b64encoded)

    url = "https://example.com/"
    responses.add(method=responses.GET, url=url, body=html)

    response = authum.http.HTTPClient().saml_request(url=url)
    assert response == saml_assertion
