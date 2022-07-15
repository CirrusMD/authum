# Authum

![Authum](assets/authum.jpg) [![Continuous
integration](https://github.com/CirrusMD/authum/actions/workflows/ci.yml/badge.svg)](https://github.com/CirrusMD/authum/actions/workflows/ci.yml)

Awesome SAML authentication tool for connecting command line applications to
SAML identity and service providers. Authum is the spiritual successor to
[aws-jumpcloud](https://github.com/CirrusMD/aws-jumpcloud).

## Features

- Support for **ALL** SAML identity and service providers via
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

## Example Usage: Assume AWS IAM Roles via Identity Provider Credentials

1. If you had been storing persistent AWS credentials under `~/.aws`, here are
   some tips for moving to SAML authentication and Authum:
    - Since you won't be using those persistent credentials anymore, you can
      delete the `credentials` file.
    - If you had been setting `AWS_DEFAULT_PROFILE` in your login scripts, you
      can stop doing that.
    - If nothing else is using the persistent AWS credentials previously stored
      under `~/.aws`, you should disable or delete those keys via the [IAM
      Console](https://console.aws.amazon.com/iam/home#/users). From that page
      you can search for the access key itself, or browse/search by username.

1. Everything starts with your SAML identity provider(s). You can run `athm
   --help` to see which plugins are available, then configure them
   appropriately:

    ```sh
    athm okta -d example.okta.com -u example@example.com -p
    ```

1. The `apps` command will prompt you for multi-factor authentication
   credentials when necessary and return an aggregated list of applications from
   all configured identity providers:

    ```sh
    athm apps
    ```

1. Add aliases for application URLs listed in the previous step. Note that not
   every application will be useful to Authum, but your identity provider
   administrator should have provided application names that are descriptive
   enough for you to figure out what you need. Alternatively, you can ignore the
   `athm apps` output and simply copy and paste the SSO URL from your identity
   provider's portal page. In this example, we're adding an alias to our AWS SSO
   URL so we have a convenient way to refer to it later:

    ```sh
    athm alias add example http://example.com/
    ```

1. Now we're ready to assume roles in AWS. We do this by creating a session with
   the `aws` plugin, using the alias we created in the previous step. This
   command will use SAML single sign-on to authenticate with AWS and request a
   set of temporary IAM credentials which will be stored in your operating
   system's keychain service:

    ```sh
    athm aws add example
    ```

1. Now you can continue to use the `exec` command, and Authum will automatically
   rotate credentials for you in the background. You'll only be prompted to
   authenticate again as needed:

    ```sh
    athm aws exec example <command>
    ```

## More Help

For help on available commands and options, see the `--help` output:

```sh
athm [command] --help
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
