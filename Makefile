SHELL := /bin/bash

PYTHON_BIN = venv/bin/python3
DOCKER_COMPOSE_BIN = COMPOSE_HTTP_TIMEOUT=1000 $(shell pwd)/venv/bin/docker-compose
DOCKER_RESTART_OPTS = --no-color -V --force-recreate --always-recreate-deps --attach-dependencies
DOCKER_OPTS = $(DOCKER_RESTART_OPTS) --abort-on-container-exit
AWX_COMPOSE = srv/awx.var/awxcompose/docker-compose.yml
CURRENT_UID=$(shell id -u)
OS="$(shell docker info | grep 'Operating System')"

venv:
	scripts/create_venv.sh

clean:
	rm -rf srv/integration_tests/cypress/screenshots/*
	rm -rf srv/integration_tests/cypress/videos/*
	$(DOCKER_COMPOSE_BIN) -f genstack.yml down || echo "docker-compose down failed"
	$(DOCKER_COMPOSE_BIN) -f genstack.yml rm -f || echo "docker-compose rm failed"
	if [[ -f $(AWX_COMPOSE) ]]; then $(DOCKER_COMPOSE_BIN) -f $(AWX_COMPOSE) kill; fi;
	if [[ -f $(AWX_COMPOSE) ]]; then $(DOCKER_COMPOSE_BIN) -f $(AWX_COMPOSE) rm -f; fi;
	docker volume prune -f
	docker volume ls | fgrep _local_ | awk '{print $2}' | xargs -I {} docker volume rm -f {}
	if [[ -d srv/tower-analytics-backend ]]; then sudo rm -rf srv/tower-analytics-backend/local_*_data; fi;
	if [[ -d srv/tower-analytics-backend ]]; then sudo rm -rf srv/tower-analytics-backend/local_*_data_backups; fi;

clean_apps:
	rm -rf srv/insights-chrome
	rm -rf srv/landing-page-frontend
	rm -rf srv/tower-analytics-frontend

clean_node_modules:
	rm -rf srv/*/node_modules

stack: clean venv
	$(PYTHON_BIN) tool.py --static=chrome --static=landing
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_OPTS)

stack_allow_restart: clean venv
	$(PYTHON_BIN) tool.py --static=chrome --static=landing
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS)

stack_with_awx: clean venv
	$(PYTHON_BIN) tool.py --static=chrome --static=landing --awx
	#cd srv/awx && $(DOCKER_COMPOSE_BIN) -f tools/docker-compose.yml up $(DOCKER_RESTART_OPTS) awx
	#$(DOCKER_COMPOSE_BIN) -f srv/awx/tools/docker-compose.yml up $(DOCKER_RESTART_OPTS)
	#$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS)
	#scripts/multi-compose -f srv/awx/tools/docker-compose.yml -f genstack.yml $(DOCKER_RESTART_OPTS)
	scripts/multi-command \
		--command="cd srv/awx && make docker-compose" \
		--command="$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS)"

stack_backend_mock: clean venv
	$(PYTHON_BIN) tool.py --backend_mock --static=chrome --static=landing
	cat genstack.yml
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_OPTS)

stack_mock_static: clean venv
	$(PYTHON_BIN) tool.py --backend_mock --static=all
	cat genstack.yml
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_OPTS)

stack_ci_puppeteer: clean venv
	$(PYTHON_BIN) tool.py --backend_mock --static=all --integration --puppeteer
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS) --exit-code-from integration

stack_ci_cypress: clean venv
	$(PYTHON_BIN) tool.py --backend_mock --static=all --integration --cypress
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS) --exit-code-from integration

stack_ci_cypress_debug: clean venv
	pwd
	if [[ -f /etc/issue ]]; then cat /etc/issue; fi;
	uname -a
	if [[ "$(shell uname)" == "Darwin" ]]; then echo "$(shell top -l 1 -s 0 | grep PhysMem)"; else free -m; fi;
	if [[ "$(shell uname)" == "Darwin" ]]; then echo "$(shell sysctl -n machdep.cpu.brand_string)"; else cat /proc/cpuinfo; fi;
	docker --version
	which python3
	$(PYTHON_BIN) tool.py --backend_mock --static=all --integration --cypress_debug
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS) --exit-code-from integration

########################################
init: migrations data

data:
	$(DOCKER_COMPOSE_BIN) -f genstack.yml exec fastapi ./entrypoint ./manage.py generate_development_data
	$(DOCKER_COMPOSE_BIN) -f genstack.yml exec fastapi ./entrypoint ./manage.py refresh_materialized_views_one_time
	$(DOCKER_COMPOSE_BIN) -f genstack.yml exec fastapi ./entrypoint ./manage.py process_rollups_one_time

migrations:
	$(DOCKER_COMPOSE_BIN) -f genstack.yml exec fastapi ./entrypoint ./manage.py run_report_migrations $*

rollups:
	$(DOCKER_COMPOSE_BIN) -f genstack.yml restart refresher
	$(DOCKER_COMPOSE_BIN) -f genstack.yml restart rollups_processor
