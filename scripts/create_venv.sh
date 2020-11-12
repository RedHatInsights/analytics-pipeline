#!/bin/bash -x

PY3=$(which python3)
PY3_PIP=$(dirname $PY3)/pip3
BASEDIR=$(pwd)
VENVDIR=$BASEDIR/venv
VENV_PIPBIN=$VENVDIR/bin/pip3
CACHEDIR=$BASEDIR/.cache
INSTALLDIR=$BASEDIR/.python3
SRCURL="https://www.python.org/ftp/python/3.9.0/Python-3.9.0.tgz"
TAR=$(basename $SRCURL)
SRC=$(echo $TAR | sed 's/\.tgz//')

OS=$(uname)

function install_anaconda3 {
    if [[ ! -d $CACHEDIR ]]; then
        mkdir -p $CACHEDIR
    fi
    cd $CACHEDIR

    URL="https://repo.anaconda.com/archive/Anaconda3-2020.07-MacOSX-x86_64.sh"
    INSTALLER=$(basename $URL)

    if [[ ! -f $INSTALLER ]]; then
        curl -o $INSTALLER $URL
        chmod +x $INSTALLER
    fi

    if [[ ! -d $INSTALLDIR ]]; then
        ./$INSTALLER -b -p $INSTALLDIR
    fi

    cd $BASEDIR
}

function check_virtualenv_module {
    $PY3 -m virtualenv --help
    RC=$?
    return $RC
}


if [[ $OS == "Darwin" || -z $PY3 ]]; then
    install_anaconda3
    PY3=$INSTALLDIR/bin/python3
    PY3_PIP=$(dirname $PY3)/pip3
fi

if [[ ! -d $VENVDIR ]]; then
    check_virtualevenv_module || $PY3_PIP install --user virtualenv
    $PY3 -m virtualenv $VENVDIR
fi

$VENV_PIPBIN install -r requirements.txt
