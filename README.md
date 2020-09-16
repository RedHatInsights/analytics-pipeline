# Local automation analytics stack maker

Assembles and builds and runs the entire stack for automation-analytics including chrome,landing and sso.

## How to use

**Make sure you have a functioning docker (not podman) setup. Ubuntu virtual machines are great for this.**

    virtualenv --python=$(which python3) venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install --upgrade docker-compose
    make stack

