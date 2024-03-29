# CHANGELOG

### 1.1.0 - 2022-10-18

- [aws] Added `authorize_sso` command to force SSO client
  registration/authorization.

## 1.0.0 - 2022-09-27

- Aliases and associated commands have been removed, so it's OK to delete the
  authum alias item from your keychain (e.g. `keyring del authum alias`)
- [aws] AWS IAM Identity Center (SSO) is now supported. Note that the internal
  representation of credentials has changed, so you should re-add all your
  credentials to avoid errors (i.e. `athm aws rm -a`, `athm aws add-* ...`).
- [aws] The `add` command has been replaced by the `add-saml` and `add-sso`
  commands.
- [aws] Added the `ls-sso-roles` command to list available roles from AWS IAM
  Identity Center.

## 0.4.1 - 2022-08-12

- Bump constraint on python to >=3.8,<3.12 (upper constraint is required by pex)
- Update dependencies
- [aws] Improve `exec` error messages
- [jumpcloud,okta] Verify SSO URLs before making SAML requests
- [jumpcloud,okta] Verify that plugin is configured before making SAML requests

## 0.4.0 - 2022-08-02

- [aws] Add the ability to rename sessions

## 0.3.0 - 2022-07-20

- [aws] Assume-role sessions now have a many-to-one relationship with apps. The
  session name defaults to the name of the app, but it can be overridden with
  the `-n/--session-name` option. Note that the internal representation of
  sessions has changed, so you should recreate all your sessions to avoid errors
  (i.e. `athm aws rm -a`, `athm aws add ...`).
- Miscellaneous bugfixes

## 0.2.0 - 2022-07-14

- Added graphical MFA prompts
- [aws] Handle exception when no args are supplied to exec
- [aws] Set `soft_wrap=True` to prevent newlines in exported keys

## 0.1.0 - 2022-06-14

Initial release
