# CHANGELOG

## Unreleased

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
