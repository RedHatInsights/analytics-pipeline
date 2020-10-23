#!/bin/bash

# need curl ...
which curl
RC=$?
if [[ $RC -ne 0 ]]; then
    apt -y update
    apt -y install curl
fi


SSO="https://sso.local.redhat.com:8443"
KCADMIN="http://172.23.0.4"
CRHC="https://prod.foo.redhat.com:8443"
CLUSTERS="https://prod.foo.redhat.com:8443/ansible/automation-analytics/clusters"

COUNT=0
MAXCOUNT=100
FINAL_RC=1
while true; do
    echo "####################################"
    echo "# WAITING FOR SERVICES: $COUNT"
    echo "####################################"
    curl -k -v --connect-timeout 2 $SSO
    SSO_RC=$?
    curl -k -v --connect-timeout 2 $KCADMIN
    KCADMIN_RC=$?
    curl -k -v --connect-timeout 2 $CRHC
    CRHC_RC=$?
    curl -k -v --connect-timeout 2 $CLUSTERS > /tmp/clusters.html
    CLUSTERS_RC=$?
    fgrep -i 'cannot get /ansible/automation-analytics' /tmp/clusters.html
    GREP_RC=$?

    ((COUNT=COUNT+1))

    if [[ $SSO_RC -eq 0 && $KCADMIN_RC -eq 0 && $CHRC_RC -eq 0 && $CLUSTERS_RC -eq 0  && $GREP_RC -eq 1 ]]; then
        echo "ALL SERVICES ARE AVAILABLE. WAITING 60s ..."
        # wait a bit longer and then exit ...
        sleep 10
        exit 0
    fi

    if [[ $COUNT -eq $MAXCOUNT ]]; then
        exit 1
    fi

    sleep 10
done

