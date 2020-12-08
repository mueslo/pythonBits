# -*- coding: utf-8 -*-
import requests
import json

from .logging import log

API_URL = 'https://www.googleapis.com/books/v1/'

cache = {}


def find_cover(isbn):
    if _get_or_set(key=isbn):
        return _extract_cover(cache[isbn])

    path = 'volumes?q=isbn:{}'.format(isbn)
    resp = requests.get(API_URL+path)
    log.debug('Fetching alt cover art from {}'.format(resp.url))
    if resp.status_code == 200:
        content = json.loads(resp.content)
        _get_or_set(key=isbn, value=content)
        return _extract_cover(content)
    else:
        log.warn('Couldn\'t find cover art for ISBN {}'.format(isbn))
        return ''


def find_categories(isbn):
    if _get_or_set(key=isbn):
        return _extract_categories(cache[isbn])

    path = 'volumes?q=isbn:{}'.format(isbn)
    resp = requests.get(API_URL+path)
    log.debug('Fetching categories from {}'.format(resp.url))
    if resp.status_code == 200:
        content = json.loads(resp.content)
        _get_or_set(key=isbn, value=content)
        return _extract_categories(content)
    else:
        log.warn('Couldn\'t find categories for ISBN {}'.format(isbn))
        return ''


def _get_or_set(**kwargs):
    value = kwargs.get('value', None)
    key = kwargs.get('key', None)
    if value:
        cache[key] = value
        return value
    elif key in cache:
        return cache[key]


def _extract_categories(book):
    return (book['items'][0]['volumeInfo']
                ['categories'] or '')


def _extract_cover(book):
    return (book['items'][0]['volumeInfo']
            ['imageLinks']['thumbnail'] or '')
