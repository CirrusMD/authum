# JumpCloud Plugin

This plugin handles authentication with [JumpCloud](https://jumpcloud.com/) for
SAML applications. See: `athm jumpcloud --help`.

## Features

- Supports the following multi-factor authentication methods:
  - Verification Code (TOTP)
  - Duo Security

## Getting Started

1. Add your JumpCloud credentials:

    ```sh
    athm jumpcloud -e example@example.com -p
    ```

2. Now the plugin will make SAML requests to JumpCloud SSO URLs.
