# AWS Plugin

This plugin manages temporary [IAM](https://docs.aws.amazon.com/iam/)
credentials for [Amazon Web Services](https://aws.amazon.com/). See: `athm aws
--help`.

## Getting Started

If you had been storing persistent AWS credentials under `~/.aws`, here are some
tips for moving to SSO authentication and Authum:

- Since you won't be using those persistent credentials anymore, you can delete
  the `credentials` file.
- If you had been setting `AWS_DEFAULT_PROFILE` in your login scripts, you can
  stop doing that.
- If nothing else is using the persistent AWS credentials previously stored
  under `~/.aws`, you should disable or delete those keys via the [IAM
  Console](https://console.aws.amazon.com/iam/home#/users). From that page you
  can search for the access key itself, or browse/search by username.

### Using AWS IAM Identity Center (SSO)

1. Obtain the appropriate "start URL(s)" from your AWS administrator. These will
   generally have a format like: `https://<subdomain>.awsapps.com/start#/`

1. Get a list of available roles:

    ```sh
    athm aws ls-sso-roles <start url or subdomain>
    ```

1. Create AWS credentials for the desired role:

    ```sh
    athm aws add-sso example -u <start url or subdomain> -a <account id> -r <role name>
    ```

1. Run commands that require AWS credentials:

    ```sh
    athm aws exec example -- aws sts get-caller-identity
    ```

### Using IAM and SAML Applications

1. Configure the appropriate identity provider plugin(s).

1. Get a list of SSO apps from your identity provider(s):

   ```sh
   athm apps
   ```

1. Create AWS credentials using the desired SSO app URL:

    ```sh
    athm aws add-saml example -u https://sso.example.com/saml/example
    ```

1. Run commands that require AWS credentials:

    ```sh
    athm aws exec example -- aws sts get-caller-identity
    ```

## Advanced Features

### Credential Rotation

Credentials will normally be rotated for you automatically in the background,
but you can also force rotation any time by using the `--rotate` option:

```sh
athm aws exec example --rotate -- <command>
```

### Exporting AWS Credentials to your Environment

It can be a hassle to put `athm aws exec <name>` before every AWS-related
command that you run. The `athm aws export` command displays the `export`
commands that will load your temporary AWS credentials directly into your shell.
This will let you run AWS commands directly from the shell (though it won't
recognize when your temporary credentials have expired). You can put a command
like this into your `.bash_profile` to load the AWS into every shell:

```sh
eval "$(athm aws export example)"
```

### Assuming Roles Automatically

You may find that you need to interact with AWS using a different IAM role than
the one connected to your identity provider. Different roles can be assumed
automatically by adding the `--assume-role-arn` parameter to the `athm aws
add-*` command:

```sh
athm aws add-saml example -u https://sso.example.com/saml/example --assume-role-arn=arn:aws:iam::123456789012:role/ExampleRole
```

The AWS IAM User Guide contains [more information about assuming IAM
roles](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use.html).

### FIPS Endpoints

If your environment requires use of
[FIPS](https://aws.amazon.com/compliance/fips/), you can use the
`--endpoint-url` option to specify an alternative endpoint for the AWS Security
Token Service (STS):

```sh
athm aws add-saml example -u https://sso.example.com/saml/example --endpoint-url https://sts-fips.us-east-1.amazonaws.com
```
