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


def get_vagrant_ssh_config(boxpath):
    cfgfile = os.path.join(boxpath, 'ssh_cfg.json')
    txtfile = os.path.join(boxpath, 'ssh.cfg')

    if not os.path.exists(cfgfile) or not os.path.exists(txtfile):
        cfg_cmd = f'cd {boxpath} ; vagrant ssh-config'
        res = subprocess.run(cfg_cmd, shell=True, stdout=subprocess.PIPE)
        lines = res.stdout.decode('utf-8').split('\n')
        lines = [x.strip() for x in lines if x.strip()]

        with open(txtfile, 'w') as f:
            f.write(res.stdout.decode('utf-8'))

        cfg = {}
        for line in lines:
            parts = line.split(None, 1)
            cfg[parts[0]] = parts[1]
        with open(cfgfile, 'w') as f:
            f.write(json.dumps(cfg))
    
    with open(cfgfile, 'r') as f:
        cfg = json.loads(f.read())

    return cfg


def vagrant_scp_to(boxpath, src, dst):

    cfg = get_vagrant_ssh_config(boxpath)

    basecmd = f"scp -rp"
    basecmd += f" -i {cfg['IdentityFile']}"
    basecmd += f" -o StrictHostKeyChecking=no"
    basecmd += f" -o PasswordAuthentication=no"
    basecmd += f" -o UserKnownHostsFile=/dev/null"
    basecmd += f" -P {cfg['Port']}"
    basecmd += f" {src} {cfg['User']}@{cfg['HostName']}:{dst}"

    print(basecmd)
    res = subprocess.run(basecmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise Exception(f'{basecmd} failed: {res.stderr.decode("utf-8")}')
    return (res.returncode, res.stdout.decode('utf-8'), res.stderr.decode('utf-8'))


def vagrant_ssh(boxpath, cmd):

    cfg = get_vagrant_ssh_config(boxpath)

    '''
    basecmd = f"ssh -i {cfg['IdentityFile']}"
    basecmd += f" -o StrictHostKeyChecking=no"
    basecmd += f" -o PasswordAuthentication=no"
    #basecmd += f" -o UserKnownHostsFile=/dev/null"
    basecmd += f" -p {cfg['Port']}"
    basecmd += " -tt"
    basecmd += f" {cfg['User']}@{cfg['HostName']}"
    '''
    basecmd = f"ssh -F {os.path.join(boxpath, 'ssh.cfg')} default"

    sshcmd = f"{basecmd} '{cmd}'"
    print('#' * 100)
    print(sshcmd)
    print('#' * 100)
    res = subprocess.run(sshcmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return (res.returncode, res.stdout.decode('utf-8'), res.stderr.decode('utf-8'))


def parse_cli_listing(stdout):
    if not stdout.strip():
        return []
    
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

    def __init__(self, boxpath):
        self.boxpath = boxpath
        #self.check_ssh()
        self.get_admin_password()
        self.install_towercli()
        self.towercli_login()

        self.make_inventory()
        self.make_hosts()
        self.make_manual_project()
        self.make_job_template()

    def check_ssh(self):
        vagrant_ssh(self.boxpath, 'whoami')
        vagrant_ssh(self.boxpath, 'sudo whoami')

    def get_admin_password(self):
        res = vagrant_ssh(self.boxpath, 'cat /etc/profile.d/ansible-tower.sh | fgrep -i password')
        pprint(res)
        assert res[0] == 0
        self.tower_password = res[1].strip().split()[-2].strip()

    def install_towercli(self):
        pprint(vagrant_ssh(self.boxpath, 'which tower-cli || sudo pip3 install ansible-tower-cli'))

    def towercli_login(self):
        pprint(vagrant_ssh(self.boxpath, "tower-cli config verify_ssl false"))
        login_command = f"tower-cli login --password {self.tower_password} admin"
        #print(login_command)
        pprint(vagrant_ssh(self.boxpath, login_command))

    def get_inventories(self):
        (rc, so, se) = vagrant_ssh(self.boxpath, "tower-cli inventory list")
        lines = so.split('\n')
        lines = [x.strip() for x in lines if x.strip() and '=' not in x and 'name' not in x]

        inventories = {}
        for line in lines:
            parts = line.split(None, 1)
            thisid = int(parts[0])
            thisname = parts[1][::-1].split(None, 1)[-1]
            thisname = thisname[::-1]
            inventories[thisid] = thisname

        return inventories

    def make_inventory(self):
        (rc, so, se) = vagrant_ssh(self.boxpath, "tower-cli inventory list")
        lines = so.split('\n')
        lines = [x.strip() for x in lines if x.strip() and '=' not in x and 'name' not in x]

        inventories = {}
        for line in lines:
            parts = line.split(None, 1)
            thisid = int(parts[0])
            thisname = parts[1][::-1].split(None, 1)[-1]
            thisname = thisname[::-1]
            inventories[thisid] = thisname

        pprint(inventories)

        if 'test_inventory' not in inventories.values():
            cmd = f"tower-cli inventory create --name=test_inventory --organization=1"
            (rc, so, se) = vagrant_ssh(self.boxpath, cmd)
            if rc != 0:
                raise Exception('inventory create failed')

    def make_hosts(self):
        (rc, so, se) = vagrant_ssh(self.boxpath, "tower-cli host list --all-pages")
        lines = so.split('\n')
        lines = [x.strip() for x in lines if x.strip() and '=' not in x and 'name' not in x]

        hosts = {}
        for line in lines:
            parts = line.split()
            thisid = int(parts[0])
            thisname = parts[1]
            invid = int(parts[2])
            hosts[thisid] = {'name': thisname, 'inventory_id': invid}

        pprint(hosts)
        hkeys = sorted(list(hosts.keys()))

        if len(hosts) < 10000:
            inventories = self.get_inventories()
            ti = [x for x in inventories.items() if x[1] == 'test_inventory']
            ti = ti[0][0]
            for x in range(hkeys[-1], 10000):
                thisname = f"host-{x}"
                cmd = f"tower-cli host create --name={thisname} --inventory={ti}"
                (rc, so, se) = vagrant_ssh(self.boxpath, cmd)
                if rc != 0:
                    raise Exception(se)

    def make_manual_project(self):
        (rc, so, se) = vagrant_ssh(self.boxpath, "tower-cli project list")
        projects = parse_cli_listing(so)
        pnames = [x['name'] for x in projects]
        if 'test_project' not in pnames:
            cmd = f"tower-cli project create"
            cmd += " --name=test_project"
            cmd += " --organization=1"
            cmd += " --scm-type manual"
            cmd += " --local-path=test_project"
            cmd += " --force-on-exists"
            pprint(vagrant_ssh(self.boxpath, cmd))

        (rc, so, se) = vagrant_ssh(self.boxpath, "sudo chmod 777 /var/lib/awx/projects")
        (rc, so, se) = vagrant_ssh(self.boxpath, "[ -d /var/lib/awx/projects/test_project ]")
        if rc != 0:
            (rc, so, se) = vagrant_ssh(self.boxpath, "sudo mkdir -p /var/lib/awx/projects/test_project")
            (rc, so, se) = vagrant_ssh(self.boxpath, "sudo chmod -R 777 /var/lib/awx/projects/test_project")
        (rc, so, se) = vagrant_ssh(self.boxpath, "[ -f /var/lib/awx/projects/test_project/site.yml ]")
        if rc != 0:
            td = tempfile.mkdtemp()
            src = os.path.join(td, 'site.yml')
            with open(src, 'w') as f:
                f.write(SIMPLE_PLAYBOOK)
            (rc, so, se) = vagrant_scp_to(self.boxpath, src, '/var/lib/awx/projects/test_project/site.yml')
            shutil.rmtree(td)

    def make_job_template(self):

        (rc, so, se) = vagrant_ssh(self.boxpath, "tower-cli job_template list")
        templates = parse_cli_listing(so)
        tnames = [x['name'] for x in templates]

        if 'test_template' not in tnames:
            (rc, so, se) = vagrant_ssh(self.boxpath, "tower-cli inventory list")
            inventories = parse_cli_listing(so)
            if inventories:
                iid = [x['id'] for x in inventories if x['name'] == 'test_inventory'][0]
            else:
                raise Exception('NO INVENTORIES!')

            (rc, so, se) = vagrant_ssh(self.boxpath, "tower-cli project list")
            projects = parse_cli_listing(so)
            pid = [x['id'] for x in projects if x['name'] == 'test_project'][0]

            cmd =  f"tower-cli job_template create"
            cmd += " --name=test_template"
            cmd += f" --project={pid}"
            cmd += f" --inventory={iid}"
            cmd += " --job-type=run"
            cmd += " --playbook=site.yml"

            pprint(vagrant_ssh(self.boxpath, cmd))

    def _no_file(self):
        '''
        with open('/tmp/test.txt', 'w') as f:
            f.write('testme\n')
        pprint(vagrant_scp_to(boxpath, '/tmp/test.txt', '/tmp/test.txt'))
        '''
        pass


def main():
    boxpath = os.path.expanduser('~/vagrant.boxes/tower373')
    AT = Tower(boxpath)



if __name__  == "__main__":
    main()
