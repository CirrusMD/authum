import json
import re

import boto3
import botocore.stub
import botocore.utils
import pytest

import authum
import authum.plugins.aws.lib


@pytest.fixture()
def start_url():
    return "https://test.awsapps.com/start#/"


@pytest.fixture()
def aws_sso_client(response_data, start_url):
    boto_sso_oidc_client = boto3.client(
        "sso-oidc", aws_access_key_id="test", aws_secret_access_key="test"
    )
    stubber = botocore.stub.Stubber(boto_sso_oidc_client)

    stubber.add_response(
        "register_client",
        json.loads(response_data("aws/sso-oidc/register_client.json")),
        {"clientName": authum.metadata["name"], "clientType": "public"},
    )

    stubber.add_response(
        "start_device_authorization",
        json.loads(response_data("aws/sso-oidc/start_device_authorization.json")),
        {
            "clientId": "EXAMPLECLIENTID",
            "clientSecret": "EXAMPLECLIENTSECRET",
            "startUrl": start_url,
        },
    )

    stubber.add_response(
        "create_token",
        json.loads(response_data("aws/sso-oidc/create_token.json")),
        {
            "clientId": "EXAMPLECLIENTID",
            "clientSecret": "EXAMPLECLIENTSECRET",
            "grantType": "urn:ietf:params:oauth:grant-type:device_code",
            "deviceCode": "EXAMPLEDEVICECODE",
        },
    )

    stubber.activate()

    return authum.plugins.aws.lib.AWSSSOClient(
        start_url=start_url,
        boto_sso_oidc_client=boto_sso_oidc_client,
        launch_web_browser=False,
    )


@pytest.fixture()
def aws_sso_role_credentials(start_url):
    return authum.plugins.aws.lib.AWSSSORoleCredentials(
        name="example_sso",
        start_url=start_url,
        account_id="123456789012",
        role_name="TestRole",
        access_key_id="EXAMPLEACCESSKEY",
        secret_access_key="EXAMPLEACCESSKEY",
        session_token="EXAMPLESESSIONTOKEN",
    )


@pytest.fixture()
def aws_saml_role_credentials():
    return authum.plugins.aws.lib.AWSSAMLRoleCredentials(
        name="example_saml",
        saml_url="https://example.com/example",
        access_key_id="EXAMPLEACCESSKEY",
        secret_access_key="EXAMPLEACCESSKEY",
        session_token="EXAMPLESESSIONTOKEN",
    )


@pytest.fixture
def aws_role_credentials(request):
    return request.getfixturevalue(request.param)


def test_aws_sso_client_registration(aws_sso_client):
    assert aws_sso_client.registration.client_id == "EXAMPLECLIENTID"
    assert aws_sso_client.registration.client_secret == "EXAMPLECLIENTSECRET"
    assert aws_sso_client.registration.expiration_timestamp == 1672169185.0


def test_aws_sso_client_authorization(aws_sso_client):
    assert aws_sso_client.authorization.access_token == "EXAMPLEACCESSTOKEN"


def test_aws_sso_client_list_accounts(response_data, aws_sso_client):
    boto_sso_client = boto3.client(
        "sso", aws_access_key_id="test", aws_secret_access_key="test"
    )
    stubber = botocore.stub.Stubber(boto_sso_client)

    stubber.add_response(
        "list_accounts",
        json.loads(response_data("aws/sso/list_accounts.json")),
        {"accessToken": "EXAMPLEACCESSTOKEN"},
    )

    stubber.add_response(
        "list_account_roles",
        json.loads(response_data("aws/sso/list_account_roles.json")),
        {
            "accessToken": "EXAMPLEACCESSTOKEN",
            "accountId": "123456789012",
        },
    )

    stubber.activate()

    accounts = aws_sso_client.list_accounts(boto_sso_client=boto_sso_client)
    assert accounts == [
        {
            "accountId": "123456789012",
            "accountName": "Test Account",
            "emailAddress": "test@example.com",
            "roles": ["Test SSO", "Test SAML"],
        }
    ]


@pytest.mark.parametrize(
    "aws_role_credentials",
    ["aws_sso_role_credentials", "aws_saml_role_credentials"],
    indirect=True,
)
def test_aws_data(random_string, aws_role_credentials):
    ad = authum.plugins.aws.lib.AWSData()

    ad.set_credentials(random_string, aws_role_credentials)
    assert ad.list_credentials == {random_string: aws_role_credentials}

    new_name = f"{random_string}/renamed"
    ad.mv_credentials(random_string, new_name)

    ad.rm_credentials(new_name)
    with pytest.raises(KeyError):
        ad.credentials(new_name)


def test_aws_sso_role_credentials_renew(
    response_data, aws_sso_role_credentials, aws_sso_client
):
    boto_sso_client = boto3.client(
        "sso", aws_access_key_id="test", aws_secret_access_key="test"
    )
    stubber = botocore.stub.Stubber(boto_sso_client)

    stubber.add_response(
        "get_role_credentials",
        json.loads(response_data("aws/sso/get_role_credentials.json")),
        {
            "accessToken": "EXAMPLEACCESSTOKEN",
            "accountId": "123456789012",
            "roleName": "TestRole",
        },
    )

    stubber.activate()

    aws_sso_role_credentials.renew(
        sso_client=aws_sso_client,
        boto_sso_client=boto_sso_client,
    )

    assert aws_sso_role_credentials.access_key_id == "EXAMPLESSOACCESSKEYID"
    assert aws_sso_role_credentials.secret_access_key == "EXAMPLESSOSECRETACCESSKEY"
    assert aws_sso_role_credentials.session_token == "EXAMPLESSOSESSIONTOKEN"


@pytest.mark.parametrize(
    "aws_role_credentials",
    ["aws_sso_role_credentials", "aws_saml_role_credentials"],
    indirect=True,
)
def test_aws_role_credentials_env_vars_export(aws_role_credentials):
    assert (
        aws_role_credentials.env_vars_export
        == "export AWS_ACCESS_KEY_ID='EXAMPLEACCESSKEY'\nexport"
        " AWS_SECRET_ACCESS_KEY='EXAMPLEACCESSKEY'\nexport"
        " AWS_SESSION_TOKEN='EXAMPLESESSIONTOKEN'"
    )


@pytest.mark.parametrize(
    "aws_role_credentials",
    ["aws_sso_role_credentials", "aws_saml_role_credentials"],
    indirect=True,
)
def test_aws_role_credentials_ttl_str(aws_role_credentials):
    assert re.match(r"^-\d+ days", aws_role_credentials.ttl_str)


@pytest.mark.parametrize(
    "aws_role_credentials",
    ["aws_sso_role_credentials", "aws_saml_role_credentials"],
    indirect=True,
)
def test_aws_role_credentials_exec(aws_role_credentials):
    cp = aws_role_credentials.exec(
        ["bash", "-c", "echo $AWS_SECRET_ACCESS_KEY"], capture_output=True
    )
    assert cp.stdout == "EXAMPLEACCESSKEY\n"


@pytest.mark.parametrize(
    "aws_role_credentials",
    ["aws_sso_role_credentials", "aws_saml_role_credentials"],
    indirect=True,
)
def test_aws_role_credentials_assume_role(response_data, aws_role_credentials):
    boto_sts_client = boto3.client(
        "sts", aws_access_key_id="test", aws_secret_access_key="test"
    )
    stubber = botocore.stub.Stubber(boto_sts_client)

    stubber.add_response(
        "get_caller_identity",
        json.loads(response_data("aws/sts/get_caller_identity.json")),
    )

    assume_role_response = json.loads(response_data("aws/sts/assume_role.json"))
    assume_role_response["Credentials"]["Expiration"] = botocore.utils.parse_timestamp(
        assume_role_response["Credentials"]["Expiration"]
    )
    stubber.add_response(
        "assume_role",
        assume_role_response,
        {
            "RoleArn": "arn:aws:sts::123456789012:assumed-role/TestRole",
            "RoleSessionName": "test@example.com",
            "ExternalId": "example",
        },
    )

    stubber.activate()

    aws_role_credentials.assume_role_arn = (
        "arn:aws:sts::123456789012:assumed-role/TestRole"
    )
    aws_role_credentials.assume_role_external_id = "example"
    aws_role_credentials.assume_role(boto_sts_client=boto_sts_client)

    assert aws_role_credentials.access_key_id == "EXAMPLESTSACCESSKEY"
    assert aws_role_credentials.secret_access_key == "EXAMPLESTSSECRETACCESSKEY"
    assert aws_role_credentials.session_token == "EXAMPLESTSSESSIONTOKEN"


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
