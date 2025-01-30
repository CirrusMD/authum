ci: lint test

lint:
	uv run ruff check

test:
	uv run pytest --cov=authum --cov-report=term-missing

tdd:
	uv run pytest -f --color=yes -o log_cli=1 --capture=tee-sys --log-level=DEBUG

# FIXME: run `dist/athm --version` at the end of CI to make sure it works.
# Need to get keyring working on headless Ubuntu first.
# See: https://pypi.org/project/keyring/
pex:
	$(eval REQUIREMENTS=${TMPDIR}requirements.txt)
	uv export --no-hashes --no-emit-project > ${REQUIREMENTS}
	uv run pex -r ${REQUIREMENTS} -e authum.cli:main -o dist/athm .

release:
	$(eval VERSION=`uvx --from=toml-cli toml get --toml-path=pyproject.toml project.version`)
	git tag -a v${VERSION} -m "Release version ${VERSION}"
	git push --tags
