import arn.iam
import click
import rich.console
import rich.table

import authum.alias
import authum.plugin
import authum.plugins.aws.lib


rich_stdout = rich.console.Console()
rich_stderr = rich.console.Console(stderr=True)


def create_session(
    alias_or_url: str, role_arn: str = "", external_id: str = "", endpoint_url: str = ""
):
    """Creates an AWS session"""
    try:
        url = authum.alias.aliases.resolve(alias_or_url)
    except authum.alias.AliasError as e:
        raise click.ClickException(str(e))

    assertion = authum.plugin.manager.hook.saml_request(url=url)  # type: ignore
    if not assertion:
        raise click.ClickException(
            f"All plugins declined to handle SAML application URL: {url}"
        )

    try:
        session = authum.plugins.aws.lib.assume_role_with_saml(
            assertion, endpoint_url=endpoint_url
        )
    except authum.plugins.aws.lib.AWSPluginError as e:
        raise click.ClickException(str(e))

    if role_arn or external_id:
        session = authum.plugins.aws.lib.assume_role_with_session(
            session=session, role_arn=role_arn, external_id=external_id
        )

    authum.plugins.aws.lib.aws_data.set_session(url, session)

    return session


def get_session(alias_or_url: str, force_rotate: bool = False):
    """Returns an AWS session"""
    try:
        url = authum.alias.aliases.resolve(alias_or_url)
    except authum.alias.AliasError as e:
        raise click.ClickException(str(e))

    aws_data = authum.plugins.aws.lib.aws_data
    session = aws_data.session(url)

    if force_rotate or session.is_expired:
        return create_session(
            url,
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
    @click.option("-r", "--role-arn", help="ARN of secondary role to assume")
    @click.option("-i", "--external-id", help="External id for secondary role")
    @click.option("-e", "--endpoint-url", help="Endpoint URL for API calls")
    @click.argument("alias_or_url")
    def add(
        ctx: click.Context,
        role_arn: str,
        external_id: str,
        endpoint_url: str,
        alias_or_url: str,
    ):
        """Add an assume-role session"""
        create_session(
            alias_or_url,
            role_arn=role_arn,
            external_id=external_id,
            endpoint_url=endpoint_url,
        )
        ctx.invoke(ls)

    @aws.command(context_settings=dict(ignore_unknown_options=True))
    @click.option("-r", "--rotate", is_flag=True, help="Force credential rotation")
    @click.argument("alias_or_url")
    @click.argument("command", nargs=-1, type=click.UNPROCESSED)
    def exec(rotate: bool, alias_or_url: str, command: tuple):
        """Run a shell command in the context of an assume-role session"""
        session = get_session(alias_or_url, force_rotate=rotate)
        exit(session.exec(command).returncode)

    @aws.command()
    @click.option("-r", "--rotate", is_flag=True, help="Force credential rotation")
    @click.argument("alias_or_url")
    def export(rotate: bool, alias_or_url: str):
        """Export AWS_* environment variables from an assume-role session"""
        session = get_session(alias_or_url, force_rotate=rotate)
        rich_stdout.print(session.env_vars_export)

    @aws.command()
    def ls():
        """List assume-role sessions"""
        aws_data = authum.plugins.aws.lib.aws_data
        if not aws_data.sessions:
            rich_stderr.print("No sessions")
            return

        aliases = authum.alias.aliases
        sessions = {
            ", ".join(aliases.aliases_for(alias_or_url)) or alias_or_url: session
            for alias_or_url, session in aws_data.sessions.items()
        }

        table = rich.table.Table()
        table.add_column("Name")
        table.add_column("Account")
        table.add_column("Assumed Role")
        table.add_column("Endpoint URL")
        table.add_column("TTL")
        for aliases, session in sorted(sessions.items()):
            assumed_role_arn = arn.iam.AssumedRoleArn(session.arn)
            session_color = "red" if session.is_expired else "green"
            table.add_row(
                aliases,
                assumed_role_arn.account,
                f"{assumed_role_arn.role_name} ({assumed_role_arn.role_session_name})",
                session.endpoint_url,
                f"[{session_color}]{session.pretty_ttl}[/{session_color}]",
            )
        rich_stderr.print(table)

    @aws.command()
    @click.pass_context
    @click.option("--all", "-a", is_flag=True, help="Remove all aliases")
    @click.argument("alias_or_url", required=False)
    def rm(ctx: click.Context, all: bool, alias_or_url: str):
        """Remove assume-role sessions"""
        aws_data = authum.plugins.aws.lib.aws_data
        if all:
            aws_data.delete()
        elif alias_or_url:
            try:
                url = authum.alias.aliases.resolve(alias_or_url)
            except authum.alias.AliasError as e:
                raise click.ClickException(str(e))
            aws_data.rm_session(url)
        ctx.invoke(ls)
