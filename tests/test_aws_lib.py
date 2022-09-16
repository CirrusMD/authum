import re

import pytest

import authum.plugins.aws.lib


@pytest.fixture()
def common_credential_attrs():
    return {
        "access_key_id": "EXAMPLEACCESSKEY",
        "secret_access_key": "EXAMPLEACCESSKEY",
        "session_token": "EXAMPLESESSIONTOKEN",
        "assume_role_arn": "arn:aws:sts::123456789012:assumed-role/TestRole",
        "assume_role_external_id": "example",
        "sts_endpoint": "https://fips.example.com/example",
    }


@pytest.fixture()
def oidc_credentials(common_credential_attrs):
    return authum.plugins.aws.lib.AWSSSORoleCredentials(
        name="example_oidc",
        start_url="https://example.awsapps.com/start#/",
        account_id="123456789012",
        role_name="TestRole",
        **common_credential_attrs,
    )


@pytest.fixture()
def saml_credentials(common_credential_attrs):
    return authum.plugins.aws.lib.AWSSAMLRoleCredentials(
        name="example_saml",
        saml_url="https://example.com/example",
        **common_credential_attrs,
    )


@pytest.fixture
def credentials(request):
    return request.getfixturevalue(request.param)


@pytest.mark.parametrize(
    "credentials",
    ["oidc_credentials", "saml_credentials"],
    indirect=True,
)
def test_aws_data(random_string, credentials):
    ad = authum.plugins.aws.lib.AWSData()

    ad.set_credentials(random_string, credentials)
    assert ad.credentials(random_string) == credentials

    new_name = f"{random_string}/renamed"
    ad.mv_credentials(random_string, new_name)

    ad.rm_credentials(new_name)
    with pytest.raises(KeyError):
        ad.credentials(new_name)


@pytest.mark.parametrize(
    "credentials",
    ["oidc_credentials", "saml_credentials"],
    indirect=True,
)
def test_aws_session_env_vars_export(credentials):
    assert (
        credentials.env_vars_export
        == "export AWS_ACCESS_KEY_ID='EXAMPLEACCESSKEY'\nexport"
        " AWS_SECRET_ACCESS_KEY='EXAMPLEACCESSKEY'\nexport"
        " AWS_SESSION_TOKEN='EXAMPLESESSIONTOKEN'"
    )


@pytest.mark.parametrize(
    "credentials",
    ["oidc_credentials", "saml_credentials"],
    indirect=True,
)
def test_aws_session_ttl_str(credentials):
    assert re.match(r"^-\d+ days", credentials.ttl_str)


@pytest.mark.parametrize(
    "str, result",
    [
        ["http://example.com/path", "http://example.com/path"],
        ["foo", "http://foo.example.com/path/"],
    ],
)
def test_normalize_start_url(str, result):
    assert (
        authum.plugins.aws.lib.normalize_start_url(
            str, scheme="http://", domain="example.com", path="/path/"
        )
        == result
    )


@pytest.mark.parametrize(
    "credentials",
    ["oidc_credentials", "saml_credentials"],
    indirect=True,
)
def test_aws_session_exec(credentials):
    cp = credentials.exec(
        ["bash", "-c", "echo $AWS_SECRET_ACCESS_KEY"], capture_output=True
    )
    assert cp.stdout == "EXAMPLEACCESSKEY\n"
