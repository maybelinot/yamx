TEST = pytest
TEST_DIR = tests/
TEST_RUN = $(TEST) $(TEST_DIR)

.PHONY: default $(MAKECMDGOALS)

help:
	@echo "make check"
	@echo "     run lint and tests"
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

lint:
	pre-commit run -a

snyk:
	snyk test --all-projects --policy-path=.snyk

test:
	$(TEST_RUN)

test-with-coverage:
	$(TEST_RUN) --junitxml=pytest.xml --cov-report=term-missing:skip-covered --cov=yamx | tee pytest-coverage.txt

test-with-coverage-html:
	$(TEST_RUN) --cov=yamx --cov-report=html

update-deps:
	poetry update

publish:
	poetry publish --build
