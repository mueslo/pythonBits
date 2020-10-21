
# -*- coding: utf-8 -*-

"""
Note, read https://openlibrary.org/dev/docs/api/covers
The cover access by ids other than CoverID and OLID are rate-limited.
Currently only 100 requests/IP are allowed for every 5 minutes.
If any IP tries to access more that the allowed limit,
the service will return "403 Forbidden" status.
"""

API_URL = 'http://covers.openlibrary.org/b/{}/{}-{}.jpg'


"""
key can be any one of ISBN, OCLC, LCCN, OLID and ID (case-insensitive)
value is the value of the chosen key
size can be one of S, M and L for small, medium and large respectively.
"""


def format_cover_url(key, value, size):
    return API_URL.format(key, value, size)
