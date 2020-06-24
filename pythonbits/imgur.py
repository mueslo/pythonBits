# -*- coding: utf-8 -*-
import requests
import json
from urllib.parse import urlparse

from .api_utils import d
from .config import config
from .logging import log

API_URL = 'https://api.imgur.com/'
USER_URL_TEMPLATE = ("https://api.imgur.com/oauth2/"
                     "authorize?client_id=%s&response_type=pin")
client_id = 'US\x01]T\\RPQ\x06YP\x03V\x07'
client_secret = ('VSW\x0eVT\x03\x07\x03\x01\x0fR\x07\x01\x02RVSP\x06V\x01\x03T'
                 '\x01\x08\r\x03P\\Q\x0eYRP\x03\x03VU\x01')


class ImgurAuth(object):
    def __init__(self):
        self.refresh_token = config.get('Imgur', 'refresh_token', None)
        self.access_token = None

    def prepare(self):
        if self.access_token:
            # Already prepared
            return

        if self.refresh_token:
            self.refresh_access_token()

        while not self.access_token:
            log.notice("You are not currently logged in.")
            self.request_login()

    def request_login(self):
        user_url = USER_URL_TEMPLATE % d(client_id)
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
            'client_id': d(client_id),
            'client_secret': d(client_secret),
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

    def upload(self, *images):
        self.imgur_auth.prepare()
        for image in images:
            params = {'headers': self.imgur_auth.get_auth_headers()}

            if urlparse(image).scheme in ('http', 'https'):
                params['data'] = {'image': image}
            elif urlparse(image).scheme in ('file', ''):
                params['files'] = {'image': open(urlparse(image).path, "rb")}
            else:
                raise Exception('Unknown image URI scheme',
                                urlparse(image).scheme)
            res = requests.post(API_URL + "3/image", **params)
            res.raise_for_status()  # raises if invalid api request
            response = json.loads(res.text)

            link = response["data"]["link"]
            extensions = [path.split(".")[-1]
                          for path in (image, link)]
            if extensions[0] != extensions[1]:
                log.warn("Imgur converted {} to a {}.",
                         extensions[0], extensions[1])

            log.notice("Image URL: {}", link)
            yield link
