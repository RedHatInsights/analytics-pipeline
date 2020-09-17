SHELL := /bin/bash

DOCKER_OPTS = -V --force-recreate --always-recreate-deps --attach-dependencies --abort-on-container-exit

stack:
	python3 tool.py
	docker-compose -f genstack.yml up $(DOCKER_OPTS)

stack_backend_mock:
	python3 tool.py --backend_mock
	docker-compose -f genstack.yml up $(DOCKER_OPTS)

stack_no_reset_no_build:
	python3 tool.py --skip_chrome_reset --skip_chrome_build 
	docker-compose -f genstack.yml up $(DOCKER_OPTS)

########################################
init: migrations data

data:
	docker-compose -f local.yml exec fastapi ./entrypoint ./manage.py generate_development_data
	docker-compose -f local.yml exec fastapi ./entrypoint ./manage.py refresh_materialized_views_one_time
	docker-compose -f local.yml exec fastapi ./entrypoint ./manage.py process_rollups_one_time

db_cleanup:
	docker-compose -f local.yml exec fastapi ./entrypoint ./manage.py api_perf_test 1 --run_only="0" --cleanup

migrations:
	docker-compose -f local.yml exec fastapi ./entrypoint ./manage.py run_report_migrations $*

