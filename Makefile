SHELL := /bin/bash

stack:
	python3 tool.py --backend_mock
	docker-compose -f genstack.yml up -V --force-recreate --always-recreate-deps --attach-dependencies

stack_no_reset:
	python3 tool.py --skip_chrome_reset --backend_mock
	docker-compose -f genstack.yml up -V --force-recreate --always-recreate-deps --attach-dependencies
