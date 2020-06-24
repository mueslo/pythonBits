# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
"""
Upload image file or image URL to the ptpimg.me image hosting.

Borrowed from
https://github.com/theirix/ptpimg-uploader/blob/master/ptpimg_uploader.py

"""

import contextlib
import mimetypes
import os
from io import BytesIO
from textwrap import dedent
from urllib.parse import urlparse

import requests

from .config import config
from .logging import log

mimetypes.init()

config.register(
    'PtpImg', 'api_key',
    dedent("""\
    To find your PTPImg API key, login to https://ptpimg.me, open the page
    source (i.e. "View->Developer->View source" menu in Chrome), find the
    string api_key and copy the hexademical string from the value attribute.
    Your API key should look like 43fe0fee-f935-4084-8a38-3e632b0be68c.
    3. Enter the API Key below
    API Key"""))


class UploadFailed(Exception):
    def __str__(self):
        msg, *args = self.args
        return msg.format(*args)


class PtpImgUploader:
    """ Upload image or image URL to the ptpimg.me image hosting """

    def __init__(self, timeout=None):
        self.api_key = config.get('PtpImg', 'api_key')
        self.timeout = timeout

    @staticmethod
    def _handle_result(res):
        image_url = 'https://ptpimg.me/{0}.{1}'.format(
            res['code'], res['ext'])
        return image_url

    def _perform(self, files=None, **data):
        # Compose request
        headers = {'referer': 'https://ptpimg.me/index.php'}
        data['api_key'] = self.api_key
        url = 'https://ptpimg.me/upload.php'

        resp = requests.post(
            url, headers=headers, data=data, files=files, timeout=self.timeout)

        # pylint: disable=no-member
        if resp.status_code == requests.codes.ok:
            try:
                print('Successful response', resp.json())
                # r.json() is like this: [{'code': 'ulkm79', 'ext': 'jpg'}]
                return [self._handle_result(r) for r in resp.json()]
            except ValueError as e:
                raise UploadFailed(
                    'Failed decoding body:\n{0}\n{1!r}', e, resp.content
                ) from None
        else:
            raise UploadFailed(
                'Failed. Status {0}:\n{1}', resp.status_code, resp.content)

    def upload_files(self, *filenames):
        log.notice('Got files to upload {} to ptpimg', filenames)
        """ Upload files using form """
        # The ExitStack closes files for us when the with block exits
        with contextlib.ExitStack() as stack:
            files = {}
            for i, filename in enumerate(filenames):
                open_file = stack.enter_context(open(filename, 'rb'))
                mime_type, _ = mimetypes.guess_type(filename)
                if not mime_type or mime_type.split('/')[0] != 'image':
                    raise ValueError(
                        'Unknown image file type {}'.format(mime_type))

                name = os.path.basename(filename)
                try:
                    # until https://github.com/shazow/urllib3/issues/303 is
                    # resolved, only use the filename if it is Latin-1 safe
                    name.encode('latin1')
                except UnicodeEncodeError:
                    name = 'justfilename'
                files['file-upload[{}]'.format(i)] = (
                    name, open_file, mime_type)

            log.notice('Processed and trying to upload {} to ptpimg', files)
            return self._perform(files=files)

    def upload_urls(self, *urls):
        log.notice('Got links to upload {} to ptpimg', urls)
        """ Upload image URLs by downloading them before """
        with contextlib.ExitStack() as stack:
            files = {}
            for i, url in enumerate(urls):
                resp = requests.get(url, timeout=self.timeout)
                if resp.status_code != requests.codes.ok:
                    raise ValueError(
                        'Cannot fetch url {} with error {}'.format(
                            url, resp.status_code))

                mime_type = resp.headers['content-type']
                if not mime_type or mime_type.split('/')[0] != 'image':
                    raise ValueError(
                        'Unknown image file type {}'.format(mime_type))
                open_file = stack.enter_context(BytesIO(resp.content))
                files['file-upload[{}]'.format(i)] = (
                    'file-{}'.format(i), open_file, mime_type)

            return self._perform(files=files)

    def upload(self, *images):
        for image in images:
            if urlparse(image).scheme in ('http', 'https'):
                yield self.upload_urls(image)
            elif urlparse(image).scheme in ('file', ''):
                yield self.upload_files(image)
            else:
                raise Exception('Unknown image URI scheme '
                                '{}'.format(urlparse(image).scheme))


def _partition(files_or_urls):
    files, urls = [], []
    for file_or_url in files_or_urls:
        if os.path.exists(file_or_url):
            files.append(file_or_url)
        elif file_or_url.startswith('http'):
            urls.append(file_or_url)
        else:
            raise ValueError(
                'Not an existing file or image URL: {}'.format(file_or_url))
    return files, urls
