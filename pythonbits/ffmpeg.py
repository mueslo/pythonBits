# -*- coding: utf-8 -*-
"""
ffmpeg.py

Created by Ichabond on 2012-07-01.
Copyright (c) 2012 Baconseed. All rights reserved.
"""
import os
import subprocess
import re

from tempfile import mkdtemp
from concurrent.futures.thread import ThreadPoolExecutor


class FfmpegException(Exception):
    pass


class FFMpeg(object):
    def __init__(self, filepath):
        self.file = filepath
        self.ffmpeg = None
        self.tempdir = mkdtemp(prefix="pythonbits-") + os.sep

    def duration(self):
        self.ffmpeg = subprocess.Popen([r"ffmpeg", "-i", self.file],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
        ffmpeg_out = self.ffmpeg.stdout.read().decode('utf8')
        ffmpeg_duration = re.findall(
            r'Duration:\D(\d{2}):(\d{2}):(\d{2})', ffmpeg_out)
        if not ffmpeg_duration:
            raise FfmpegException("ffmpeg output did not contain 'Duration'")
        dur = ffmpeg_duration[0]
        dur_hh = int(dur[0])
        dur_mm = int(dur[1])
        dur_ss = int(dur[2])
        return dur_hh * 3600 + dur_mm * 60 + dur_ss

    def make_screenshot(self, seek, fname_out):
        subprocess.Popen(
            [r"ffmpeg",
             "-ss", str(seek),
             "-i", self.file,
             "-vframes", "1",
             "-y",
             "-f", "image2",
             "-vf", "scale='max(sar,1)*iw':'max(1/sar,1)*ih'", fname_out],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()
        return fname_out

    def take_screenshots(self, num_screenshots):
        duration = self.duration()
        stops = range(20, 81, 60 // (num_screenshots - 1))

        with ThreadPoolExecutor() as executor:
            imgs = executor.map(
                lambda x: self.make_screenshot(x[0], x[1]),
                [(duration * stop / 100,
                 os.path.join(self.tempdir, "screen%s.png" % stop))
                 for stop in stops])
        return list(imgs)
