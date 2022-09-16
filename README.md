# Authum

![Authum](assets/authum.jpg) [![Continuous
integration](https://github.com/CirrusMD/authum/actions/workflows/ci.yml/badge.svg)](https://github.com/CirrusMD/authum/actions/workflows/ci.yml)

Awesome authentication tool for connecting command line applications to
SAML/OIDC identity and service providers. Authum is the successor to
[aws-jumpcloud](https://github.com/CirrusMD/aws-jumpcloud).

## Features

- Support for **ANY** SAML/OIDC identity and service provider via
  [pluggy](https://pluggy.readthedocs.io) plugins. Built-in plugins include:
  - [aws](authum/plugins/aws/)
  - [jumpcloud](authum/plugins/jumpcloud/)
  - [okta](authum/plugins/okta/)
- Support for [Duo two-factor authentication](https://duo.com/)
- Support for graphical prompts when no TTY is available (e.g. when using
  Authum with GUI apps)
- Securely stores all sensitive data in the native OS keyring

## Installation

1. Install [Poetry](https://python-poetry.org)
1. Clone this repository
1. `cd /path/to/repository`
1. `poetry install`
1. `make pex`
1. `make install`
1. `rehash` to update binaries in `$PATH`

### Graphical Prompts

[tkinter](https://docs.python.org/3/library/tkinter.html) is required for
graphical prompts.

#### Homebrew on macOS

```sh
brew install python-tk
```

## Example Usage: Generate Temporary IAM Credentials via Identity Provider Credentials

See [aws](authum/plugins/aws/) plugin documentation.

## More Help

For help on available commands and options, see the `--help` output:

```sh
athm [command] --help
```

For debugging, use the `--debug` option:

```sh
athm --debug <command>
```

## Development

1. Install [Poetry](https://python-poetry.org)
1. Clone this repository
1. `cd /path/to/repository`
1. `poetry install`
1. `poetry shell`

### Running Tests

Run `pytest`

### Developing Plugins

See [Developing Authum Plugins](authum/plugins/)

### Releasing New Versions

1. Bump the version (e.g. run [poetry version](https://python-poetry.org/docs/cli/#version))
1. Update the [CHANGELOG](./CHANGELOG.md)
1. Run `make release`
