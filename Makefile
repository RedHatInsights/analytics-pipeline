SHELL := /bin/bash

DOCKER_COMPOSE_BIN = COMPOSE_HTTP_TIMEOUT=1000 venv/bin/docker-compose
DOCKER_RESTART_OPTS = --no-color -V --force-recreate --always-recreate-deps --attach-dependencies
DOCKER_OPTS = $(DOCKER_RESTART_OPTS) --abort-on-container-exit

clean:
	rm -rf srv/integration_tests/cypress/screenshots/*
	rm -rf srv/integration_tests/cypress/videos/*
	docker-compose -f genstack.yml down || echo "docker-compose down failed"
	docker-compose -f genstack.yml rm -f || echo "docker-compose rm failed"
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

stack: clean
	python3 tool.py
	 $(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_OPTS)

stack_backend_mock: clean
	python3 tool.py --backend_mock --skip_frontend_install
	cat genstack.yml
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_OPTS)

# compiles but does not spin up the stack
build_backend_mock: clean
	python3 tool.py --backend_mock --skip_frontend_install
	cat genstack.yml
	#$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_OPTS)

stack_mock_static: clean
	python3 tool.py --backend_mock --static
	cat genstack.yml
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_OPTS)

stack_ci: clean
	python3 tool.py --backend_mock --integration --static
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS) --exit-code-from integration

stack_ci_devservers: clean
	python3 tool.py --backend_mock --skip_frontend_install
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS)

stack_ci_puppeteer: clean
	python3 tool.py --backend_mock --static --integration --puppeteer
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS) --exit-code-from integration

stack_ci_cypress: clean
	python3 tool.py --backend_mock --static --integration --cypress
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS) --exit-code-from integration

stack_ci_cypress_debug: clean
	cat /etc/issue
	free -m
	cat /proc/cpuinfo
	python3 tool.py --backend_mock --static --integration --cypress_debug
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS) --exit-code-from integration

stack_ci_test: clean
	python3 tool.py --backend_mock --skip_frontend_install --integration
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS)

stack_no_reset_no_build: clean
	python3 tool.py --skip_chrome_reset --skip_chrome_build 
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_OPTS)

stack_allow_restart: clean
	python3 tool.py
	$(DOCKER_COMPOSE_BIN) -f genstack.yml up $(DOCKER_RESTART_OPTS)

########################################
init: migrations data

data:
	$(DOCKER_COMPOSE_BIN) -f genstack.yml exec fastapi ./entrypoint ./manage.py generate_development_data
	$(DOCKER_COMPOSE_BIN) -f genstack.yml exec fastapi ./entrypoint ./manage.py refresh_materialized_views_one_time
	$(DOCKER_COMPOSE_BIN) -f genstack.yml exec fastapi ./entrypoint ./manage.py process_rollups_one_time

migrations:
	$(DOCKER_COMPOSE_BIN) -f genstack.yml exec fastapi ./entrypoint ./manage.py run_report_migrations $*

