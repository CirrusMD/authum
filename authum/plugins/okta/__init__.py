from typing import Type

import click
import rich.console
import rich.table
import yaml

import authum.http
import authum.persistence
import authum.plugin
import authum.plugins.okta.lib
import authum.util


rich_stdout = rich.console.Console()
rich_stderr = rich.console.Console(stderr=True)


def prompt_mfa(factors: dict) -> dict:
    """Prompts for multi-factor authentication"""
    if len(factors) == 1:
        return factors[0]

    table = rich.table.Table()
    table.add_column()
    table.add_column("Type")
    table.add_column("Provider")
    table.add_column("Profile")
    for i, f in enumerate(factors):
        table.add_row(str(i), f["factorType"], f["provider"], yaml.dump(f["profile"]))
    rich_stderr.print(table)
    choice = click.prompt(
        "Okta MFA choice", type=click.IntRange(min=0, max=len(factors))
    )

    return factors[choice]


def prompt_factor_args(factor_type: str) -> dict:
    """Prompts for multi-factor authentication arguments"""
    if factor_type in (
        "call",
        "email",
        "sms",
        "token",
        "token:hardware",
        "token:hotp",
        "token:software:totp",
    ):
        return {"passCode": click.prompt("Okta passcode")}
    elif factor_type in ["push", "web"]:
        return {}
    elif factor_type == "question":
        return {"answer": click.prompt("Okta answer")}
    else:
        raise click.ClickException(
            f"Unknown or unimplemented Okta factor type: {factor_type}"
        )


def get_okta_client() -> Type:
    """Returns an Okta client"""
    okta_data = authum.plugins.okta.lib.okta_data
    if not okta_data.domain or not okta_data.username or not okta_data.password:
        return

    client = authum.plugins.okta.lib.OktaClient(
        domain=okta_data.domain,
        username=okta_data.username,
        password=okta_data.password,
        session=okta_data.session,
    )

    try:
        client.authn(lazy=True)

    except authum.plugins.okta.lib.OktaError as e:
        raise click.ClickException(str(e))

    except authum.plugins.okta.lib.OktaMFARequired as e:
        factor = prompt_mfa(e.response["_embedded"]["factors"])
        factor_args = prompt_factor_args(factor["factorType"])
        with rich_stderr.status("Waiting for MFA verification..."):
            e.client.verify(e.response, factor["id"], factor_args)

    okta_data.session = client.session

    return client


@authum.plugin.hookimpl
def extend_cli(click_group):
    okta_data = authum.plugins.okta.lib.okta_data

    @click_group.command()
    @click.option(
        "--domain",
        "-d",
        default=okta_data.domain,
        help="Set Okta domain",
        show_default=True,
    )
    @click.option(
        "--username",
        "-u",
        default=okta_data.username,
        help="Set Okta username",
        show_default=True,
    )
    @click.option("--password", "-p", is_flag=True, help="Set Okta password")
    @click.option("--rm-session", is_flag=True, help="Delete Okta session data")
    @click.option("--rm", is_flag=True, help="Delete all Okta data")
    def okta(
        domain: str, username: str, password: str, rm_session: bool, rm: bool
    ) -> None:
        """Manage Okta data"""
        if rm:
            okta_data.delete()
        else:
            if domain:
                okta_data.domain = domain
            if username:
                okta_data.username = username
            if password:
                okta_data.password = click.prompt(f"Okta password", hide_input=True)
            if rm_session:
                okta_data.session = {}

        rich_stderr.print(okta_data.asyaml(masked_keys=["password", "session"]))


@authum.plugin.hookimpl
def get_apps():
    client = get_okta_client()
    if not client:
        return []

    return [
        authum.http.SAMLApplication(name=app["label"], url=app["linkUrl"])
        for app in client.app_links()
    ]


@authum.plugin.hookimpl
def saml_request(url):
    okta_data = authum.plugins.okta.lib.okta_data
    if authum.util.url_has_domain(url, okta_data.domain):
        client = get_okta_client()
        return client.saml_request(url=url)
