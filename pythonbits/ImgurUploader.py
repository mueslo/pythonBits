# -*- coding: utf-8 -*-
import urllib2
import urllib
import ConfigParser
import json
import re
import os
import sys
from textwrap import dedent

from . import MultipartPostHandler
from .config import config

API_URL = 'https://api.imgur.com/'
USER_URL_TEMPLATE = "https://api.imgur.com/oauth2/authorize?client_id=%s&response_type=pin"

config.register('Imgur', 'client_id',
                dedent("""\
                To upload images to Imgur, you must first create an Imgur account and application
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
        self.access_token =  None

    def prepare(self):
        if self.access_token:
            # Already prepared
            return

        while not (self.client_id and self.client_secret):
            print("Client ID: %s or Client Secret: %s missing" % 
                    (self.client_id, self.client_secret) )
            self.request_client_details()

        if self.refresh_token:
            self.refresh_access_token()

        while not self.access_token:
            print("You are not currently logged in.")
            self.request_login()


    def request_client_details(self):
        #todo properly query these

        self.client_id = raw_input("Client ID: ")
        self.client_secret = raw_input("Client Secret: ")
      

    def request_login(self):
        user_url = USER_URL_TEMPLATE % self.client_id
        print("pythonBits needs access to your account.")
        print("To authorize:")
        print("   1. In your browser, open: " + user_url)
        print("   2. Log in to Imgur and authorize the application")
        print("   3. Enter the displayed PIN number below")
        pin = raw_input("PIN: ")
        self.fetch_access_token('pin', pin)

    def refresh_access_token(self):
        self.fetch_access_token('refresh_token', self.refresh_token)

    def fetch_access_token(self, grant_type, value):
        #grant type: pin or refresh_token
        data = urllib.urlencode({
            'client_id': config.get('Imgur', 'client_id'),
            'client_secret': config.get('Imgur', 'client_secret'),
            'grant_type': grant_type,
            grant_type : value
        })
        req = urllib2.Request(API_URL + "/oauth2/token", data)
        res = urllib2.urlopen(req)
        response = json.loads(res.read())

        self.access_token = response["access_token"]

        if response["refresh_token"]:
            self.refresh_token = response["refresh_token"]
            config.set('Imgur', 'refresh_token', self.refresh_token)

        print("Logged in to Imgur as %s" % response["account_username"])
        print

    def get_auth_header(self):
       return ("Authorization", "Bearer %s" % self.access_token)     


class ImgurUploader(object):
    # todo: upload to album to avoid clutter
    def __init__(self, filelist):
        self.images = filelist
        self.imageurls = []
        self.imgur_auth = ImgurAuth()

    def upload(self):
        self.imgur_auth.prepare()
        opener = urllib2.build_opener(MultipartPostHandler.MultipartPostHandler)
        opener.addheaders = [self.imgur_auth.get_auth_header()]
        matcher = re.compile(r'http(s)*://')
        for image in self.images:
            try:
                if matcher.match(image):
                    params = ({'image': image})
                else:
                    params = ({'image': open(image, "rb")})
                socket = opener.open(API_URL + "3/image", params)
                res = socket.read()
                response = json.loads(res)
                if response["success"] and response["data"]:
                    link = response["data"]["link"]
                    extensions = [path.split(".")[-1] for path in (image, link)]
                    if extensions[0] != extensions[1]:
                        placeholder = image.split("/")[-1]
                        print("WARNING: Imgur converted %s to a %s." % (extensions[0], extensions[1]))
                        print("Please upload elsewhere and replace the placeholder link.")
                        print("Imgur link: %s" % link)
                        print("Placeholder: %s" % placeholder)
                        print("File: %s" % image)
                        print
                        self.imageurls.append(placeholder)
                    else:
                        self.imageurls.append(link)
                else:
                    print("Could not upload image: %s, skipping. Result: " % (image, res))
            except Exception as e:
                    print("Exception uploading image: %s, skipping. Exception: " % (image, e))
        return self.imageurls

