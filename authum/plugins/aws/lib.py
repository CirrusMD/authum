import abc
import dataclasses
import datetime
import itertools
import logging
import os
import subprocess
import time
from typing import ClassVar, Union
import webbrowser

import arn.iam
import boto3

import authum
import authum.http
import authum.persistence
import authum.plugin
import authum.util


logging.getLogger("botocore").propagate = False
log = logging.getLogger(__name__)


class AWSData(authum.persistence.KeyringItem):
    """Represents persistent AWS data"""

    def __init__(self) -> None:
        super().__init__("aws")

    def set_credentials(self, name: str, v: "AWSRoleCredentials") -> None:
        """Save credentials"""
        self.setdefault("credentials", {})[name] = dataclasses.asdict(v)
        self.save()

    def credentials(
        self, name: str
    ) -> Union["AWSSSORoleCredentials", "AWSSAMLRoleCredentials"]:
        """Return credentials by name"""
        args = self["credentials"][name]
        if "start_url" in args:
            return AWSSSORoleCredentials(**args)
        else:
            return AWSSAMLRoleCredentials(**args)

    def mv_credentials(self, current_name: str, new_name: str) -> None:
        """Rename credentials"""
        self.set_credentials(new_name, self.credentials(current_name))
        self.rm_credentials(current_name)

    def rm_credentials(self, name: str) -> None:
        """Delete a credentials by name"""
        del self.get("credentials", {})[name]
        self.save()

    @property
    def list_credentials(self) -> dict:
        """Return all role credentials as a dict"""
        return {
            name: self.credentials(name) for name in self.get("credentials", {}).keys()
        }


@dataclasses.dataclass
class CacheableAWSObject(abc.ABC):
    """Represents a cacheable AWS object"""

    cache: ClassVar[AWSData] = AWSData()
    expiration_timestamp: float = 0

    @abc.abstractmethod
    def load(self):
        """Load data from cache"""
        pass

    @abc.abstractmethod
    def renew(self):
        """Renew and save data to cache"""
        pass

    @property
    def ttl(self) -> datetime.timedelta:
        """Computes time to live"""
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            expiration = datetime.datetime.fromtimestamp(
                float(self.expiration_timestamp), tz=datetime.timezone.utc
            )
        except ValueError:
            expiration = now

        return expiration - now

    @property
    def is_expired(self) -> bool:
        """Checks whether the object is expired"""
        return self.ttl < datetime.timedelta()

    @property
    def ttl_str(self) -> str:
        """Fix for normalization of negative values for ttl.

        See: https://docs.python.org/3/library/datetime.html#timedelta-objects"""
        ttl = str(abs(self.ttl))
        if self.is_expired:
            ttl = f"-{ttl}"
        return ttl

    def load_cached_fields(
        self,
        cache: dict,
        fields: list = [],
    ) -> None:
        """Load list of fields from the cache"""
        if not fields:
            fields = [f.name for f in dataclasses.fields(self)]

        for field in fields:
            local_val = getattr(self, field)
            if not local_val:
                setattr(self, field, cache.get(field, local_val))

    def require_fields(self, *fields: str) -> None:
        """Check for required fields"""
        missing_fields = [field for field in fields if not getattr(self, field)]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")


@dataclasses.dataclass
class AWSSSORegistration(CacheableAWSObject):
    """Represents an AWS SSO client registration"""

    client_id: str = ""
    client_secret: str = ""

    def load(self):
        """Load attributes from the cache"""
        sso_registration = self.cache.get("sso", {}).get("registration", {})
        self.load_cached_fields(cache=sso_registration)

    def renew(self, force: bool = False):
        """Renew attributes from AWS"""
        self.load()
        if not force and not self.is_expired:
            return

        log.debug(f"Renewing SSO client registration")
        sso_oidc = boto3.client("sso-oidc")
        response = sso_oidc.register_client(
            clientName=authum.metadata["Name"], clientType="public"
        )
        log.debug(f"AWS response: {response}")

        self.client_id = response["clientId"]
        self.client_secret = response["clientSecret"]
        self.expiration_timestamp = float(response["clientSecretExpiresAt"])

        self.cache.setdefault("sso", {})["registration"] = dataclasses.asdict(self)
        self.cache.save()


@dataclasses.dataclass
class AWSSSOAuthorization(CacheableAWSObject):
    """Represents an AWS SSO client authorization"""

    start_url: str = ""
    access_token: str = ""

    def __post_init__(self):
        self.require_fields("start_url")

    def load(self):
        """Load attributes from the cache"""
        sso_authorization = (
            self.cache.get("sso", {}).get("authorization", {}).get(self.start_url, {})
        )
        self.load_cached_fields(cache=sso_authorization)

    def renew(
        self,
        registration: AWSSSORegistration,
        force: bool = False,
    ):
        """Renew attributes from AWS"""
        self.load()
        if not force and not self.is_expired:
            return

        log.debug(f"Renewing SSO client authorization for: {self.start_url}")
        sso_oidc = boto3.client("sso-oidc")
        authorization = sso_oidc.start_device_authorization(
            clientId=registration.client_id,
            clientSecret=registration.client_secret,
            startUrl=self.start_url,
        )
        log.debug(f"AWS response: {authorization}")

        webbrowser.open(authorization["verificationUriComplete"])

        response = {}
        interval = authorization["interval"]
        for i in itertools.count(1):
            try:
                log.debug(f"Requesting SSO client token (try: {i})")
                response = sso_oidc.create_token(
                    clientId=registration.client_id,
                    clientSecret=registration.client_secret,
                    grantType="urn:ietf:params:oauth:grant-type:device_code",
                    deviceCode=authorization["deviceCode"],
                )
                log.debug(f"AWS response: {response}")
                break
            except sso_oidc.exceptions.AuthorizationPendingException:
                pass
            except sso_oidc.exceptions.SlowDownException:
                interval += 5
                pass
            time.sleep(interval)

        self.access_token = response["accessToken"]
        self.expiration_timestamp = datetime.datetime.timestamp(
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=response["expiresIn"])
        )

        self.cache.setdefault("sso", {}).setdefault("authorization", {})[
            self.start_url
        ] = dataclasses.asdict(self)
        self.cache.save()


class AWSSSOClient:
    """Represents an AWS SSO client"""

    def __init__(
        self,
        start_url: str,
        force_renew_registration: bool = False,
        force_renew_authorization: bool = False,
    ) -> None:
        self.registration = AWSSSORegistration()
        self.registration.renew(force=force_renew_registration)
        self.authorization = AWSSSOAuthorization(start_url=start_url)
        with authum.util.rich_stderr.status("Waiting for device authorization"):
            self.authorization.renew(
                registration=self.registration,
                force=force_renew_authorization,
            )

    def list_accounts(self) -> list:
        """Returns a list of available accounts and roles"""
        account_list = []

        sso = boto3.client("sso")
        accounts = sso.list_accounts(accessToken=self.authorization.access_token)
        for account in accounts["accountList"]:
            roles = sso.list_account_roles(
                accessToken=self.authorization.access_token,
                accountId=account["accountId"],
            )
            account_list.append(
                {**account, "roles": [r["roleName"] for r in roles["roleList"]]}
            )

        return account_list


@dataclasses.dataclass
class AWSRoleCredentials(CacheableAWSObject):
    """Base class for AWS role credentials"""

    name: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""
    session_token: str = ""

    assume_role_arn: str = ""
    assume_role_external_id: str = ""
    sts_endpoint: str = ""

    def __post_init__(self):
        self.require_fields("name")

    def load(self):
        """Load attributes from the cache"""
        cached_args = self.cache.get("credentials", {}).get(self.name, {})
        self.load_cached_fields(cache=cached_args)

    @property
    def env_vars(self) -> dict:
        """Return a list of credential environment variables"""
        return {
            "AWS_ACCESS_KEY_ID": self.access_key_id,
            "AWS_SECRET_ACCESS_KEY": self.secret_access_key,
            "AWS_SESSION_TOKEN": self.session_token,
        }

    @property
    def env_vars_export(self) -> str:
        """Returns a list of credential environment variables suitable for
        eval'ing in a shell"""
        return "\n".join(f"export {k}='{v}'" for k, v in self.env_vars.items())

    def exec(self, command: tuple, capture_output=False) -> subprocess.CompletedProcess:
        """Runs a shell command with AWS_* environment variables set"""
        if len(command) == 0:
            return subprocess.CompletedProcess(command, 0)
        return subprocess.run(
            args=command,
            env={**dict(os.environ), **self.env_vars},
            capture_output=capture_output,
            text=True,
        )

    def assume_role(self):
        """Assumes a role"""
        sts = boto3.client(
            "sts",
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            aws_session_token=self.session_token,
            endpoint_url=self.sts_endpoint if self.sts_endpoint else None,
        )

        log.debug(f"Requesting STS caller identity")
        response = sts.get_caller_identity()
        log.debug(f"AWS response: {response}")

        assume_role_args = {
            "RoleArn": self.assume_role_arn,
            "RoleSessionName": arn.iam.AssumedRoleArn(
                response["Arn"]
            ).role_session_name,
        }
        if self.assume_role_external_id:
            assume_role_args["ExternalId"] = self.assume_role_external_id

        log.debug(f"Assuming role: {self.assume_role_arn}")
        response = sts.assume_role(**assume_role_args)
        log.debug(f"AWS response: {response}")

        self.access_key_id = response["Credentials"]["AccessKeyId"]
        self.secret_access_key = response["Credentials"]["SecretAccessKey"]
        self.session_token = response["Credentials"]["SessionToken"]
        self.expiration_timestamp = response["Credentials"]["Expiration"].timestamp()


@dataclasses.dataclass
class AWSSSORoleCredentials(AWSRoleCredentials):
    """Represents AWS SSO role credentials"""

    start_url: str = ""
    account_id: str = ""
    role_name: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.require_fields("start_url", "account_id", "role_name")

    def renew(
        self,
        force: bool = False,
    ):
        """Renew attributes from AWS"""
        self.load()
        if not force and not self.is_expired:
            return

        client = AWSSSOClient(start_url=self.start_url)
        log.debug(
            f"Renewing SSO role credentials for: start_url={self.start_url}, account_id={self.account_id}, role_name={self.role_name}"
        )
        sso = boto3.client("sso")
        response = sso.get_role_credentials(
            accessToken=client.authorization.access_token,
            accountId=self.account_id,
            roleName=self.role_name,
        )
        log.debug(f"AWS response: {response}")

        self.access_key_id = response["roleCredentials"]["accessKeyId"]
        self.secret_access_key = response["roleCredentials"]["secretAccessKey"]
        self.session_token = response["roleCredentials"]["sessionToken"]
        self.expiration_timestamp = response["roleCredentials"]["expiration"] / 1000.0

        if self.assume_role_arn:
            self.assume_role()

        self.cache.setdefault("credentials", {})[self.name] = dataclasses.asdict(self)
        self.cache.save()


@dataclasses.dataclass
class AWSSAMLRoleCredentials(AWSRoleCredentials):
    """Represents AWS SAML role credentials"""

    saml_url: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.require_fields("saml_url")

    def renew(
        self,
        force: bool = False,
    ):
        """Renew attributes from AWS"""
        self.load()
        if not force and not self.is_expired:
            return

        assertion = authum.plugin.manager.hook.saml_request(url=self.saml_url)  # type: ignore
        if not assertion:
            raise AWSPluginError(
                f"No plugins responded for SAML application URL: {self.saml_url}"
            )

        assume_role_args = {"SAMLAssertion": assertion.b64encoded}

        try:
            role = assertion.attrs["https://aws.amazon.com/SAML/Attributes/Role"][0]
            assume_role_args["RoleArn"], assume_role_args["PrincipalArn"] = role.split(
                ","
            )
        except IndexError:
            raise AWSPluginError(f"No role ARN found in SAML assertion")

        try:
            assume_role_args["DurationSeconds"] = int(
                assertion.attrs[
                    "https://aws.amazon.com/SAML/Attributes/SessionDuration"
                ][0]
            )
        except IndexError:
            pass

        log.debug(f"Renewing SAML role credentials for: {self.saml_url}")
        sts = boto3.client(
            "sts", endpoint_url=self.sts_endpoint if self.sts_endpoint else None
        )
        response = sts.assume_role_with_saml(**assume_role_args)
        log.debug(f"AWS response: {response}")

        self.access_key_id = response["Credentials"]["AccessKeyId"]
        self.secret_access_key = response["Credentials"]["SecretAccessKey"]
        self.session_token = response["Credentials"]["SessionToken"]
        self.expiration_timestamp = response["Credentials"]["Expiration"].timestamp()

        if self.assume_role_arn:
            self.assume_role()

        self.cache.setdefault("credentials", {})[self.name] = dataclasses.asdict(self)
        self.cache.save()


class AWSPluginError(Exception):
    """Represents AWS plugin errors"""


def normalize_start_url(
    subdomain_or_url: str,
    scheme: str = "https://",
    domain: str = "awsapps.com",
    path: str = "/start#/",
) -> str:
    """Construct an AWS SSO start URL from a subdomain"""
    if authum.util.is_url(subdomain_or_url):
        return subdomain_or_url
    else:
        return f"{scheme}{subdomain_or_url}.{domain}{path}"
