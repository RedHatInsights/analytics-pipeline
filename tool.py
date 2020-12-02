#!/usr/bin/env python3

import argparse
import copy
import getpass
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

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

def get_npm_path():
    # /home/vagrant/.nvm/versions/node/v10.15.3/bin/npm
    #npath = os.path.expanduser('~/.nvm/versions/node/v10.15.3/bin/npm')
    res = subprocess.run('which npm', shell=True, stdout=subprocess.PIPE)
    npath = res.stdout.decode('utf-8').strip()
    return npath


def get_node_path():
    # /home/vagrant/.nvm/versions/node/v10.15.3/bin/npm
    #npath = os.path.expanduser('~/.nvm/versions/node/v10.15.3/bin/npm')
    res = subprocess.run('which node', shell=True, stdout=subprocess.PIPE)
    npath = res.stdout.decode('utf-8').strip()
    return npath


class HostVerifier:

    def __init__(self, args):
        self.args = args
        self.run()

    def run(self):
        self.verify_python()
        self.verify_docker()
        self.verify_npm()

    def verify_python(self):
        major = sys.version_info.major
        if major != 3:
            raise Exception('python3 must be used for this stack')

    def verify_docker(self):
        cmd = 'which docker'
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        if res.returncode != 0:
            raise Exception("docker was not found in your PATH")

        dockerbin = res.stdout.decode('utf-8').strip()
        res = subprocess.run(f'{dockerbin} --version', shell=True, stdout=subprocess.PIPE)
        version = res.stdout.decode('utf-8').split()[2]
        vmajor = int(version.split('.')[0])
        if vmajor < 19:
            raise Exception('docker version needs to be >= 19')

        if platform.system().lower() == 'darwin':
            settings_path = '~/Library/Group Containers/group.com.docker/settings.json'
            settings_path = os.path.expanduser(settings_path)
            with open(settings_path, 'r') as f:
                settings = json.loads(f.read())

            if 'filesharingDirectories' not in settings:
                raise Exception('dockerd is not configured to share any folders')

            shares = settings['filesharingDirectories']
            if shares != ['/Users']:
                msg = 'docker is configured to share more than /Users and this causes performance issues'
                raise Exception(msg)

            if settings['memoryMiB'] < 4000:
                raise Exception("the docker service needs at least 4GB of RAM")

    def verify_npm(self):
        npm = get_npm_path()
        if not npm:
            raise Exception('npm is not in your path, please install and configure NVM')

        res = subprocess.run(f'{npm} --version', shell=True, stdout=subprocess.PIPE)
        version = res.stdout.decode('utf-8').strip()

        node = get_node_path()
        if not npm:
            raise Exception('node is not in your path, please install and configure NVM')

        res = subprocess.run(f'{node} --version', shell=True, stdout=subprocess.PIPE)
        version = res.stdout.decode('utf-8').strip()
        vparts = version.split('.')
        vmajor = int(vparts[0].replace('v', ''))
        if vmajor < 10:
            raise Exception(f'found node version {version} which is not >= 10')


''' When npm install was run from the mac but is being used by webpack devserver in linux ...
| Child mini-css-extract-plugin node_modules/css-loader/dist/cjs.js!node_modules/sass-loader/dist/cjs.js!node_modules/@patternfly/react-core/node_modules/@patternfly/react-styles/css/components/Alert/alert.css:                                                                                                                                                
|     Entrypoint mini-css-extract-plugin = *                                                                                                                                                                                                                                                                                                                      
|     [./node_modules/css-loader/dist/cjs.js!./node_modules/sass-loader/dist/cjs.js!./node_modules/@patternfly/react-core/node_modules/@patternfly/react-styles/css/components/Alert/alert.css] 1.18 KiB {mini-css-extract-plugin} [built] [failed] [1 error]                                                                                                     
|                                                                                                                                                                  
|     ERROR in ./node_modules/@patternfly/react-core/node_modules/@patternfly/react-styles/css/components/Alert/alert.css (./node_modules/css-loader/dist/cjs.js!./node_modules/sass-loader/dist/cjs.js!./node_modules/@patternfly/react-core/node_modules/@patternfly/react-styles/css/components/Alert/alert.css)                                               
|     Module build failed (from ./node_modules/sass-loader/dist/cjs.js):                                                                                           
|     Error: Missing binding /app/node_modules/node-sass/vendor/linux-x64-64/binding.node                                                                          
|     Node Sass could not find a binding for your current environment: Linux 64-bit with Node.js 10.x                                                              
|                                                                                                                                                                                                                                                                                                                                                                 
|     Found bindings for the following environments:                                                                                                                                                                                                                                                                                                              
|       - OS X 64-bit with Node.js 10.x   
'''

class GenericFrontendComponent:

    _installed = False
    _built = False
    distdir = 'dist'
    www_app_name = None
    www_deploy_paths = None

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
        if 'all' in self.cb.args.static or self.www_app_name in self.cb.args.static:
            install = True

        if os.path.exists(os.path.join(self.srcpath, 'node_modules')):
            install = False

        # make sure node has the right arch bindings for the location this app
        # is going to run from if it's going to be run with webpack devserver ...
        if 'all' not in self.cb.args.static and self.www_app_name not in self.cb.args.static:
            nmpath = os.path.join(self.srcpath, 'node_modules')
            vendor_path = os.path.join(nmpath, 'node-sass', 'vendor')
            arches = glob.glob(f'{vendor_path}/*')
            arches = [os.path.basename(x) for x in arches]

            if arches == ['darwin-x64-64']:
                logger.warning(f'deleting {nmpath} because it has the wrong arch for linux')
                shutil.rmtree(nmpath)

        if not install:
            return

        cmd = ' '.join([get_npm_path(), 'install'])
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
        #if self.cb.args.static:
        if 'all' in self.cb.args.static or self.www_app_name in self.cb.args.static:
            build = True

        # aa & landing
        if os.path.exists(os.path.join(self.srcpath, 'dist')):
            build = False

        # chrome
        if os.path.exists(os.path.join(self.srcpath, 'build')):
            build = False

        if not build:
            return

        cmd = ' '.join([get_npm_path(), 'run', 'build'])
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
        '''
        if self.cb.args.static:
            wwwdir = os.path.join(self.cb.checkouts_root, 'www')
            appsdir = os.path.join(wwwdir, 'apps')
            src = os.path.join(self.srcpath, self.distdir)
            dst = os.path.join(appsdir, self.www_app_name)
            if os.path.exists(dst):
                shutil.rmtree(dst)
            logger.info(f'deploy {src} -> {dst}')
            shutil.copytree(src, dst)
        '''
        pass

    def postdeploy(self):
        pass

"""
insights_proxy| GET /apps/landing/js/App.js from http://webroot/apps/landing/js/App.js
webroot       | 2020/11/02 16:18:42 [error] 22#22: *19 open() "/usr/share/nginx/html/apps/landing/js/App.js" failed (2: No such file or directory), client: 172.29.0.6, server: localhost, request: "GET /apps/landing/js/App.js HTTP/1.1", host: "webroot", referrer: "https://prod.foo.redhat.com:8443/"
webroot       | 172.29.0.6 - - [02/Nov/2020:16:18:42 +0000] "GET /apps/landing/js/App.js HTTP/1.1" 404 555 "https://prod.foo.redhat.com:8443/" "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/85.0.4183.121 Safari/537.36" "-"  
"""
class LandingPageFrontend(GenericFrontendComponent):

    www_app_name = 'landing'
    www_deploy_paths = ['apps/landing']

    def configure(self):

        logger.info(f'configure {self.www_app_name}')

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


class InsightsChrome(GenericFrontendComponent):

    www_app_name = 'chrome'
    distdir = 'build'
    www_deploy_paths = ['apps/chrome']

    def configure(self):

        logger.info(f'configure {self.www_app_name}')

        constants_path = os.path.join(self.srcpath, 'src', 'js', 'jwt', 'constants.js')
        with open(constants_path, 'r') as f:
            cdata = f.read()
        cdata = cdata.replace('https://sso.redhat.com', self.cb.keycloak)
        with open(constants_path, 'w') as f:
            f.write(cdata)

    def postbuild(self):

        logger.info(f'postbuild {self.www_app_name}')

        # link the hashed css file to non-hashed
        if os.path.exists(os.path.join(self.srcpath, 'build', 'chrome.css')):
            os.remove(os.path.join(self.srcpath, 'build', 'chrome.css'))
        cmd = 'ln -s chrome.*.css chrome.css'
        logger.info(cmd)
        res = subprocess.run(cmd, cwd=os.path.join(self.srcpath, 'build'), shell=True)
        if res.returncode != 0:
            raise Exception('chrome.css symlinking failed')

        # link the hashed js file to non-hashed
        if os.path.exists(os.path.join(self.srcpath, 'build', 'js', 'chrome.js')):
            os.remove(os.path.join(self.srcpath, 'build', 'js', 'chrome.js'))
        cmd = 'ln -s chrome.*.js chrome.js'
        logger.info(cmd)
        res = subprocess.run(cmd, cwd=os.path.join(self.srcpath, 'build', 'js'), shell=True)
        if res.returncode != 0:
            raise Exception('chrome.js symlinking failed')


class TowerAnalyticsFrontend(GenericFrontendComponent):

    www_app_name = 'automation-analytics'
    www_deploy_paths = ['apps/automation-analytics', 'ansible/automation-analytics']

    def postdeploy(self):

        logger.info(f'postdeploy {self.www_app_name}')

        if self.cb.args.static:
            wwwdir = os.path.join(self.cb.checkouts_root, 'www')
            ansible_dir = os.path.join(wwwdir, 'ansible')
            if not os.path.exists(ansible_dir):
                os.makedirs(ansible_dir)
            '''
            if not os.path.exists(os.path.join(wwwdir, 'ansible', self.www_app_name)):
                cmd = f'ln -s ../apps/{self.www_app_name} {self.www_app_name}'
                res = subprocess.run(cmd, shell=True, cwd=ansible_dir)
                if res.returncode != 0:
                    raise Exception(f'symlink failed')
            '''

class CloudBuilder:
    frontend_services = None
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

        if self.args.awx:
            self.build_awx()
            #sys.exit(0)

        self.frontend_services = []
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
            self.frontend_services.append(gfc)

        self.make_spandx()
        #self.make_aa_frontend()
        self.make_aa_backend()
        self.make_www()
        self.make_entitlements()
        self.make_rbac()

        #if not self.args.skip_landing:
        #    self.make_landing()
        #if not self.args.skip_chrome:
        #    self.make_chrome(build=not self.args.skip_chrome_build, reset=not self.args.skip_chrome_reset)

        self.create_compose_file()

    def build_awx(self):
        git_url = 'https://github.com/ansible/awx'
        srcdir = os.path.join(self.checkouts_root, 'awx')
        if not os.path.exists(srcdir):
            cmd = f'git clone {git_url} {srcdir}'
            res = subprocess.run(cmd, shell=True)
            if res.returncode != 0:
                raise Exception(f'cloning {git_url} failed')
        
        # RESET ALL CHANGES
        cmd = 'git reset --hard'
        res = subprocess.run(cmd, cwd=srcdir, shell=True)
        if res.returncode != 0:
            raise Exception(f'git reset failed')

        # COPY THE SETTINGS FILE ...
        shutil.copy(
            os.path.join(srcdir, 'awx/settings/local_settings.py.docker_compose'),
            os.path.join(srcdir, 'awx/settings/local_settings.py')
        )

        # PATCH THE ANALYTICS GATHERING CODE TO SKIP LICENSE CHECK ...
        core_file = os.path.join(srcdir, 'awx/main/analytics/core.py')
        with open(core_file, 'r') as f:
            code = f.read()
        code = code.replace('\r\n', '\n')
        code = code.replace('def _valid_license():', 'def _valid_license():\n    return True\n')
        with open(core_file, 'w') as f:
            f.write(code)

        # BUILD THE UI ...
        makefile = os.path.join(srcdir, 'Makefile')
        node_modules_dir = os.path.join(srcdir, 'awx', 'ui', 'node_modules')
        static_dir = os.path.join(srcdir, 'awx', 'ui', 'static')
        if not os.path.exists(node_modules_dir) or not os.path.exists(static_dir):

            # $(NPM_BIN) --prefix awx/ui run build-devel -- $(MAKEFLAGS)
            with open(makefile, 'r') as f:
                makedata = f.read()
            makedata = makedata.replace(
                '$(NPM_BIN) --prefix awx/ui run build-devel -- $(MAKEFLAGS)',
                '$(NPM_BIN) --prefix awx/ui run build-devel'
            )
            with open(makefile, 'w') as f:
                f.write(makedata)

            cmd = 'make clean-ui'
            logger.info(cmd)
            res = subprocess.run(cmd, cwd=srcdir, shell=True)
            if res.returncode != 0:
                raise Exception(f'ui clean failed')

            cmd = 'make ui-devel'
            logger.info(cmd)
            #import epdb; epdb.st()
            res = subprocess.run(cmd, cwd=srcdir, shell=True)
            if res.returncode != 0:
                raise Exception(f'ui build failed')

        '''
        composefn = os.path.join(srcdir, 'tools', 'docker-compose.yml')
        with open(composefn, 'r') as f:
            compose = f.read()

        # GIT BRANCH
        cmd = f'cd {srcdir} && git rev-parse --abbrev-ref HEAD'
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        gbranch = res.stdout.decode('utf-8').strip()
        compose = compose.replace('${TAG}', gbranch)

        # CURRENT USER
        cmd = 'id -u'
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        uid = res.stdout.decode('utf-8').strip()
        compose = compose.replace('${CURRENT_UID}', '"' + uid + '"')

        # OS
        cmd = 'docker info | grep "Operatiing System"'
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        osname = res.stdout.decode('utf-8').strip()

        # TAG
        tag_base = 'gcr.io/ansible-tower-engineering'
        compose = compose.replace('${DEV_DOCKER_TAG_BASE}', tag_base)

        # VOLUMES 
        abs_src = os.path.abspath(srcdir)
        compose = compose.replace('../:/awx_devel', abs_src + '/:/awx_devel')
        compose = compose.replace('../awx/', os.path.join(abs_src, 'awx') + '/')
        compose = compose.replace('./docker-compose/', os.path.join(abs_src, 'docker-compose') + '/')
        compose = compose.replace('./redis/', os.path.join(abs_src, 'redis') + '/')
        #compose = compose.replace('"awx_db:', os.path.join(abs_src, '"awx_db'))
        #import epdb; epdb.st()

        with open(composefn, 'w') as f:
            f.write(compose)
        '''

        #sys.exit(1)

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

        ds['services'].update(self.get_tower_analytics_frontend_service())
        ds['services'].update(self.get_landing_services())
        #import epdb; epdb.st()

        # macs can't do static IPs
        if platform.system().lower() == 'darwin':
            ds.pop('networks', None)

        # Add squid for the mac users who can't directly connect to containers
        if not self.args.integration:
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

        if True:
            ds['services']['kcadmin'].pop('networks', None)
            ds['services']['sso.local.redhat.com'].pop('networks', None)
            ds['services']['sso.local.redhat.com'].pop('depends_on', None)

            pf = copy.deepcopy(ds['services']['insights_proxy'])
            pf['container_name'] = 'prod.foo.redhat.com'
            ds['services'].pop('insights_proxy', None)
            ds['services']['prod.foo.redhat.com'] = pf

        # if static, chrome/landing/frontend should be compiled and put into wwwroot
        if self.args.static:

            if 'all' in self.args.static or 'chrome' in self.args.static:
                ds['services'].pop('chrome', None)
                ds['services'].pop('chrome_beta', None)
            if 'all' in self.args.static or 'landing' in self.args.static:
                ds['services'].pop('landing', None)
            if 'all' in self.args.static or 'tower-analytics-frontend' in self.args.static:
                ds['services'].pop('aafrontend', None)

            for fc in self.frontend_services:
                if 'all' in self.args.static or fc.www_app_name in self.args.static:
                    for dp in fc.www_deploy_paths:
                        src = os.path.join(fc.srcpath, fc.distdir)
                        dst = f"/usr/share/nginx/html/{dp}"
                        volume = f"./{src}:{dst}"
                        ds['services']['webroot']['volumes'].append(volume)
                        #import epdb; epdb.st()


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


        # add the cloudnet network to all of the services ...
        #for k,v in ds['services'].items():
        #    ds['services'][k]['networks'] = ['awxcompose_default']
        #import epdb; epdb.st()

        if self.args.awx:
            ds['networks'] = {
                'default': {
                    'external': {
                        'name': 'tools_default',
                    }
                }
            }

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

        svcs = {}
        if 'all' not in self.args.static and 'landing' not in self.args.static:
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


    def get_tower_analytics_frontend_service(self):

        if 'all' in self.args.static or 'tower-analytics-frontend' in self.args.static:
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

        #pprint(fs)

        return {'tower-analytics-frontend': fs}

    def get_integration_compose(self):

        # pick a dockerfile based on the test framework selected
        def pick_dockerfile():
            if self.args.puppeteer:
                return 'Dockerfile.puppeteer'
            if self.args.cypress or self.args.cypress_debug:
                return 'Dockerfile.cypress'
            return 'Dockerfile'

        # build the entrypoing/command for the container ...

        ipath = os.path.join(self.checkouts_root, 'integration_tests')
        srcpath = os.path.join(self.checkouts_root, 'tower-analytics-frontend')
        
        wscript = os.path.join(srcpath, 'wait_for_stack.sh')
        if not os.path.exists(wscript):
            shutil.copy(os.path.join(ipath, 'wait_for_stack.sh'), wscript)

        basecmd = '/bin/bash -c "cd /app && npm install && ./wait_for_stack.sh && timeout -s SIGKILL 1000s '
        if self.args.puppeteer:
            testcmd = basecmd + 'npm run tests:integration:puppeteer"'
        elif self.args.cypress or self.args.cypress_debug:
            testcmd = basecmd + 'cypress run --headless --browser chrome --spec cypress/integration/automation-analytics.js"'
        else:
            testcmd = basecmd + './node_modules/jest/bin/jest.js src/index.test.js"'

        svc = {
            'container_name': 'integration',
            'image': 'aa_integration:latest',
            'build': {
                'context': './srv/integration_tests',
                'dockerfile': pick_dockerfile()
            },
            'volumes': [f"./{srcpath}:/app:rw"],
            'user': self.get_node_container_user(),
            'entrypoint': '',
            'depends_on': ['sso.local.redhat.com', 'kcadmin', 'aafrontend', 'aabackend'],
            'command': testcmd,
            'environment': {
                'CYPRESS_CLOUD_BASE_URL': 'https://prod.foo.redhat.com:8443',
                'CYPRESS_CLOUD_USERNAME': 'bob',
                'CYPRESS_CLOUD_PASSWORD': 'redhat1234'
            }
        }

        # these are very important for cypress to work in a container ...
        svc['ipc'] = 'host'
        svc['cap_add'] = ['SYS_ADMIN']

        # is the frontend standalone or in webroot?
        if 'all' in self.args.static or 'tower-analytics-frontend' in self.args.static:
            svc['depends_on'].remove('aafrontend')

        return svc

    def make_spandx(self):

        logger.info('generate spandx.js')

        stemp = SPANDX_TEMPLATE

        #if not self.args.static:
        if 'all' not in self.args.static and 'tower-analytics-frontend' not in self.args.static:
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

        if self.args.static:
            stlines = stemp.split('\n')
            for idx,x in enumerate(stlines):
                if '/chrome' in x and ('all' in self.args.static or 'chrome' in self.args.static):
                    stlines[idx] = x.replace('http://chrome', 'http://webroot')
                elif 'beta/apps/landing' in x and ('all' in self.args.static or 'landing' in self.args.static):
                    stlines[idx] = x.replace('http://landing_beta', 'http://webroot')
                elif 'landing' in x and ('all' in self.args.static or 'landing' in self.args.static):
                    stlines[idx] = x.replace('https://landing:8002', 'http://webroot')
                elif 'analytics' in x and not '/api' in x and ('all' in self.args.static or 'tower-analytics-frontend' in self.args.static):
                    stlines[idx] = x.replace('FRONTEND', 'http://webroot')

            stemp = '\n'.join(stlines)
            #import epdb; epdb.st()

        with open(os.path.join(self.webroot, 'spandx.config.js'), 'w') as f:
            f.write(stemp)

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
    parser.add_argument('--frontend_address', help="use local or remote address for frontend")
    parser.add_argument('--frontend_hash', help="what aa frontend hash to use")
    parser.add_argument('--frontend_path', help="path to an aa frontend checkout")
    parser.add_argument('--backend_address', help="use local or remote address for backend")
    parser.add_argument('--backend_hash', help="what aa backend hash to use")
    parser.add_argument('--backend_path', help="path to an aa backend checkout")
    parser.add_argument('--backend_mock', action='store_true', help="use the mock backend")
    parser.add_argument(
        '--static',
        action='append',
        default=[],
        choices=['all', 'chrome', 'landing', 'automation-analytics'],
        help="do not use webpack dev server where possible"
    )
    parser.add_argument('--integration', action='store_true')
    parser.add_argument('--puppeteer', action='store_true')
    parser.add_argument('--cypress', action='store_true')
    parser.add_argument('--cypress_debug', action='store_true')
    parser.add_argument('--awx', action='store_true')

    args = parser.parse_args()

    HostVerifier(args)

    logger.info("starting cloudbuilder")
    cbuilder = CloudBuilder(args=args)


if __name__ == "__main__":
    main()
