# -*- coding: utf-8 -*-
from textwrap import dedent

import goodreads_api_client as gr
import pycountry

from .config import config
from .logging import log
from .calibre import read_metadata
from collections import OrderedDict

config.register(
    'Goodreads', 'api_key',
    dedent("""\
    To find your Goodreads API key, login to https://www.goodreads.com/api/keys
    Enter the API Key below
    API Key"""))

EXCLUDED_WORDS = ['read', 'favorites', 'book',
                  'own', 'series', 'novel', 'kindle', 'shelf'
                  'library', 'buy', 'abandoned',
                  'audible', 'audio', 'finish', 'wish']


def _extract_authors(authors):
    if isinstance(authors['author'], OrderedDict):
        return [{
            'name': authors['author']['name'],
            'link': authors['author']['link']
        }]
    else:
        return [_extract_author(auth)
                for auth in authors['author']]


def _extract_author(auth):
    return {
        'name': auth['name'],
        'link': auth['link']
    }


def _extract_language(alpha_3):
    if not alpha_3:
        return _read_language()
    try:
        return pycountry.languages.get(alpha_3=alpha_3).name
    except AttributeError:
        try:
            return pycountry.languages.get(alpha_2=alpha_3[:2]).name
        except AttributeError:
            # I give up
            return _read_language()


def _read_language():
    return input('Please specify the book\'s Language: ')


def _extract_shelves(shelves, take):
    # source for tags e.g. sci-fi
    return [_extract_shelf(shelf)
            for shelf in filter(_exclude_well_known,
                                sorted(shelves, key=_shelf_sort_key,
                                       reverse=True)[:take])]


def _exclude_well_known(s):
    return not any(w in s['@name'] for w in EXCLUDED_WORDS)


def _shelf_sort_key(s):
    return int(s['@count'])


def _extract_shelf(shelf):
    return {'name': shelf['@name'], 'count': shelf['@count']}


def _process_book(books):
    keys_wanted = ['id', 'title', 'isbn', 'isbn13', 'description',
                   'language_code', 'publication_year', 'publisher',
                   'image_url', 'url', 'authors', 'average_rating',
                   'work', 'popular_shelves']
    book = {k: v for k, v in books if k in keys_wanted}
    book['authors'] = _extract_authors(book['authors'])
    book['ratings_count'] = int(book['work']['ratings_count']['#text'])
    book['language'] = _extract_language(book['language_code'])
    book['shelves'] = _extract_shelves(book['popular_shelves']['shelf'], 10)
    return book


class Goodreads(object):
    def __init__(self, interactive=True):
        self.goodreads = gr.Client(
            developer_key=config.get('Goodreads', 'api_key'))

    def show_by_isbn(self, isbn):
        return _process_book(self.goodreads.Book.show_by_isbn(
                    isbn).items())

    def search(self, path):

        book = read_metadata(path)
        isbn = ''
        try:
            isbn = book['Identifiers'].split(':')[1].split(',')[0]
        except KeyError:
            pass

        if isbn:
            log.debug("Searching Goodreads by ISBN {} for '{}'",
                      isbn, book.get('Title', isbn))
            return self.show_by_isbn(isbn)
        elif book['Title']:
            search_term = book['Title']
            log.debug(
                "Searching Goodreads by Title only for '{}'", search_term)
            book_results = self.goodreads.search_book(search_term)
            print("Results:")
            for i, book in enumerate(book_results['results']['work']):
                print('{}: {} by {} ({})'
                      .format(i, book['best_book']['title'],
                              book['best_book']['author']['name'],
                              book['original_publication_year']
                              .get('#text', '')))

            while True:
                choice = input('Select number or enter an alternate'
                               ' search term'
                               ' (or an ISBN with isbn: prefix):'
                               ' [0-{}, 0 default] '
                               .format(
                                   len(book_results['results']['work']) - 1))
                try:
                    choice = int(choice)
                except ValueError:
                    if choice:
                        return self.show_by_isbn(choice.replace('isbn:', ''))
                    choice = 0

                try:
                    result = book_results['results']['work'][choice]
                except IndexError:
                    pass
                else:
                    id = result['best_book']['id'].get('#text', '')
                    log.debug("Selected Goodreads item {}", id)
                    log.debug("Searching Goodreads by ID {}", id)
                    return _process_book(self.goodreads.Book.show(
                        id).items())
