SHELL := /bin/bash

DOCKER_OPTS = -V --force-recreate --always-recreate-deps --attach-dependencies --abort-on-container-exit

stack:
	python3 tool.py --backend_mock
	docker-compose -f genstack.yml up $(DOCKER_OPTS)

stack_no_reset:
	python3 tool.py --skip_chrome_reset --backend_mock
	docker-compose -f genstack.yml up $(DOCKER_OPTS)
