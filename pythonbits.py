#!/usr/bin/env python2
# encoding: utf-8
"""
Pythonbits2.py

Created by Ichabond on 2012-07-01.
"""

__version__ = (2, 1)
__version_str__ = '.'.join(str(x) for x in __version__)

import sys
import os
import re
import subprocess
from textwrap import dedent
import unicodedata

import ImdbParser
import TvdbParser

from Screenshots import createScreenshots

from ImgurUploader import ImgurUploader

from mktorrent import make_torrent

from argparse import ArgumentParser


def generateSeriesSummary(summary):
    description = "[b]Description[/b] \n"
    if 'seriessummary' in summary:
        description += "[quote]%s\n[spoiler]%s[/spoiler][/quote]\n" % (
            summary['seriessummary'], summary['summary'])
    else:
        description += "[quote]%s[/quote]\n" % summary['summary']
    description += "[b]Information:[/b]\n"
    description += "[quote]TVDB Url: %s\n" % summary['url']
    if 'title' in summary:
        description += "Title: %s\n" % summary['title']
    description += "Show: %s\n" % summary['series']
    if 'aired' in summary:
        description += "Aired: %s\n" % summary['aired']
    if 'rating' in summary:
        description += "Rating: %s\n" % summary['rating']
    if 'genre' in summary:
        description += "Genre: %s\n" % summary['genre']
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
    description += "[/quote]"

    return description


def generateMovieDescription(summary):
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
        
    return description

def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = nfkd_form.encode('ASCII', 'ignore')
    return only_ascii

def generateTags(summary, num_cast=5):
    cast = [remove_accents(actor
                      ).replace(' ','.'
                      ).replace('-','.'
                      ).replace('\'','.'
                      ).lower() for actor in summary['cast']]
    genres = [g.replace('-','.').lower() for g in summary['genres']]
    return genres+cast[:num_cast]

def findMediaInfo(path):
    mediainfo = None
    try:
        if os.name == "nt":
            mediainfo = subprocess.Popen([r"mediainfo", path], shell=True, stdout=subprocess.PIPE).communicate()[0]
        else:
            mediainfo = subprocess.Popen([r"mediainfo", path], stdout=subprocess.PIPE).communicate()[0]
    except OSError:
        sys.stderr.write(
            "Error: Media Info not installed, refer to http://mediainfo.sourceforge.net/en for installation")
        exit(1)

    return mediainfo

def parse_title(fname):
    pass

def main(argv):
    parser = ArgumentParser(version="%%prog %s" % __version_str__, description="A Python pretty printer for generating attractive movie descriptions with screenshots.")
    parser.add_argument("title", metavar='TITLE', help="Title of media (e.g. \"The Walking Dead S01\")")
    parser.add_argument("path", metavar='PATH', help="File or directory of media")
    
    feature_toggle = parser.add_argument_group(title="Feature toggle", description="Enables only the selected features, while everything else will not be executed.")
    default_features = ["d", "i", "s"]
    feature_toggle.add_argument("-d", "--description", action="append_const",
        const="d", help="Generate description of media (default on)", dest="tags")
    feature_toggle.add_argument("-i", "--mediainfo", action="append_const", 
        const="i", help="Generate mediainfo output (default on)", dest="tags")
    feature_toggle.add_argument("-s", "--screenshots", action="append_const", 
        const="s", help="Generate screenshots and upload to imgur (default on)", dest="tags")
    feature_toggle.add_argument("-t", "--torrent", action="append_const", 
        const="t", help="Generate torrent file from given PATH (default off)", dest="tags")
    
    options = parser.add_argument_group(title="Tunables", description="Additional options such as number of screenshots")
    options.add_argument("--num-screenshots", type=int, default=2, action="store", help="Number of screenshots (default 2)")
    
    args = parser.parse_args()
    if args.tags is None:
        args.tags = default_features
    
    filename = args.path
    if "s" in args.tags:
        screenshot = createScreenshots(filename, shots=args.num_screenshots)
        if "d" not in args.tags:
            for shot in screenshot:
                print shot
    
    if "i" in args.tags:
        mediainfo = findMediaInfo(filename)
        if "d" not in args.tags:
            print "[mediainfo]\n{}\n[/mediainfo]".format(mediainfo)
    
    if "d" in args.tags:
        tv_re = r"^(?P<title>.+)(?<!season) (?P<season_marker>(s|season |))(?P<season>((?<= s)[0-9]{2,})|(?<= )[0-9]+(?=x)|(?<=season )[0-9]+(?=$))((?P<episode_marker>[ex])(?P<episode>[0-9]+))?$"
        match = re.match(tv_re, args.title, re.IGNORECASE)
        if match: # TV
            search_string = match.group('title')
            tvdb = TvdbParser.TVDB()
            if match.group('episode'): # Episode
                episode_string = "S"+match.group('season')+"E"+match.group('episode')
                tvdb.search(search_string, episode=episode_string)
            else: # Season pack
                tvdb.search(search_string, season=int(match.group('season')))
            summary = tvdb.summary()
            summary = generateSeriesSummary(summary)
            
            if "s" in args.tags:
                summary += "Screenshots:\n[quote][align=center]"
                for shot in screenshot:
                    summary += "[img=%s]" % shot
                summary += "[/align][/quote]"
                
            if "i" in args.tags:
                summary += "[mediainfo]\n%s\n[/mediainfo]" % mediainfo
            print summary
        else: # Movie
            search_string = args.title
            imdb = ImdbParser.IMDB()
            imdb.search(search_string)
            imdb.movieSelector()
            summary = imdb.summary()
            description = generateMovieDescription(summary)
            tags = generateTags(summary)
            print "\n\n\n"
            print "Year: ", summary['year']
            print "\n\n\n"
            print "Tags: ", ",".join(tags)
            print "\n\n\n"
            print "Movie Description: \n", description
            print "\n\n\n"
            if "i" in args.tags:
                print "Mediainfo: \n", "[mediainfo]\n",mediainfo,"\n[/mediainfo]"
            
            if "s" in args.tags:
                for shot in screenshot:
                    print "Screenshot: %s" % shot
                cover = ImgurUploader([summary['cover']]).upload()
                if cover:
                    print "Image (Optional): ", cover[0]
                    
    if "t" in args.tags:
        torrentfile = make_torrent(args.path)
        print "Torrent file created at file://{}".format(torrentfile)


if __name__ == '__main__':
    main(sys.argv)

