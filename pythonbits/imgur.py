# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # noqa: F401, F403

import requests
import json
from future.moves.urllib.parse import urlparse
from textwrap import dedent

from .config import config
from .logging import log

API_URL = 'https://api.imgur.com/'
USER_URL_TEMPLATE = ("https://api.imgur.com/oauth2/"
                     "authorize?client_id=%s&response_type=pin")

config.register(
    'Imgur', 'client_id',
    dedent("""\
    To upload images to Imgur, you first have to create an Imgur account
    and application:
    1. Sign up for an imgur account: https://imgur.com/register
    2. Create an application: https://api.imgur.com/oauth2/addclient
        - Application name: Your choice
        - Authorization type: "OAuth 2 authorization without a callback URL"
        - Authorization callback URL: Leave blank
        - Application website: Leave blank
        - Email: Your choice
        - Description: Your choice
    3. Enter the Client ID and Client Secret below
    Client ID"""))
config.register('Imgur', 'client_secret', "Client Secret")


class ImgurAuth(object):
    def __init__(self):
        self.client_id = config.get('Imgur', 'client_id')
        self.client_secret = config.get('Imgur', 'client_secret')
        self.refresh_token = config.get('Imgur', 'refresh_token', None)
        self.access_token = None

    def prepare(self):
        if self.access_token:
            # Already prepared
            return

        while not (self.client_id and self.client_secret):
            print(("Client ID: %s or Client Secret: %s missing" %
                  (self.client_id, self.client_secret)))
            self.request_client_details()

        if self.refresh_token:
            self.refresh_access_token()

        while not self.access_token:
            log.notice("You are not currently logged in.")
            self.request_login()

    def request_client_details(self):
        # todo properly query these

        self.client_id = input("Client ID: ")
        self.client_secret = input("Client Secret: ")

    def request_login(self):
        user_url = USER_URL_TEMPLATE % self.client_id
        print("pythonBits needs access to your account.")
        print("To authorize:")
        print(("   1. In your browser, open: " + user_url))
        print("   2. Log in to Imgur and authorize the application")
        print("   3. Enter the displayed PIN number below")
        pin = input("PIN: ")
        self.fetch_access_token('pin', pin)

    def refresh_access_token(self):
        self.fetch_access_token('refresh_token', self.refresh_token)

    def fetch_access_token(self, grant_type, value):
        # grant type: pin or refresh_token
        data = {
            'client_id': config.get('Imgur', 'client_id'),
            'client_secret': config.get('Imgur', 'client_secret'),
            'grant_type': grant_type,
            grant_type: value
        }
        res = requests.post(API_URL + "/oauth2/token", data=data)
        res.raise_for_status()

        response = json.loads(res.text)
        self.access_token = response["access_token"]

        if response["refresh_token"]:
            self.refresh_token = response["refresh_token"]
            config.set('Imgur', 'refresh_token', self.refresh_token)

        log.notice("Logged in to Imgur as {}", response["account_username"])

    def get_auth_headers(self):
        return {"Authorization": "Bearer %s" % self.access_token}


class ImgurUploader(object):
    # todo: upload to album to avoid clutter
    def __init__(self):
        self.imgur_auth = ImgurAuth()

    def upload(self, image):
        if not isinstance(image, str):
                return [self.upload(p) for p in image]
        self.imgur_auth.prepare()
        params = {'headers': self.imgur_auth.get_auth_headers()}

        if urlparse(image).scheme in ('http', 'https'):
            params['data'] = {'image': image}
        elif urlparse(image).scheme in ('file', ''):
            params['files'] = {'image': open(urlparse(image).path, "rb")}
        else:
            raise Exception('Unknown image URI scheme', urlparse(image).scheme)
        res = requests.post(API_URL + "3/image", **params)
        res.raise_for_status()  # raises if invalid api request
        response = json.loads(res.text)

        link = response["data"]["link"]
        extensions = [path.split(".")[-1]
                      for path in (image, link)]
        if extensions[0] != extensions[1]:
            log.warn("Imgur converted {} to a {}.",
                     extensions[0], extensions[1])

        return link
