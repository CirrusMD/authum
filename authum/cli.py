import functools
import logging

import click
import rich.console
import rich.logging
import rich.table

import authum.alias
import authum.plugin


rich_stdout = rich.console.Console()
rich_stderr = rich.console.Console(stderr=True)

authum.plugin.load_plugins()
plugin_list = "\n".join(
    f"- {p.__name__.split('.')[-1]} ({p.__name__})"
    for p in authum.plugin.manager.get_plugins()
)


@click.group()
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode (WARNING: logs may include sensitive data)",
)
@click.version_option(
    prog_name="athm", message=f"%(prog)s %(version)s\n\nPlugins:\n{plugin_list}"
)
def main(debug: bool) -> None:
    handler_opts = {
        "console": rich.console.Console(stderr=True),
        "show_level": False,
        "show_path": False,
        "show_time": False,
    }
    if debug:
        handler_opts.update({"show_level": True, "show_time": True})
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="[%(name)s] %(message)s",
        datefmt="[%X]",
        handlers=[rich.logging.RichHandler(**handler_opts)],
    )


@main.command()
def apps() -> None:
    """List apps"""
    apps = functools.reduce(list.__add__, authum.plugin.manager.hook.get_apps())  # type: ignore
    if not apps:
        rich_stderr.print(
            "No apps found. Do you have at least one identity provider configured?"
        )
        return

    aliases = authum.alias.aliases

    table = rich.table.Table()
    table.add_column("Name")
    table.add_column("URL")
    table.add_column("Alias")
    for a in sorted(apps):
        aliases_for = ", ".join(aliases.aliases_for(a.url))
        table.add_row(a.name, a.url, aliases_for)
    rich_stderr.print(table)


@main.group()
def alias() -> None:
    """Manage URL aliases"""
    pass


@alias.command()
@click.pass_context
@click.argument("name")
@click.argument("url")
def add(ctx: click.Context, name: str, url: str) -> None:
    """Add an alias"""
    aliases = authum.alias.aliases
    aliases.add(name, url)
    ctx.invoke(ls)


@alias.command()
def ls():
    """List aliases"""
    aliases = authum.alias.aliases
    if not aliases:
        rich_stderr.print("No aliases")
        return

    table = rich.table.Table()
    table.add_column("Name")
    table.add_column("URL")
    for name, url in sorted(aliases.items()):
        table.add_row(name, url)
    rich_stderr.print(table)


@alias.command()
@click.pass_context
@click.argument("cur")
@click.argument("new")
def mv(ctx: click.Context, cur: str, new: str) -> None:
    """Rename an alias"""
    aliases = authum.alias.aliases
    try:
        aliases.mv(cur, new)
        ctx.invoke(ls)
    except authum.alias.AliasError as e:
        raise click.ClickException(str(e))


@alias.command()
@click.pass_context
@click.option("--all", "-a", is_flag=True, help="Remove all aliases")
@click.argument("name", required=False)
def rm(ctx: click.Context, all: bool, name: str) -> None:
    """Remove aliases"""
    aliases = authum.alias.aliases
    if all:
        aliases.delete()
    elif name:
        try:
            aliases.rm(name)
        except authum.alias.AliasError as e:
            raise click.ClickException(str(e))
    ctx.invoke(ls)


authum.plugin.manager.hook.extend_cli(click_group=main)  # type: ignore
