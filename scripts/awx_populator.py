#!/usr/bin/env python

import json
import os
import shutil
import subprocess
import tempfile

from pprint import pprint

SIMPLE_PLAYBOOK = '''
- hosts: all
  connection: local
  gather_facts: False
  tasks:
    - ping:
'''


def docker_scp_to(container, src, dst):

    '''
    basecmd = f"scp -rp"
    basecmd += f" -i {cfg['IdentityFile']}"
    basecmd += f" -o StrictHostKeyChecking=no"
    basecmd += f" -o PasswordAuthentication=no"
    basecmd += f" -o UserKnownHostsFile=/dev/null"
    basecmd += f" -P {cfg['Port']}"
    basecmd += f" {src} {cfg['User']}@{cfg['HostName']}:{dst}"
    '''

    basecmd = f'docker cp {src} {container}:{dst}'
    print(basecmd)
    res = subprocess.run(basecmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return (res.returncode, res.stdout.decode('utf-8'), res.stderr.decode('utf-8'))


def docker_ssh(container, cmd):

    #basecmd = f"ssh -F {os.path.join(boxpath, 'ssh.cfg')} default"
    #sshcmd = f"{basecmd} '{cmd}'"

    if 'pip' not in cmd and 'tower-cli' in cmd:
        cmd = cmd.replace('tower-cli', '~/.local/bin/awx-cli')

    sshcmd = f'docker exec -it {container} /bin/bash -c "{cmd}"'

    print('#' * 100)
    print(sshcmd)
    print('#' * 100)
    res = subprocess.run(sshcmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return (res.returncode, res.stdout.decode('utf-8'), res.stderr.decode('utf-8'))


def parse_cli_listing(stdout):
    lines = stdout.split('\n')
    header = lines[0].rstrip()
    titles = lines[1].rstrip()
    markers = []
    for idx,x in enumerate(header):
        if x == " " or idx == len(header):
            markers.append(idx)
    markers.append(None)

    _titles = []
    for idm,marker in enumerate(markers):
        start = 0
        end = marker
        if idm > 0:
            start = markers[idm-1]
        if idm == len(markers):
            end = None
        print(start, end)
        _titles.append(titles[start:end].strip())

    bits = []
    for line in lines[2:]:
        if not line.strip():
            continue
        if line.strip().startswith('='):
            continue
        line = line.rstrip()
        print(line)
        ds = {}
        for idm,marker in enumerate(markers):
            start = 0
            end = marker
            if idm > 0:
                start = markers[idm-1]
            if idm == len(markers):
                end = None
            val = line[start:end].strip()
            ds[_titles[idm]] = val
        bits.append(ds)

    return bits



class Tower:
    boxpath = None
    tower_password = None

    def __init__(self, container):
        self.container = container
        #self.check_ssh()
        self.get_admin_password()
        self.install_towercli()
        self.towercli_login()

        self.make_org()
        self.make_inventory()
        self.make_hosts()
        self.make_manual_project()
        self.make_job_template()

    def check_ssh(self):
        #docker_ssh(self.container, 'whoami')
        #docker_ssh(self.container, 'sudo whoami')
        pass

    def get_admin_password(self):
        #res = docker_ssh(self.container, 'cat /etc/profile.d/ansible-tower.sh | fgrep -i password')
        #pprint(res)
        #assert res[0] == 0
        #self.tower_password = res[1].strip().split()[-2].strip()
        self.tower_password = 'redhat1234'

    def install_towercli(self):
        pprint(docker_ssh(self.container, 'which tower-cli || pip3 install --user ansible-tower-cli'))

    def towercli_login(self):
        pprint(docker_ssh(self.container, "tower-cli config verify_ssl false"))
        pprint(docker_ssh(self.container, "tower-cli config host https://awx:8043"))
        login_command = f"tower-cli login --password {self.tower_password} admin"
        #print(login_command)
        pprint(docker_ssh(self.container, login_command))

    def make_org(self):
        (rc, so, se) = docker_ssh(self.container, "tower-cli organization list")
        orgs = {}
        if not 'No records found' in so:
            lines = so.split('\n')
            lines = [x.strip() for x in lines if x.strip() and '=' not in x and 'name' not in x]

            for line in lines:
                parts = line.split(None, 1)
                thisid = int(parts[0])
                thisname = parts[1][::-1].split(None, 1)[-1]
                thisname = thisname[::-1]
                orgs[thisid] = thisname

        if not orgs:
            (rc, so, se) = docker_ssh(self.container, "tower-cli organization create --name=default")
            #import epdb; epdb.st()

    def get_inventories(self):
        (rc, so, se) = docker_ssh(self.container, "tower-cli inventory list")
        inventories = {}
        if not 'No records found' in so:
            lines = so.split('\n')
            lines = [x.strip() for x in lines if x.strip() and '=' not in x and 'name' not in x]

            for line in lines:
                parts = line.split(None, 1)
                thisid = int(parts[0])
                thisname = parts[1][::-1].split(None, 1)[-1]
                thisname = thisname[::-1]
                inventories[thisid] = thisname

        return inventories

    def make_inventory(self):
        (rc, so, se) = docker_ssh(self.container, "tower-cli inventory list")
        inventories = {}
        if 'No records found' not in so:
            lines = so.split('\n')
            lines = [x.strip() for x in lines if x.strip() and '=' not in x and 'name' not in x]
            pprint(lines)
            for line in lines:
                parts = line.split(None, 1)
                print(parts)
                thisid = int(parts[0])
                thisname = parts[1][::-1].split(None, 1)[-1]
                thisname = thisname[::-1]
                inventories[thisid] = thisname

        if 'test_inventory' not in inventories.values():
            cmd = f"tower-cli inventory create --name=test_inventory --organization=1"
            (rc, so, se) = docker_ssh(self.container, cmd)
            print(rc)
            print(so)
            print(se)

    def make_hosts(self):
        (rc, so, se) = docker_ssh(self.container, "tower-cli host list")

        hosts = {}
        if 'No records found' not in so:
            lines = so.split('\n')
            lines = [x.strip() for x in lines if x.strip() and '=' not in x and 'name' not in x]
            for line in lines:
                parts = line.split()
                thisid = int(parts[0])
                thisname = parts[1]
                invid = int(parts[2])
                hosts[thisid] = {'name': thisname, 'inventory_id': invid}

        if len(hosts) == 0:
            inventories = self.get_inventories()
            #import epdb; epdb.st()
            ti = [x for x in inventories.items() if x[1] == 'test_inventory']
            ti = ti[0][0]
            #import epdb; epdb.st()
            for x in range(0, 101):
                thisname = f"host-{x}"
                cmd = f"tower-cli host create --name={thisname} --inventory={ti}"
                pprint(docker_ssh(self.container, cmd))
                #import epdb; epdb.st()

    def make_manual_project(self):
        (rc, so, se) = docker_ssh(self.container, "tower-cli project list")
        projects = parse_cli_listing(so)
        pnames = [x['name'] for x in projects]
        if 'test_project' not in pnames:
            cmd = f"tower-cli project create"
            cmd += " --name=test_project"
            cmd += " --organization=1"
            cmd += " --scm-type manual"
            cmd += " --local-path=test_project"
            cmd += " --force-on-exists"
            pprint(docker_ssh(self.container, cmd))

        (rc, so, se) = docker_ssh(self.container, "ls -al /var/lib/awx/projects/test_project")
        if rc != 0:
            (rc, so, se) = docker_ssh(self.container, "mkdir -p /var/lib/awx/projects/test_project")
            (rc, so, se) = docker_ssh(self.container, "chmod -R 777 /var/lib/awx/projects/test_project")
        (rc, so, se) = docker_ssh(self.container, "ls -al /var/lib/awx/projects/test_project/site.yml")
        if rc != 0:
            td = tempfile.mkdtemp()
            src = os.path.join(td, 'site.yml')
            with open(src, 'w') as f:
                f.write(SIMPLE_PLAYBOOK)
            (rc, so, se) = docker_scp_to(self.container, src, '/var/lib/awx/projects/test_project/site.yml')
            shutil.rmtree(td)

    def make_job_template(self):

        (rc, so, se) = docker_ssh(self.container, "tower-cli job_template list")
        templates = parse_cli_listing(so)
        tnames = [x['name'] for x in templates]

        if 'test_template' not in tnames:
            (rc, so, se) = docker_ssh(self.container, "tower-cli inventory list")
            inventories = parse_cli_listing(so)
            iid = [x['id'] for x in inventories if x['name'] == 'test_inventory'][0]
            (rc, so, se) = docker_ssh(self.container, "tower-cli project list")
            projects = parse_cli_listing(so)
            pid = [x['id'] for x in projects if x['name'] == 'test_project'][0]

            cmd =  f"tower-cli job_template create"
            cmd += " --name=test_template"
            cmd += f" --project={pid}"
            cmd += f" --inventory={iid}"
            cmd += " --job-type=run"
            cmd += " --playbook=site.yml"

            pprint(docker_ssh(self.container, cmd))

    def _no_file(self):
        '''
        with open('/tmp/test.txt', 'w') as f:
            f.write('testme\n')
        pprint(docker_scp_to(boxpath, '/tmp/test.txt', '/tmp/test.txt'))
        '''
        pass


def main():
    AT = Tower('tools_awx_1')



if __name__  == "__main__":
    main()
