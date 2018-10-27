# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # noqa: F401, F403

import requests
import contextlib
import re

from . import __version__ as version, __title__ as title
from .config import config
from .logging import log

config.register('Tracker', 'announce_url',
                "Please enter your personal announce URL")
config.register('Tracker', 'username', "Username", ask=True)
config.register('Tracker', 'password', "Password", ask=True, getpass=True)
config.register('Tracker', 'domain',
                "Please enter the tracker's domain, e.g. 'mydomain.net'")


class TrackerException(Exception):
    pass


class Tracker():
    headers = {'User-Agent': '{}/{}'.format(title, version)}

    @staticmethod
    def logged_in(resp):
        if ("Log in!" in resp.text or "href=\"login.php\"" in resp.text):
            return False
        if ("logout.php" in resp.text):
            return True

        log.error(resp.text)
        raise TrackerException('Unknown response format')

    @contextlib.contextmanager
    def login(self):
        domain = config.get('Tracker', 'domain')
        login_url = "https://{}/login.php".format(domain)

        username = config.get('Tracker', 'username')
        password = config.get('Tracker', 'password')

        payload = {'username': username,
                   'password': password,
                   'keep_logged': "1",
                   'login': "Log in!"}

        with requests.Session() as s:
            s.headers.update(self.headers)

            log.notice("Logging in {} to {}", username, domain)
            resp = s.post(login_url, data=payload)
            resp.raise_for_status()

            # alternatively check for redirects via resp.history
            if not self.logged_in(resp):
                raise TrackerException("Log-in failed!")
            logout_re = r"logout\.php\?auth=[0-9a-f]{32}"
            m = re.search(logout_re, resp.text)

            logout_url = "https://{}/{}".format(domain, m.group(0))

            yield s

            resp = s.get(logout_url)
            if self.logged_in(resp):
                raise TrackerException("Log-out failed!")
            log.notice("Logged out {}", username)

    def upload(self, **kwargs):
        url = "https://{}/upload.php".format(config.get('Tracker', 'domain'))
        with self.login() as session:
            log.notice("Posting submission")
            resp = session.post(url, **kwargs)
            resp.raise_for_status()

            log.debug(resp.history)
            if resp.history:
                # todo: check if url is good, might have been logged out
                # (unlikely)
                return resp.url
            else:
                log.error('resp {}', resp)
                log.error('search {}',
                          ("No torrent file uploaded" in resp.text))
                raise TrackerException('Failed to upload submission')
