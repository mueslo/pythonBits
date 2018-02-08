# -*- coding: utf-8 -*-

import os
import sys
import re
import subprocess
from textwrap import dedent
from collections import namedtuple
from math import floor

import pymediainfo
import guessit
from unidecode import unidecode

from .mktorrent import make_torrent
from .tracker import Tracker
from . import tvdb
from . import imdb
from .imgur import ImgurUploader
from .ffmpeg import FFMpeg
from . import templating as bb


def format_rating(rating, max, limit=10, s=None, fill=None, empty=None):
    if rating is None:
        return "No rating"

    s = s or u'★'
    fill = fill or [0xff, 0xff, 0x00]
    empty = empty or [0xa0, 0xa0, 0xa0]

    limit = min(max, limit)
    num_stars = rating * limit / max
    black_stars = int(floor(num_stars))
    partial_star = num_stars - black_stars
    white_stars = limit - black_stars - 1

    pf = [comp * partial_star for comp in fill]
    pe = [comp * (1 - partial_star) for comp in empty]
    partial_color = bb.fmt_col(map(lambda x, y: int(x+y), pf, pe))

    stars = (bb.color(s * black_stars, bb.fmt_col(fill)) +
             bb.color(s,               partial_color) +
             bb.color(s * white_stars, bb.fmt_col(empty)))
    return str(rating) + '/' + str(max) + ' ' + stars


def format_tag(tag):
    tag = unidecode(tag)
    return tag.replace(' ', '.').replace('-', '.').replace('\'', '.').lower()


class SubmissionAttributeError(Exception):
    pass


class InvalidSubmission(SubmissionAttributeError):
    pass


class FieldRenderException(Exception):
    pass


class Submission(object):
    def __init__(self, **kwargs):
        self.fields = kwargs

    def __getitem__(self, field):
        try:
            return self.fields[field]
        except KeyError:
            try:
                field_renderer = getattr(self, '_render_' + field)
            except AttributeError:
                raise SubmissionAttributeError(
                    self.__class__.__name__ + " does not contain or "
                    "has no rules to generate field '" + field + "'")

            try:
                rv = field_renderer()
            except SubmissionAttributeError as e:
                raise FieldRenderException(
                    'Could not render field ' + field + ':\n' + e.message)

            self.fields[field] = rv
            return rv

    def __repr__(self):
        return "\n".join(
            ["Field {k}:\n\t{v}\n".format(k=k, v=v)
             for k, v in self.fields.items()])

    def _render_torrentfile(self):
        return make_torrent(self['path'])

    def _render_category(self):
        return None

    def cache_fields(self, fields):
        # check that all required values are non-zero
        missing_keys = []
        for k in fields:
            try:
                v = self[k]
            except SubmissionAttributeError as e:
                print e
                missing_keys.append(k)
            else:
                if not v:
                    raise InvalidSubmission(
                        "Value of key {key} is {value}".format(key=k, value=v))

        if missing_keys:
            raise InvalidSubmission("Missing field(s) (" +
                                    ", ".join(missing_keys) + ")")

    def _render_scene(self):
        while True:
            choice = raw_input('Is this a scene release? [y/N] ')

            if not choice or choice.lower() == 'n':
                return False
            elif choice.lower() == 'y':
                return True

    def _render_payload_preview(self):
        preview = ""

        # todo dict map field names
        # todo truncate mediainfo in preview
        consolewidth = 80
        for t, fields in self['payload'].items():
            for name, value in fields.items():
                preview += ("  " + name +
                            "  ").center(consolewidth, "=") + "\n"
                preview += unicode(value) + "\n"

        return preview

    def _render_form_type(self):
        catmap = {'tv': 'TV', 'movie': 'Movies'}

        return catmap[self['category']]

    def _render_submit(self):
        payload = self['payload']

        print self['payload_preview']

        if self['options']['dry_run']:
            print "Note: Dry run. Nothing will be submitted."

        while True:
            print ("Reminder: YOU are responsible for following the "
                   "submission rules!")
            choice = raw_input('Submit these values? [y/n] ')

            if not choice:
                pass
            elif choice.lower() == 'n':
                amend = raw_input("Amend a field? [N/<field name>] ")
                if not amend.lower() or amend.lower() == 'n':
                    return "Cancelled by user"

                try:
                    val = self['payload']['data'][amend]
                except KeyError:
                    print "No field named", amend
                    print "Choices are:", self['payload']['data'].keys()
                else:
                    print "Current value:", val
                    new_value = raw_input("New value (empty to cancel): ")

                    if new_value:
                        self['payload']['data'][amend] = new_value
                        del self.fields['payload_preview']
                        print self['payload_preview']

            elif choice.lower() == 'y':
                if self['options']['dry_run']:
                    return "Skipping submission due to dry run"

                t = Tracker()
                return t.upload(**payload)


title_tv_re = (
    r"^(?P<title>.+)(?<!season) "
    r"(?P<season_marker>(s|season |))"
    r"(?P<season>((?<= s)[0-9]{2,})|(?<= )[0-9]+(?=x)|(?<=season )[0-9]+(?=$))"
    r"((?P<episode_marker>[ex])(?P<episode>[0-9]+))?$")

TvSpecifier = namedtuple('TvSpecifier', ['title', 'season', 'episode'])


class VideoSubmission(Submission):
    default_fields = ("form_title", "tags", "cover")

    def _render_guess(self):
        return {k: v for k, v in guessit.guessit(self['path']).items()}

    def _render_category(self):
        if self['tv_specifier']:
            return 'tv'
        else:
            return 'movie'

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

    def _render_tags(self):
        # todo: get episode-specific actors (from imdb?)
        # todo: offer option to edit tags before submitting
        # todo: tag map, so that either science.fiction or sci.fi will be used,
        #       rules prefer the former (no abbreviations)

        n = self['options']['num_cast']
        tags = list(self['summary']['genres'])
        tags += [a['name'] for a in self['summary']['cast'][:n]]
        return ",".join(format_tag(tag) for tag in tags)

    def _render_mediainfo_path(self):
        if os.path.isfile(self['path']):
            return self['path']

        contained_files = []
        for dp, dns, fns in os.walk(self['path']):
            contained_files += [
                os.path.join(dp, fn) for fn in fns
                if os.path.getsize(os.path.join(dp, fn)) > 10 * 2**20]

        print "\nWhich file would you like to run mediainfo on? Choices are"
        contained_files.sort()
        for k, v in enumerate(contained_files):
            print "{}: {}".format(k, os.path.relpath(v, self['path']))
        while True:
            try:
                choice = raw_input(
                    "Enter [0-{}]: ".format(len(contained_files) - 1))
                return contained_files[int(choice)]
            except (ValueError, IndexError):
                pass

    def _render_screenshots(self):
        ns = self['options']['num_screenshots']
        ffmpeg = FFMpeg(self['mediainfo_path'])
        images = ffmpeg.take_screenshots(ns)
        if self['options']['dry_run']:
            print "Upload of screenshots skipped due to dry run"
            return images
        return ImgurUploader().upload(images)

    def _render_mediainfo(self):
        try:
            path = self['mediainfo_path']
            if os.name == "nt":
                return subprocess.Popen([r"mediainfo", path], shell=True,
                                        stdout=subprocess.PIPE
                                        ).communicate()[0]
            else:
                return subprocess.Popen([r"mediainfo", path],
                                        stdout=subprocess.PIPE
                                        ).communicate()[0]
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
                print "Unknown track", track

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
                   'WebRip', 'HDTV', 'DVDSCR', 'CAM')
        # ignored: R5, DVDRip, TeleSync, PDTV, SDTV, BluRay RC, HDRip, VODRip,
        #          TC, SDTV, DVD5, DVD9, HD-DVD

        # todo: replace with guessit
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
            print "File:", self['path']
            print "Choices:", dict(enumerate(sources))
            while True:
                choice = raw_input("Please specify source: ")
                try:
                    return sources[int(choice)]
                except (ValueError, IndexError):
                    print "Please enter a valid choice"

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

        raise Exception("Unkown or unsupported audio codec",
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
            print "File:", self['path']
            print "Choices:", dict(enumerate(resolutions))
            while True:
                choice = raw_input("Please specify resolution: ")
                try:
                    return resolutions[int(choice)]
                except (ValueError, IndexError):
                    print "Please enter a valid choice"
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

    def _render_cover(self):
        banner_url = self['summary']['cover']
        if self['options']['dry_run']:
            print 'Upload of cover image skipped due to dry run'
            return banner_url
        return ImgurUploader().upload(banner_url)


class TvSubmission(VideoSubmission):
    default_fields = VideoSubmission.default_fields + ('form_description',)

    def _render_category(self):
        return 'tv'

    def _render_search_title(self):
        return self['tv_specifier'].title

    def _render_title(self):
        return self['summary']['title']

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
        if self['tv_specifier'].episode:
            if s['imdb_id']:
                rating, votes = i.get_rating(s['imdb_id'])

                rating_bb = (format_rating(rating[0], max=rating[1]) + " " +
                             bb.s1("({votes} votes)".format(
                                 votes=votes)))
            else:
                rating_bb = ""

            description = dedent(u"""\
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
                writers=u' | '.join(s['writers']),
                contentrating=s['contentrating']
            )
        else:
            description = dedent(u"""\
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
                        bb.s1(format_rating(*rating)))

            description += "[b]Episodes[/b]:\n" + bb.list(
                map(episode_fmt, s['episodes']), style=1)

        return description

    def _render_description(self):
        sections = [("Description", self['section_description']),
                    ("Information", self['section_information'])]

        description = "\n".join(bb.section(*s) for s in sections)
        description += bb.release
        return description

    def _render_form_description(self):
        ss = "".join(map(bb.img, self['screenshots']))
        return (self['description'] + "\n" +
                bb.section("Screenshots", bb.center(ss)) +
                bb.mi(self['mediainfo']))

    def _render_payload(self):
        data = {
            'submit': 'true',
            'type': self['form_type'],
            'title': self['form_title'],
            'tags': self['tags'],
            'desc': self['form_description'],
            'image': self['cover']
        }

        torrentfile = open(self['torrentfile'], 'rb')
        files = {'file_input': (os.path.basename(torrentfile.name),
                                torrentfile,
                                'application/octet-stream')}

        if self['scene']:
            data['scene'] = 'on'

        return {'files': files, 'data': data}


class MovieSubmission(VideoSubmission):
    default_fields = (VideoSubmission.default_fields +
                      ("description", "mediainfo", "screenshots"))

    def _render_category(self):
        return 'movie'

    def _render_search_title(self):
        if self['title_arg']:
            return self['title_arg']

        return self['guess']['title']

    def _render_title(self):
        return self['summary']['title']

    def _render_form_title(self):
        return self['title']

    def _render_year(self):
        # todo: if path does not have year we need to get it from db
        return self['guess']['year']

    def _render_summary(self):
        i = imdb.IMDB()
        movie = i.search(self['search_title'])
        return movie.summary()

    def _render_section_information(self):
        def imdb_link(r):
            return bb.link(r.name, "https://www.imdb.com"+r.id)

        # todo: synopsis/longer description
        n = self['options']['num_cast']
        summary = self['summary']
        links = [("IMDb", summary['url'])]

        return dedent(u"""\
        [b]Title[/b]: {name} ({links})
        [b]MPAA[/b]: {mpaa}
        [b]Rating[/b]: {rating} [size=1]({votes} votes)[/size]
        [b]Runtime[/b]: {runtime}
        [b]Director(s)[/b]: {directors}
        [b]Writer(s)[/b]: {writers}
        [b]Cast[/b]: {cast}""").format(
            links=u", ".join(bb.link(*l) for l in links),
            name=summary['name'],
            mpaa=summary['mpaa'],
            rating=format_rating(summary['rating'][0],
                                 max=summary['rating'][1]),
            votes=summary['votes'],
            runtime=summary['runtime'],
            directors=u" | ".join(imdb_link(d) for d in summary['directors']),
            writers=u" | ".join(imdb_link(w) for w in summary['writers']),
            cast=u" | ".join(imdb_link(a) for a in summary['cast'][:n])
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

    def _render_payload(self):
        data = {
            'submit': 'true',
            'type': self['form_type'],
            'title': self['form_title'],
            'source': self['source'],
            'videoformat': self['video_codec'],
            'audioformat': self['audio_codec'],
            'container': self['container'],
            'resolution': self['resolution'],
            'remaster_title': self['form_release_info'],
            'year': self['year'],
            'tags': self['tags'],
            'desc': self['form_description'],
            'release_desc': self['mediainfo'],
            'image': self['cover'],
        }

        torrentfile = open(self['torrentfile'], 'rb')
        files = {'file_input': (os.path.basename(torrentfile.name),
                                torrentfile,
                                'application/octet-stream')}

        for i, s in enumerate(self['screenshots'], start=1):
            data['screenshot' + str(i)] = s

        if self['scene']:
            data['scene'] = 'on'

        return {'files': files, 'data': data}

    def _render_form_description(self):
        return self['description']
