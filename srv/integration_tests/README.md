docker run -it -v $(pwd)/integration_tests:/app --network host --add-host sso.local.redhat.com:172.23.0.3 --user=node --cap-add=SYS_ADMIN buildkite/puppeteer /bin/bash
