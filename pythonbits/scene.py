# -*- coding: utf-8 -*-
import os
import requests
import progressbar
from base64 import b64decode
from zlib import crc32

from .logging import log

srrdb = b64decode('aHR0cHM6Ly9zcnJkYi5jb20v').decode('utf8')


def check_scene_rename(fname, release):
    release_url = srrdb + "release/details/{}".format(release)
    r = requests.get(release_url)

    if fname not in r.text:
        log.warning('Possibly renamed scene file!\n'
                    '\tFilename {}\n\tnot found at {}',
                    fname, release_url)


def crc(path):
    log.debug('Calculating CRC32 value')
    checksum = 0
    fsize = os.path.getsize(path)
    i = 0
    chunk_size = 4 * 2**20
    with open(path, 'rb') as f:
        with progressbar.DataTransferBar(max_value=fsize,
                                         max_error=False) as bar:
            while True:
                i += 1
                data = f.read(chunk_size)
                if not data:
                    return checksum & 0xFFFFFFFF

                bar.update(i*chunk_size)
                checksum = crc32(data, checksum)


def is_scene_crc(path):
    checksum = crc(path)
    log.debug('CRC32 {:08X}', checksum)
    r = requests.get(srrdb + 'api/search/archive-crc:%08X' % checksum)
    r.raise_for_status()

    scene = int(r.json()['resultsCount']) != 0
    if int(r.json()['resultsCount']) > 1:
        log.warning('More than one srrDB result for CRC32 query')
    log.info('Scene checkbox set to {} '
             'due to CRC query result'.format(scene))

    if scene:
        release = r.json()['results'][0]['release']
        fname = os.path.basename(path)
        check_scene_rename(fname, release)

    return scene


def query_scene_fname(path):
    if os.path.isfile(path):
        query = os.path.splitext(os.path.basename(path))[0]
    elif os.path.isdir(path):
        query = os.path.basename(path)
    elif not os.path.exists(path):
        raise FileNotFoundError('File or directory not found: %s' % (path,))
    else:
        raise Exception('wat')

    # full search (slow)
    r = requests.get(srrdb + "api/search/{}".format(query))
    r.raise_for_status()
    results = r.json()['results']

    if results:
        print('Found srrDB results for filename:')
        print("\t" + "\n".join(r['release'] for r in results))
    else:
        print('No results found in srrDB for query "{}"'.format(query))
