SHELL := /bin/bash

keycloak:
	docker run \
		--name=keycloak \
		-e "KEYCLOAK_USER=admin" \
		-e "KEYCLOAK_PASSWORD=password" \
		-p 8443:8443 \
		-it quay.io/keycloak/keycloak:11.0.0


stack:
	python3 tool.py
	docker-compose -f genstack.yml up -V --force-recreate --always-recreate-deps --attach-dependencies

stack_no_reset:
	python3 tool.py --skip_chrome_reset
	docker-compose -f genstack.yml up -V --force-recreate --always-recreate-deps --attach-dependencies
