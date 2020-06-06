# -*- coding: utf-8 -*-
from hashlib import sha256, sha224

from .config import config

seed = config.get('Tracker', 'domain').encode('utf8')
assert sha224(seed).hexdigest().endswith('f280f')
psk = sha256(seed).hexdigest()


def d(a):
    return "".join([chr(ord(a[i]) ^ ord(psk[i])) for i in range(len(a))])
