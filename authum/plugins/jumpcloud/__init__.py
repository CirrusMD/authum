from typing import Type

import click
import rich.table

import authum.gui
import authum.http
import authum.persistence
import authum.plugin
import authum.plugins.jumpcloud.lib
import authum.util


def prompt_mfa(factors: list, gui: bool = authum.gui.PROMPT_GUI) -> dict:
    """Prompts for multi-factor authentication"""
    factors = [f for f in factors if f["status"] == "available"]
    if len(factors) == 1:
        return factors[0]

    prompt = "JumpCloud MFA choice"
    if gui:
        choice = authum.gui.choose(prompt, choices=[f["type"] for f in factors])
    else:
        table = rich.table.Table()
        table.add_column()
        table.add_column("Type")
        for i, f in enumerate(factors):
            table.add_row(str(i), f["type"])
        authum.util.rich_stderr.print(table)
        choice = click.prompt(prompt, type=click.IntRange(min=0, max=len(factors)))

    return factors[choice]


def prompt_factor_args(factor_type: str, gui: bool = authum.gui.PROMPT_GUI) -> dict:
    """Prompts for multi-factor authentication arguments"""
    if factor_type == "totp":
        prompt = "JumpCloud verification code"
        otp = authum.gui.prompt(prompt) if gui else click.prompt(prompt)
        return {"otp": otp}
    elif factor_type == "duo":
        return {}
    else:
        raise click.ClickException(
            f"Unknown or unimplemented JumpCloud factor type: {factor_type}"
        )


def get_jumpcloud_client(fail_unconfigured: bool = True) -> Type:
    """Returns a JumpCloud client"""
    jumpcloud_data = authum.plugins.jumpcloud.lib.jumpcloud_data
    if not jumpcloud_data.email or not jumpcloud_data.password:
        if fail_unconfigured:
            raise click.ClickException("JumpCloud plugin is not configured")
        else:
            return

    client = authum.plugins.jumpcloud.lib.JumpCloudClient(
        email=jumpcloud_data.email,
        password=jumpcloud_data.password,
        session=jumpcloud_data.session,
    )

    try:
        client.auth(lazy=True)

    except authum.plugins.jumpcloud.lib.JumpCloudError as e:
        raise click.ClickException(str(e))

    except authum.plugins.jumpcloud.lib.JumpCloudMFARequired as e:
        factor = prompt_mfa(e.response["factors"])
        factor_args = prompt_factor_args(factor["type"])
        with authum.util.rich_stderr.status("Waiting for MFA verification..."):
            getattr(e.client, f"auth_{factor['type']}")(**factor_args)

    jumpcloud_data.session = client.session

    return client


@authum.plugin.hookimpl
def extend_cli(click_group):
    jumpcloud_data = authum.plugins.jumpcloud.lib.jumpcloud_data

    @click_group.command()
    @click.option(
        "--email",
        "-e",
        default=jumpcloud_data.email,
        help="Set JumpCloud email",
        show_default=True,
    )
    @click.option("--password", "-p", is_flag=True, help="Set JumpCloud password")
    @click.option("--rm-session", is_flag=True, help="Delete JumpCloud session data")
    @click.option("--rm", is_flag=True, help="Delete all JumpCloud data")
    def jumpcloud(email: str, password: str, rm_session: bool, rm: bool) -> None:
        """Manage JumpCloud data"""
        if rm:
            jumpcloud_data.delete()
        else:
            if email:
                jumpcloud_data.email = email
            if password:
                jumpcloud_data.password = click.prompt(
                    f"JumpCloud password", hide_input=True
                )
            if rm_session:
                jumpcloud_data.session = {}

        authum.util.rich_stderr.print(
            jumpcloud_data.asyaml(masked_keys=["password", "session"])
        )


@authum.plugin.hookimpl
def get_apps():
    client = get_jumpcloud_client(fail_unconfigured=False)
    if not client:
        return []

    return [
        authum.http.SAMLApplication(name=app["displayLabel"], url=app["ssoUrl"])
        for app in client.applications()
    ]


@authum.plugin.hookimpl
def saml_request(url):
    if authum.util.url_has_domain(
        url, authum.plugins.jumpcloud.lib.JUMPCLOUD_SSO_DOMAIN
    ):
        client = get_jumpcloud_client()
        try:
            return client.saml_request(url=url)
        except authum.plugins.jumpcloud.lib.JumpCloudError as e:
            raise click.ClickException(str(e))
