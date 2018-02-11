# -*- coding: utf-8 -*-
import tvdb_api


class TvdbResult(object):
    def __init__(self, show, season, episode=None):
        self.show = show
        self.season = season
        self.episode = episode

    def banner(self, season_number=-1):
        # todo offer choice of cover if multiple?
        # todo cache banner upload per season?
        # get best banner, preferably for season

        def best_banner(banners): return sorted(
            banners, key=lambda b: float(b.get('rating', 0)))[-1]

        try:
            season_banners = self.show['_banners']['season']['season']

            season_banners = [
                banner for banner in season_banners.values()
                if banner['season'] == str(season_number)]

            return best_banner(season_banners)['_bannerpath']
        except (IndexError, KeyError):
            # failing that, use show banner. if there's no banner at all we
            # just error out for now
            series_banners = [v for r in self.show['_banners']
                              ['poster'].values() for k, v in r.items()]
            return best_banner(series_banners)['_bannerpath']

    def summary(self):
        return {
            'title': self.show['seriesname'],
            'network': self.show['network'],
            'genres': self.show['genre'].strip('|').split('|'),
            'seriessummary': self.show['overview'],
            'cast': self.show['_actors'],
            # 'seasons': len(self.show),
            # 'status': self.show['status'],
            'contentrating': self.show['contentrating']
        }


class TvdbSeason(TvdbResult):
    def summary(self):
        s = super(TvdbSeason, self).summary()
        some_episode = self.season.itervalues().next()
        season_number = some_episode['seasonnumber']
        series_id = some_episode['seriesid']
        season_id = some_episode['seasonid']

        s.update(**{'num_episodes': len(self.season),
                    'episodes': []})
        for episode_number in self.season:
            episode = self.season[episode_number]
            s["episodes"].append({
                'title': episode['episodename'],
                'url': "http://thetvdb.com/?tab=episode&seriesid=" + series_id
                       + "&seasonid=" + season_id +
                       "&id=" + episode['id'],
                'imdb_id': episode['imdb_id'],
                'rating': (episode['rating'] and
                           float(episode['rating']), 10)})
        s['url'] = ("http://thetvdb.com/?tab=episode&seriesid=" + series_id +
                    "&seasonid=" + season_id)
        s['cover'] = self.banner(season_number)
        s['season'] = season_number
        s['imdb_id'] = self.show['imdb_id']
        return s


class TvdbEpisode(TvdbResult):
    def summary(self):
        summary = super(TvdbEpisode, self).summary()
        summary.update(**{
                'season': self.episode['seasonnumber'],
                'episode': self.episode['episodenumber'],
                'episode_title': self.episode['episodename'],
                'imdb_id': self.episode['imdb_id'],
                'director': self.episode['director'],
                'air_date': self.episode['firstaired'],
                # 'air_dow': self.show['airs_dayofweek'],
                # 'air_time': self.show['airs_time'],
                'writers': (self.episode['writer'] or
                            "").strip('|').split('|'),
                'rating': (self.episode['rating'] and
                           float(self.episode['rating']), 10),
                'votes': self.episode['ratingcount'],
                'episodesummary': self.episode['overview'],
                'language': self.episode['language'],
                'url': "http://thetvdb.com/?tab=episode&seriesid=" +
                       self.episode['seriesid'] + "&seasonid=" +
                       self.episode['seasonid'] + "&id=" + self.episode['id'],
                'cover': self.banner(self.episode['seasonnumber'])})

        return summary


class TVDB(object):
    def __init__(self):
        # todo: selectfirst=False
        self.tvdb = tvdb_api.Tvdb(banners=True, actors=True)

    def search(self, tv_specifier):
        show = self.tvdb[tv_specifier.title]
        season = show[tv_specifier.season]
        if tv_specifier.episode:
            episode = season[tv_specifier.episode]
            return TvdbEpisode(show, season, episode)
        return TvdbSeason(show, season)
