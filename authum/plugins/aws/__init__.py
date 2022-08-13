import arn.iam
import click
import os
import rich.console
import rich.table
import sys

import authum.alias
import authum.plugin
import authum.plugins.aws.lib


rich_stdout = rich.console.Console(soft_wrap=True)
rich_stderr = rich.console.Console(stderr=True)


def create_session(
    session_name: str,
    alias_or_url: str,
    role_arn: str = "",
    external_id: str = "",
    endpoint_url: str = "",
):
    """Creates an AWS session"""
    try:
        sso_url = authum.alias.aliases.resolve(alias_or_url)
    except authum.alias.AliasError as e:
        raise click.ClickException(str(e))

    try:
        session = authum.plugins.aws.lib.assume_role_with_saml(sso_url, endpoint_url)
    except authum.plugins.aws.lib.AWSPluginError as e:
        raise click.ClickException(str(e))

    if role_arn or external_id:
        session = authum.plugins.aws.lib.assume_role_with_session(
            session=session, role_arn=role_arn, external_id=external_id
        )

    authum.plugins.aws.lib.aws_data.set_session(session_name or alias_or_url, session)

    return session


def get_session(name: str, force_rotate: bool = False):
    """Returns an AWS session"""
    aws_data = authum.plugins.aws.lib.aws_data
    try:
        session = aws_data.session(name)
    except authum.plugins.aws.lib.AWSPluginError as e:
        raise click.ClickException(str(e))

    if force_rotate or session.is_expired:
        return create_session(
            name,
            session.sso_url,
            role_arn=session.role_arn,
            external_id=session.external_id,
            endpoint_url=session.endpoint_url,
        )

    return session


@authum.plugin.hookimpl
def extend_cli(click_group):
    @click_group.group()
    def aws():
        """Work with AWS"""
        pass

    @aws.command()
    @click.pass_context
    @click.option("-n", "--session-name", help="Session name")
    @click.option("-r", "--role-arn", help="ARN of secondary role to assume")
    @click.option("-i", "--external-id", help="External id for secondary role")
    @click.option("-e", "--endpoint-url", help="Endpoint URL for API calls")
    @click.argument("alias_or_url")
    def add(
        ctx: click.Context,
        session_name: str,
        role_arn: str,
        external_id: str,
        endpoint_url: str,
        alias_or_url: str,
    ):
        """Add an assume-role session"""
        create_session(
            session_name,
            alias_or_url,
            role_arn=role_arn,
            external_id=external_id,
            endpoint_url=endpoint_url,
        )
        ctx.invoke(ls)

    @aws.command(context_settings=dict(ignore_unknown_options=True))
    @click.option("-r", "--rotate", is_flag=True, help="Force credential rotation")
    @click.argument("session_name")
    @click.argument("command", nargs=-1, type=click.UNPROCESSED)
    def exec(rotate: bool, session_name: str, command: tuple):
        """Run a shell command in the context of an assume-role session"""
        session = get_session(session_name, force_rotate=rotate)
        executable = os.path.basename(sys.argv[0])
        try:
            exit(session.exec(command).returncode)
        except PermissionError:
            rich_stderr.print(f"{executable}: permission denied: {command[0]}")
            exit(126)
        except FileNotFoundError:
            rich_stderr.print(f"{executable}: command not found: {command[0]}")
            exit(127)

    @aws.command()
    @click.option("-r", "--rotate", is_flag=True, help="Force credential rotation")
    @click.argument("session_name")
    def export(rotate: bool, session_name: str):
        """Export AWS_* environment variables from an assume-role session"""
        session = get_session(session_name, force_rotate=rotate)
        rich_stdout.print(session.env_vars_export)

    @aws.command()
    def ls():
        """List assume-role sessions"""
        aws_data = authum.plugins.aws.lib.aws_data
        if not aws_data.sessions:
            rich_stderr.print("No sessions")
            return

        aliases = authum.alias.aliases

        table = rich.table.Table()
        table.add_column("Session")
        table.add_column("App")
        table.add_column("Account")
        table.add_column("Assumed Role")
        table.add_column("Endpoint URL")
        table.add_column("TTL")
        for session_name, session in sorted(aws_data.sessions.items()):
            assumed_role_arn = arn.iam.AssumedRoleArn(session.arn)
            session_color = "red" if session.is_expired else "green"
            table.add_row(
                session_name,
                ", ".join(aliases.aliases_for(session.sso_url)),
                assumed_role_arn.account,
                f"{assumed_role_arn.role_name} ({assumed_role_arn.role_session_name})",
                session.endpoint_url,
                f"[{session_color}]{session.pretty_ttl}[/{session_color}]",
            )
        rich_stderr.print(table)

    @aws.command()
    @click.pass_context
    @click.argument("current_name")
    @click.argument("new_name")
    def mv(ctx: click.Context, current_name: str, new_name: str):
        """Rename an assume-role session"""
        aws_data = authum.plugins.aws.lib.aws_data
        try:
            aws_data.mv_session(current_name, new_name)
        except authum.plugins.aws.lib.AWSPluginError as e:
            raise click.ClickException(str(e))
        ctx.invoke(ls)

    @aws.command()
    @click.pass_context
    @click.option("--all", "-a", is_flag=True, help="Remove all sessions")
    @click.argument("session_name", required=False)
    def rm(ctx: click.Context, all: bool, session_name: str):
        """Remove assume-role sessions"""
        aws_data = authum.plugins.aws.lib.aws_data
        if all:
            aws_data.delete()
        elif session_name:
            try:
                aws_data.rm_session(session_name)
            except authum.plugins.aws.lib.AWSPluginError as e:
                raise click.ClickException(str(e))
        ctx.invoke(ls)
