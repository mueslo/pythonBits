# -*- coding: utf-8 -*-
import tvdb_api


class TvdbResult(object):
    def __init__(self, show, season, episode=None):
        self.show = show
        self.season = season
        self.episode = episode

    def banner(self, season_number=-1):
        # todo offer choice of cover if multiple?
        # use highest rated season banner
        season_banners = self.show['_banners']['season']['season']

        def best_banner(banners): return sorted(
            banners, key=lambda b: float(b.get('rating', 0)))[-1]

        season_banners = [
            banner for banner in season_banners.values()
            if banner['season'] == str(season_number)]

        try:
            return best_banner(season_banners)['_bannerpath']
        except IndexError:
            # failing that, use show banner
            series_banners = [v for r in self.show['_banners']
                              ['poster'].values() for k, v in r.items()]
            return best_banner(series_banners)['_bannerpath']


class TvdbSeason(TvdbResult):
    def summary(self):
        summary = {'episodes': len(self.season),
                   'title': self.show['seriesname']}
        for (counter, episode) in enumerate(self.season):
            summary['url'] = ("http://thetvdb.com/?tab=season&seriesid=" +
                              self.season[episode]['seriesid'] +
                              "&seasonid=" +
                              self.season[episode]['seasonid'])
            summary["episode" + str(counter + 1)
                    ] = self.season[episode]['episodename']
        summary['summary'] = self.show['overview']
        summary['genres'] = self.show['genre'].strip('|').split('|')
        summary['cast'] = [actor['name'] for actor in self.show['_actors']]
        summary['cover'] = self.banner(self.season[1]['seasonnumber'])
        return summary


class TvdbEpisode(TvdbResult):
    def summary(self):
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


class TVDB(object):
    def __init__(self):
        self.tvdb = tvdb_api.Tvdb(banners=True, actors=True)

    def search(self, tv_specifier):
        show = self.tvdb[tv_specifier.title]
        season = show[tv_specifier.season]
        if tv_specifier.episode:
            episode = season[tv_specifier.episode]
            return TvdbEpisode(show, season, episode)
        return TvdbSeason(show, season)
