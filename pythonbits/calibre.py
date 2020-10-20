# -*- coding: utf-8 -*-
import subprocess

from .logging import log

COMMAND = "ebook-meta"


class EbookMetaException(Exception):
    pass


def get_version():
    try:
        ebook_meta = subprocess.Popen(
            [COMMAND, '--version'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return ebook_meta.communicate()[0].decode('utf8')
    except OSError:
        raise EbookMetaException(
            "Could not find {}, please ensure it is installed (via Calibre)."
            .format(COMMAND))


def read_metadata(path):
    version = get_version()
    log.debug('Found ebook-meta version: %s' % version)
    log.info("Trying to read eBook metadata...")

    output = subprocess.check_output(
        '{} "{}"'.format(COMMAND, path), shell=True)
    result = {}
    for row in output.decode('utf8').split('\n'):
        if ': ' in row:
            try:
                key, value = row.split(': ')
                result[key.strip(' .')] = value.strip()
            except ValueError:
                pass
    return result
