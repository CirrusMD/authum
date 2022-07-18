import datetime

import pytest

import authum.plugins.aws.lib


@pytest.fixture()
def session():
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sts.html#STS.Client.assume_role_with_saml
    sts_response = {
        "Credentials": {
            "AccessKeyId": "EXAMPLEACCESSKEY",
            "SecretAccessKey": "EXAMPLEACCESSKEY",
            "SessionToken": "EXAMPLESESSIONTOKEN",
            "Expiration": datetime.datetime.now(datetime.timezone.utc),
        },
        "AssumedRoleUser": {
            "AssumedRoleId": "ARO456EXAMPLE789:TestSaml",
            "Arn": "arn:aws:sts::123456789012:assumed-role/TestSaml",
        },
        "PackedPolicySize": 123,
        "Subject": "SamlExample",
        "SubjectType": "transient",
        "Issuer": "https://integ.example.com/idp/shibboleth",
        "Audience": "ttps://signin.aws.amazon.com/saml",
        "NameQualifier": "SbdGOnUkh1i4+EXAMPLExL/jEvs=",
        "SourceIdentity": "SourceIdentityValue",
    }

    return authum.plugins.aws.lib.AWSSession().from_sts_response(sts_response)


def test_aws_session_env_vars_export(session):
    assert (
        session.env_vars_export == "export AWS_ACCESS_KEY_ID='EXAMPLEACCESSKEY'\nexport"
        " AWS_SECRET_ACCESS_KEY='EXAMPLEACCESSKEY'\nexport"
        " AWS_SESSION_TOKEN='EXAMPLESESSIONTOKEN'\nexport"
        " AWS_SECURITY_TOKEN='EXAMPLESESSIONTOKEN'"
    )


def test_aws_session_pretty_ttl(session):
    assert session.pretty_ttl.startswith("-0:00:0")


def test_aws_session_exec(session):
    cp = session.exec(
        ["bash", "-c", "echo $AWS_SECRET_ACCESS_KEY"], capture_output=True
    )
    assert cp.stdout == "EXAMPLEACCESSKEY\n"


def test_aws_data(random_url, session):
    ad = authum.plugins.aws.lib.AWSData()
    ad.set_session(random_url, session)
    assert ad.session(random_url) == session

    ad.rm_session(random_url)
    with pytest.raises(authum.plugins.aws.lib.AWSPluginError):
        ad.session(random_url)
