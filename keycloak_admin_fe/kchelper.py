#!/usr/bin/env python3

import os
import json
import time
from pprint import pprint

import requests
import keycloak


class KeyCloakHelper:

    def __init__(self, server, username, password):
        self.server = server
        self.username = username
        self.password = password

    def get_mapper(self, attribute, mtype='String'):
        mapper = {
            'name': attribute,
            'id': attribute,
            'protocol': 'openid-connect',
            'protocolMapper': 'oidc-usermodel-attribute-mapper',
            'consentRequired': False,
            'config': {
                'userinfo.token.claim': True,
                'user.attribute': attribute,
                'id.token.claim': True,
                'access.token.claim': True,
                'claim.name': attribute,
                'jsonType.label': mtype
            } 
        }
        return mapper


    def get_admin_object(self):
        return keycloak.KeycloakAdmin(
                self.server + '/auth/',
                username=self.username,
                password=self.password,
                verify=False
            )

    def get_realms(self):
        admin = self.get_admin_object()
        return admin.get_realms()

    def get_realm_users(self, realm):
        radmin = self.get_realm_admin(realm)
        users = radmin.get_users()
        return users

    def get_all_users(self):
        realms = self.get_realms()
        rusers = []
        for realm in realms:
            _rusers = self.get_realm_users(realm['realm'])
            for idx, x in enumerate(_rusers):
                _rusers[idx]['realm'] = realm['realm']
                if not 'attributes' in x:
                    _rusers[idx]['attributes'] = {
                        'first_name': None,
                        'last_name': None,
                        'org_id': None,
                        'account_number': None
                    }
            rusers += _rusers
        return rusers

    def get_realm_admin(self, realm):
        radmin = keycloak.KeycloakAdmin(
                self.server + '/auth/',
                realm_name=realm,
                user_realm_name='master',
                username=self.username,
                password=self.password,
                verify=False
            )
        return radmin

    def create_realm_client(self, realm, client):
        radmin = self.get_realm_admin(realm)
        protocol_mappers = [
            self.get_mapper('account_number', mtype='int'),
            self.get_mapper('account_id', mtype='int'),
            self.get_mapper('org_id', mtype='int'),
            self.get_mapper('username', mtype='String'),
            self.get_mapper('email', mtype='String'),
            self.get_mapper('first_name', mtype='String'),
            self.get_mapper('last_name', mtype='String')
        ]

        # TODO: service accouts enabled == True, authorization enabled = True
        radmin.create_client({
                'clientId': client,
                'enabled': True,
                'bearerOnly': False,
                'publicClient': True,
                'rootUrl': 'https://prod.foo.redhat.com:1337',
                'baseUrl': 'https://prod.foo.redhat.com:1337',
                'redirectUris': ['https://prod.foo.redhat.com:1337/*'],
                'protocolMappers': protocol_mappers
            })

    def create_realm_user(self, realm, uname, password, fname, lname, email, account_id, org_id):
        radmin = self.get_realm_admin(realm)
        radmin.create_user({
            'enabled': True,
            'username': uname,
            'firstName': fname,
            'lastName': lname,
            'email': email,
            'attributes': {
                'first_name': fname,
                'last_name': lname,
                'account_id': account_id,
                'account_number': account_id,
                'org_id': org_id
            },
            'credentials': [{
                'temporary': False,
                'type': 'password',
                'value': password
            }]
        })
