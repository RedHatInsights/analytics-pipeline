#!/bin/bash

# need curl ...
which curl
RC=$?
if [[ $RC -ne 0 ]]; then
    apt -y update
    apt -y install curl
fi


SSO="https://sso.local.redhat.com:8443"
KCADMIN="http://kcadmin"
CRHC="https://prod.foo.redhat.com:8443"
CLUSTERS="https://prod.foo.redhat.com:8443/ansible/automation-analytics/clusters"

COUNT=0
MAXCOUNT=100
FINAL_RC=1
while true; do
    echo "####################################"
    echo "# CHECKING SERVICES: $COUNT"
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

    if [[ $SSO_RC -ne 0 ]]; then
        echo "STILL WAITING FOR SSO"
    fi

    if [[ $KCADMIN_RC -ne 0 ]]; then
        echo "STILL WAITING FOR KCADMIN"
    fi

    if [[ $CLUSTERS_RC -ne 0 ]]; then
        echo "STILL WAITING FOR CLUSTERS"
    fi

    if [[ $GREP_RC -eq 0 ]]; then
        echo "STILL WAITING FOR CLEAN HTML ($GREP_RC)"
    fi

    echo "sso:$SSO_RC kcadmin:$KCADMIN_RC cloud:$CHRC_RC clusters:$CLUSTERS_RC get:$GREP_RC"

    if [[ $SSO_RC -eq 0 && $KCADMIN_RC -eq 0 && $CHRC_RC -eq 0 && $CLUSTERS_RC -eq 0  && $GREP_RC -ne 0 ]]; then
        echo "ALL SERVICES ARE AVAILABLE. WAITING 10s ..."
        # wait a bit longer and then exit ...
        sleep 10
        exit 0
    fi

    if [[ $COUNT -eq $MAXCOUNT ]]; then
        exit 1
    fi

    sleep 10
done

