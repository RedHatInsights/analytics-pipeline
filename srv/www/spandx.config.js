/*global module, process*/
const localhost = (process.env.PLATFORM === 'linux') ? 'localhost' : 'host.docker.internal';

module.exports = {
    routes: {
        '/apps/automation-analytics': { host: `http://webroot` },
        '/ansible/automation-analytics': { host: `http://webroot` },
        '/beta/ansible/automation-analytics': { host: `http://webroot` },
        '/api/tower-analytics': { host: `https://aabackend:443` },
        '/apps/chrome': { host: `http://webroot` },
        '/apps/landing': { host: `http://webroot` },
        '/beta/apps/landing': { host: `http://webroot` },
        '/api/entitlements': { host: `http://entitlements` },
        '/api/rbac': { host: `http://rbac` },
        '/beta/config': { host: `http://${localhost}:8889` },
        '/': { host: `http://webroot` }
    }
};
