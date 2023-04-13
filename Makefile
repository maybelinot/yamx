TEST = pytest
TEST_DIR = tests/
TEST_RUN = $(TEST) $(TEST_DIR)

.PHONY: default $(MAKECMDGOALS)

help:
	@echo "make check"
	@echo "     run lint and tests"
	@echo "make ci-check"
	@echo "     CI env specfic, run non-test checks (linting)"
	@echo "make help"
	@echo "     see this help"
	@echo "make lint"
	@echo "     run complete pre-commit/pre-push lint"
	@echo "make snyk"
	@echo "     run Snyk check for vulnerabilities"
	@echo "make test"
	@echo "     run tests"
	@echo "make test-with-coverage"
	@echo "     run tests with coverage output to console"
	@echo "make test-with-coverage-html"
	@echo "     run tests with coverage output to html file"



check: lint test

ci-check: lint

lint:
	pre-commit run -a

snyk:
	snyk test --all-projects --policy-path=.snyk

test:
	$(TEST_RUN)

test-with-coverage:
	$(TEST_RUN) --junitxml=pytest.xml --cov-report=term-missing:skip-covered --cov=yamjinx | tee pytest-coverage.txt

test-with-coverage-html:
	$(TEST_RUN) --cov=yamjinx --cov-report=html

update-deps:
	poetry update
	# Workaround for poetry install to be able to install ruamel.yaml library
	./dev/fix_ruamel_pkg_names.py poetry.lock
