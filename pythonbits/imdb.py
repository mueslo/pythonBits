# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor

import imdbpie
from attrdict import AttrDict

from .logging import log


def get(o, *attrs, **kwargs):
    rv = o
    used = []
    for a in attrs:
        used.append(a)
        try:
            rv = rv[a]
        except KeyError:
            log.warning('Cannot get {}: {} missing from IMDb API response',
                        ".".join(attrs), ".".join(used))
            return kwargs.get('default')
    return rv


class ImdbResult(object):
    def __init__(self, movie):
        log.debug("ImdbResult {}", movie)
        self.movie = movie

    @property
    def description(self):
        outline = get(self.movie, 'plot', 'outline')
        if outline:
            return outline['text']
        summaries = get(self.movie, 'plot', 'summaries')
        if summaries:
            return summaries[0]['text']

    @property
    def runtime(self):
        runtime = get(self.movie, 'base', 'runningTimeInMinutes')
        return runtime and str(runtime) + " min"

    @property
    def url(self):
        movie_id = get(self.movie, 'base', 'id')
        if movie_id:
            return "https://www.imdb.com" + movie_id

    @property
    def cast(self):
        cast = get(self.movie, 'credits', 'cast', default=[])
        stars = get(self.movie, 'stars', default=[])
        star_ids = set(star['id'] for star in stars)
        return stars + [actor for actor in cast if actor['id'] not in star_ids]

    def summary(self):
        return {
            'title': get(self.movie, 'base', 'title'),
            'titles': get(self.movie, 'titles'),
            'directors': get(self.movie, 'credits', 'director', default=[]),
            'runtime': self.runtime,
            'rating': (get(self.movie, 'ratings', 'rating'), 10),
            'name': get(self.movie, 'base', 'title'),
            'votes': get(self.movie, 'ratings', 'ratingCount', default=0),
            'cover': get(self.movie, 'base', 'image', 'url'),
            'genres': get(self.movie, 'genres', default=[]),
            'cast': self.cast,
            'writers': get(self.movie, 'credits', 'writer', default=[]),
            'mpaa': "",
            'description': self.description,
            'url': self.url,
            'year': get(self.movie, 'base', 'year')}


class IMDB(object):
    def __init__(self):
        self.imdb = imdbpie.Imdb()
        self.movie = None

    def get_rating(self, imdb_id):
        try:
            res = self.imdb.get_title_ratings(imdb_id)
        except LookupError:
            res = {}
        return (res.get('rating'), 10), res.get('ratingCount', 0)

    def search(self, title):
        log.debug("Searching IMDb for '{}'", title)
        results = self.imdb.search_for_title(title)
        if len(results) == 1:
            return self.get_info(results[0]['imdb_id'])

        print("Results:")
        for i, movie in enumerate(results):
            print("%s: %s (%s)" % (i, movie['title'], movie['year']))

        while True:
            choice = input('Select number or enter an alternate'
                           ' search term (or an IMDb id): [0-%s, 0 default] ' %
                           (len(results) - 1))
            try:
                choice = int(choice)
            except ValueError:
                if choice:
                    return self.search(choice)
                choice = 0

            try:
                result = results[choice]
            except IndexError:
                pass
            else:
                log.debug("Found IMDb item {}", result['imdb_id'])
                return self.get_info(result['imdb_id'])

    def get_info(self, imdb_id):
        log.debug('imdb getinfo')
        with ThreadPoolExecutor() as executor:
            f_movie = executor.submit(self.imdb.get_title, imdb_id)
            f_credits = executor.submit(self.imdb.get_title_credits, imdb_id)
            f_aux = executor.submit(self.imdb.get_title_auxiliary, imdb_id)
            f_genres = executor.submit(self.imdb.get_title_genres, imdb_id)
            f_versions = executor.submit(self.imdb.get_title_versions, imdb_id)

        movie = AttrDict(f_movie.result())
        movie.credits = f_credits.result()['credits']
        movie.stars = f_aux.result()['principals']
        movie.genres = f_genres.result()['genres']
        title_versions = f_versions.result()
        movie.titles = {item["region"]: item["title"]
                        for item in title_versions['alternateTitles']
                        if "region" in item and "title" in item}
        return ImdbResult(movie)
