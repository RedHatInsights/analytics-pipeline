#!/bin/bash

set -x

if [ ! -f ssh.config ]; then
    vagrant ssh-config > ssh.config
fi

ssh -D 1337 -q -C -N -F ssh.config default
