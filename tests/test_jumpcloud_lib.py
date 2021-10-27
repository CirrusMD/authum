import os

import pytest
import responses

import authum.plugins.jumpcloud.lib
import authum.http


@pytest.fixture
def jumpcloud_email(random_string):
    return os.environ.get("AUTHUM_JUMPCLOUD_EMAIL", random_string)


@pytest.fixture
def jumpcloud_password(random_string):
    return os.environ.get("AUTHUM_JUMPCLOUD_PASSWORD", random_string)


@pytest.fixture
def jumpcloud_client(jumpcloud_email, jumpcloud_password):
    return authum.plugins.jumpcloud.lib.JumpCloudClient(
        email=jumpcloud_email, password=jumpcloud_password
    )


@responses.activate
def test_jumpcloud_auth_invalid_credentials(random_string, response_data):
    jumpcloud_client = authum.plugins.jumpcloud.lib.JumpCloudClient(
        email=random_string, password=random_string
    )

    responses.add(
        method=responses.GET,
        url=jumpcloud_client.urls["xsrf"],
        body=response_data("jumpcloud/xsrf.json"),
        headers={
            "Set-Cookie": f"{authum.plugins.jumpcloud.lib.JUMPCLOUD_SESSION_COOKIE}={random_string}"
        },
    )
    responses.add(
        method=responses.POST,
        url=jumpcloud_client.urls["auth"],
        status=401,
        body=response_data("jumpcloud/auth_failed.json"),
    )

    with pytest.raises(authum.plugins.jumpcloud.lib.JumpCloudError):
        jumpcloud_client.auth()


@responses.activate
def test_jumpcloud_auth_lazy_auth_totp(jumpcloud_client, random_string, response_data):
    responses.add(method=responses.GET, url=jumpcloud_client.urls["self"], status=401)
    responses.add(
        method=responses.GET,
        url=jumpcloud_client.urls["xsrf"],
        body=response_data("jumpcloud/xsrf.json"),
        headers={
            "Set-Cookie": f"{authum.plugins.jumpcloud.lib.JUMPCLOUD_SESSION_COOKIE}={random_string}"
        },
    )
    responses.add(
        method=responses.POST,
        url=jumpcloud_client.urls["auth"],
        status=401,
        body=response_data("jumpcloud/mfa_required.json"),
    )

    try:
        jumpcloud_client.auth(lazy=True)

    except authum.plugins.jumpcloud.lib.JumpCloudMFARequired as e:
        responses.add(method=responses.POST, url=jumpcloud_client.urls["auth_totp"])
        response = e.client.auth_totp("123456")
        assert response == {}


@responses.activate
def test_jumpcloud_auth_lazy_refresh(jumpcloud_client, response_data):
    responses.add(
        method=responses.GET,
        url=jumpcloud_client.urls["self"],
        body=response_data("jumpcloud/self.json"),
    )

    response = jumpcloud_client.auth(lazy=True)
    assert response["_id"] == "61138e94597fd874e1257a9f"


@responses.activate
def test_jumpcloud_applications(jumpcloud_client, response_data):
    responses.add(
        method=responses.GET,
        url=jumpcloud_client.urls["applications"],
        body=response_data("jumpcloud/applications.json"),
    )

    labels = [app["displayLabel"] for app in jumpcloud_client.applications()]
    assert labels == ["GitHub", "Google Mail"]


def test_jumpcloud_data():
    od = authum.plugins.jumpcloud.lib.JumpCloudData()
    od.email = "foo"
    od.password = "bar"
    od.session = authum.plugins.jumpcloud.lib.JumpCloudClientSession()

    assert od.email == "foo"
    assert od.password == "bar"
    assert od.session == authum.plugins.jumpcloud.lib.JumpCloudClientSession()
