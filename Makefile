SHELL := /bin/bash

keycloak:
	docker run \
		--name=keycloak \
		-e "KEYCLOAK_USER=admin" \
		-e "KEYCLOAK_PASSWORD=admin" \
		-p 8443:8443 \
		-it quay.io/keycloak/keycloak:11.0.0

chrome:
	cd insights-chrome && [ -d node_modules ] || npm install
	cd insights-chrome && rm -rf www && mkdir -p www/apps
	cd insights-chrome/www && curl -o index.html https://cloud.redhat.com
	cd insights-chrome/www && sed -i.bak 's/chrome\..*\.css/chrome\.css/' index.html

	cd insights-chrome && rm -rf build
	cd insights-chrome && npm run build
	cd insights-chrome/build && ln -s chrome.*.css chrome.css
	cd insights-chrome/build/js && ln -s chrome.*.js chrome.js
	cd insights-chrome/www/apps && ln -s ../../build chrome
	cd insights-chrome/build && ln -s ../node_modules node_modules
	cd insights-chrome && [ -d node_modules/http-server ] || npm install http-server
	cd insights-chrome/www && ../node_modules/http-server/bin/http-server -a 0.0.0.0 -p 8080
