#!/usr/bin/env python

import pexpect


def main():
    cmd = 'awx-manage createsuperuser --no-color --user admin --email root@localhost'
    cmd = f"docker exec -it tools_awx_1 /bin/bash -c \"{cmd}\""

    child = pexpect.spawn(cmd)

    print('waiting for password:')
    child.expect('Password:')
    child.sendline('redhat1234')
    print('waiting for password again:')
    child.expect('Password (again):')
    child.sendline('redhat1234')



if __name__ == "__main__":
    main()
