# -*- coding: utf-8 -*-
import os
import sys
import shutil
import re
import subprocess

from textwrap import dedent
from collections import namedtuple, abc
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import timedelta
from mimetypes import guess_type

import pymediainfo
import mutagen
import guessit
from unidecode import unidecode
from requests.exceptions import HTTPError

from .config import config
from .logging import log
from .torrent import make_torrent
from . import tvdb
from . import imdb
from . import musicbrainz as mb
from . import imagehosting
from .ffmpeg import FFMpeg
from . import templating as bb
from .submission import (Submission, form_field, finalize,
                         SubmissionAttributeError, rlinput)
from .tracker import Tracker
from .scene import is_scene_crc, query_scene_fname


def format_tag(tag):
    tag = unidecode(tag)
    if '/' in tag:
        # Multiple actors can be listed as a single actor like this:
        # "Thierry Kazazian / Max Mittleman"
        # (e.g. for "Miraculous: Tales of Ladybug & Cat Noir")
        tag = tag[:tag.index('/')].strip()
    return tag.replace(' ', '.').replace('-', '.').replace('\'', '.').lower()


def format_choices(choices):
    return ", ".join([
        str(num) + ": " + value
        for num, value in enumerate(choices)
    ])


class BbSubmission(Submission):
    default_fields = ("form_title", "tags", "cover")

    def show_fields(self, fields):
        return super(BbSubmission, self).show_fields(
            fields or self.default_fields)

    def confirm_finalization(self, fields):
        return super(BbSubmission, self).confirm_finalization(
            fields or self.default_fields)

    def subcategory(self):
        path = self['path']
        if os.path.isfile(path):
            files = [(os.path.getsize(path), path)]
        else:
            files = []

        for root, _, fs in os.walk(path):
            for f in fs:
                fpath = os.path.join(root, f)
                files.append((os.path.getsize(fpath), fpath))

        for _, path in sorted(files, reverse=True):
            mime_guess, _ = guess_type(path)
            if mime_guess:
                mime_guess = mime_guess.split('/')
                if mime_guess[0] == 'video':
                    return VideoSubmission
                elif mime_guess[0] == 'audio':
                    return AudioSubmission

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
        # todo: if path is directory, choose file for crc
        path = os.path.normpath(self['path'])  # removes trailing slash
        try:
            try:
                if os.path.exists(path) and not os.path.isdir(path):
                    return is_scene_crc(path)
            except KeyboardInterrupt:
                sys.stdout.write('...skipped\n')

            query_scene_fname(path)
        except HTTPError as e:
            log.notice(e)

        while True:
            choice = input('Is this a scene release? [y/N] ')

            if not choice or choice.lower() == 'n':
                return False
            elif choice.lower() == 'y':
                return True

    def data_method(self, source, target):
        def copy(source, target):
            if os.path.isfile(source):
                return shutil.copy(source, target)
            if os.path.isdir(source):
                return shutil.copytree(source, target)
            raise Exception('Source {} is neither '
                            'file nor directory'.format(source))

        cat_methods_map = {
            'movie': ['hard', 'sym', 'copy', 'move'],
            'tv': ['hard', 'sym', 'copy', 'move'],
            'music': ['copy', 'move'],
            }

        method_map = {'hard': os.link,
                      'sym': os.symlink,
                      'copy': copy,
                      'move': shutil.move}

        # use cmd line option if specified
        option_method = self['options'].get('data_method', 'auto')
        if option_method != 'auto':
            method = option_method
        else:
            pref_method = config.get('Torrent', 'data_method')
            if pref_method not in method_map:
                log.warning(
                    'Preferred method {} not valid. '
                    'Choices are {}'.format(pref_method,
                                            list(method_map.keys())))
            try:
                # todo fix this, proper category mapping,
                #  e.g. 'music' <-> bb.MusicSubmission
                category = ('music' if isinstance(self, AudioSubmission)
                            else 'movie')
            except AttributeError:
                log.warning("{} does not have a category attribute",
                            type(self).__name__)
                category = 'movie'  # use movie data methods

            cat_methods = cat_methods_map[category]
            if pref_method in cat_methods:
                # use user preferred method if in category method list
                method = pref_method
            else:
                # otherwise use first category method
                method = cat_methods[0]

        log.notice('Copying data using \'{}\' method', method)
        return method_map[method](source, target)

    @finalize
    @form_field('file_input', 'file')
    def _render_torrentfile(self):
        return make_torrent(self['path'])

    def _finalize_torrentfile(self):
        # move data to upload directory
        up_dir = config.get('Torrent', 'upload_dir')
        path_dir, path_base = os.path.split(self['path'])
        if up_dir and not os.path.samefile(up_dir, path_dir):
            target = os.path.join(up_dir, path_base)
            if not os.path.exists(target):
                self.data_method(self['path'], target)
            else:
                log.notice('Data method target already exists, skipping...')

        # black hole
        bh_dir = config.get('Torrent', 'black_hole')
        if bh_dir:
            fname = os.path.basename(self['torrentfile'])
            dest = os.path.join(bh_dir, fname)

            try:
                assert os.path.exists(bh_dir)
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
        return dict(guessit.guessit(self['path']))

    def subcategory(self):
        if type(self) == VideoSubmission:
            if self['tv_specifier']:
                return TvSubmission
            else:
                return MovieSubmission
        return type(self)

    def _render_title(self):
        # Use format "<original title> AKA <english title>" where applicable
        title_original = self['summary']['title']
        title_english = self['summary']['titles'].get('XWW', None)
        if title_english is not None and title_original != title_english:
            return '{} AKA {}'.format(title_original, title_english)
        else:
            return title_original

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
            try:
                season = guess['season']
            except KeyError:
                raise Exception('Could not find a season in the path name. '
                                'Try specifying it in the TITLE argument, '
                                'e.g. "Some TV Show S02" for a season 2 pack')
            return TvSpecifier(title, season, guess.get('episode'))

    @form_field('tags')
    def _render_tags(self):
        # todo: get episode-specific actors (from imdb?)

        n = self['options']['num_cast']
        tags = list(self['summary']['genres'])
        tags += [a['name']
                 for a in self['summary']['cast'][:n]
                 if a['name']]

        # Maximum tags length is 200 characters
        def tags_string(tags):
            return ",".join(format_tag(tag) for tag in tags)
        while len(tags_string(tags)) > 200:
            del tags[-1]
        return tags_string(tags)

    def _render_mediainfo_path(self):
        assert os.path.exists(self['path'])
        if os.path.isfile(self['path']):
            return self['path']

        contained_files = []
        for dp, dns, fns in os.walk(self['path']):
            contained_files += [os.path.join(dp, fn) for fn in fns
                                if (os.path.getsize(os.path.join(dp, fn))
                                    > 10 * 2**20)]
        if len(contained_files) == 1:
            return contained_files[0]

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
        return imagehosting.upload(*self['screenshots'])

    def _render_mediainfo(self):
        try:
            path = self['mediainfo_path']
            if os.name == "nt":
                mi = subprocess.Popen([r"mediainfo", path], shell=True,
                                      stdout=subprocess.PIPE
                                      ).communicate()[0].decode('utf8')
            else:
                mi = subprocess.Popen([r"mediainfo", path],
                                      stdout=subprocess.PIPE
                                      ).communicate()[0].decode('utf8')
        except OSError:
            sys.stderr.write(
                "Error: Media Info not installed, refer to "
                "http://mediainfo.sourceforge.net/en for installation")
            exit(1)
        else:
            # Replace absolute path with file name
            mi_dir = os.path.dirname(self['mediainfo_path']) + '/'
            mi = mi.replace(mi_dir, '')

            # bB's mediainfo parser expects "Xbps" instead of "Xb/s"
            mi = mi.replace('Kb/s', 'Kbps') \
                   .replace('kb/s', 'Kbps') \
                   .replace('Mb/s', 'Mbps')
            return mi

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
        regpath = self['path'].lower().replace('-', '')
        if 'bluray' in regpath:
            return 'BluRay'  # todo: 3d
        elif 'webdl' in regpath:
            return 'WEB-DL'
        elif 'webrip' in regpath:
            return 'WebRip'
        elif 'hdtv' in regpath:
            return 'HDTV'
        # elif 'dvdscr' in self['path'].lower():
        #    markers['source'] = 'DVDSCR'
        else:
            print("File:", self['path'])
            print("Choices:", format_choices(sources))
            while True:
                choice = input("Please specify a source by number: ")
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
        elif general['format'] == 'BDAV':
            return 'm2ts'
        else:
            raise RuntimeError("Unknown or unsupported container '{}'".format(
                general.format))

    def _render_video_codec(self):
        video_track = self['tracks']['video']
        # norm_bitrate = (float(bit_rate) /
        #     (video_track.width*video_track.height))
        if (video_track['codec_id'] in ('V_MPEG4/ISO/AVC', 'AVC', 'avc1') or
                video_track['format'] == 'AVC'):
            if 'x264' in video_track.get('writing_library', ''):
                return 'x264'
            else:
                return 'H.264'
        elif video_track['codec_id'] in ('V_MPEGH/ISO/HEVC', 'HEVC'):
            if 'x265' in video_track.get('writing_library', ''):
                return 'x265'
            else:
                return 'H.265'
        elif video_track['codec_id'] in ('V_MS/VFW/FOURCC / WVC1',):
            return 'VC-1'
        elif 'VP9' in video_track['codec_id']:
            return 'VP9'
        elif video_track['codec_id'] == 'XVID':
            return 'XVid'
        elif video_track['format'] == 'MPEG Video':
            return 'MPEG-2'
        else:
            msg = "Unknown or unsupported video codec '{}' ({})".format(
                            video_track.get('codec_id'),
                            video_track.get('writing_library'))
            raise RuntimeError(msg)

    def _render_audio_codec(self):
        audio_track = self['tracks']['audio'][0]  # main audio track
        if (audio_track.get('codec_id_hint') == 'MP3' or
                audio_track['codec_id'] in ('MPA1L3', '55')):
            return 'MP3'
        elif audio_track['codec_id'].lower().startswith('mp4a'):
            return 'AAC'
        elif 'Dolby Atmos' in audio_track['commercial_name']:
            return 'Dolby Atmos'
        elif 'DTS-HD' in audio_track['commercial_name']:
            if audio_track.get('other_format', '') == 'DTS XLL X':
                return 'DTS:X'
            return 'DTS-HD'

        if audio_track['codec_id'].startswith('A_'):
            audio_track['codec_id'] = audio_track['codec_id'][2:]
        audio_codecs = ('AC3', 'EAC3', 'DTS', 'FLAC', 'AAC', 'MP3', 'TRUEHD',
                        'PCM')
        for c in audio_codecs:
            if audio_track['codec_id'].startswith(c):
                c = c.replace('EAC3', 'AC-3') \
                     .replace('AC3', 'AC-3') \
                     .replace('TRUEHD', 'True-HD')
                return c

        raise ValueError("Unknown or unsupported audio codec '{}'".format(
            audio_track['codec_id']))

    def _render_resolution(self):
        resolutions = ('2160p', '1080p', '720p', '1080i', '720i',
                       '480p', '480i', 'SD')

        # todo: replace with regex?
        # todo: compare result with mediainfo
        for res in resolutions:
            if res.lower() in self['path'].lower():
                # warning: 'sd' might match any ol' title, but it's last anyway
                return res
        else:
            print("File:", self['path'])
            print("Choices:", format_choices(resolutions))
            while True:
                choice = input("Please specify a resolution by number: ")
                try:
                    return resolutions[int(choice)]
                except (ValueError, IndexError):
                    print("Please enter a valid choice")
        # from mediainfo and filename

    def _render_additional(self):
        additional = []
        video_track = self['tracks']['video']
        audio_tracks = self['tracks']['audio']
        text_tracks = self['tracks']['text']

        # print [(track.title, track.language) for track in text_tracks]
        # todo: rule checking, e.g.
        # main_audio = audio_tracks[0]
        # if (main_audio.language and main_audio.language != 'en' and
        #         not self['tracks']['text']):
        #     raise BrokenRule("Missing subtitles")

        if 'remux' in os.path.basename(self['path']).lower():
            additional.append('REMUX')

        if self['guess'].get('proper_count') and self['scene']:
            additional.append('PROPER')

        edition = self['guess'].get('edition')
        if isinstance(edition, str):
            additional.append(edition)
        elif isinstance(edition, abc.Sequence):
            additional.extend(edition)

        if 'BT.2020' in video_track.get('color_primaries', ''):
            additional.append('HDR10')

        for track in audio_tracks[1:]:
            if 'title' in track and 'commentary' in track['title'].lower():
                additional.append('w. Commentary')
                break
        if text_tracks:
            additional.append('w. Subtitles')

        return additional

    def _render_form_release_info(self):
        return " / ".join(self['additional'])

    @finalize
    @form_field('image')
    def _render_cover(self):
        return self['summary']['cover']

    def _finalize_cover(self):
        return imagehosting.upload(self['cover'])


class TvSubmission(VideoSubmission):
    default_fields = VideoSubmission.default_fields + ('form_description',)
    _form_type = 'TV'
    __form_fields__ = {
        'form_title': ('title', 'text'),
        'form_description': ('desc', 'text'),
        }

    @property
    def season(self):
        return self['tv_specifier'].season

    def _render_guess(self):
        return dict(guessit.guessit(self['path'],
                                    options=('--type', 'episode')))

    def _render_search_title(self):
        return self['tv_specifier'].title

    def subcategory(self):
        if type(self) == TvSubmission:
            if self['tv_specifier'].episode is None:
                return SeasonSubmission
            else:
                return EpisodeSubmission

        return type(self)

    @staticmethod
    def tvdb_title_i18n(result):
        try:
            tvdb_sum = result.summary()
            imdb_id = tvdb_sum['show_imdb_id']
            i = imdb.IMDB()
            imdb_info = i.get_info(imdb_id)
        except Exception as e:
            log.error(e)
            return {'titles': {}}

        imdb_sum = imdb_info.summary()
        tvdb_title = tvdb_sum['title']
        titles_d = {}
        # Original title
        titles_d['title'] = imdb_sum['title']
        # dict of international titles
        titles_d['titles'] = imdb_sum['titles']
        # "XWW" is IMDb's international title, but unlike TVDB, it doesn't
        # include the year if there are multiple shows with the same name.
        if 'XWW' in titles_d['titles']:
            titles_d['titles']['XWW'] = tvdb_title
        return titles_d

    def _render_markers(self):
        return [self['source'], self['video_codec'],
                self['audio_codec'], self['container'],
                self['resolution']] + self['additional']

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


class EpisodeSubmission(TvSubmission):
    @property
    def episodes(self):
        episodes = self['tv_specifier'].episode
        if isinstance(episodes, abc.Sequence):
            return episodes
        return [episodes]

    @form_field('title')
    def _render_form_title(self):
        return "{t} S{s:02d}{es} [{m}]".format(
            t=self['title'], s=self.season,
            es="".join("E{:02d}".format(e)
                       for e in self.episodes),
            m=" / ".join(self['markers']))

    def _render_summary(self):
        t = tvdb.TVDB()
        results = t.search(self['tv_specifier'])
        title_i18n = self.tvdb_title_i18n(results[0])
        summaries = []
        show_summary = results[0].show_summary()
        for result in results:
            summary = result.summary()
            summaries.append(summary)

        ks = summaries[0].keys()
        assert all(s.keys() == ks for s in summaries)
        summary = {k: [s[k] for s in summaries] for k in ks}
        summary.update(**show_summary)
        summary.update(**title_i18n)
        summary['cover'] = summary['cover'][0]
        return summary

    def _render_section_description(self):
        summary = self['summary']
        return (summary['seriessummary'] +
                "".join(bb.spoiler(es, "Episode description")
                        for es in summary['episodesummary']))

    def _render_section_information(self):
        s = self['summary']
        links = [[('TVDB', u)] for u in s['url']]
        rating_bb = []

        for i, imdb_id in enumerate(s['imdb_id']):
            if imdb_id:
                links[i].append(
                    ('IMDb', "https://www.imdb.com/title/" + imdb_id))

                i = imdb.IMDB()
                rating, votes = i.get_rating(imdb_id)

                rating_bb.append(
                    (bb.format_rating(rating[0], max=rating[1]) + " " +
                     bb.s1("({votes} votes)".format(votes=votes))))
            else:
                rating_bb.append("")

        description = dedent("""\
        [b]Episode titles[/b]: {title}
        [b]Aired[/b]: {air_date} on {network}
        [b]IMDb Rating[/b]: {rating}
        [b]Directors[/b]: {directors}
        [b]Writer(s)[/b]: {writers}
        [b]Content rating[/b]: {contentrating}""").format(
            title=' | '.join(
                "{} ({})".format(
                    t, ", ".join(bb.link(*l) for l in ls))  # noqa: E741
                for t, ls in zip(s['episode_title'], links)),
            air_date=' | '.join(s['air_date']),
            network=s['network'],
            rating=' | '.join(rating_bb),
            directors=' | '.join(set(sum(s['directors'], []))),
            writers=' | '.join(set(sum(s['writers'], []))),
            contentrating=s['contentrating']
            )
        return description


class SeasonSubmission(TvSubmission):
    @form_field('title')
    def _render_form_title(self):
        return "{t} - Season {s} [{m}]".format(
            t=self['title'],
            s=self['tv_specifier'].season,
            m=" / ".join(self['markers']))

    def _render_summary(self):
        t = tvdb.TVDB()
        result = t.search(self['tv_specifier'])
        summary = result.summary()
        summary.update(self.tvdb_title_i18n(result))
        return summary

    def _render_section_description(self):
        summary = self['summary']
        return summary['seriessummary']

    def _render_section_information(self):
        s = self['summary']
        links = [('TVDB', s['url'])]

        imdb_id = s.get('show_imdb_id')
        if imdb_id:
            links.append(('IMDb',
                          "https://www.imdb.com/title/" + imdb_id))

        description = dedent("""\
        [b]Network[/b]: {network}
        [b]Content rating[/b]: {contentrating}\n""").format(
            contentrating=s['contentrating'],
            network=s['network'],
            )

        i = imdb.IMDB()
        # todo unify rating_bb and episode_fmt

        def episode_fmt(e):
            if not e['imdb_id']:
                return bb.link(e['title'], e['url']) + "\n"

            try:
                rating, votes = i.get_rating(e['imdb_id'])
            except ValueError:
                return ''
            else:
                return (bb.link(e['title'], e['url']) + "\n" +
                        bb.s1(bb.format_rating(*rating)))

        with ThreadPoolExecutor() as executor:
            episodes = executor.map(episode_fmt, s['episodes'])
        description += "[b]Episodes[/b]:\n" + bb.list(episodes, style=1)
        return description


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

    def _render_guess(self):
        return dict(guessit.guessit(self['path'],
                                    options=('--type', 'movie')))

    def _render_search_title(self):
        if self['title_arg']:
            return self['title_arg']

        return self['guess']['title']

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
            links=", ".join(bb.link(*l) for l in links),  # noqa: E741
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


class AudioSubmission(BbSubmission):
    default_fields = ("description", "form_tags", "year", "cover",
                      "title", "format", "bitrate")

    def subcategory(self):
        release, rg = self['release']

        if 'Audiobook' in rg.get('secondary-type-list', []):
            return AudiobookSubmission
        return MusicSubmission

    @form_field('format')
    def _render_format(self):
        # MP3, FLAC, Ogg, AAC, DTS 5.1 Audio, 24bit FLAC
        # choices = ('MP3', 'FLAC', 'Ogg', 'AAC', '24bit FLAC')

        tl_format = {
            'MP3': 'MP3',
            'EasyMP3': 'MP3',
            'OggVorbis': 'Ogg',
            'OggOpus': 'Ogg',
            'FLAC': 'FLAC',
            'AAC': 'AAC',
            }

        tags = self['tags']
        format = tl_format[tags['format']]
        if format == 'FLAC' and tags['bits_per_sample'] >= 24:
            format = '24bit FLAC'

        return format

    @form_field('bitrate')
    def _render_bitrate(self):
        # 192, V2 (VBR), 256, V0 (VBR), 320, Lossless, Other)
        format = self['format']
        tags = self['tags']
        if format == 'MP3':
            br_mode = tags['bitrate_mode']
            enc_settings = tags['encoder_settings']
            if ('-V 0' in enc_settings or
                    'preset extereme' in enc_settings):
                return 'V0 (VBR)'
            elif ('-V 2' in enc_settings or
                    'preset standard' in enc_settings):
                return 'V2 (VBR)'
            elif br_mode in [mutagen.mp3.BitrateMode.CBR,
                             mutagen.mp3.BitrateMode.UNKNOWN]:
                if abs(tags['bitrate']-192000) < 100:
                    return '192'
                elif abs(tags['bitrate']-256000) < 100:
                    return '256'
                elif abs(tags['bitrate']-320000) < 100:
                    return '320'
            log.debug("br_mode: {}\nenc_settings: {}", br_mode, enc_settings)

        elif 'FLAC' in format:
            return 'Lossless'

        log.debug("format:{}\ntags:{}", format, tags)
        raise RuntimeError('Unrecognized format/bitrate')

    def _render_mediainfo_path(self):
        assert os.path.isdir(self['path'])

        # get first file over 1 MiB
        for dp, _, fns in os.walk(self['path']):
            for fn in fns:
                g = guess_type(fn)[0]
                if g and g.startswith('audio'):
                    return os.path.join(dp, fn)  # return full path
        raise Exception('No media file found')

    def _render_tracklist(self):
        release, _ = self['release']
        full_tracklist = []
        mediumlist = release['medium-list']

        DEFAULT_FORMAT = 'CD'
        for medium in mediumlist:
            log.debug('medium {}', medium.keys())
            title = medium.get('format', DEFAULT_FORMAT)
            if len(mediumlist) > 1:
                title += " {}".format(medium['position'])
                if 'title' in medium:
                    title += ": {}".format(medium['title'])

            tracklist = [
                (t['number'], t['recording']['title'],
                 timedelta(milliseconds=int(t['recording']['length'])))
                for t in medium['track-list']]
            full_tracklist.append((title, tracklist))

        return full_tracklist

    def _render_tags(self):
        tags = mutagen.File(self['mediainfo_path'], easy=True)
        # if type(tags) == mutagen.mp3.MP3:
        #     tags = mutagen.mp3.MP3(self['mediainfo_path'], ID3=EasyID3)

        log.debug('tagsdir', dir(tags.info))
        log.debug('type tags', type(tags))
        log.debug('tags', tags.pprint())

        return {'artist': tags.get('albumartist', tags['artist'])[0],
                'title': tags['album'][0],
                'rid': tags.get('musicbrainz_albumid', [None])[0],
                'format': type(tags).__name__,
                'bitrate': tags.info.bitrate,
                'bitrate_mode': getattr(tags.info, 'bitrate_mode', None),
                'bits_per_sample': getattr(tags.info, 'bits_per_sample',
                                           None),
                'encoder_info': getattr(tags.info, 'encoder_info', None),
                'encoder_settings': getattr(tags.info, 'encoder_settings',
                                            None),
                }

    def _render_release(self):
        tags = self['tags']
        if tags['rid']:
            log.info('Found MusicBrainz release in tags')
            release = mb.musicbrainzngs.get_release_by_id(
                tags['rid'],
                includes=['release-groups', 'media', 'recordings',
                          'url-rels'])['release']
            rg = mb.musicbrainzngs.get_release_group_by_id(
                release['release-group']['id'],
                includes=['tags', 'artist-credits', 'url-rels']
                )['release-group']

        else:
            if self['title_arg']:
                query_artist = None
                query = self['title_arg']
            else:
                query_artist = tags['artist']
                query = tags['title']
            rg, release = mb.find_release(query, artist=query_artist)

        # identify self:
        #  - num tracks todo
        #  - scan for mb tags
        log.debug('release-group {}', rg)
        log.debug('release', release)

        # todo: assert release group matches!
        #  e.g.: assert # of tracks equal
        #  and if not, generate basic info from release group only

        return release, rg

    def _render_summary(self):
        release, rg = self['release']

        return {
            'artist': rg['artist-credit-phrase'],
            'title': rg['title'],
            'year': rg['first-release-date'][:4],
            'tags': [t['name'] for t in
                     sorted(rg.get('tag-list', []),
                            key=lambda t: int(t['count']))][-5:],
            'media': [m.get('format', 'CD') for m in release['medium-list']],
            'cover': mb.get_artwork(rg['id']),
            }

    @finalize
    @form_field('image')
    def _render_cover(self):
        cover = self['summary']['cover']
        assert cover is not None
        return cover

    def _finalize_cover(self):
        return imagehosting.upload(self['cover'])

    @form_field('year')
    def _render_year(self):
        return self['summary']['year']

    def _render_links(self):
        release, rg = self['release']
        try:
            return rg['url-relation-list']
        except KeyError:
            log.warning('No links found for release group, trying release.')

        try:
            return release['url-relation-list']
        except KeyError:
            log.warning('No links found for release.')
            return []

    def _render_section_information(self):
        release, rg = self['release']
        urls = self['links']
        mb_link = "https://musicbrainz.org/release-group/" + rg['id']
        urls.insert(0, {'type': 'MusicBrainz', 'target': mb_link})
        return dedent("""\
                [b]Title[/b]: {title} ({links})
                [b]Artist(s)[/b]: {artist}
                [b]Type[/b]: {type}
                [b]Original release[/b]: {firstrel}""").format(
            title=rg['title'],
            artist=rg['artist-credit-phrase'],
            links=", ".join(bb.link(u['type'], u['target']) for u in urls),
            type=rg['type'],
            firstrel=rg['first-release-date'],
            )

    def _render_section_tracklist(self):
        s = ""
        for title, tracks in self['tracklist']:
            s += title
            s += bb.table("".join(bb.tr(bb.td(i) +
                                        bb.td(tt) +
                                        bb.td(str(l).split(".")[0]))
                                  for i, tt, l in tracks))

        return s

    @form_field('album_desc')
    def _render_description(self):
        sections = [("Information", self['section_information'])]

        description = "\n".join(bb.section(*s) for s in sections)
        description += bb.release

        return description

    @form_field('release_desc')
    def _render_release_desc(self):
        release, rg = self['release']
        tags = self['tags']
        s = dedent("""\
                [b]MusicBrainz[/b]: [url]{release}[/url]
                [b]Status[/b]: {status}
                [b]Release[/b]: {thisrel} ({country})""").format(
            release="https://musicbrainz.org/release/" + release['id'],
            status=release['status'],
            thisrel=release['date'],
            country=release['country'],
            )

        if tags['encoder_info']:
            s += "\n[b]Encoder[/b]: " + tags['encoder_info']

        if tags['encoder_settings']:
            s += "\n[b]Encoder settings[/b]: " + tags['encoder_settings']

        sections = [("Release Information", s),
                    ("Track list", self['section_tracklist'])]

        description = "\n".join(bb.section(*s) for s in sections)
        description += bb.release

        return description

    @form_field('scene', 'checkbox')
    def _render_scene(self):
        return False

    def _get_tags(self, required_tags):
        tags = self['summary']['tags']
        if not tags:
            tags = input("No tags found. Please enter tags "
                         "(comma-separated): ").split(',')
        tags = set(format_tag(tag) for tag in tags)
        tags -= {'audiobook'}
        while True:
            try:
                assert tags & required_tags != set()
            except AssertionError:
                print("Default tags:\n" + ", ".join(sorted(required_tags)))
                print("Submission must contain at least one default tag.")
                tags = rlinput("Enter tags: ", ",".join(tags)).split(',')
                tags = set(format_tag(tag) for tag in tags)
            else:
                return ",".join(tags)


class AudiobookSubmission(AudioSubmission):
    _form_type = 'Audiobooks'

    @form_field('tags')
    def _render_form_tags(self):
        _defaults = {'fiction', 'non.fiction'}
        return self._get_tags(_defaults)

    @form_field('title')
    def _render_title(self):
        return "{} - {}".format(
            self['summary']['artist'], self['summary']['title'])


class MusicSubmission(AudioSubmission):
    default_fields = (AudioSubmission.default_fields + (
         'artist', 'remaster', 'remaster_year', 'remaster_title', 'media',))
    _form_type = 'Music'

    @form_field('remaster_true', 'checkbox')
    def _render_remaster(self):
        # todo user input function/module to reduce boilerplating
        return bool(
            input('Is this a special/remastered edition? [y/N] ').lower()
            == 'y')

    @form_field('remaster_year')
    def _render_remaster_year(self):
        if self['remaster']:
            return input('Please enter the remaster year: ')

    @form_field('remaster_title')
    def _render_remaster_title(self):
        if self['remaster']:
            return (input('Please enter the remaster title (optional): ')
                    or None)

    @form_field('media')
    def _render_media(self):
        # choices = ['CD', 'DVD', 'Vinyl', 'Soundboard', 'DAT', 'Web']

        media = self['summary']['media']
        if len(media) > 1:
            log.debug(media)
        media = media[0]

        if media == 'CD':
            return media
        elif media == 'Digital Media':
            return 'Web'
        elif "vinyl" in media.lower():
            return 'Vinyl'

        raise NotImplementedError(media)

    @form_field('tags')
    def _render_form_tags(self):
        _defaults = {
            'acoustic', 'alternative', 'ambient', 'blues', 'classic.rock',
            'classical', 'country', 'dance', 'dubstep', 'electronic',
            'experimental', 'folk', 'funk', 'hardcore', 'heavy.metal',
            'hip.hop', 'indie', 'indie.pop', 'instrumental', 'jazz', 'metal',
            'pop', 'post.hardcore', 'post.rock', 'progressive.rock',
            'psychedelic', 'punk', 'reggae', 'rock', 'soul', 'trance',
            'trip.hop'}
        return self._get_tags(_defaults)

    @form_field('artist')
    def _render_artist(self):
        return self['summary']['artist']

    @form_field('title')
    def _render_title(self):
        return self['summary']['title']
