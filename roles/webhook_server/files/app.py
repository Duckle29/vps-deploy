"""Deploy static sites from GitHub push webhooks.

Replaces Duckle29/webhook_server (Flask 1.0 + Flask-Hookserver, which is no
longer on PyPI). Same config.ini, same behaviour: a push to a configured repo's
production branch runs `git pull` in its path and then its optional `command`.

config.ini:

    [main]
    github_secret = ...
    endpoint = /deploy
    ; validate_ip = false      only for tests, default true

    [Owner/repo]
    clone_uri = https://github.com/Owner/repo
    path = /srv/site
    ; production_branch = main  defaults to the repo's default branch
    ; command = cd blog && hugo run after every pull and after the first clone

Requests must come from GitHub's hook IP ranges (https://api.github.com/meta)
and carry a valid X-Hub-Signature-256. The client IP is the last entry of
X-Forwarded-For, which the reverse proxy sets (one proxy in front).
"""
import hashlib
import hmac
import ipaddress
import json
import logging
import subprocess
import threading
import time
from configparser import ConfigParser
from pathlib import Path

import requests
from flask import Flask, abort, request
from werkzeug.middleware.proxy_fix import ProxyFix

BASE = Path(__file__).resolve().parent
GIT = '/usr/bin/git'
GITHUB_META = 'https://api.github.com/meta'
META_TTL = 3600

config = ConfigParser(interpolation=None)
config.read(BASE / 'config.ini')

SECRET = config['main']['github_secret'].encode()
ENDPOINT = config['main'].get('endpoint', '/deploy')
VALIDATE_IP = config['main'].getboolean('validate_ip', fallback=True)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
log = logging.getLogger('webhook')
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

_deploy_lock = threading.Lock()
_meta = {'ranges': [], 'fetched': 0.0}


def sites():
    return [s for s in config.sections() if s != 'main']


def hook_networks():
    """GitHub's webhook source ranges, cached for an hour."""
    now = time.time()
    if not _meta['ranges'] or now - _meta['fetched'] > META_TTL:
        try:
            resp = requests.get(GITHUB_META, timeout=10)
            resp.raise_for_status()
            _meta['ranges'] = [ipaddress.ip_network(n) for n in resp.json()['hooks']]
            _meta['fetched'] = now
        except (requests.RequestException, ValueError, KeyError) as err:
            log.warning('could not refresh GitHub hook ranges: %s', err)
    return _meta['ranges']


def source_allowed():
    if not VALIDATE_IP:
        return True
    try:
        addr = ipaddress.ip_address(request.remote_addr)
    except ValueError:
        return False
    # Fail closed: no known ranges means nobody is allowed.
    return any(addr in net for net in hook_networks())


def signature_ok(body):
    header = request.headers.get('X-Hub-Signature-256', '')
    expected = 'sha256=' + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header, expected)


def run(args, cwd, **kw):
    return subprocess.run(args, cwd=cwd, text=True, check=True,
                          capture_output=True, **kw)


def build(site):
    command = config[site].get('command')
    if command:
        run(command, config[site]['path'], shell=True, timeout=900)


def clone_missing():
    """Clone every configured site whose webroot is still empty."""
    for site in sites():
        path = Path(config[site]['path'])
        try:
            if not path.is_dir():
                raise FileNotFoundError(f'{path} must exist and be writable')
            if (path / '.git').is_dir():
                continue
            run([GIT, 'clone', config[site]['clone_uri'], '.'], path, timeout=600)
            build(site)
            log.info('cloned %s into %s', site, path)
        except (OSError, subprocess.SubprocessError) as err:
            detail = getattr(err, 'stderr', '') or err
            log.error('initial clone of %s failed: %s', site, detail)


def deploy(data):
    repo = data['repository']['full_name']
    ref = data.get('ref', '')
    if repo not in config:
        return 'Nothing to do for this repo, skipped.'
    if not ref.startswith('refs/heads/'):
        return 'Not a branch push, skipped.'
    branch = ref[len('refs/heads/'):]
    default = (data['repository'].get('default_branch')
               or data['repository'].get('master_branch'))
    production = config[repo].get('production_branch', default)
    if branch != production:
        return 'Not production branch, skipped.'

    path = config[repo]['path']
    with _deploy_lock:
        try:
            run([GIT, 'pull', '--ff-only'], path, timeout=300)
            build(repo)
        except subprocess.CalledProcessError as err:
            log.error('deploy of %s failed: %s %s', repo, err, err.stderr)
            abort(500)
        except subprocess.TimeoutExpired as err:
            log.error('deploy of %s timed out: %s', repo, err)
            abort(500)
    log.info('deployed %s', repo)
    return f'Deployed website from {repo}'


@app.route(ENDPOINT, methods=['POST'])
def hook():
    if not source_allowed():
        abort(403)
    body = request.get_data()
    if not signature_ok(body):
        abort(403)
    event = request.headers.get('X-GitHub-Event', '')
    if event == 'ping':
        return 'pong'
    if event != 'push':
        return f'Event {event!r} ignored.'
    try:
        data = json.loads(body)
    except ValueError:
        abort(400)
    return deploy(data)


clone_missing()
