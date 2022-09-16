# Okta Plugin

This plugin handles authentication with [Okta](https://www.okta.com/) for SAML
applications. See: `athm okta --help`.

## Features

- Supports the following [multi-factor authentication
  methods](https://developer.okta.com/docs/reference/api/factors/#factor-type):
  - `call`
  - `email`
  - `push`
  - `question`
  - `sms`
  - `token`
  - `token:hardware`
  - `token:hotp`
  - `token:software:totp`
  - `web`

## Getting Started

1. Add your Okta credentials:

    ```sh
    athm okta -d example.okta.com -u example@example.com -p
    ```

2. Now the plugin will make SAML requests to SSO URLs with the domain you
   specified.
