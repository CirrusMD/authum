# Developing Authum Plugins

An Authum plugin is any Python module which:

- Is located in `sys.path`
- Is named `authum-*`
- Provides [implementations](https://pluggy.readthedocs.io/en/stable/index.html#implementations) of one or more of the [pluggy hookspecs](https://pluggy.readthedocs.io/en/stable/index.html#specifications) defined in [authum/plugin.py](/authum/plugin.py).

See the built-in plugins in this directory for examples.

## Guidelines for Terminal I/O

- Use [click](https://click.palletsprojects.com/) for input (parameters, options, prompting, etc.).
- Use [rich](https://rich.readthedocs.io) for output. Only use [sys.stdout](https://docs.python.org/3/library/sys.html#sys.stdout) for output that may be piped to another program or `eval`'ed by a shell. Send everything else to [sys.stderr](https://docs.python.org/3/library/sys.html#sys.stderr).
    - Use [logging](https://docs.python.org/3/library/logging.html) for diagnostics. [rich.logging.RichHandler](https://rich.readthedocs.io/en/stable/reference/logging.html) will be used by default.
    - Use [Console.print()](https://rich.readthedocs.io/en/stable/reference/console.html#rich.console.Console.print) to write to `sys.stdout`. Set `stderr=True` for fancy tables, status bars, etc.
