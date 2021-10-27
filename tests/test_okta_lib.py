import os

import pytest
import responses

import authum.plugins.okta.lib
import authum.http


@pytest.fixture
def okta_domain(random_string):
    return os.environ.get("AUTHUM_OKTA_DOMAIN", f"{random_string}.okta.com")


@pytest.fixture
def okta_username(random_string):
    return os.environ.get("AUTHUM_OKTA_USERNAME", random_string)


@pytest.fixture
def okta_password(random_string):
    return os.environ.get("AUTHUM_OKTA_PASSWORD", random_string)


@pytest.fixture
def okta_client(okta_domain, okta_username, okta_password):
    return authum.plugins.okta.lib.OktaClient(
        domain=okta_domain,
        username=okta_username,
        password=okta_password,
        session=authum.plugins.okta.lib.OktaClientSession(
            id="initial_session_id",
            refresh_url=f"http://{okta_domain}/api/v1/sessions/initial_session_id/lifecycle/refresh",
        ),
        poll_interval=0,
    )


@responses.activate
def test_okta_authn_org_not_found(random_string, okta_username, okta_password):
    okta_client = authum.plugins.okta.lib.OktaClient(
        domain=random_string, username=okta_username, password=okta_password
    )

    responses.add(method=responses.POST, url=okta_client.urls["authn"], status=404)

    response = okta_client.authn()
    assert response.response.status_code == 404


@responses.activate
def test_okta_authn_invalid_credentials(okta_domain, random_string, response_data):
    okta_client = authum.plugins.okta.lib.OktaClient(
        domain=okta_domain, username=random_string, password=random_string
    )

    responses.add(
        method=responses.POST,
        url=okta_client.urls["authn"],
        body=response_data("okta/authn_failed.json"),
        status=401,
    )

    with pytest.raises(authum.plugins.okta.lib.OktaError):
        okta_client.authn()


@pytest.mark.parametrize(
    "factor_type, factor_args, wait_count",
    [
        ["token", {"passCode": "123456"}, 0],
        ["token:software:totp", {"passCode": "123456"}, 0],
        ["sms", {"passCode": "123456"}, 0],
        ["call", {"passCode": "123456"}, 0],
        ["push", {}, 2],
    ],
)
@responses.activate
def test_okta_authn_lazy_mfa(
    okta_client, response_data, okta_domain, factor_type, factor_args, wait_count
):
    responses.add(
        method=responses.POST,
        url=okta_client.session.refresh_url,
        status=404,
        body=response_data("okta/session_expired.json", yourOktaDomain=okta_domain),
    )
    responses.add(
        method=responses.POST,
        url=okta_client.urls["authn"],
        body=response_data("okta/mfa_required.json", yourOktaDomain=okta_domain),
    )
    responses.add(
        method=responses.POST,
        url=okta_client.urls["sessions"],
        body=response_data("okta/session_create.json", yourOktaDomain=okta_domain),
    )

    try:
        okta_client.authn(lazy=True)
        assert False

    except authum.plugins.okta.lib.OktaMFARequired as e:
        factor_id = authum.plugins.okta.lib.factor_ids_by_type(e.response, factor_type)[
            0
        ]
        url = authum.plugins.okta.lib.factor_by_id(e.response, factor_id)["_links"][
            "verify"
        ]["href"]

        for _ in range(wait_count):
            responses.add(
                method=responses.POST,
                url=url,
                body=response_data(
                    "okta/mfa_challenge.json", yourOktaDomain=okta_domain
                ),
            )
        responses.add(
            method=responses.POST,
            url=url,
            body=response_data("okta/authn_success.json"),
        )

        e.client.verify(e.response, factor_id, factor_args)
        assert okta_client.session.id == "101W_juydrDRByB7fUdRyE2JQ"


@responses.activate
def test_okta_authn_lazy_refresh(okta_client, response_data, okta_domain):
    responses.add(
        method=responses.POST,
        url=okta_client.session.refresh_url,
        body=response_data("okta/session_refresh.json", yourOktaDomain=okta_domain),
    )

    okta_client.authn(lazy=True)
    assert okta_client.session.id == "initial_session_id"


@responses.activate
def test_okta_app_links(okta_client, response_data, okta_domain):
    responses.add(
        method=responses.GET,
        url=okta_client.urls["app_links"],
        body=response_data("okta/app_links.json", yourOktaDomain=okta_domain),
    )

    labels = [link["label"] for link in okta_client.app_links()]
    assert labels == [
        "Google Apps Mail",
        "Google Apps Calendar",
        "Box",
        "Salesforce.com",
    ]


def test_okta_data():
    od = authum.plugins.okta.lib.OktaData()
    od.domain = "foo"
    od.username = "bar"
    od.password = "baz"
    od.session = authum.plugins.okta.lib.OktaClientSession()

    assert od.domain == "foo"
    assert od.username == "bar"
    assert od.password == "baz"
    assert od.session == authum.plugins.okta.lib.OktaClientSession()
