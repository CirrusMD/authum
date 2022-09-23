import functools
import logging

import click
import rich.logging
import rich.table

import authum
import authum.plugin
import authum.util


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
    prog_name=authum.metadata["Name"],
    message=f"%(prog)s %(version)s\n\nPlugins:\n{plugin_list}",
)
def main(debug: bool) -> None:
    handler_opts = {
        "console": authum.util.rich_stderr,
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
        authum.util.rich_stderr.print(
            "No apps found. Do you have at least one identity provider configured?"
        )
        return

    table = rich.table.Table(**authum.util.rich_table_horizontal_opts)
    table.add_column("Name")
    table.add_column("URL")
    for a in sorted(apps):
        table.add_row(a.name, a.url)
    authum.util.rich_stderr.print(table)


authum.plugin.manager.hook.extend_cli(click_group=main)  # type: ignore
