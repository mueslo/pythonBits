# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # noqa: F401, F403

import os
import re
import subprocess
import math
import tempfile
from future.moves.urllib.parse import urlparse

from . import _release as release
from .config import config
from .logging import log

config.register('Torrent', 'black_hole',
                "Enter a directory where you would like to save the created "
                "torrent file. Temporary directory will be used if left blank."
                "\nDirectory",
                ask=True)
config.register('Torrent', 'upload_dir',
                "Enter a directory where the media files should be placed "
                "so the torrent client has access to them for seeding. If "
                "left blank, no action will be taken."
                "\nDirectory",
                ask=True)
config.register('Torrent', 'data_method',
                "Enter a preferred method to use for placing media files in "
                "the upload directory. Choices are: 'hard', 'sym', 'copy', "
                "'move'. Unless explicitly overridden, further restrictions "
                "are automatically applied, e.g. music will be copied or "
                "moved even if the preferred data method is linking."
                "\nData method")

COMMAND = "mktorrent"


def log2(x):
    return math.log(x) / math.log(2)


def get_size(fname):
    if os.path.isfile(fname):
        return os.path.getsize(fname)
    else:
        return sum(get_size(os.path.join(fname, f)) for f in os.listdir(fname))


def piece_size_exp(size):
    min_psize_exp = 15  # 32 KiB piece size
    max_psize_exp = 24  # 16 MiB piece size
    target_pnum_exp = 10  # 1024 pieces

    psize_exp = int(math.floor(log2(size) - target_pnum_exp))
    return max(min(psize_exp, max_psize_exp), min_psize_exp)


class MkTorrentException(Exception):
    pass


def get_version():
    try:
        mktorrent = subprocess.Popen(
            [COMMAND], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = mktorrent.communicate()[0].decode('utf8')
        return tuple(map(int, re.search(
            r"(?<=^mktorrent )[\d.]+", out).group(0).split('.')))
    except OSError:
        raise MkTorrentException(
            "Could not find mktorrent, please ensure it is installed.")


def make_torrent(fname):
    fsize = get_size(fname)
    psize_exp = piece_size_exp(fsize)

    announce_url = config.get('Tracker', 'announce_url')
    tracker = urlparse(announce_url).hostname
    comment = "Created by {} for {}".format(release, tracker)

    out_dir = tempfile.mkdtemp()
    out_fname = os.path.splitext(os.path.split(fname)[1])[0] + ".torrent"
    out_fname = os.path.join(out_dir, out_fname)

    params = [
        "-p",
        "-l", str(psize_exp),
        "-a", announce_url,
        "-c", comment,
        "-o", out_fname,
    ]

    version = get_version()
    target_version = (1, 1)
    if version < target_version:
        log.warning("Cannot modify infohash by tracker since an old version "
                    "({}<{}) of mktorrent is installed. Be careful with "
                    "cross-seeding.",
                    ".".join(map(str, version)),
                    ".".join(map(str, target_version)))
    else:
        params.extend(["-s", tracker])

    call = [COMMAND] + params + [fname]
    mktorrent = subprocess.Popen(call, shell=False)

    log.info("Waiting for torrent creation to complete...")
    mktorrent.wait()
    if mktorrent.returncode:
        raise MkTorrentException()

    return out_fname
