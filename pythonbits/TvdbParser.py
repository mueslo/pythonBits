# -*- coding: utf-8 -*-
"""
TvdbParser.py

Created by Ichabond on 2012-07-01.
"""

import re
import sys
import tvdb_api

#todo: clean up this horrid mess
class TVDB(object):
    def __init__(self):
        self.tvdb = tvdb_api.Tvdb(banners=True, actors=True)
        self.episode = None
        self.season = None
        self.show = None

    def search(self, series, season=None, episode=None, ):
        if episode:
            matchers = [re.compile(r'(\d+)x(\d+)'), re.compile(r'(?i)s(\d+)e(\d+)')]
            tv_episode = None
            for matcher in matchers:
                ma = matcher.match(episode)
                if ma:
                    tv_episode = (int(ma.group(1)), int(ma.group(2)))
                    break

            if not tv_episode:
                print >> sys.stderr, "Unable to decipher your tv-episode \"%s\"" % episode
                sys.exit(1)

            self.episode = self.tvdb[series][tv_episode[0]][tv_episode[1]]
            self.season = None
            self.show = self.tvdb[series]
            return self.episode
        if isinstance(season, int):
            self.season = self.tvdb[series][season]
            self.episode = None
            self.show = self.tvdb[series]
            return self.season

        else:
            self.show = self.tvdb[series]
            self.season = None
            self.episode = None
            return self.show

    def banner(self, season_number=-1):
        
        #use highest rated season banner
        season_banners = self.show['_banners']['season']['season']

        best_banner = lambda banners: sorted(
            banners, key=lambda b: float(b.get('rating', 0)))[-1]
                                                    
        season_banners = [banner for banner in self.show['_banners']['season']['season'].values() if banner['season'] == str(season_number)]
               
        
        try:
            return best_banner(season_banners)['_bannerpath']
        except IndexError:
            #failing that, use show banner
            series_banners = [v for r in self.show['_banners']['poster'].values() for k, v in r.items()]
            return best_banner(series_banners)['_bannerpath']
        
    def summary(self):
        if isinstance(self.episode, tvdb_api.Episode) and not self.season:
            return {'title': self.show['seriesname'],
                    'episode_title': self.episode['episodename'],
                    'director': self.episode['director'],
                    'aired': self.episode['firstaired'],
                    'writer': self.episode['writer'],
                    'rating': self.episode['rating'],
                    'summary': self.episode['overview'],
                    'language': self.episode['language'],
                    'genres': self.show['genre'].strip('|').split('|'),
                    'cast': [actor['name'] for actor in self.show['_actors']],
                    'url': "http://thetvdb.com/?tab=episode&seriesid=" + 
                        self.episode['seriesid'] + "&seasonid=" + 
                        self.episode['seasonid'] + "&id=" + self.episode['id'],
                    'seriessummary': self.show['overview'],
                    'cover': self.banner(self.episode['seasonnumber'])}
        
        elif isinstance(self.season, tvdb_api.Season):
            summary = {'episodes': len(self.season),
                       'title': self.show['seriesname']}
            for (counter, episode) in enumerate(self.season):
                summary['url'] = ("http://thetvdb.com/?tab=season&seriesid=" + 
                    self.season[episode]['seriesid'] + "&seasonid=" + 
                    self.season[episode]['seasonid'])
                summary["episode" + str(counter + 1)] = self.season[episode]['episodename']
            summary['summary'] = self.show['overview']
            summary['genres'] = self.show['genre'].strip('|').split('|')
            summary['cast'] = [actor['name'] for actor in self.show['_actors']]
            summary['cover'] = self.banner(self.season[1]['seasonnumber'])
            
            return summary
        
        if isinstance(self.show, tvdb_api.Show):
            raise Exception('is this needed?')
            #return {'series': self.show['seriesname'],
            #        'seasons': len(self.show),
            #        'network': self.show['network'],
            #        'rating': self.show['rating'],
            #        'contentrating': self.show['contentrating'],
            #        'summary': self.show['overview'],
            #        'url': "http://thetvdb.com/?tab=series&id=" + self.show['id']}
