ci: lint test

lint:
	poetry run black --check .

test:
	poetry run pytest --cov=authum --cov-report=term-missing

tdd:
	poetry run pytest -f --color=yes -o log_cli=1 --capture=tee-sys --log-level=DEBUG

# FIXME: run `dist/athm --version` at the end of CI to make sure it works.
# Need to get keyring working on headless Ubuntu first.
# See: https://pypi.org/project/keyring/
pex:
	$(eval REQUIREMENTS=${TMPDIR}requirements.txt)
	poetry export --without-hashes > ${REQUIREMENTS}
	poetry run pex -r ${REQUIREMENTS} -e authum.cli:main -o dist/athm .

install:
	cp dist/athm /usr/local/bin

release:
	$(eval VERSION=`poetry version -s`)
	git tag -a v${VERSION} -m "Release version ${VERSION}"
	git push --tags
