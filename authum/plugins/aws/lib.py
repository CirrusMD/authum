import dataclasses
import datetime
import logging
import os
import subprocess

import arn.iam
import boto3

import authum.http
import authum.persistence
import authum.plugin


logging.getLogger("botocore").propagate = False
log = logging.getLogger()


@dataclasses.dataclass
class AWSSession:
    """Represents an AWS Session"""

    sso_url: str = ""

    role_arn: str = ""
    external_id: str = ""
    endpoint_url: str = ""

    access_key_id: str = ""
    secret_access_key: str = ""
    session_token: str = ""
    arn: str = ""
    expiration: str = ""

    def from_sts_response(self, response: dict):
        """Set attributes from an AWS response"""
        self.access_key_id = response["Credentials"]["AccessKeyId"]
        self.secret_access_key = response["Credentials"]["SecretAccessKey"]
        self.session_token = response["Credentials"]["SessionToken"]
        self.arn = response["AssumedRoleUser"]["Arn"]
        self.expiration = str(response["Credentials"]["Expiration"])

        return self

    @property
    def env_vars(self) -> dict:
        """Return a list of credential environment variables"""
        return {
            "AWS_ACCESS_KEY_ID": self.access_key_id,
            "AWS_SECRET_ACCESS_KEY": self.secret_access_key,
            "AWS_SESSION_TOKEN": self.session_token,
            "AWS_SECURITY_TOKEN": self.session_token,
        }

    @property
    def env_vars_export(self) -> str:
        """Returns a list of credential environment variables suitable for
        eval'ing in a shell"""
        return "\n".join(f"export {k}='{v}'" for k, v in self.env_vars.items())

    @property
    def ttl(self) -> datetime.timedelta:
        """Computes time to expiration"""
        try:
            expiration = datetime.datetime.fromisoformat(self.expiration)
        except ValueError:
            return datetime.timedelta(-1)
        now = datetime.datetime.now(datetime.timezone.utc)

        return expiration - now

    @property
    def is_expired(self) -> bool:
        """Checks whether the session is expired"""
        return self.ttl < datetime.timedelta()

    @property
    def pretty_ttl(self) -> str:
        """Fix for normalization of negative values for ttl.

        See: https://docs.python.org/3/library/datetime.html#timedelta-objects"""
        ttl_str = str(abs(self.ttl))
        if self.is_expired:
            ttl_str = f"-{ttl_str}"
        return ttl_str

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(arn={self.arn}, ttl={self.ttl})"

    def exec(self, command: tuple, capture_output=False) -> subprocess.CompletedProcess:
        """Runs a shell command with AWS_* environment variables set"""
        if len(command) == 0:
            return subprocess.CompletedProcess("", 0)
        return subprocess.run(
            args=command,
            env={**dict(os.environ), **self.env_vars},
            capture_output=capture_output,
            text=True,
        )


class AWSPluginError(Exception):
    """Represents AWS plugin errors"""


class AWSData(authum.persistence.KeyringItem):
    """Represents persistent AWS data"""

    def __init__(self) -> None:
        super().__init__("aws")

    def set_session(self, name: str, v: AWSSession) -> None:
        self.setdefault("session", {})[name] = dataclasses.asdict(v)
        self.save()

    def session(self, name: str) -> AWSSession:
        try:
            return AWSSession(**self["session"][name])
        except KeyError:
            raise AWSPluginError(f"No such session: {name}")

    def rm_session(self, name: str) -> None:
        del self.get("session", {})[name]
        self.save()

    @property
    def sessions(self) -> dict:
        return {
            name: AWSSession(**session)
            for name, session in self.get("session", {}).items()
        }


def assume_role_with_saml(sso_url: str, endpoint_url: str = "") -> AWSSession:
    """Assumes a role via SAML assertion"""
    assertion = authum.plugin.manager.hook.saml_request(url=sso_url)  # type: ignore
    if not assertion:
        raise AWSPluginError(
            f"All plugins declined to handle SAML application URL: {sso_url}"
        )

    assume_role_args = {"SAMLAssertion": assertion.b64encoded}

    try:
        role = assertion.attrs["https://aws.amazon.com/SAML/Attributes/Role"][0]
        assume_role_args["RoleArn"], assume_role_args["PrincipalArn"] = role.split(",")
    except IndexError:
        raise AWSPluginError(f"No AWS role found in SAML assertion")

    try:
        assume_role_args["DurationSeconds"] = int(  # type: ignore
            assertion.attrs["https://aws.amazon.com/SAML/Attributes/SessionDuration"][0]
        )
    except IndexError:
        pass

    sts = boto3.client("sts", endpoint_url=endpoint_url if endpoint_url else None)

    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sts.html#STS.Client.assume_role_with_saml
    response = sts.assume_role_with_saml(**assume_role_args)
    log.debug(f"AWS response: {response}")

    return AWSSession(sso_url=sso_url, endpoint_url=endpoint_url).from_sts_response(
        response
    )


def assume_role_with_session(
    session: AWSSession, role_arn: str, external_id: str = ""
) -> AWSSession:
    """Assumes a role via existing session"""
    sts = boto3.client(
        "sts",
        aws_access_key_id=session.access_key_id,
        aws_secret_access_key=session.secret_access_key,
        aws_session_token=session.session_token,
        endpoint_url=session.endpoint_url if session.endpoint_url else None,
    )

    assume_role_args = {
        "RoleArn": role_arn,
        "RoleSessionName": arn.iam.AssumedRoleArn(session.arn).role_session_name,
    }

    if external_id:
        assume_role_args["ExternalId"] = external_id

    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sts.html#STS.Client.assume_role
    response = sts.assume_role(**assume_role_args)
    log.debug(f"AWS response: {response}")

    return AWSSession(
        sso_url=session.sso_url,
        role_arn=role_arn,
        external_id=external_id,
        endpoint_url=session.endpoint_url,
    ).from_sts_response(response)


aws_data = AWSData()
