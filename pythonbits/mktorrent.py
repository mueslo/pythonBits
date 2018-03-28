# -*- coding: utf-8 -*-
import os
import subprocess
import math
import tempfile

from . import _release as release
from .config import config
from .logging import log

config.register('Torrent', 'black_hole',
                "Enter a directory where you would like to save the created "
                "torrent file. Temporary directory will be used if left blank."
                "\nDirectory",
                ask=True)


l2 = math.log(2)


def log2(x):
    return math.log(x) / l2


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


def make_torrent(fname, psize_exp):
        # todo: multiprocessing
    fsize = get_size(fname)
    if psize_exp == 0:
        psize_exp = piece_size_exp(fsize)

    announce_url = config.get('Tracker', 'announce_url')

    out_dir = tempfile.mkdtemp()
    out_fname = os.path.splitext(os.path.split(fname)[1])[0] + ".torrent"
    out_fname = os.path.join(out_dir, out_fname)

    mktorrent = subprocess.Popen([r"mktorrent", "--private",
                                  "-l", str(psize_exp),
                                  "-a", announce_url,
                                  "-c", release,
                                  "-o", out_fname,
                                  fname], shell=False)

    log.info("Waiting for torrent creation to complete...")
    mktorrent.wait()
    if mktorrent.returncode:
        raise MkTorrentException()

    return out_fname
