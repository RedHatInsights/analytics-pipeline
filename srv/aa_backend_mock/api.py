#!/usr/bin/env python3

import os
import json

import flask
from flask import Flask
from flask import jsonify
from flask import request
from flask import redirect

from pprint import pprint
#import sockjs_flask

app = Flask(__name__)


@app.route('/')
def hello():
    return "Hello World!"


@app.route('/api/entitlements/v1/services')
def services():
    with open('api_payloads/services.json', 'r') as f:
        data = json.loads(f.read())
    return jsonify(data)


@app.route('/api/rbac/v1/access/')
def rbac_access():
    with open('api_payloads/rbac.json', 'r') as f:
        data = json.loads(f.read())
    return jsonify(data)


@app.route('/api/tower-analytics/authorized/')
@app.route('/api/tower-analytics/v0/authorized/')
def api_aa_authorized():
    return jsonify({'msg': 'Authorized'})


@app.route('/api/tower-analytics/chart30/')
@app.route('/api/tower-analytics/v0/chart30/')
def api_aa_chart30():
    with open('api_payloads/chart30.json', 'r') as f:
        data = json.loads(f.read())
    return jsonify(data)


@app.route('/api/tower-analytics/clusters/')
@app.route('/api/tower-analytics/v0/clusters/')
def api_aa_clusters():
    with open('api_payloads/clusters.json', 'r') as f:
        data = json.loads(f.read())
    return jsonify(data)


@app.route('/api/tower-analytics/templates/')
@app.route('/api/tower-analytics/v0/templates/')
def api_aa_templates():
    with open('api_payloads/templates.json', 'r') as f:
        data = json.loads(f.read())
    return jsonify(data)


@app.route('/api/tower-analytics/modules/')
@app.route('/api/tower-analytics/v0/modules/')
def api_aa_modules():
    with open('api_payloads/modules.json', 'r') as f:
        data = json.loads(f.read())
    return jsonify(data)


@app.route('/api/tower-analytics/jobs_by_date_and_org_30/')
@app.route('/api/tower-analytics/v0/jobs_by_date_and_org_30/')
def api_aa_jobs_by_date_and_org_30():
    with open('api_payloads/jobs_by_date_and_org_30.json', 'r') as f:
        data = json.loads(f.read())
    return jsonify(data)


@app.route('/api/tower-analytics/job_runs_by_org_30/')
@app.route('/api/tower-analytics/v0/job_runs_by_org_30/')
def api_aa_job_runs_by_org_30():
    with open('api_payloads/job_runs_by_org_30.json', 'r') as f:
        data = json.loads(f.read())
    return jsonify(data)


@app.route('/api/tower-analytics/job_events_by_org_30/')
@app.route('/api/tower-analytics/v0/job_events_by_org_30/')
def api_aa_job_events_by_org_30():
    with open('api_payloads/job_events_by_org_30.json', 'r') as f:
        data = json.loads(f.read())
    return jsonify(data)


@app.route('/api/tower-analytics/roi_templates/')
@app.route('/api/tower-analytics/v0/roi_templates/')
def api_aa_roi_templates():
    with open('api_payloads/roi_templates.json', 'r') as f:
        data = json.loads(f.read())
    return jsonify(data)


@app.route('/api/tower-analytics/notifications/')
@app.route('/api/tower-analytics/v0/notifications/')
def api_aa_notificaitons():
    with open('api_payloads/notifications.json', 'r') as f:
        data = json.loads(f.read())
    return jsonify(data)


if __name__ == '__main__':
    #app.run(ssl_context='adhoc', host='0.0.0.0', port=443, debug=True)
    #server = Server(('0.0.0.0', 443), app.wsgi_app)
    #server.serve_forever()
    #app.run(ssl_context=('cert.pem', 'key.pem'), host='0.0.0.0', port=443, debug=True)
    if os.environ.get('API_SECURE'):
        app.run(ssl_context='adhoc', host='0.0.0.0', port=443, debug=True)
    else:
        app.run(host='0.0.0.0', port=5000, debug=True)
