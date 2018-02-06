# -*- coding: utf-8 -*-

import os
import sys
import re
import subprocess
from textwrap import dedent
import unicodedata

import pymediainfo
import guessit

from . import _release as release
from .mktorrent import make_torrent
from .tracker import Tracker
from . import TvdbParser
from . import ImdbParser
from .ImgurUploader import ImgurUploader
from .Ffmpeg import FFMpeg


class SubmissionAttributeError(Exception):
    pass

class InvalidSubmission(SubmissionAttributeError):
    pass

class FieldRenderException(Exception):
    pass


bb_img = lambda x: "[img="+x+"]"
bb_b = lambda x: "[b]"+x+"[/b]"
bb_link = lambda x, y="": "[url={}]{}[/url]".format(x,y)
bb_tiny = lambda x: "[size=1]{}[/size]".format(x)
bb_center = lambda x: "[align=center]{}[/align]".format(x)


class Submission(object):
    def __init__(self, **kwargs):
        self.fields = kwargs
    
    def __getitem__(self, field):
        try:
            return self.fields[field]
        except KeyError as ke:
            try:
                field_renderer = getattr(self, '_render_' + field)
            except AttributeError as ae:
                raise SubmissionAttributeError(
                    self.__class__.__name__ + " does not contain or "
                    "has no rules to generate field '" + field + "'")
            
            try:
                rv = field_renderer()
            except SubmissionAttributeError as e:
                raise FieldRenderException('Could not render field '+field+':\n'+
                                           e.message)
                
            self.fields[field] = rv
            return rv
                
    def __repr__(self):            
        return "\n\n\n".join(
            ["{k}\n{v}".format(k=k,v=v) for k,v in self.fields.items()])

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
            raise InvalidSubmission("Missing field(s) ("+
                                    ", ".join(missing_keys)+")")
        
    def _render_scene(self):
        while True:
            choice = raw_input('Is this a scene release? [y/N] ')
            
            if not choice or choice.lower() == 'n':
                return False
            elif choice.lower() == 'y':
                return True

    def _render_payload_preview(self):
        preview = ""
        
        #todo dict map field names
        #todo truncate mediainfo in preview
        consolewidth = 80
        for t, fields in self['payload'].items():
            for name, value in fields.items():
                preview += ("  "+name+"  ").center(consolewidth, "=") + "\n"
                preview += str(value) + "\n"
            
        return preview
    
    def _render_form_type(self):
        catmap = {'tv': 'TV', 'movie': 'Movies'}
        
        return catmap[self['category']]

    def _render_submit(self):
        payload = self['payload']
        
        print self['payload_preview']
        
        if self['options']['dry_run']:
            return 'Skipping submission due to dry run'
        
        while True:
            print ("Reminder: YOU are responsible for following the submission "
                   "rules!")
            choice = raw_input('Submit these values? [y/n] ')
            
            if not choice:
                pass
            elif choice.lower() == 'n':
                break
            elif choice.lower() == 'y':
                t = Tracker()
                return t.upload(**payload)


title_tv_re = r"^(?P<title>.+)(?<!season) (?P<season_marker>(s|season |))(?P<season>((?<= s)[0-9]{2,})|(?<= )[0-9]+(?=x)|(?<=season )[0-9]+(?=$))((?P<episode_marker>[ex])(?P<episode>[0-9]+))?$"

from collections import namedtuple

TvSpecifier = namedtuple('TvSpecifier', ['title', 'season', 'episode'])

class VideoSubmission(Submission):
    default_fields = ("form_title", "tags", "cover")
    
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
                return TvSpecifier(match.group('title'),
                                   int(match.group('season')),
                                   episode and int(episode)) #if episode is None
            
            #todo: test tv show name from title_arg, but episode from filename
        
        guess = guessit.guessit(self['path'])
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
        def format_tag(tag):
            nfkd_form = unicodedata.normalize('NFKD', tag)
            tag = nfkd_form.encode('ASCII', 'ignore')
            return tag.replace(' ','.'
                    ).replace('-','.'
                    ).replace('\'','.'
                    ).lower()
        
        n = self['options']['num_cast']
        tags = self['summary']['genres']+self['summary']['cast'][:n]
        return ",".join(format_tag(tag) for tag in tags)
    
    def _render_mediainfo_path(self):
        if os.path.isfile(self['path']):
            return self['path']
        
        contained_files = []
        for dp, dns, fns in os.walk(self['path']):
            contained_files += [os.path.join(dp, fn) for fn in fns 
                                if os.path.getsize(os.path.join(dp, fn)) > 10*2**20]

        print "\nWhich file would you like to run mediainfo on? Choices are"
        contained_files.sort()
        for k,v in enumerate(contained_files):
            print "{}: {}".format(k, os.path.relpath(v, self['path']))
        while True:
            try:
                choice = raw_input("Enter [0-{}]: ".format(len(contained_files)-1))
                return contained_files[int(choice)]
            except (ValueError, IndexError):
                pass
            
    def _render_screenshots(self):
        ns = self['options']['num_screenshots']
        ffmpeg = FFMpeg(self['mediainfo_path'])
        images = ffmpeg.takeScreenshots(ns)
        if self['options']['dry_run']:
            print "Upload of screenshots skipped due to dry run"
            return images
        return ImgurUploader(images).upload()
        
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
                general = track
            elif track.track_type == 'Video':
                video_tracks.append(track)
            elif track.track_type == 'Audio':
                audio_tracks.append(track)
            elif track.track_type == 'Text':
                text_tracks.append(track)
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
        sources = ('BluRay', 'BluRay 3D', 'WEB-DL', 'WebRip', 'HDTV', 'DVDSCR', 'CAM')
        #ignored: R5, DVDRip, TeleSync, PDTV, SDTV, BluRay RC, HDRip, VODRip, TC
        #         SDTV, DVD5, DVD9, HD-DVD
        
        #todo: replace with guessit
        if 'bluray' in self['path'].lower():
            return 'BluRay'
            #todo: 3d
        elif 'web-dl' in self['path'].lower() or 'webdl' in self['path'].lower():
            return 'WEB-DL'
        elif 'webrip' in self['path'].lower():
            return 'WebRip' 
        elif 'hdtv' in self['path'].lower():
            return 'HDTV'
        #elif 'dvdscr' in self['path'].lower():
        #    markers['source'] = 'DVDSCR'
        else:
            print "File:", self['path']
            print "Choices:", dict(enumerate(sources))
            while True:
                choice = raw_input("Please specify source: ")
                try:
                    return sources[int(choice)]
                except (ValueError, IndexError):
                    print "Please enter an integer corresponding to your choice"
    
    def _render_container(self):
        general = self['tracks']['general']
        if general.format == 'Matroska':
            return 'MKV'
        elif general.format == 'AVI':
            return 'AVI'
        elif general.format == 'MPEG-4':
            return 'MP4'
        else:
            raise Exception("Unknown or unsupported container", general.format)

    
    def _render_video_codec(self):
        video_track = self['tracks']['video']
        bit_rate = video_track.bit_rate or video_track.nominal_bit_rate
        #print 'Resolution-normalised bitrate:', float(bit_rate)/(video_track.width*video_track.height), 'b/(px s) [higher is better]'
        if video_track.codec in ('V_MPEG4/ISO/AVC', 'AVC'):
            if video_track.writing_library and 'x264' in video_track.writing_library:
                return 'x264'
            else:
                return 'H.264'
        elif video_track.codec == 'XVID':
            return 'XVid'
        else:
            raise Exception("Unknown or unsupported video codec", 
                            video_track.codec, video_track.writing_library)
    
    def _render_audio_codec(self):
        audio_tracks = self['tracks']['audio']
        audio_track = audio_tracks[0]  # main audio track
        if audio_track.codec in ('AC3', 'AC3+'):
            return 'AC-3'
        elif audio_track.codec in ('DTS', 'FLAC', 'AAC'):
            return audio_track.codec
        elif audio_track.codec == 'AAC LC':
            return 'AAC'
        elif audio_track.codec == 'DTS-HD':
            return 'DTS'
        else:
            raise Exception("Unkown or unsupported audio codec", 
                            audio_track.codec)
    
    def _render_resolution(self):
        resolutions = ('1080p', '720p', '1080i', '720i', '480p', '480i', 'SD')
        
        
        #todo: replace with regex?
        #todo: compare result with mediainfo
        for res in resolutions:
            if res.lower() in self['path'].lower():
                #warning: 'sd' might match any ol' title, but it's last anyway
                return res
        else:
            print "File:", self['path']
            print "Choices:", dict(enumerate(resolutions))
            while True:
                choice = raw_input("Please specify resolution: ")
                try:
                    return resolutions[int(choice)]
                except (ValueError, IndexError):
                    print "Please enter an integer corresponding to your choice"
        # from mediainfo and filename
        
    def _render_additional(self):
        additional = []
        audio_tracks = self['tracks']['audio']
        text_tracks = self['tracks']['text']
        
        for track in audio_tracks[1:]:
            if track.title and 'commentary' in track.title.lower():
                additional.append('w. Commentary')
        
        if text_tracks:
            additional.append('w. Subtitles')
        #print [(track.title, track.language) for track in text_tracks]
        
        return additional
    
    def _render_form_release_info(self):
        return " / ".join(self['additional'])
    
    def _render_cover(self):
        banner_url = self['summary']['cover']
        if self['options']['dry_run']:
            print 'Upload of cover image skipped due to dry run'
            return banner_url
        return ImgurUploader([banner_url]).upload()[0]


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
        tvdb = TvdbParser.TVDB()
        episode = self['tv_specifier'].episode
        season = self['tv_specifier'].season
        if episode: # Episode
            tvdb.search(self['search_title'],
                        episode="S{:0d}E{:0d}".format(season, episode))
        else: # Season pack
            tvdb.search(self['search_title'], season=season)
    
        #todo offer choice of cover if multiple?
        return tvdb.summary()
    
    def _render_description(self):
        summary = self['summary']
        
        # todo: fix this horrid mess
        description = "[b]Description[/b] \n"
        if 'seriessummary' in summary:
            description += "[quote]%s\n[spoiler]%s[/spoiler][/quote]\n" % (
                summary['seriessummary'], summary['summary'])
        else:
            description += "[quote]%s[/quote]\n" % summary['summary']
        description += "[b]Information:[/b]\n"
        description += "[quote]TVDB Url: %s\n" % summary['url']
        if 'episode_title' in summary:
            description += "Episode title: %s\n" % summary['episode_title']
        description += "Show: %s\n" % summary['title']
        if 'aired' in summary:
            description += "Aired: %s\n" % summary['aired']
        if 'rating' in summary:
            description += "Rating: %s\n" % summary['rating']
        if 'director' in summary:
            description += "Director: %s\n" % summary['director']
        if 'writer' in summary:
            description += "Writer(s): %s\n" % summary['writer']
        if 'network' in summary:
            description += "Network: %s\n" % summary['network']
        if 'seasons' in summary:
            description += "Seasons: %s\n" % summary['seasons']
        if 'season' in summary:
            description += "Season: %s\n" % summary['season']
        if 'episode1' in summary:
            description += "Episodes:\n[list=1]\n"
            for i, key in enumerate(summary):
                if i in range(1, summary['episodes'] + 1):
                    description += "[*] %s\n" % summary['episode' + str(i)]
            description += "[/list]"
        description += "[/quote]\n"

        description += bb_center(bb_tiny("Generated by "+release))
        return description
    
    def _render_form_description(self):
        ss = "".join(map(bb_img, self['screenshots']))
        return ("{dt}\n"
                "Screenshots:\n"
                "[quote][align=center]"
                "{ss}"
                "[/align][/quote]\n"
                "[mediainfo]{mi}[/mediainfo]").format(
                    dt=self['description'],
                    ss=ss,
                    mi=self['mediainfo'])
    
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
        
        return guessit.guessit(self['path'])['title']
    
    def _render_title(self):
        return self['summary']['title']
    
    def _render_form_title(self):
        return self['title']
    
    def _render_year(self):
        return guessit.guessit(self['path'])['year']
    
    def _render_summary(self):
        imdb = ImdbParser.IMDB()
        imdb.search(self['search_title'])
        imdb.movieSelector()
        return imdb.summary()
    
    def _render_description(self):
        # todo: templating, rottentomatoes
        summary = self['summary']
        
        description = dedent("""\
        [b]Description[/b]
        [quote]{description}[/quote]
        [b]Information:[/b]
        [quote]IMDB Url: {url}
        Title: {name}
        Year: {year}
        MPAA: {mpaa}
        Rating: {rating}
        Votes: {votes}
        Runtime: {runtime}
        Director(s): {directors}
        Writer(s): {writers}
        [/quote]""").format(
            description=summary['description'],
            url=summary['url'],
            name=summary['name'],
            year=summary['year'],
            mpaa=summary['mpaa'],
            rating=summary['rating'],
            votes=summary['votes'],
            runtime=summary['runtime'],
            directors=summary['directors'],
            writers=summary['writers'],
            )
        
        description += bb_center(bb_tiny("Generated by "+release))
            
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
            data['screenshot'+str(i)] = s
        
        if self['scene']:
            data['scene'] = 'on'
            
        return {'files': files, 'data': data}
    
    def _render_form_description(self):
        return self['description']
    
