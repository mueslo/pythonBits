# -*- coding: utf-8 -*-
from attrdict import AttrDict
import imdbpie

from .logging import log


class ImdbResult(object):
    def __init__(self, movie):
        log.debug("ImdbResult {}", movie)
        self.movie = movie

    def description(self):
        outline = self.movie.plot.get('outline')
        summaries = self.movie.plot.get('summaries')
        description = None
        if outline:
            description = outline['text']
        elif summaries:
            description = summaries[0]['text']
        return description

    def runtime(self):
        runtime = self.movie.base.get('runningTimeInMinutes')
        return runtime and str(runtime) + " min"

    def summary(self):
        return {
            'title': self.movie.base.title,
            'directors': self.movie.credits.get('director', []),
            'runtime': self.runtime(),
            'rating': (self.movie.ratings.rating, 10),
            'name': self.movie.base.title,
            'votes': self.movie.ratings.ratingCount,
            'cover': self.movie.base.image.url,
            'genres': self.movie.get('genres', []),
            'cast': self.movie.credits.get('cast', []),
            'writers': self.movie.credits.get('writer', []),
            'mpaa': u"",
            'description': self.description(),
            'url': u"http://www.imdb.com" + self.movie.base.id,
            'year': self.movie.base.year}


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

        print "Results:"
        for i, movie in enumerate(results):
            print "%s: %s (%s)" % (i, movie['title'], movie['year'])

        while True:
            choice = raw_input('Select number or enter an alternate'
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
