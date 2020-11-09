# Integrating with AWX

## prerequisites

* spin up the local stack with a real backend

## install process

* sudo mkdir -p /var/lib/awx/projects
* chown -R $(whoami):$(whoami) /var/lib/awx/projects
* git clone https://github.com/ansible/awx
* cd awx
* ansible-playbook -i inventory -e project_data_dir=/var/lib/awx/projects -v install.yml

## post install

* docker exec -it awx_task /bin/bash
* vi /var/lib/awx/venv/awx/lib/python3.6/site-packages/awx/main/analytics/core.py
** change the `_valid_license` function to always return True
* in the gui settings, enable analytics
