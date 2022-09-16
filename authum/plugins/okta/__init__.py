from typing import Type

import click
import rich.table
import yaml

import authum.gui
import authum.http
import authum.persistence
import authum.plugin
import authum.plugins.okta.lib
import authum.util


def prompt_mfa(factors: dict, gui: bool = authum.gui.PROMPT_GUI) -> dict:
    """Prompts for multi-factor authentication"""
    if len(factors) == 1:
        return factors[0]

    prompt = "Okta MFA choice"
    if gui:
        choice = authum.gui.choose(
            prompt,
            choices=[
                f"{factor['factorType']} ({factor['provider']})" for factor in factors
            ],
        )
    else:
        table = rich.table.Table(**authum.util.rich_table_horizontal_opts)
        table.add_column()
        table.add_column("Type")
        table.add_column("Provider")
        table.add_column("Profile")
        for i, f in enumerate(factors):
            table.add_row(
                str(i), f["factorType"], f["provider"], yaml.dump(f["profile"])
            )
        authum.util.rich_stderr.print(table)
        choice = click.prompt(prompt, type=click.IntRange(min=0, max=len(factors)))

    return factors[choice]


def prompt_factor_args(factor_type: str, gui: bool = authum.gui.PROMPT_GUI) -> dict:
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
        prompt = "Okta passcode"
        pass_code = authum.gui.prompt(prompt) if gui else click.prompt(prompt)
        return {"passCode": pass_code}
    elif factor_type in ["push", "web"]:
        return {}
    elif factor_type == "question":
        prompt = "Okta answer"
        answer = authum.gui.prompt(prompt) if gui else click.prompt(prompt)
        return {"answer": answer}
    else:
        raise click.ClickException(
            f"Unknown or unimplemented Okta factor type: {factor_type}"
        )


def get_okta_client(fail_unconfigured: bool = True) -> Type:
    """Returns an Okta client"""
    okta_data = authum.plugins.okta.lib.OktaData()
    if not okta_data.domain or not okta_data.username or not okta_data.password:
        if fail_unconfigured:
            raise click.ClickException("Okta plugin is not configured")
        else:
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
        with authum.util.rich_stderr.status("Waiting for MFA verification"):
            e.client.verify(e.response, factor["id"], factor_args)

    okta_data.session = client.session

    return client


@authum.plugin.hookimpl
def extend_cli(click_group):
    okta_data = authum.plugins.okta.lib.OktaData()

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
        """Manage Okta configuration"""
        if rm:
            okta_data.delete()
        else:
            if domain:
                okta_data.domain = domain
            if username:
                okta_data.username = username
            if password:
                okta_data.password = click.prompt("Okta password", hide_input=True)
            if rm_session:
                okta_data.session = {}

        table = rich.table.Table(
            title="Okta Configuration", **authum.util.rich_table_vertical_opts
        )
        table.add_row("Domain", okta_data.domain)
        table.add_row("Username", okta_data.username)
        table.add_row("Password", authum.util.sensitive_value(okta_data.password))
        table.add_row("Session", authum.util.sensitive_value(okta_data.session))
        authum.util.rich_stderr.print(table)


@authum.plugin.hookimpl
def list_apps():
    client = get_okta_client(fail_unconfigured=False)
    if not client:
        return []

    return [
        authum.http.SSOApplication(name=app["label"], url=app["linkUrl"])
        for app in client.app_links()
    ]


@authum.plugin.hookimpl
def saml_request(url):
    okta_data = authum.plugins.okta.lib.OktaData()
    if authum.util.url_has_domain(url, okta_data.domain):
        client = get_okta_client()
        try:
            return client.saml_request(url=url)
        except authum.plugins.okta.lib.OktaError as e:
            raise click.ClickException(str(e))
