SHELL := /bin/bash

DOCKER_OPTS = -V --force-recreate --always-recreate-deps --attach-dependencies --abort-on-container-exit

clean:
	sudo rm -rf srv/tower-analytics-backend/local_postgres_data

stack: clean
	python3 tool.py
	docker-compose -f genstack.yml up $(DOCKER_OPTS)

stack_backend_mock: clean
	python3 tool.py --backend_mock
	docker-compose -f genstack.yml up $(DOCKER_OPTS)

stack_no_reset_no_build: clean
	python3 tool.py --skip_chrome_reset --skip_chrome_build 
	docker-compose -f genstack.yml up $(DOCKER_OPTS)

########################################
init: migrations data

data:
	docker-compose -f genstack.yml exec fastapi ./entrypoint ./manage.py generate_development_data
	docker-compose -f genstack.yml exec fastapi ./entrypoint ./manage.py refresh_materialized_views_one_time
	docker-compose -f genstack.yml exec fastapi ./entrypoint ./manage.py process_rollups_one_time

migrations:
	docker-compose -f genstack.yml exec fastapi ./entrypoint ./manage.py run_report_migrations $*

