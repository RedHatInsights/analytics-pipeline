# Local automation analytics stack maker

Assembles and builds and runs the entire stack for automation-analytics including chrome,landing and sso.

## Why

To make it easier on AA developers and CI to spin up the full stack without leaking senstive information
to the public internet. It's also a good intro to how sso/insights-platform/insights-chrome are connected
to analytics and vice versa.

Fault injection is another huge capability of this system. When happens when you have a valid sso user but isn't
entitled for automation? You can find out. What happens when sso is down? You can find out. What happens when 
the backend returns large amounts of data? You can find out.

## How to use

**Make sure you have a functioning docker (not podman) setup. Ubuntu virtual machines are great for this.**

    virtualenv --python=$(which python3) venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install --upgrade docker-compose
    make stack

## keycloak

Keycloak is the magic behind sso.redhat.com. It's a java based service that handles identity and authorization.
When a user logs into keycloak through with a valid realm and client, they can obtain an encoded/encrypted token.
This token can contain attributes about the user such as their account number and orgid. Insights chrome actually
pulls those attributes out of the token and sets a cookie in the browser for each and those are used throughout
the rest of the stack for user verification (specifically the account number).

This stack will create a local keycloak instance, with the realm and client setup along with a default user "bob"
with password "redhat1234".

## tool.py

Getting all the bits necessary to use a local keycloak instance for disconnected SSO are complicated. The steps are
more complicated than what could exist in docker compose file also. Therefore tool.py was written to abstact all those
steps and put bits where they need to be, to configure those bits, to build the bits and to create the appropriate
docker compose file.

## aa_backend_mock

Due to speed concerns when hacking on this project, the real analytics backend was dropped in favor of a mock written
in flask which serves out static fixture data. tool.py has a few options to allow the user to specify a backend url
or a hash, but those features are not yet fully implemented and will raise an exception.

The plan is to have tool.py, if given the option, bring in a real backend checkout and aggregate it's docker compose
information into the generated docker compose such that everything comes up together.


