SHELL := /bin/bash

DOCKER_RESTART_OPTS = -V --force-recreate --always-recreate-deps --attach-dependencies
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

stack: clean
	python3 tool.py
	docker-compose -f genstack.yml up $(DOCKER_OPTS)

stack_backend_mock: clean
	python3 tool.py --backend_mock --skip_frontend_install
	cat genstack.yml
	docker-compose -f genstack.yml up $(DOCKER_OPTS)

stack_ci: clean
	python3 tool.py --backend_mock --skip_frontend_install --integration
	docker-compose -f genstack.yml up $(DOCKER_RESTART_OPTS) --exit-code-from integration

stack_ci_puppeteer: clean
	python3 tool.py --backend_mock --skip_frontend_install --integration --puppeteer
	docker-compose -f genstack.yml up $(DOCKER_RESTART_OPTS) --exit-code-from integration

stack_ci_cypress: clean
	python3 tool.py --backend_mock --skip_frontend_install --integration --cypress
	docker-compose -f genstack.yml up $(DOCKER_RESTART_OPTS) --exit-code-from integration

stack_ci_cypress_debug: clean
	python3 tool.py --backend_mock --skip_frontend_install --integration --cypress_debug
	docker-compose -f genstack.yml up $(DOCKER_RESTART_OPTS) --exit-code-from integration

stack_ci_test: clean
	python3 tool.py --backend_mock --skip_frontend_install --integration
	docker-compose -f genstack.yml up $(DOCKER_RESTART_OPTS)

stack_no_reset_no_build: clean
	python3 tool.py --skip_chrome_reset --skip_chrome_build 
	docker-compose -f genstack.yml up $(DOCKER_OPTS)

stack_allow_restart: clean
	python3 tool.py
	docker-compose -f genstack.yml up $(DOCKER_RESTART_OPTS)

########################################
init: migrations data

data:
	docker-compose -f genstack.yml exec fastapi ./entrypoint ./manage.py generate_development_data
	docker-compose -f genstack.yml exec fastapi ./entrypoint ./manage.py refresh_materialized_views_one_time
	docker-compose -f genstack.yml exec fastapi ./entrypoint ./manage.py process_rollups_one_time

migrations:
	docker-compose -f genstack.yml exec fastapi ./entrypoint ./manage.py run_report_migrations $*

