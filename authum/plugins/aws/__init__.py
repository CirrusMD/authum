import click
import os
import rich.table
import sys

import authum.plugin
import authum.plugins.aws.lib
import authum.util


@authum.plugin.hookimpl
def extend_cli(click_group):
    @click_group.group()
    def aws():
        """Work with AWS"""
        pass

    @aws.command()
    @click.pass_context
    @click.option(
        "-u",
        "--start-url",
        required=True,
        help="AWS Identity Center start URL (or subdomain)",
    )
    @click.option("-a", "--account-id", required=True, help="AWS account ID")
    @click.option("-r", "--role-name", required=True, help="AWS role name")
    @click.option("--assume-role-arn", help="ARN of role to assume")
    @click.option("--assume-role-external-id", help="External id for role to assume")
    @click.option("--sts-endpoint", help="Endpoint URL for STS API calls")
    @click.argument("name")
    def add_sso(
        ctx: click.Context,
        name: str,
        start_url: str,
        account_id: str,
        role_name: str,
        assume_role_arn: str,
        assume_role_external_id: str,
        sts_endpoint: str,
    ):
        """Add SSO credentials"""
        role = authum.plugins.aws.lib.AWSSSORoleCredentials(
            name=name,
            start_url=authum.plugins.aws.lib.normalize_start_url(start_url),
            account_id=account_id,
            role_name=role_name,
            assume_role_arn=assume_role_arn,
            assume_role_external_id=assume_role_external_id,
            sts_endpoint=sts_endpoint,
        )
        role.renew(force=True)
        ctx.invoke(ls)

    @aws.command()
    @click.pass_context
    @click.option("-u", "--saml-url", required=True, help="SAML application URL")
    @click.option("--assume-role-arn", help="ARN of role to assume")
    @click.option("--assume-role-external-id", help="External id for role to assume")
    @click.option("--sts-endpoint", help="Endpoint URL for STS API calls")
    @click.argument("name")
    def add_saml(
        ctx: click.Context,
        name: str,
        saml_url: str,
        assume_role_arn: str,
        assume_role_external_id: str,
        sts_endpoint: str,
    ):
        """Add SAML credentials"""
        role = authum.plugins.aws.lib.AWSSAMLRoleCredentials(
            name=name,
            saml_url=saml_url,
            assume_role_arn=assume_role_arn,
            assume_role_external_id=assume_role_external_id,
            sts_endpoint=sts_endpoint,
        )
        role.renew(force=True)
        ctx.invoke(ls)

    @aws.command()
    @click.argument("start_url_or_subdomain")
    def authorize_sso(start_url_or_subdomain: str):
        """Perform SSO client registration/authorization"""
        authum.plugins.aws.lib.AWSSSOClient(
            start_url=authum.plugins.aws.lib.normalize_start_url(
                start_url_or_subdomain
            ),
            force_renew_registration=True,
            force_renew_authorization=True,
        )

    @aws.command(context_settings=dict(ignore_unknown_options=True))
    @click.option("-r", "--rotate", is_flag=True, help="Force credential rotation")
    @click.argument("name")
    @click.argument("command", nargs=-1, type=click.UNPROCESSED)
    def exec(rotate: bool, name: str, command: tuple):
        """Run a shell command with the selected credentials"""
        aws_data = authum.plugins.aws.lib.AWSData()
        credentials = aws_data.credentials(name)
        credentials.renew(force=rotate)
        executable = os.path.basename(sys.argv[0])
        try:
            exit(credentials.exec(command).returncode)
        except PermissionError:
            authum.util.rich_stderr.print(
                f"{executable}: permission denied: {command[0]}"
            )
            exit(126)
        except FileNotFoundError:
            authum.util.rich_stderr.print(
                f"{executable}: command not found: {command[0]}"
            )
            exit(127)

    @aws.command()
    @click.option("-r", "--rotate", is_flag=True, help="Force credential rotation")
    @click.argument("name")
    def export(rotate: bool, name: str):
        """Export AWS_* environment variables for the selected credentials"""
        aws_data = authum.plugins.aws.lib.AWSData()
        credentials = aws_data.credentials(name)
        credentials.renew(force=rotate)
        authum.util.rich_stdout.print(credentials.env_vars_export)

    @aws.command()
    def ls():
        """List credentials"""
        aws_data = authum.plugins.aws.lib.AWSData()
        if not aws_data.list_credentials:
            authum.util.rich_stderr.print("No credentials")
            return

        for name, credentials in sorted(aws_data.list_credentials.items()):
            table = rich.table.Table(title=name, **authum.util.rich_table_vertical_opts)

            if hasattr(credentials, "start_url"):
                table.add_row("Type", "SSO")
                table.add_row("Start URL", credentials.start_url)
                table.add_row("Account ID", credentials.account_id)
                table.add_row("Role Name", credentials.role_name)

            elif hasattr(credentials, "saml_url"):
                table.add_row("Type", "SAML")
                table.add_row("SAML URL", credentials.saml_url)

            if credentials.assume_role_arn:
                table.add_row("Assume-role ARN", credentials.assume_role_arn)

            if credentials.assume_role_external_id:
                table.add_row(
                    "Assume-role External ID",
                    authum.util.sensitive_value(credentials.assume_role_external_id),
                )

            if credentials.sts_endpoint:
                table.add_row("STS Endpoint", credentials.sts_endpoint)

            color = "red" if credentials.is_expired else "green"
            table.add_row("TTL", f"[{color}]{credentials.ttl_str}[/{color}]")

            authum.util.rich_stderr.print(table)

    @aws.command()
    @click.argument("start_url_or_subdomain")
    def ls_sso_roles(start_url_or_subdomain: str):
        """List available SSO roles"""
        client = authum.plugins.aws.lib.AWSSSOClient(
            start_url=authum.plugins.aws.lib.normalize_start_url(start_url_or_subdomain)
        )
        for account in sorted(
            client.list_accounts(), key=lambda a: (a["accountName"], a["accountId"])
        ):
            table = rich.table.Table(
                title=account["accountName"], **authum.util.rich_table_vertical_opts
            )
            table.add_row("Account Id", account["accountId"])
            table.add_row("Email", account["emailAddress"])
            table.add_row("Roles", ", ".join(account["roles"]))
            authum.util.rich_stderr.print(table)

    @aws.command()
    @click.pass_context
    @click.argument("current_name")
    @click.argument("new_name")
    def mv(ctx: click.Context, current_name: str, new_name: str):
        """Rename credentials"""
        aws_data = authum.plugins.aws.lib.AWSData()
        try:
            aws_data.mv_credentials(current_name, new_name)
        except KeyError:
            raise click.ClickException(f"No such credentials: {current_name}")
        ctx.invoke(ls)

    @aws.command()
    @click.pass_context
    @click.option("--all", "-a", is_flag=True, help="Remove all credentials")
    @click.argument("name", required=False)
    def rm(ctx: click.Context, all: bool, name: str):
        """Remove credentials"""
        aws_data = authum.plugins.aws.lib.AWSData()
        if all:
            aws_data.delete()
        elif name:
            try:
                aws_data.rm_credentials(name)
            except KeyError:
                raise click.ClickException(f"No such credentials: {name}")
        ctx.invoke(ls)
