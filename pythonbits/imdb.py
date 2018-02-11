# -*- coding: utf-8 -*-
from attrdict import AttrDict

import imdbpie


class ImdbResult(object):
    def __init__(self, movie):
        self.movie = movie

    def summary(self):
        return {
            'title': self.movie.base.title,
            'directors': self.movie.credits.director,
            'runtime': str(self.movie.base.runningTimeInMinutes) + " min",
            'rating': (self.movie.ratings.rating, 10),
            'name': self.movie.base.title,
            'votes': self.movie.ratings.ratingCount,
            'cover': self.movie.base.image.url,
            'genres': self.movie.genres,
            'cast': self.movie.credits.cast,
            'writers': self.movie.credits.writer,
            'mpaa': u"",
            'description': self.movie.plot.outline.text,
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
        results = self.imdb.search_for_title(title)

        print "Results:"
        for i, movie in enumerate(results):
            print "%s: %s (%s)" % (i, movie['title'], movie['year'])

        while True:
            choice = raw_input('Select the correct movie or enter an alternate'
                               ' search term: [0-%s] ' % (len(results) - 1))
            try:
                result = results[int(choice)]
            except IndexError:
                pass
            except ValueError:
                if choice:
                    return self.search(choice)
                pass
            else:
                imdb_id = result['imdb_id']
                movie = AttrDict(self.imdb.get_title(result['imdb_id']))
                movie.credits = self.imdb.get_title_credits(imdb_id)['credits']
                movie.genres = self.imdb.get_title_genres(imdb_id)['genres']
                return ImdbResult(movie)
