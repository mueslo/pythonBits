# -*- coding: utf-8 -*-
from hashlib import sha256, sha224

from .config import config


def get_psk():
    seed = config.get('Tracker', 'domain').encode('utf8')
    test = sha224(seed).hexdigest()
    if not test.endswith('f280f') and not test.endswith('5abc3'):
        raise Exception('Wrong domain! '
                        'Manually fix {}'.format(config.config_path))
    return sha256(seed).hexdigest()


def d(a):
    psk = get_psk()
    return "".join([chr(ord(a[i]) ^ ord(psk[i])) for i in range(len(a))])
