# -*- coding: utf-8 -*-
import requests
import contextlib
import re
import time

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

    def _login(self, session, _tries=0):
        maxtries = 10

        domain = config.get('Tracker', 'domain')
        login_url = "https://{}/login.php".format(domain)
        payload = {'username': config.get('Tracker', 'username'),
                   'password': config.get('Tracker', 'password'),
                   'keeplogged': "1",
                   'login': "Log in!"}

        resp = session.post(login_url, data=payload)
        resp.raise_for_status()

        if 'href="login.php"' in resp.text:
            if 'id="loginform"' in resp.text:
                raise TrackerException("Login failed")
            elif 'You are banned' in resp.text:
                raise TrackerException(
                    "Login failed (login attempts exceeded)")
            else:
                # We encountered the login bug that sends you to "/" (which
                # doesn't contain the login form) without logging you in
                # todo: convert this to a retry decorator
                if _tries < maxtries:
                    backoff = min(10**_tries/1000, 16.)
                    log.debug('Encountered login bug; trying again after '
                              '{}s back-off'.format(backoff))
                    time.sleep(backoff)
                    self._login(session, _tries=_tries+1)
                else:
                    log.debug('Encountered login bug; '
                              'giving up after '
                              '{} login attempts'.format(_tries))
                    raise TrackerException("Login failed")
        elif 'logout.php' in resp.text:
            # Login successful, find and remember logout URL
            match = re.search(r"logout\.php\?auth=[0-9a-f]{32}", resp.text)
            if match:
                self._logout_url = "https://{}/{}".format(
                    domain, match.group(0))
            else:
                raise TrackerException("Couldn't find logout URL")
        else:
            log.error(resp.text)
            raise TrackerException("Couldn't determine login status from HTML")

    def _logout(self, session):
        logout_url = getattr(self, '_logout_url')
        if logout_url:
            delattr(self, '_logout_url')
            resp = session.get(logout_url)
            if 'logout.php' in resp.text:
                raise TrackerException("Logout failed")
        else:
            raise TrackerException("No logout URL: Unable to logout")

    @contextlib.contextmanager
    def login(self):
        log.notice("Logging in {} to {}",
                   config.get('Tracker', 'username'),
                   config.get('Tracker', 'domain'))
        with requests.Session() as s:
            s.headers.update(self.headers)
            self._login(s)
            yield s
            self._logout(s)
        log.notice("Logged out {} of ",
                   config.get('Tracker', 'username'),
                   config.get('Tracker', 'domain'))

    def upload(self, **kwargs):
        url = "https://{}/upload.php".format(config.get('Tracker', 'domain'))
        with self.login() as session:
            log.notice("Posting submission")
            resp = session.post(url, **kwargs)
            resp.raise_for_status()

            # TODO: Catch this somehow:
            # <p style="color: red;text-align:center;">You must enter at least
            # one tag. Maximum length is 200 characters.</p>

            if resp.history:
                # todo: check if url is good, might have been logged out
                # (unlikely)
                return resp.url
            else:
                log.error('Response: %s' % resp)
                err_match = re.search(r''.join(
                        (r'(No torrent file uploaded.*?)',
                         re.escape(r'</p>'))),
                    resp.text)
                if err_match:
                    log.error('Error: %s' % err_match.group(1))
                else:
                    log.debug(resp.text)
                    log.error('Unknown error')
                raise TrackerException('Failed to upload submission')
