#!/usr/bin/env python3

import argparse
import copy
import getpass
import os
import shutil
import subprocess
import sys

import platform
import yaml
import ruamel.yaml
from ruamel.yaml import YAML

from logzero import logger
from pprint import pprint

NODE_RUNNER_DOCKERFILE = '''
FROM node:10.22

RUN useradd runner
RUN rm -rf /home/runner
RUN cp -Rp /home/node /home/runner
RUN chown -R runner:runner /home/runner
'''

SPANDX_TEMPLATE = '''/*global module, process*/
const localhost = (process.env.PLATFORM === 'linux') ? 'localhost' : 'host.docker.internal';

module.exports = {
    routes: {
        '/apps/automation-analytics': { host: `FRONTEND` },
        '/ansible/automation-analytics': { host: `FRONTEND` },
        '/beta/ansible/automation-analytics': { host: `FRONTEND` },
        '/api/tower-analytics': { host: `BACKEND` },
        '/apps/chrome': { host: `http://chrome` },
        '/apps/landing': { host: `https://landing:8002` },
        '/beta/apps/landing': { host: `http://landing_beta` },
        '/api/entitlements': { host: `http://entitlements` },
        '/api/rbac': { host: `http://rbac` },
        '/beta/config': { host: `http://${localhost}:8889` },
        '/': { host: `http://webroot` }
    }
};
'''

ENTITLEMENTS_SERVER = '''#/usr/bin/env python3

import os

import flask
from flask import Flask
from flask import jsonify
from flask import request
from flask import redirect


app = Flask(__name__)


services = [
    'ansible',
    'cost_management',
    'insights',
    'migrations',
    'openshift',
    'settings',
    'smart_management',
    'subscriptions',
    'user_preferences'
]


entitlements = {}
for svc in services:
    entitlements[svc] = {'is_entitled': True, 'is_trial': False}


rbac = {
    'meta': {'count': 30, 'limit': 1000, 'offset': 0},
    'links': {
        'first': '/api/rbac/v1/access/?application=&format=json&limit=1000&offset=0',
        'next': None,
        'previous': None,
        'last': '/api/rbac/v1/access/?application=&format=json&limit=1000&offset=0',
    },
    'data': [
        {'resourceDefinitions': [], 'permission': 'insights:*:*'}
    ]
}


@app.route('/api/entitlements/v1/services')
def services():
    return jsonify(entitlements)


@app.route('/api/rbac/v1/access/')
def rbac_access():
    return jsonify(rbac)


if __name__ == '__main__':
    if os.environ.get('API_SECURE'):
        app.run(ssl_context='adhoc', host='0.0.0.0', port=443, debug=True)
    else:
        app.run(host='0.0.0.0', port=80, debug=True)
'''

FLASKDOCKERFILE = '''FROM python:3
COPY requirements.txt /.
RUN pip install -r /requirements.txt
WORKDIR /app
CMD python3 api.py
'''

FLASKREQUIREMENTS = '''flask
cryptography
'''


class GenericFrontendComponent:

    _installed = False
    _built = False
    distdir = 'dist'
    www_app_name = None

    def __init__(self, cloudbuilder, repo, srcpath, name):
        self.name = name
        self.repo = repo
        self.srcpath = srcpath
        self.cb = cloudbuilder
        self.clone()
        self.configure()
        self.preinstall()
        self.install()
        self.prebuild()
        self.build()
        self.postbuild()
        self.predeploy()
        self.deploy()
        self.postdeploy()

    @property
    def installed(self):
        return self._installed

    @property
    def built(self):
        return self._built


    def get_npm_path(self):
        # /home/vagrant/.nvm/versions/node/v10.15.3/bin/npm
        #npath = os.path.expanduser('~/.nvm/versions/node/v10.15.3/bin/npm')
        res = subprocess.run('which npm', shell=True, stdout=subprocess.PIPE)
        npath = res.stdout.decode('utf-8').strip()
        return npath

    def clone(self):
        if not os.path.exists(self.srcpath):
            logger.info(f"clone {self.repo}")
            cmd = f'git clone {self.repo} {self.srcpath}'
            res = subprocess.run(cmd, shell=True)
            if res.returncode != 0:
                raise Exception(f'cloning {self.repo} failed')

    def configure(self):
        pass

    def preinstall(self):
        pass

    def install(self):
        # should we install?
        install = False
        if self.cb.args.static:
            install = True

        if os.path.exists(os.path.join(self.srcpath, 'node_modules')):
            install = False

        if not install:
            return

        cmd = ' '.join([self.get_npm_path(), 'install'])
        logger.info(f'installing npm deps for {self.name}') 
        logger.info(cmd)
        res = subprocess.run(cmd, shell=True, cwd=self.srcpath)
        if res.returncode != 0:
            raise Exception(f'npm install failed')

        self._installed = True

    def prebuild(self):
        pass

    def build(self):
        # should we build?
        build = False
        if self.cb.args.static:
            build = True

        # aa & landing
        if os.path.exists(os.path.join(self.srcpath, 'dist')):
            build = False

        # chrome
        if os.path.exists(os.path.join(self.srcpath, 'build')):
            build = False

        if not build:
            return

        cmd = ' '.join([self.get_npm_path(), 'run', 'build'])
        logger.info(f'building static version of {self.name}') 
        logger.info(cmd)
        res = subprocess.run(cmd, shell=True, cwd=self.srcpath)
        if res.returncode != 0:
            raise Exception(f'npm run build failed')

        self._built = True

    def postbuild(self):
        pass

    def predeploy(self):
        pass

    def deploy(self):
        if self.cb.args.static:
            wwwdir = os.path.join(self.cb.checkouts_root, 'www')
            appsdir = os.path.join(wwwdir, 'apps')
            src = os.path.join(self.srcpath, self.distdir)
            dst = os.path.join(appsdir, self.www_app_name)
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

    def postdeploy(self):
        pass

"""
insights_proxy| GET /apps/landing/js/App.js from http://webroot/apps/landing/js/App.js
webroot       | 2020/11/02 16:18:42 [error] 22#22: *19 open() "/usr/share/nginx/html/apps/landing/js/App.js" failed (2: No such file or directory), client: 172.29.0.6, server: localhost, request: "GET /apps/landing/js/App.js HTTP/1.1", host: "webroot", referrer: "https://prod.foo.redhat.com:8443/"
webroot       | 172.29.0.6 - - [02/Nov/2020:16:18:42 +0000] "GET /apps/landing/js/App.js HTTP/1.1" 404 555 "https://prod.foo.redhat.com:8443/" "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/85.0.4183.121 Safari/537.36" "-"  
"""
class LandingPageFrontend(GenericFrontendComponent):

    www_app_name = 'landing'

    def configure(self):

        # kill the hashed filenames ...
        cfile = os.path.join(self.srcpath, 'config', 'base.webpack.config.js')
        with open(cfile, 'r') as f:
            cdata = f.read()
        if '.[hash]' in cdata:
            cdata = cdata.replace('.[hash]', '')
            with open(cfile, 'w') as f:
                f.write(cdata)

        # kill the /beta prefix ...
        cfg = os.path.join(self.srcpath, 'config', 'webpack.common.js')
        with open(cfg, 'r') as f:
            cdata = f.read()
        cdata = cdata.replace('/beta/apps', '/apps')
        with open(cfg, 'w') as f:
            f.write(cdata)

    '''
    def postbuild(self):
        # need to make App.js available via a symlink
        jsdir = os.path.join(self.srcpath, self.distdir, 'js')
        if os.path.exists(jsdir):
            linkfile = os.path.join(jsdir, 'App.js')
            if not os.path.exists(linkfile):
                cmd = f'ln -s App.*.js App.js'
                res = subprocess.run(cmd, shell=True, cwd=jsdir)
                if res.returncode != 0:
                    raise Exception(f'symlinking failed')
    '''

class InsightsChrome(GenericFrontendComponent):

    www_app_name = 'chrome'
    distdir = 'build'

    def configure(self):
        constants_path = os.path.join(self.srcpath, 'src', 'js', 'jwt', 'constants.js')
        with open(constants_path, 'r') as f:
            cdata = f.read()
        cdata = cdata.replace('https://sso.redhat.com', self.cb.keycloak)
        with open(constants_path, 'w') as f:
            f.write(cdata)

    def postbuild(self):
        # link the hashed css file to non-hashed
        if os.path.exists(os.path.join(self.srcpath, 'build', 'chrome.css')):
            os.remove(os.path.join(self.srcpath, 'build', 'chrome.css'))
        cmd = 'ln -s chrome.*.css chrome.css'
        res = subprocess.run(cmd, cwd=os.path.join(self.srcpath, 'build'), shell=True)
        if res.returncode != 0:
            raise Exception('chrome.css symlinking failed')

        # link the hashed js file to non-hashed
        if os.path.exists(os.path.join(self.srcpath, 'build', 'js', 'chrome.js')):
            os.remove(os.path.join(self.srcpath, 'build', 'js', 'chrome.js'))
        cmd = 'ln -s chrome.*.js chrome.js'
        res = subprocess.run(cmd, cwd=os.path.join(self.srcpath, 'build', 'js'), shell=True)
        if res.returncode != 0:
            raise Exception('chrome.js symlinking failed')


class TowerAnalyticsFrontend(GenericFrontendComponent):

    www_app_name = 'automation-analytics'

    def postdeploy(self):
        if self.cb.args.static:
            wwwdir = os.path.join(self.cb.checkouts_root, 'www')
            ansible_dir = os.path.join(wwwdir, 'ansible')
            if not os.path.exists(ansible_dir):
                os.makedirs(ansible_dir)
            if not os.path.exists(os.path.join(wwwdir, 'ansible', self.www_app_name)):
                cmd = f'ln -s ../apps/{self.www_app_name} {self.www_app_name}'
                res = subprocess.run(cmd, shell=True, cwd=ansible_dir)
                if res.returncode != 0:
                    raise Exception(f'symlink failed')



class CloudBuilder:
    frontend_components = None
    checkouts_root = "srv"
    webroot = "srv/www"
    cache_root = "cache"
    #keycloak = "https://172.19.0.2:8443"
    keycloak = "https://sso.local.redhat.com:8443"
    #keycloak = "https://sso.local.redhat.com:8443"
    #keycloak_ip = "172.19.0.2"
    frontend = "https://192.168.122.81:8002"
    backend = "http://192.168.122.81:5000"

    def __init__(self, args=None):
        self.args = args
        if not os.path.exists(self.checkouts_root):
            os.makedirs(self.checkouts_root)
        if not os.path.exists(self.cache_root):
            os.makedirs(self.cache_root)
        if not os.path.exists(self.webroot):
            os.makedirs(self.webroot)

        self.frontend_components = []
        for svc_name in ['insights-chrome', 'landing-page-frontend', 'tower-analytics-frontend']:
            src_path = os.path.join(self.checkouts_root, svc_name)
            repo = f'https://github.com/RedHatInsights/{svc_name}'
            logger.info(f"create service object for {svc_name}")
            if svc_name == 'landing-page-frontend':
                gfc = LandingPageFrontend(self, repo, src_path, svc_name)
            elif svc_name == 'insights-chrome':
                gfc = InsightsChrome(self, repo, src_path, svc_name)
            elif svc_name == 'tower-analytics-frontend':
                gfc = TowerAnalyticsFrontend(self, repo, src_path, svc_name)
            else:
                gfc = GenericFrontendComponent(self, repo, src_path, svc_name)
            self.frontend_components.append(gfc)

        self.make_spandx()
        #self.make_aa_frontend()
        #self.make_aa_backend()
        self.make_www()
        self.make_entitlements()
        self.make_rbac()

        #if not self.args.skip_landing:
        #    self.make_landing()
        #if not self.args.skip_chrome:
        #    self.make_chrome(build=not self.args.skip_chrome_build, reset=not self.args.skip_chrome_reset)

        self.create_compose_file()

    def get_node_container_user(self):
        '''github actions create bind moundts as root and the node user can't write'''

        # if whoami == runner, we're probably inside a github action container
        # so we need to use root in order to read/write the bind mount ...
        un = getpass.getuser()
        if un == 'runner':
            return 'runner'

        # use "node" by default ...
        return 'node'

    def create_compose_file(self):
        ds = {
            'version': '3',
            'networks': {
                'ssonet': {
                    'ipam': {
                        'config': [{'subnet': '172.23.0.0/24'}]
                    }
                }
            },
            'volumes': {
                'local_postgres_data': {},
                'local_postgres_data_backups': {},
                'local_zookeeper_data': {},
                'local_kafka_data': {}
            },
            'services': {
                'sso.local.redhat.com': {
                    'container_name': 'sso.local.redhat.com',
                    'image': 'quay.io/keycloak/keycloak:11.0.0',
                    'environment': {
                        'DB_VENDOR': 'h2',
                        'PROXY_ADDRESS_FORWARDING': "true",
                        'KEYCLOAK_USER': 'admin',
                        'KEYCLOAK_PASSWORD': 'password',
                    },
                    #'ports': ['8443:8443'],
                    'expose': [8443],
                    'networks': {
                        'ssonet': {
                            'ipv4_address': '172.23.0.3'
                        }
                    }
                },
                'kcadmin': {
                    'container_name': 'kcadmin',
                    'image': 'python:3',
                    'build': {
                        'context': f"{os.path.join(self.checkouts_root, 'keycloak_admin')}",
                    },
                    'volumes': [f"./{os.path.join(self.checkouts_root, 'keycloak_admin')}:/app"],
                    'depends_on': ['sso.local.redhat.com'],
                    #'command': '/bin/bash -c "cd /app && pip install -r requirements.txt && flask run --host=0.0.0.0 --port=80"'
                    'command': '/bin/bash -c "cd /app && pip install -r requirements.txt && python -c \'from kchelper import init_realm; init_realm()\' && flask run --host=0.0.0.0 --port=80"',
                    'networks': {
                        'ssonet': {
                            'ipv4_address': '172.23.0.4'
                        }
                    }

                },
                'insights_proxy': {
                    'container_name': 'insights_proxy',
                    'image': 'redhatinsights/insights-proxy',
                    #'ports': ['1337:1337'],
                    'ports': ['8443:8443'],
                    'environment': ['PLATFORM=linux', 'CUSTOM_CONF=true'],
                    'security_opt': ['label=disable'],
                    'extra_hosts': ['prod.foo.redhat.com:127.0.0.1'],
                    'environment': {
                        'SPANDX_PORT': 8443
                    },
                    'volumes': [f'./{os.path.join(self.checkouts_root, "www", "spandx.config.js")}:/config/spandx.config.js']
                },
                'webroot': {
                    'container_name': 'webroot',
                    'image': 'nginx',
                    'volumes': [
                        f"./{os.path.join(self.checkouts_root, 'www')}:/usr/share/nginx/html",
                        f"./{os.path.join(self.checkouts_root, 'nginx.conf.d')}:/etc/nginx/conf.d"
                    ],
                    'command': ['nginx-debug', '-g', 'daemon off;']
                },
                'chrome': {
                    'container_name': 'chrome',
                    'image': 'nginx',
                    'volumes': [f"./{os.path.join(self.checkouts_root, 'insights-chrome')}:/usr/share/nginx/html"],
                    'command': ['nginx-debug', '-g', 'daemon off;']
                },
                'chrome_beta': {
                    'container_name': 'chrome_beta',
                    'image': 'nginx',
                    'volumes': [f"./{os.path.join(self.checkouts_root, 'insights-chrome')}:/usr/share/nginx/html"],
                    'command': ['nginx-debug', '-g', 'daemon off;']
                },
                'entitlements': {
                    'container_name': 'entitlements',
                    'image': 'python:3',
                    'build': {
                        'context': f"{os.path.join(self.checkouts_root, 'entitlements')}",
                    },
                    'volumes': [f"./{os.path.join(self.checkouts_root, 'entitlements')}:/app"],
                    'command': '/bin/bash -c "cd /app && pip install -r requirements.txt && python api.py"'
                },
                'rbac': {
                    'container_name': 'rbac',
                    'image': 'python:3',
                    'build': {
                        'context': f"{os.path.join(self.checkouts_root, 'rbac')}",
                    },
                    'volumes': [f"./{os.path.join(self.checkouts_root, 'rbac')}:/app"],
                    'command': '/bin/bash -c "cd /app && pip install -r requirements.txt && python api.py"'
                }

            }
        }

        ds['services'].update(self.get_frontend_service())
        ds['services'].update(self.get_landing_services())

        # macs can't do static IPs
        #if platform.system().lower() == 'darwin':
        if True:
            ds['services']['kcadmin'].pop('networks', None)
            ds['services']['sso.local.redhat.com'].pop('networks', None)
            ds['services']['sso.local.redhat.com'].pop('depends_on', None)

            squid_logs = os.path.join(self.checkouts_root, 'squid', 'logs')
            squid_conf = os.path.join(self.checkouts_root, 'squid', 'conf')
            if not os.path.exists(squid_logs):
                os.makedirs(squid_logs)
            ds['services']['squid'] = {
                'container_name': 'squid',
                'image': 'datadog/squid',
                'ports': ['3128:3128'],
                'volumes': [
                    f"./{squid_conf}:/etc/squid",
                    f"./{squid_logs}:/var/log/squid",
                ]
            }

            pf = copy.deepcopy(ds['services']['insights_proxy'])
            pf['container_name'] = 'prod.foo.redhat.com'
            ds['services'].pop('insights_proxy', None)
            ds['services']['prod.foo.redhat.com'] = pf

        # if static, chrome/landing/frontend should be compiled and put into wwwroot
        if self.args.static:
            ds['services'].pop('chrome', None)
            ds['services'].pop('chrome_beta', None)
            ds['services'].pop('landing', None)
            ds['services'].pop('aafrontend', None)

        # build the backend?
        if self.args.backend_mock:
            aa_be_srcpath = os.path.join(self.checkouts_root, 'aa_backend_mock')
            bs = {
                'container_name': 'aabackend',
                'image': 'python:3',
                'build': {
                    'context': f"./{aa_be_srcpath}"
                },
                'environment': {
                    'API_SECURE': '1',
                },
                'volumes': [f"./{aa_be_srcpath}:/app"],
                'command': '/bin/bash -c "cd /app && pip install -r requirements.txt && python api.py"'
            }
            ds['services']['aabackend'] = bs
        elif self.args.backend_address:
            pass
        else:
            svcs = self.get_backend_compose_services()
            ds['services'].update(svcs)
            #import epdb; epdb.st()

        if self.args.integration:
            ds['services']['integration'] = self.get_integration_compose()

        yaml = YAML(typ='rt', pure=True)
        yaml.preserve_quotes = False
        yaml.indent=4
        yaml.block_seq_indent=4
        yaml.explicit_start = True
        yaml.width = 1000
        yaml.default_flow_style = False

        with open('genstack.yml', 'w') as f:
            yaml.dump(ds, f)

        # fix port quoting for sshd ...
        with open('genstack.yml', 'r') as f:
            fyaml = f.read()
        fyaml = fyaml.replace('2222:22', '\'2222:22\'')
        with open('genstack.yml', 'w') as f:
            f.write(fyaml)
        #import epdb; epdb.st()


    def get_landing_services(self):
        '''
        'landing_beta': {
            'container_name': 'landing_beta',
            'image': 'nginx',
            'volumes': [f"./{os.path.join(self.checkouts_root, 'landing-page-frontend', 'dist')}:/usr/share/nginx/html/beta/apps/landing"],
            'command': ['nginx-debug', '-g', 'daemon off;']
        },
        '''

        svcs = {}
        if self.args.node_landing:
            svcs['landing'] = {
                'container_name': 'landing',
                'image': 'node:10.22.0',
                'environment': {
                    'DEBUG': 'express:*',
                },
                'volumes': [f"./{os.path.join(self.checkouts_root, 'landing-page-frontend')}:/app"],
                'command': '/bin/bash -c "cd /app && npm install && npm run start:container"',
            }
            return svcs

        return svcs


    def get_frontend_service(self):
        if self.args.static:
            return {}

        if self.args.frontend_path or self.args.frontend_hash:
            if self.args.frontend_hash:
                raise Exception('frontend hash not yet implemented!')
            aa_fe_srcpath = os.path.abspath(os.path.expanduser(self.args.frontend_path))
        else:
            aa_fe_srcpath = os.path.join(self.checkouts_root, 'tower-analytics-frontend')

        fs = {
            'container_name': 'aafrontend',
            'image': 'noderunner:latest',
            'build': {
                'context': f'./{aa_fe_srcpath}',
                'dockerfile': 'Dockerfile'
            },
            'user': self.get_node_container_user(),
            'ports': ['8002:8002'],
            'environment': {
                'DEBUG': 'express:*',
            },
            'command': '/bin/bash -c "cd /app && npm install && npm run start:container"',
            'volumes': [f"./{aa_fe_srcpath}:/app:rw"]
        }
        return {'aafrontend': fs}

    def get_integration_compose(self):

        def pick_dockerfile():
            if self.args.puppeteer:
                return 'Dockerfile.puppeteer'
            if self.args.cypress or self.args.cypress_debug:
                return 'Dockerfile.cypress'
            return 'Dockerfile'

        srcpath = os.path.join(self.checkouts_root, 'integration_tests')
        #jestcmd = '/bin/bash -c "cd /app && npm install && ./wait_for_stack.sh && timeout -s SIGKILL 1000s ./node_modules/jest/bin/jest.js src/index.test.js"'
        basecmd = '/bin/bash -c "cd /app && npm install && ./wait_for_stack.sh && timeout -s SIGKILL 1000s '
        if self.args.puppeteer:
            testcmd = basecmd + 'npm run tests:integration:puppeteer"'
        elif self.args.cypress:
            #testcmd = basecmd + 'npm run tests:integration:cypress"'
            testcmd = basecmd + 'cypress run --headless --browser chrome --spec cypress/integration/automation-analytics.js"'
        elif self.args.cypress_debug:
            #testcmd = basecmd + 'npm run tests:integration:cypress-debug"'
            #testcmd = basecmd + 'DEBUG=cypress:* cypress run --headless --browser chrome --spec cypress/integration/automation-analytics.js"'
            testcmd = basecmd + 'cypress run --headless --browser chrome --spec cypress/integration/automation-analytics.js"'
        else:
            testcmd = basecmd + './node_modules/jest/bin/jest.js src/index.test.js"'

        svc = {
            'container_name': 'integration',
            #'image': 'buildkite/puppeteer',
            'ipc': 'host',
            'image': 'aa_integration:latest',
            'build': {
                'context': './srv/integration_tests',
                'dockerfile': pick_dockerfile()
            },
            'volumes': [f"./{srcpath}:/app:rw"],
            'network_mode': 'host',
            #'user': 'node',
            'user': self.get_node_container_user(),
            'cap_add': ['SYS_ADMIN'],
            'extra_hosts': [
                'prod.foo.redhat.com:127.0.0.1',
                'sso.local.redhat.com:172.23.0.3'
            ],
            'entrypoint': '',
            'depends_on': ['sso.local.redhat.com', 'kcadmin', 'aafrontend', 'aabackend'],
            'command': testcmd,
        }

        if self.args.static:
            svc['depends_on'].remove('aafrontend')

        #if platform.system().lower() == 'darwin':
        if True:
            svc.pop('network_mode', None)
            svc.pop('extra_hosts', None)

        return svc

    def get_npm_path(self):
        # /home/vagrant/.nvm/versions/node/v10.15.3/bin/npm
        #npath = os.path.expanduser('~/.nvm/versions/node/v10.15.3/bin/npm')
        res = subprocess.run('which npm', shell=True, stdout=subprocess.PIPE)
        npath = res.stdout.decode('utf-8').strip()
        return npath

    def make_spandx(self):
        stemp = SPANDX_TEMPLATE

        if not self.args.static:
            if self.args.frontend_path:
                stemp = stemp.replace("FRONTEND", 'https://aafrontend:8002')
            elif self.args.frontend_hash:
                stemp = stemp.replace("FRONTEND", 'https://aafrontend:8002')
            elif self.args.frontend_address:
                stemp = stemp.replace("FRONTEND", self.args.frontend_address)
            else:
                stemp = stemp.replace("FRONTEND", 'https://aafrontend:8002')

        if self.args.backend_path:
            stemp = stemp.replace("BACKEND", 'http://fastapi:8080')
        elif self.args.backend_hash:
            stemp = stemp.replace("BACKEND", 'https://fastapi:8080')
        elif self.args.backend_mock:
            stemp = stemp.replace("BACKEND", 'https://aabackend:443')
        elif self.args.backend_address:
            stemp = stemp.replace("BACKEND", self.args.backend_address)
        else:
            # assume building the real deal? ...
            stemp = stemp.replace("BACKEND", 'http://fastapi:8080')

        # landing is being hosted by the www service ...
        if not self.args.node_landing and not self.args.static:
            stlines = stemp.split('\n')
            stlines = [x for x in stlines if '/apps/landing' not in x]
            stemp = '\n'.join(stlines)

        if self.args.static:
            stlines = stemp.split('\n')
            #stlines = [x for x in stlines if '/apps/landing' not in x]
            #stlines = [x for x in stlines if '/apps/chrome' not in x]
            #stlines = [x for x in stlines if '/apps/automation-analytics' not in x]
            #stlines = [x for x in stlines if '/ansible/automation-analytics' not in x]
            for idx,x in enumerate(stlines):
                if '/chrome' in x:
                    stlines[idx] = x.replace('http://chrome', 'http://webroot')
                elif 'beta/apps/landing' in x:
                    stlines[idx] = x.replace('http://landing_beta', 'http://webroot')
                elif 'landing' in x:
                    stlines[idx] = x.replace('https://landing:8002', 'http://webroot')
                elif 'analytics' in x and not '/api' in x:
                    stlines[idx] = x.replace('FRONTEND', 'http://webroot')

            stemp = '\n'.join(stlines)
            #import epdb; epdb.st()

        with open(os.path.join(self.webroot, 'spandx.config.js'), 'w') as f:
            f.write(stemp)

    def make_aa_frontend(self):
        git_url = 'https://github.com/RedhatInsights/tower-analytics-frontend'
        srcpath = os.path.join(self.checkouts_root, 'tower-analytics-frontend')
        if not os.path.exists(srcpath):
            cmd = f'git clone {git_url} {srcpath}'
            res = subprocess.run(cmd, shell=True)
            if res.returncode != 0:
                raise Exception(f'cloning {git_url} failed')

        # pre-install packages ...
        if not self.args.skip_frontend_install:
            node_modules = os.path.join(srcpath, 'node_modules')
            if not os.path.exists(node_modules):
                '''
                cmd = [self.get_npm_path(), 'install']
                print(cmd)
                res = subprocess.run(cmd, cwd=srcpath)
                if res.returncode != 0:
                    raise Exception(f'npm install failed')
                '''
                NpmInstaller(self).run_install(srcpath)

        if not self.args.static:
            # fixup the dockerfile to add the github actions runner user
            dfile = os.path.join(srcpath, 'Dockerfile')
            #with open(dfile, 'r') as f:
            #    ddata = f.read()
            with open(dfile, 'w') as f:
                f.write(NODE_RUNNER_DOCKERFILE)
        else:
            # static build that will land in the www root ...
            if os.path.exists(os.path.join(srcpath, 'dist')):
                shutil.rmtree(os.path.join(srcpath, 'dist'))

            cmd = f'{self.get_npm_path()} run build'
            print(cmd)
            res = subprocess.run(cmd, cwd=srcpath, shell=True)
            if res.returncode != 0:
                raise Exception(f'npm build failed')

            www = os.path.join(self.checkouts_root, 'www')
            if os.path.exists(os.path.join(www, 'apps', 'automation-analytics')):
                shutil.rmtree(os.path.join(www, 'apps', 'automation-analytics'))
            shutil.copytree(
                os.path.join(srcpath, 'dist'),
                os.path.join(www, 'apps', 'automation-analytics')
            )
            if os.path.exists(os.path.join(www, 'ansible')):
                shutil.rmtree(os.path.join(www, 'ansible'))
            os.makedirs(os.path.join(www, 'ansible'))
            cmd = f"ln -s ../apps/automation-analytics automation-analytics"
            res = subprocess.run(cmd, cwd=os.path.join(www, 'ansible'), shell=True)
            if res.returncode != 0:
                raise Exception(f'symlinking failed')

            #import epdb; epdb.st()

    def make_aa_backend(self):

        if self.args.backend_mock:
            return

        if self.args.backend_hash:
            raise Exception('backend hash not yet implemented')
        if self.args.backend_path:
            raise Exception('backend path not yet implemented')
        if self.args.backend_address:
            return

        git_url = 'git@github.com:RedhatInsights/tower-analytics-backend'
        srcpath = os.path.join(self.checkouts_root, 'tower-analytics-backend')

        if not os.path.exists(srcpath):
            cmd = f'git clone {git_url} {srcpath}'
            res = subprocess.run(cmd, shell=True)
            if res.returncode != 0:
                raise Exception(f'cloning {git_url} failed')

    def get_backend_compose_services(self):
        srcpath = os.path.join(self.checkouts_root, 'tower-analytics-backend')
        compose_file = os.path.join(srcpath, 'local.yml')
        with open(compose_file, 'r') as f:
            ytxt = f.read()
        ydata = yaml.load(ytxt)
        svcs = {}
        svcs['fastapi'] = ydata['services']['fastapi']
        svcs['postgres'] = ydata['services']['postgres']
        svcs['kafka'] = ydata['services']['kafka']
        svcs['zookeeper'] = ydata['services']['zookeeper']
        svcs['refresher'] = ydata['services']['refresher']
        svcs['rollups_processor'] = ydata['services']['rollups_processor']

        for k,v in svcs.items():
            if 'build' in v:
                svcs[k]['build']['context'] = './' + srcpath
            svcs[k]['container_name'] = k
            if k not in ['zookeeper', 'kafka']:
                for idv,volume in enumerate(v.get('volumes', [])):
                    svcs[k]['volumes'][idv] = './' + srcpath + '/' + volume.lstrip('./')
            for ide,envfile in enumerate(v.get('env_file', [])):
                print(envfile)
                svcs[k]['env_file'][ide] = './' + srcpath + '/' + envfile.replace('./', '')
            #import epdb; epdb.st()

        #import epdb; epdb.st()
        return svcs

    def make_www(self):
        apps_path = os.path.join(self.webroot, 'apps')
        chrome_src = os.path.join(self.checkouts_root, 'insights-chrome')

        if not os.path.exists(apps_path):
            os.makedirs(apps_path)

        '''
        # apps/chrome should point at the chrome build path
        if not os.path.exists(os.path.join(apps_path, 'chrome')):
            cmd = f'ln -s ../../{chrome_src} chrome'
            print(cmd)
            subprocess.run(cmd, cwd=apps_path, shell=True)
        '''

        # get index.html and make it point at the right chrome css file ...
        if not os.path.exists(os.path.join(self.webroot, 'index.html')):
            cmd = 'curl -o index.html https://cloud.redhat.com'
            res = subprocess.run(cmd, cwd=self.webroot, shell=True)
            if res.returncode != 0:
                raise Exception(f'curl failed')
            cmd = 'sed -i.bak "s/chrome\..*\.css/chrome\.css/" index.html && rm -f index.html.bak'
            res = subprocess.run(cmd, cwd=self.webroot, shell=True)
            if res.returncode != 0:
                raise Exception(f'sed failed')

        # symlink the silent-check-sso.html
        ssof = os.path.join(self.checkouts_root, 'landing-page-frontend', 'dist', 'silent-check-sso.html')
        dst = os.path.join(self.webroot, 'silent-check-sso.html')
        if not os.path.exists(dst):
            os.link(ssof, dst)

    def make_landing(self):
        # clone it
        repo = 'https://github.com/RedHatInsights/landing-page-frontend'
        srcpath = os.path.join(self.checkouts_root, 'landing-page-frontend')

        if not os.path.exists(srcpath):
            if os.path.exists(srcpath):
                shutil.rmtree(srcpath)
            cmd = f'git clone {repo} {srcpath}'
            cmd = cmd.split()
            print(cmd)
            res = subprocess.run(cmd)
            if res.returncode != 0:
                raise Exception(f'git clone failed')

        # add a container start target so it will bind to 0.0.0.0
        pfile = os.path.join(srcpath, 'package.json')
        with open(pfile, 'r') as f:
            pdata = f.read()
        if 'start:container' not in pdata:
            plines = pdata.split('\n')
            pix = None
            for idx,x in enumerate(plines):
                if '"start":' in x:
                    pix = idx
            nl = plines[pix][:]
            nl = nl.replace('start', 'start:container')
            nl = nl.replace('webpack-dev-server', 'webpack-dev-server --host 0.0.0.0 ')
            plines.insert(pix+1, nl)
            with open(pfile, 'w') as f:
                f.write('\n'.join(plines))

        # kill the hashed filenames ...
        cfile = os.path.join(srcpath, 'config', 'base.webpack.config.js')
        with open(cfile, 'r') as f:
            cdata = f.read()
        if '.[hash]' in cdata:
            cdata = cdata.replace('.[hash]', '')
            with open(cfile, 'w') as f:
                f.write(cdata)

        # kill the /beta prefix ...
        cfg = os.path.join(srcpath, 'config', 'webpack.common.js')
        with open(cfg, 'r') as f:
            cdata = f.read()
        cdata = cdata.replace('/beta/apps', '/apps')
        with open(cfg, 'w') as f:
            f.write(cdata)

        nm = os.path.join(srcpath, 'node_modules')
        if not os.path.exists(nm):
            NpmInstaller(self).run_install(srcpath)

        if not os.path.exists(os.path.join(srcpath, 'dist', 'index.html')):
            NpmBuilder(self).run_build(srcpath)

        # Are we going to run this is a service or are we going to host it with nginx?
        if not self.args.node_landing:

            www = os.path.join(self.checkouts_root, 'www')
            apppath = os.path.join(www, 'apps', 'landing')
            if os.path.exists(apppath):
                shutil.rmtree(apppath)
            shutil.copytree(os.path.join(srcpath, 'dist'), apppath)

    def make_chrome(self, build=False, reset=True, set_jwt=True, fix=True):

        # clone it
        repo = 'https://github.com/RedHatInsights/insights-chrome'
        srcpath = os.path.join(self.checkouts_root, 'insights-chrome')

        if not os.path.exists(srcpath):
            if os.path.exists(srcpath):
                shutil.rmtree(srcpath)
            cmd = f'git clone {repo} {srcpath}'
            cmd = cmd.split()
            print(cmd)
            res = subprocess.run(cmd)
            if res.returncode != 0:
                raise Exception(f'git clone failed')

        # reset the source
        if reset:
            cmd = f'git reset --hard'
            cmd = cmd.split()
            print(cmd)
            res = subprocess.run(cmd, cwd=srcpath)
            if res.returncode != 0:
                raise Exception('git reset failed')

        # set sso url(s) ...
        if set_jwt:
            self.set_chrome_jwt_constants()

        '''
        # install pkgs from cache or from npm
        nm = os.path.join(self.cache_root, 'chrome_node_modules')
        if not os.path.exists(nm):
            cmd = ['npm', 'install']
            print(cmd)
            subprocess.run(cmd, cwd=srcpath)
            shutil.copytree(os.path.join(srcpath, 'node_modules'), nm)
        else:
            print(f'cp -Rp {nm} -> {srcpath}/node_modules')
            #shutil.copytree(nm, os.path.join(srcpath, 'node_modules'))
            subprocess.run(['cp', '-Rp', os.path.abspath(nm), 'node_modules'], cwd=srcpath)
            #print(f'ln -s {nm} {srcpath}/node_modules')
            #subprocess.run(['ln', '-s', os.path.abspath(nm), 'node_modules'], cwd=srcpath)
        '''
        nm = os.path.join(srcpath, 'node_modules')
        if not os.path.exists(nm) and build:
            '''
            cmd = [self.get_npm_path(), 'install']
            print(cmd)
            res = subprocess.run(cmd, cwd=srcpath)
            if res.returncode != 0:
                raise Exception('npm install failed')
            '''
            NpmInstaller(self).run_installer(srcpath)

        # build the src
        if os.path.exists(os.path.join(srcpath, 'build')) and build:
            shutil.rmtree(os.path.join(srcpath, 'build'))
        if not os.path.exists(os.path.join(srcpath, 'build')) and build:
            res = subprocess.run([self.get_npm_path(), 'run', 'build'], cwd=srcpath)
            if res.returncode != 0:
                raise Exception('npm build failed')

        # node_modules -must- be served from the build root
        if not os.path.exists(os.path.join(srcpath, 'build', 'node_modules')):
            cmd = 'ln -s ../node_modules node_modules'
            res = subprocess.run(cmd, cwd=os.path.join(srcpath, 'build'), shell=True)
            if res.returncode != 0:
                raise Exception('node_modules symlinking failed')

        # make a shim for /apps/chrome to build
        apps = os.path.join(srcpath, 'apps')
        if not os.path.exists(apps):
            os.makedirs(apps)
        if not os.path.exists(os.path.join(apps, 'chrome')):
            cmd = 'ln -s ../build chrome'
            res = subprocess.run(cmd, cwd=apps, shell=True)
            if res.returncode != 0:
                raise Exception('build symlinking failed')

        bpath = os.path.join(srcpath, 'beta')
        if not os.path.exists(bpath):
            os.makedirs(bpath)
        if not os.path.exists(os.path.join(bpath, 'apps')):
            cmd = 'ln -s ../apps apps'
            res = subprocess.run(cmd, cwd=bpath, shell=True)
            if res.returncode != 0:
                raise Exception('apps symlinking failed')

        if fix:
            self.fix_chrome()

    def set_chrome_jwt_constants(self):
        # src/insights-chrome/src/js/jwt/constants.js
        srcpath = os.path.join(self.checkouts_root, 'insights-chrome')
        constants_path = os.path.join(srcpath, 'src', 'js', 'jwt', 'constants.js')
        with open(constants_path, 'r') as f:
            cdata = f.read()

        cdata = cdata.replace('https://sso.redhat.com', self.keycloak)

        with open(constants_path, 'w') as f:
            f.write(cdata)

    def fix_chrome(self):
        srcpath = os.path.join(self.checkouts_root, 'insights-chrome')

        # link the hashed css file to non-hashed
        if os.path.exists(os.path.join(srcpath, 'build', 'chrome.css')):
            os.remove(os.path.join(srcpath, 'build', 'chrome.css'))
        cmd = 'ln -s chrome.*.css chrome.css'
        res = subprocess.run(cmd, cwd=os.path.join(srcpath, 'build'), shell=True)
        if res.returncode != 0:
            raise Exception('chrome.css symlinking failed')

        # link the hashed js file to non-hashed
        if os.path.exists(os.path.join(srcpath, 'build', 'js', 'chrome.js')):
            os.remove(os.path.join(srcpath, 'build', 'js', 'chrome.js'))
        cmd = 'ln -s chrome.*.js chrome.js'
        res = subprocess.run(cmd, cwd=os.path.join(srcpath, 'build', 'js'), shell=True)
        if res.returncode != 0:
            raise Exception('chrome.js symlinking failed')

    def make_rbac(self):
        srcpath = os.path.join(self.checkouts_root, 'rbac')
        if os.path.exists(srcpath):
            shutil.rmtree(srcpath)
        os.makedirs(srcpath)

        with open(os.path.join(srcpath, 'api.py'), 'w') as f:
            f.write(ENTITLEMENTS_SERVER)
        with open(os.path.join(srcpath, 'Dockerfile'), 'w') as f:
            f.write(FLASKDOCKERFILE)
        with open(os.path.join(srcpath, 'requirements.txt'), 'w') as f:
            f.write(FLASKREQUIREMENTS)

    def make_entitlements(self):
        srcpath = os.path.join(self.checkouts_root, 'entitlements')
        if os.path.exists(srcpath):
            shutil.rmtree(srcpath)
        os.makedirs(srcpath)

        with open(os.path.join(srcpath, 'api.py'), 'w') as f:
            f.write(ENTITLEMENTS_SERVER)
        with open(os.path.join(srcpath, 'Dockerfile'), 'w') as f:
            f.write(FLASKDOCKERFILE)
        with open(os.path.join(srcpath, 'requirements.txt'), 'w') as f:
            f.write(FLASKREQUIREMENTS)


def main():

    parser = argparse.ArgumentParser()
    #parser.add_argument('--frontend', choices=['local', 'container'], default='local')
    parser.add_argument('--frontend_address', help="use local or remote address for frontend")
    parser.add_argument('--frontend_hash', help="what aa frontend hash to use")
    parser.add_argument('--frontend_path', help="path to an aa frontend checkout")
    #parser.add_argument('--backend', choices=['local', 'container', 'mock_container'], default='local')
    parser.add_argument('--backend_address', help="use local or remote address for backend")
    parser.add_argument('--backend_hash', help="what aa backend hash to use")
    parser.add_argument('--backend_path', help="path to an aa backend checkout")
    parser.add_argument('--backend_mock', action='store_true', help="use the mock backend")
    parser.add_argument('--skip_chrome', action='store_true')
    parser.add_argument('--skip_landing', action='store_true')
    parser.add_argument('--skip_chrome_reset', action='store_true')
    parser.add_argument('--skip_chrome_build', action='store_true')
    parser.add_argument('--skip_frontend_install', action='store_true')
    parser.add_argument('--node_landing', action='store_true')
    parser.add_argument('--static', action='store_true', help="do not use webpack dev server where possible")
    parser.add_argument('--integration', action='store_true')
    parser.add_argument('--puppeteer', action='store_true')
    parser.add_argument('--cypress', action='store_true')
    parser.add_argument('--cypress_debug', action='store_true')
    args = parser.parse_args()

    logger.info("starting cloudbuilder")
    cbuilder = CloudBuilder(args=args)


if __name__ == "__main__":
    main()
