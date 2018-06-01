# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # noqa: F401, F403

from attrdict import AttrDict
import imdbpie

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
            return "http://www.imdb.com" + movie_id

    def summary(self):
        return {
            'title': get(self.movie, 'base', 'title'),
            'directors': get(self.movie, 'credits', 'director', default=[]),
            'runtime': self.runtime,
            'rating': (get(self.movie, 'ratings', 'rating'), 10),
            'name': get(self.movie, 'base', 'title'),
            'votes': get(self.movie, 'ratings', 'ratingCount', default=0),
            'cover': get(self.movie, 'base', 'image', 'url'),
            'genres': get(self.movie, 'genres', default=[]),
            'cast': get(self.movie, 'credits', 'cast', default=[]),
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
        res = self.imdb.get_title_ratings(imdb_id)
        return (res.get('rating'), 10), res.get('ratingCount', 0)

    def search(self, title):
        log.debug("Searching IMDb for '{}'", title)
        results = self.imdb.search_for_title(title)

        print("Results:")
        for i, movie in enumerate(results):
            print("%s: %s (%s)" % (i, movie['title'], movie['year']))

        while True:
            choice = input('Select number or enter an alternate'
                           ' search term: [0-%s, 0 default] ' %
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
                imdb_id = result['imdb_id']
                log.debug("Found IMDb item {}", imdb_id)
                movie = AttrDict(self.imdb.get_title(imdb_id))
                movie.credits = self.imdb.get_title_credits(imdb_id)['credits']
                movie.genres = self.imdb.get_title_genres(imdb_id)['genres']
                return ImdbResult(movie)
