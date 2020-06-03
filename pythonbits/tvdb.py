# -*- coding: utf-8 -*-
import tvdb_api
from . import imdb


class TvdbResult(object):
    def __init__(self, show, season, episode=None):
        self.show = show
        self.season = season
        self.episode = episode

    def banner(self, season_number):
        # todo offer choice of cover if multiple?
        # todo cache banner upload per season?
        # get best banner, preferably for season

        def best_banner(banners):
            def get_rating(banner):
                return banner.get('ratingsInfo', {}).get('average', 0)
            sorted_banners = sorted(banners, key=get_rating)
            return sorted_banners[-1]

        try:
            season_banners = self.show['_banners']['season']
            best_banner = best_banner(
                [banner for banner in season_banners['raw']
                 if banner['subKey'] == str(season_number)])
            return (season_banners[best_banner['resolution']]
                    [best_banner['id']]['_bannerpath'])
        except (IndexError, KeyError):
            for key in ('poster', 'series', 'fanart'):
                try:
                    series_banners = self.show['_banners'][key]
                    best_banner = best_banner(series_banners['raw'])
                    return (series_banners[best_banner['resolution']]
                            [best_banner['id']]['_bannerpath'])
                except (IndexError, KeyError):
                    pass
        raise Exception('Unable to find cover')

    def summary(self):
        return {
            'title': self.show['seriesname'],
            'network': self.show['network'],
            'genres': self.show['genre'],
            'seriessummary': self.show['overview'],
            'cast': self.show['_actors'],
            # 'seasons': len(self.show),
            # 'status': self.show['status'],
            'contentrating': self.show['rating'],
            'imdb_id': self.show['imdbId'],
        }

    def add_show_titles(self, imdb_id, summary):
        i = imdb.IMDB()
        try:
            imdb_info = i.get_info(imdb_id)
        except Exception:
            summary['titles'] = {}
        else:
            imdb_sum = imdb_info.summary()
            tvdb_title = summary['title']
            # Original title
            summary['title'] = imdb_sum['title']
            # dict of international titles
            summary['titles'] = imdb_sum['titles']
            # "XWW" is IMDb's international title, but unlike TVDB, it doesn't
            # include the year if there are multiple shows with the same name.
            if 'XWW' in summary['titles']:
                summary['titles']['XWW'] = tvdb_title


class TvdbSeason(TvdbResult):
    def summary(self):
        s = super(TvdbSeason, self).summary()
        some_episode = next(iter(self.season.values()))
        season_number = some_episode['airedSeason']
        series_url = 'https://thetvdb.com/series/%s' % (self.show['slug'],)
        s.update(**{'num_episodes': len(self.season),
                    'episodes': []})
        for episode_number in self.season:
            episode = self.season[episode_number]
            episode_url = 'https://thetvdb.com/series/{}/episodes/{}'.format(
                self.show['slug'], episode['id'])

            s["episodes"].append({
                'title': episode['episodename'],
                'url': episode_url,
                'imdb_id': episode['imdbId'],
                'rating': episode['siteRating']})
        s['url'] = series_url
        s['cover'] = self.banner(season_number)
        s['season'] = season_number
        s['imdb_id'] = self.show['imdbId']
        self.add_show_titles(s['imdb_id'], s)
        return s


class TvdbEpisode(TvdbResult):
    def summary(self):
        summary = super(TvdbEpisode, self).summary()
        imdb_show_id = summary['imdb_id']
        summary.update(**{
                'season': self.episode['airedSeason'],
                'episode': self.episode['episodenumber'],
                'episode_title': self.episode['episodename'],
                'imdb_id': self.episode['imdbId'],
                'directors': self.episode['directors'],
                'air_date': self.episode['firstaired'],
                # 'air_dow': self.show['airs_dayofweek'],
                # 'air_time': self.show['airs_time'],
                'writers': self.episode['writers'],
                'rating': self.episode['siteRating'],
                'votes': self.episode['siteRatingCount'],
                'episodesummary': self.episode['overview'],
                'language': self.episode['language'],
                'url': 'https://thetvdb.com/series/{}'.format(
                    self.show['slug']),
                'cover': self.banner(self.episode['seasonnumber'])})
        self.add_show_titles(imdb_show_id, summary)
        return summary


class TVDB(object):
    def __init__(self):
        # todo: selectfirst=False
        self.tvdb = tvdb_api.Tvdb(interactive=True, banners=True, actors=True)

    def search(self, tv_specifier):
        show = self.tvdb[tv_specifier.title]
        season = show[tv_specifier.season]
        if tv_specifier.episode is not None:
            episode = season[tv_specifier.episode]
            return TvdbEpisode(show, season, episode)
        return TvdbSeason(show, season)
