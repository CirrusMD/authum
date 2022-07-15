# AWS Plugin

This plugin manages temporary [IAM](https://docs.aws.amazon.com/iam/)
credentials for [Amazon Web Services](https://aws.amazon.com/). See: `athm aws
--help`.

## Getting Started

1. Create an AWS assume-role session:

    ```sh
    athm aws add example
    ```

2. Run commands that require AWS credentials:

    ```sh
    athm aws exec example aws ec2 describe-instances
    ```

## Features

### Credential Rotation

Credentials will normally be rotated for you automatically in the background,
but you can also force rotation any time using the `--rotate` option:

```sh
athm aws exec example --rotate
```

### Exporting AWS Credentials to your Environment

It can be a hassle to put `athm aws exec <alias>` before every AWS-related
command that you run. The `athm aws export` command displays the `export`
commands that will load your temporary AWS credentials directly into your shell.
This will let you run AWS commands directly from the shell, although it won't
recognize when your temporary credentials have expired. You can put a command
like this into your `.bash_profile` to load the AWS into every shell:

```sh
eval "$(athm aws export example)"
```

### Adding a Profile with an Assumed Role

You may find that you need to interact with AWS using a different IAM role than
the one connected to your identity provider. For example, your identity provider
integration may only grant read-only access to resources in the AWS Console, and
you need to assume an expanded role in order to make changes. Or, if your
company has more than one AWS account, you may login to a single AWS account,
and then assume a role in another account to access the resources in that
account.

AWS profiles can be configured to automatically assume another IAM role when you
establish a session. Each time you establish a new AWS session using such a
profiles, this plugin will immediately call the [AssumeRole
API](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html) to
request credentials for the other role. The role can be in your own AWS account
or in another AWS account.

To configure a profile to assume a role on each login, add the `--role-arn`
parameter to the `athm aws add` command:

```sh
athm aws add --role-arn=arn:aws:iam::12345:role/other-role example

```

The AWS IAM User Guide contains [more information about assuming IAM
roles](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use.html).

### FIPS Endpoints

If your environment requires use of
[FIPS](https://aws.amazon.com/compliance/fips/), you can use the
`--endpoint-url` option to specify an alternative endpoint for the AWS Security
Token Service (STS):

```sh
athm aws add example --endpoint-url https://sts-fips.us-east-1.amazonaws.com

```
