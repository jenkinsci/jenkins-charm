#!/usr/bin/make
PYTHON := /usr/bin/env python

ensure_venv:
ifeq ("$(shell which virtualenv)","")
	@sudo apt-get install -y python-virtualenv
endif
	@virtualenv .venv --no-site-packages
	@. .venv/bin/activate; \
	pip install -q -I -r test-requirements.txt; \
	deactivate

lint: ensure_venv
	@. .venv/bin/activate; \
	.venv/bin/flake8 --exclude hooks/charmhelpers hooks unit_tests tests; \
	charm proof; \
	deactivate

functional_test:
	@echo Starting Amulet tests...
	# coreycb note: The -v should only be temporary until Amulet sends
	# raise_status() messages to stderr:
	#   https://bugs.launchpad.net/amulet/+bug/1320357
	@juju test -v -p AMULET_HTTP_PROXY --timeout 900 \
	00-setup 100-deploy-precise 100-deploy-trusty

test: ensure_venv
	@echo Starting unit tests...
	@. .venv/bin/activate; \
	.venv/bin/nosetests --nologcapture --with-coverage unit_tests; \
	deactivate

bin/charm_helpers_sync.py:
	@mkdir -p bin
	@bzr cat lp:charm-helpers/tools/charm_helpers_sync/charm_helpers_sync.py \
        > bin/charm_helpers_sync.py

sync: bin/charm_helpers_sync.py
	@$(PYTHON) bin/charm_helpers_sync.py -c charm-helpers-hooks.yaml
	@$(PYTHON) bin/charm_helpers_sync.py -c charm-helpers-tests.yaml

publish: lint unit_test
	bzr push lp:charms/jenkins
	bzr push lp:charms/trusty/jenkins
