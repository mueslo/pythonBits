# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # noqa: F401, F403

import os
import sys
import shutil
import re
import subprocess

from textwrap import dedent
from collections import namedtuple

import pymediainfo
import guessit
from unidecode import unidecode

from .config import config
from .logging import log
from .mktorrent import make_torrent
from . import tvdb
from . import imdb
from .imgur import ImgurUploader
from .ffmpeg import FFMpeg
from . import templating as bb
from .submission import (Submission, form_field, finalize,
                         SubmissionAttributeError)
from .tracker import Tracker


def format_tag(tag):
    tag = unidecode(tag)
    return tag.replace(' ', '.').replace('-', '.').replace('\'', '.').lower()


class BbSubmission(Submission):
    default_fields = ("form_title", "tags", "cover")

    def show_fields(self, fields):
        return super(BbSubmission, self).show_fields(
            fields or self.default_fields)

    def confirm_finalization(self, fields):
        return super(BbSubmission, self).confirm_finalization(
            fields or self.default_fields)

    def subcategory(self):
        # only video for now
        return VideoSubmission

    def subcategorise(self):
        log.debug('Attempting to narrow category')
        SubCategory = self.subcategory()
        if type(self) == SubCategory:
            return self

        log.info("Narrowing category from {} to {}",
                 type(self).__name__, SubCategory.__name__)
        sub = SubCategory(**self.fields)
        sub.depends_on = self.depends_on
        return sub

    @staticmethod
    def submit(payload):
        t = Tracker()
        return t.upload(**payload)

    @form_field('scene', 'checkbox')
    def _render_scene(self):
        while True:
            choice = input('Is this a scene release? [y/N] ')

            if not choice or choice.lower() == 'n':
                return False
            elif choice.lower() == 'y':
                return True

    @finalize
    @form_field('file_input', 'file')
    def _render_torrentfile(self):
        return make_torrent(self['path'])

    def _finalize_torrentfile(self):
        # black hole
        out_dir = config.get('Torrent', 'black_hole')
        if out_dir:
            fname = os.path.basename(self['torrentfile'])
            dest = os.path.join(out_dir, fname)

            try:
                assert os.path.exists(out_dir)
                assert not os.path.isfile(dest)
            except AssertionError as e:
                log.error(e)
            else:
                shutil.copy(self['torrentfile'], dest)
                log.notice("Torrent file copied to {}", dest)

        return self['torrentfile']

    @form_field('type')
    def _render_form_type(self):
        try:
            return self._form_type
        except AttributeError:
            raise SubmissionAttributeError(type(self).__name__ +
                                           ' has no _form_type attribute')

    @form_field('submit')
    def _render_form_submit(self):
        return 'true'


title_tv_re = (
    r"^(?P<title>.+)(?<!season) "
    r"(?P<season_marker>(s|season |))"
    r"(?P<season>((?<= s)[0-9]{2,})|(?<= )[0-9]+(?=x)|(?<=season )[0-9]+(?=$))"
    r"((?P<episode_marker>[ex])(?P<episode>[0-9]+))?$")

TvSpecifier = namedtuple('TvSpecifier', ['title', 'season', 'episode'])


class VideoSubmission(BbSubmission):
    default_fields = BbSubmission.default_fields

    def _render_guess(self):
        return {k: v for k, v in guessit.guessit(self['path']).items()}

    def subcategory(self):
        if type(self) == VideoSubmission:
            if self['tv_specifier']:
                return TvSubmission
            else:
                return MovieSubmission
        return type(self)

    def _render_tv_specifier(self):
        # if title is specified, look if season/episode are set
        if self['title_arg']:
            match = re.match(title_tv_re, self['title_arg'],
                             re.IGNORECASE)
            if match:
                episode = match.group('episode')
                return TvSpecifier(
                    match.group('title'), int(match.group('season')),
                    episode and int(episode))  # if episode is None

            # todo: test tv show name from title_arg, but episode from filename

        guess = self['guess']
        if guess['type'] == 'episode':
            if self['title_arg']:
                title = self['title_arg']
            else:
                title = guess['title']
            return TvSpecifier(title, guess['season'],
                               guess.get('episode', None))

    @form_field('tags')
    def _render_tags(self):
        # todo: get episode-specific actors (from imdb?)

        n = self['options']['num_cast']
        tags = list(self['summary']['genres'])
        tags += [a['name'] for a in self['summary']['cast'][:n]]
        return ",".join(format_tag(tag) for tag in tags)

    def _render_mediainfo_path(self):
        assert os.path.exists(self['path'])
        if os.path.isfile(self['path']):
            return self['path']

        contained_files = []
        for dp, dns, fns in os.walk(self['path']):
            contained_files += [
                os.path.join(dp, fn) for fn in fns
                if os.path.getsize(os.path.join(dp, fn)) > 10 * 2**20]

        print("\nWhich file would you like to run mediainfo on? Choices are")
        contained_files.sort()
        for k, v in enumerate(contained_files):
            print("{}: {}".format(k, os.path.relpath(v, self['path'])))
        while True:
            try:
                choice = input(
                    "Enter [0-{}]: ".format(len(contained_files) - 1))
                return contained_files[int(choice)]
            except (ValueError, IndexError):
                pass

    @finalize
    def _render_screenshots(self):
        ns = self['options']['num_screenshots']
        ffmpeg = FFMpeg(self['mediainfo_path'])
        return ffmpeg.take_screenshots(ns)

    def _finalize_screenshots(self):
        return ImgurUploader().upload(self['screenshots'])

    def _render_mediainfo(self):
        try:
            path = self['mediainfo_path']
            if os.name == "nt":
                return subprocess.Popen([r"mediainfo", path], shell=True,
                                        stdout=subprocess.PIPE
                                        ).communicate()[0].decode('utf8')
            else:
                return subprocess.Popen([r"mediainfo", path],
                                        stdout=subprocess.PIPE
                                        ).communicate()[0].decode('utf8')
        except OSError:
            sys.stderr.write(
                "Error: Media Info not installed, refer to "
                "http://mediainfo.sourceforge.net/en for installation")
            exit(1)

    def _render_tracks(self):
        video_tracks = []
        audio_tracks = []
        text_tracks = []
        general = None

        mi = pymediainfo.MediaInfo.parse(self['mediainfo_path'])

        for track in mi.tracks:
            if track.track_type == 'General':
                general = track.to_data()
            elif track.track_type == 'Video':
                video_tracks.append(track.to_data())
            elif track.track_type == 'Audio':
                audio_tracks.append(track.to_data())
            elif track.track_type == 'Text':
                text_tracks.append(track.to_data())
            else:
                log.debug("Unknown track {}", track)

        assert general is not None
        assert len(video_tracks) == 1
        video_track = video_tracks[0]

        assert len(audio_tracks) >= 1

        return {'general': general,
                'video': video_track,
                'audio': audio_tracks,
                'text': text_tracks}

    def _render_source(self):
        sources = ('BluRay', 'BluRay 3D', 'WEB-DL',
                   'WebRip', 'HDTV', 'DVDRip', 'DVDSCR', 'CAM')
        # ignored: R5, TeleSync, PDTV, SDTV, BluRay RC, HDRip, VODRip,
        #          TC, SDTV, DVD5, DVD9, HD-DVD

        # todo: replace with guess from self['guess']
        if 'bluray' in self['path'].lower():
            return 'BluRay'
            # todo: 3d
        elif ('web-dl' in self['path'].lower() or
              'webdl' in self['path'].lower()):
            return 'WEB-DL'
        elif 'webrip' in self['path'].lower():
            return 'WebRip'
        elif 'hdtv' in self['path'].lower():
            return 'HDTV'
        # elif 'dvdscr' in self['path'].lower():
        #    markers['source'] = 'DVDSCR'
        else:
            print("File:", self['path'])
            print("Choices:", dict(enumerate(sources)))
            while True:
                choice = input("Please specify source: ")
                try:
                    return sources[int(choice)]
                except (ValueError, IndexError):
                    print("Please enter a valid choice")

    def _render_container(self):
        general = self['tracks']['general']
        if general['format'] == 'Matroska':
            return 'MKV'
        elif general['format'] == 'AVI':
            return 'AVI'
        elif general['format'] == 'MPEG-4':
            return 'MP4'
        else:
            raise Exception("Unknown or unsupported container", general.format)

    def _render_video_codec(self):
        video_track = self['tracks']['video']
        # norm_bitrate = (float(bit_rate) /
        #     (video_track.width*video_track.height))
        if video_track['codec'] in ('V_MPEG4/ISO/AVC', 'AVC'):
            if ('writing_library' in video_track and
                    'x264' in video_track['writing_library']):
                return 'x264'
            else:
                return 'H.264'
        elif video_track['codec'] == 'XVID':
            return 'XVid'
        else:
            raise Exception("Unknown or unsupported video codec",
                            video_track['codec'],
                            video_track['writing_library'])

    def _render_audio_codec(self):
        audio_codecs = ('AC3', 'DTS', 'FLAC', 'AAC', 'MP3')

        audio_tracks = self['tracks']['audio']
        audio_track = audio_tracks[0]  # main audio track

        for c in audio_codecs:
            if audio_track['codec'].startswith(c):
                c = c.replace('AC3', 'AC-3')
                return c

        if audio_track['codec'] == 'MPA1L3':
            return 'MP3'

        raise Exception("Unknown or unsupported audio codec",
                        audio_track['codec'])

    def _render_resolution(self):
        resolutions = ('1080p', '720p', '1080i', '720i', '480p', '480i', 'SD')

        # todo: replace with regex?
        # todo: compare result with mediainfo
        for res in resolutions:
            if res.lower() in self['path'].lower():
                # warning: 'sd' might match any ol' title, but it's last anyway
                return res
        else:
            print("File:", self['path'])
            print("Choices:", dict(enumerate(resolutions)))
            while True:
                choice = input("Please specify resolution: ")
                try:
                    return resolutions[int(choice)]
                except (ValueError, IndexError):
                    print("Please enter a valid choice")
        # from mediainfo and filename

    def _render_additional(self):
        additional = []
        audio_tracks = self['tracks']['audio']
        text_tracks = self['tracks']['text']

        for track in audio_tracks[1:]:
            if 'title' in track and 'commentary' in track['title'].lower():
                additional.append('w. Commentary')

        if text_tracks:
            additional.append('w. Subtitles')
        # print [(track.title, track.language) for track in text_tracks]

        # todo: rule checking, e.g.
        # main_audio = audio_tracks[0]
        # if (main_audio.language and main_audio.language != 'en' and
        #         not self['tracks']['text']):
        #     raise BrokenRule("Missing subtitles")

        edition = self['guess'].get('edition')
        if edition:
            additional.insert(0, edition)

        if self['guess'].get('proper_count') and self['scene']:
            additional.insert(0, 'PROPER')

        return additional

    def _render_form_release_info(self):
        return " / ".join(self['additional'])

    @finalize
    @form_field('image')
    def _render_cover(self):
        return self['summary']['cover']

    def _finalize_cover(self):
        return ImgurUploader().upload(self['cover'])


class TvSubmission(VideoSubmission):
    default_fields = VideoSubmission.default_fields + ('form_description',)
    _form_type = 'TV'
    __form_fields__ = {
        'form_title': ('title', 'text'),
        'form_description': ('desc', 'text'),
        }

    def _render_search_title(self):
        return self['tv_specifier'].title

    def _render_title(self):
        return self['summary']['title']

    @form_field('title')
    def _render_form_title(self):
        markers_list = [self['source'], self['video_codec'],
                        self['audio_codec'], self['container'],
                        self['resolution']] + self['additional']
        markers = " / ".join(markers_list)

        if self['tv_specifier'].episode is not None:
            return "{t} S{s:02d}E{e:02d} [{m}]".format(
                t=self['title'], s=self['tv_specifier'].season,
                e=self['tv_specifier'].episode,
                m=markers)
        else:
            return "{t} - Season {s} [{m}]".format(
                t=self['title'], s=self['tv_specifier'].season, m=markers)

    def _render_summary(self):
        t = tvdb.TVDB()
        result = t.search(self['tv_specifier'])
        return result.summary()

    def _render_section_description(self):
        summary = self['summary']
        if 'episodesummary' in summary:
            return summary['seriessummary'] + bb.spoiler(
                summary['episodesummary'], "Episode description")
        else:
            return summary['seriessummary']

    def _render_section_information(self):
        def imdb_link(r):
            return bb.link(r.name, "https://www.imdb.com"+r.id)

        s = self['summary']
        links = [('TVDB', s['url'])]

        if s['imdb_id']:
            links.append(('IMDb',
                          "https://www.imdb.com/title/" + s['imdb_id']))
        # todo unify rating_bb and episode_fmt
        # get ratings from imdb
        i = imdb.IMDB()
        if self['tv_specifier'].episode is not None:
            if s['imdb_id']:
                rating, votes = i.get_rating(s['imdb_id'])

                rating_bb = (bb.format_rating(rating[0], max=rating[1]) + " " +
                             bb.s1("({votes} votes)".format(
                                 votes=votes)))
            else:
                rating_bb = ""

            description = dedent("""\
            [b]Episode title[/b]: {title} ({links})
            [b]Aired[/b]: {air_date} on {network}
            [b]IMDb Rating[/b]: {rating}
            [b]Director[/b]: {director}
            [b]Writer(s)[/b]: {writers}
            [b]Content rating[/b]: {contentrating}""").format(
                title=s['episode_title'],
                links=", ".join(bb.link(*l) for l in links),
                air_date=s['air_date'],
                network=s['network'],
                rating=rating_bb,
                director=s['director'],
                writers=' | '.join(s['writers']),
                contentrating=s['contentrating']
            )
        else:
            description = dedent("""\
            [b]Network[/b]: {network}
            [b]Content rating[/b]: {contentrating}\n""").format(
                contentrating=s['contentrating'],
                network=s['network'],
            )

            def episode_fmt(e):
                if not e['imdb_id']:
                    return bb.link(e['title'], e['url']) + "\n"

                rating, votes = i.get_rating(e['imdb_id'])
                return (bb.link(e['title'], e['url']) + "\n" +
                        bb.s1(bb.format_rating(*rating)))

            description += "[b]Episodes[/b]:\n" + bb.list(
                map(episode_fmt, s['episodes']), style=1)

        return description

    def _render_description(self):
        sections = [("Description", self['section_description']),
                    ("Information", self['section_information'])]

        description = "\n".join(bb.section(*s) for s in sections)
        description += bb.release
        return description

    @form_field('desc')
    def _render_form_description(self):
        ss = "".join(map(bb.img, self['screenshots']))
        return (self['description'] + "\n" +
                bb.section("Screenshots", bb.center(ss)) +
                bb.mi(self['mediainfo']))


class MovieSubmission(VideoSubmission):
    default_fields = (VideoSubmission.default_fields +
                      ("description", "mediainfo", "screenshots"))
    _form_type = 'Movies'
    __form_fields__ = {
        # field -> form field, type
        'source': ('source', 'text'),
        'video_codec': ('videoformat', 'text'),
        'audio_codec': ('audioformat', 'text'),
        'container': ('container', 'text'),
        'resolution': ('resolution', 'text'),
        'form_release_info': ('remaster_title', 'text'),
        'mediainfo': ('release_desc', 'text'),
        'screenshots': (lambda i, v: 'screenshot' + str(i + 1), 'text'),
        }

    def _render_search_title(self):
        if self['title_arg']:
            return self['title_arg']

        return self['guess']['title']

    def _render_title(self):
        return self['summary']['title']

    @form_field('title')
    def _render_form_title(self):
        return self['title']

    @form_field('year')
    def _render_year(self):
        if 'summary' in self.fields:
            return self['summary']['year']

        elif 'year' in self['guess']:
            return self['guess']['year']

        else:
            while True:
                year = input('Please enter year: ')
                try:
                    year = int(year)
                except ValueError:
                    pass
                else:
                    return year

    def _render_summary(self):
        i = imdb.IMDB()
        movie = i.search(self['search_title'])
        return movie.summary()

    def _render_section_information(self):
        def imdb_link(r):
            return bb.link(r['name'], "https://www.imdb.com"+r['id'])

        # todo: synopsis/longer description
        n = self['options']['num_cast']
        summary = self['summary']
        links = [("IMDb", summary['url'])]

        return dedent("""\
        [b]Title[/b]: {name} ({links})
        [b]MPAA[/b]: {mpaa}
        [b]Rating[/b]: {rating} [size=1]({votes} votes)[/size]
        [b]Runtime[/b]: {runtime}
        [b]Director(s)[/b]: {directors}
        [b]Writer(s)[/b]: {writers}
        [b]Cast[/b]: {cast}""").format(
            links=", ".join(bb.link(*l) for l in links),
            name=summary['name'],
            mpaa=summary['mpaa'],
            rating=bb.format_rating(summary['rating'][0],
                                    max=summary['rating'][1]),
            votes=summary['votes'],
            runtime=summary['runtime'],
            directors=" | ".join(imdb_link(d) for d in summary['directors']),
            writers=" | ".join(imdb_link(w) for w in summary['writers']),
            cast=" | ".join(imdb_link(a) for a in summary['cast'][:n])
        )

    def _render_section_description(self):
        s = self['summary']
        return s['description']

    def _render_description(self):
        # todo: templating, rottentomatoes, ...

        sections = [("Description", self['section_description']),
                    ("Information", self['section_information'])]

        description = "\n".join(bb.section(*s) for s in sections)
        description += bb.release

        return description

    @form_field('desc')
    def _render_form_description(self):
        return self['description']
