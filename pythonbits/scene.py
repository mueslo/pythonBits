# -*- coding: utf-8 -*-
import os
import requests
from base64 import b64decode
from bs4 import BeautifulSoup
import re
import guessit
import functools
import pprint

from .logging import log


srrdb = b64decode('aHR0cHM6Ly9zcnJkYi5jb20v').decode('utf8')


class SceneError(Exception):
    pass


class APIError(Exception):
    pass


# FIXME: "hd1080-wtl.mkv" (from Walk.the.Line.Extended.Cut.2005.1080p.BluRay.x264-HD1080)
#        should report an error, but it's not found on any scene indexers.


def check_integrity(path, on_error=None):
    """
    Check if `path` (file or directory) was modified

    Files that are not part of a scene release are ignored.

    Return True/False if this release was (not) modified or None if not sure.
    """
    errors_found = False
    something_found = False
    if _isdir(path):
        dirname = os.path.basename(path)
    else:
        dirname = ''
    log.debug('Base path for {}: {}', path, dirname)

    guess = _guessit(path)
    if 'release_group' not in guess:
        log.debug('No release group found - cannot find scene release: {}', guess)
        return None

    try:
        if _isdir(path):
            try:
                _check_dir(path)
            except SceneError as e:
                errors_found = True
                something_found = True
                if on_error is not None:
                    on_error(dirname, e)
                else:
                    raise

        for info in _yield_file_info(path):
            log.debug('Scene info: {}', info)
            # Allow mixed scene/non-scene releases by only checking known scene releases
            if info['size'] and info['crc']:
                something_found = True
                relpath = os.path.join(dirname, info['filename'])
                if dirname:
                    fspath = os.path.join(path, info['filename'])
                else:
                    fspath = path
                log.debug('Torrent path: {}', relpath)
                log.debug('File system path: {}', fspath)
                try:
                    _check_file(relpath, fspath, info)
                except SceneError as e:
                    errors_found = True
                    if on_error is not None:
                        on_error(relpath, e)
                    else:
                        raise
    except APIError as e:
        # Connection failed; we can't tell
        log.debug('Ignoring error: {}', e)
        if on_error is not None:
            on_error(dirname or os.path.basename(path), e)
        else:
            raise
    else:
        log.debug('Something found: {}', something_found)
        log.debug('Errors found: {}', errors_found)
        if something_found:
            return errors_found


def _check_dir(path):
    """
    Return True if `path` was not modified or None if not sure

    Raise SceneError if `path` does not match scene release
    """
    try:
        release_name, files = get_details(path)
    except APIError:
        return None
    log.debug('Checking directory: {}', path)
    log.debug('release_name: {}', release_name)
    log.debug('files: {}', files)
    if files:
        basename = _get_basename_noext(path)
        log.debug('Base name should be {}: {}', release_name, basename)
        if release_name != basename:
            raise SceneError('%s was renamed to %s' % (release_name, basename))
        else:
            return True


def _check_file(relpath, fspath, info):
    """
    Return True if `path` is unmodified or None if not sure

    relpath: Relative path that starts with the release name
    fspath: Path that exists in the file system

    It is important that `path` is relative and starts with the release/torrent name.

    Raise SceneError if `path` does not match `info`
    """
    log.debug('Checking file: {}: {}', relpath, fspath)
    log.debug('Info: {}', info)

    if info['release_name'] is None:
        log.debug('No info to check')
        return None

    release_type = 'file' if relpath == os.path.basename(relpath) else 'directory'
    log.debug('Release is {}', release_type)

    # File release names are identical to file name sans extension.
    scene_release_type = 'file' if info['release_name'] == _get_basename_noext(info['filename']) else 'directory'
    log.debug('Scene release is {}', scene_release_type)

    if scene_release_type == 'file':
        # Scene released file so we don't care about our own directory name
        filename = os.path.basename(fspath)
        exp_filename = info['filename']
        log.debug('Existing filename: {}', filename)
        log.debug('Expected filename: {}', exp_filename)
        if filename != exp_filename:
            raise SceneError('%s was renamed to %s' % (exp_filename, filename))
    else:
        # Scene released directory
        if release_type == 'file':
            # Don't check directory name
            filename = os.path.basename(fspath)
            exp_filename = info['filename']
        else:
            # Check full internal/relative path
            filename = os.path.join(os.path.basename(os.path.dirname(fspath)),
                                    os.path.basename(fspath))
            exp_filename = os.path.join(info['release_name'], info['filename'])
        log.debug('Existing filename: {}', filename)
        log.debug('Expected filename: {}', exp_filename)
        if filename != exp_filename:
            raise SceneError('%s was renamed to %s' % (exp_filename, filename))

    if not _path_exists(fspath):
        raise SceneError('%s: Missing file' % (fspath,))

    try:
        filesize = _path_getsize(fspath)
    except OSError as e:
        raise SceneError('%s: Unable to get file size: %s' % (fspath, e.strerror))
    log.debug('File size of {}: {} bytes', fspath, filesize)
    if filesize != info['size']:
        raise SceneError('%s: Wrong size: %s instead of %s bytes' %
                         (info['filename'], filesize, info['size']))

    return True


def release_names(path):
    """
    Get release information from guess it. If we know the title, release group and year or season
    Search for release title, resolution, release_group and season/episode or year. If the
    last segment in `path` is not in the results, return them.  Otherwise return an empty
    list.
    """
    guess = _guessit(path)
    # If we don't have enough information, don't bother searching.
    log.debug('Guess: {}', guess)
    if 'release_group' not in guess or 'title' not in guess:
        return []

    log.debug('Looking for release names matching: {}', guess)
    results = search(guess)
    if not results and 'season' in guess and 'episode' in guess:
        # Try again, search for season pack
        guess.pop('episode', None)
        log.debug('Looking for release names matching: {}', guess)
        results = search(guess)
    return results


def search(guess):
    """
    Search for scene releases

    guess: Dictionary from guessit.guessit()

    Return a list of release names
    """
    log.debug('Searching for {}', guess)
    # Make search query
    query = list(guess['title'].split(' '))
    # Use guess.get(...) to ignore non-existing values as well as None and ""
    if guess.get('release_group'):
        query.append('group:' + guess['release_group'])
    if guess.get('other'):
        query.append(guess['other'])
    if guess.get('screen_size'):
        query.append(guess['screen_size'])
    if guess.get('type') == 'movie':
        if guess.get('year'):
            query.append(guess['year'])
    elif guess.get('type') == 'episode':
        episode_info = []
        if guess.get('season'):
            episode_info.append('S%02d' % (guess['season'],))
        if guess.get('episode'):
            episode_info.append('E%02d' % (guess['episode'],))
        if episode_info:
            query.append(''.join(episode_info))

    query_str = '/'.join(str(q) for q in query)

    # Make request
    try:
        r = _get("api/search/" + query_str)
    except APIError:
        return []

    # Parse response
    try:
        json = r.json()
    except ValueError:
        log.debug('Invalid JSON: {}', r.text)
    else:
        log.debug('Scene search result:\n{}', pprint.pformat(json))
        if json.get('results'):
            return [r['release'] for r in json['results']]
    return []


def get_details(path):
    """
    Find release info for file or directory at `path`

    Return the release name and a dictionary that maps file names to dictionaries with the
    keys "release_name", "filename", "size" and "crc".
    """
    r = _get('api/details/' + _get_basename_noext(path))
    # log.debug('Response:\n{}', r.text)
    try:
        json = r.json()
    except ValueError:
        # The API fixes our release name by capitalizing it correctly, removing file
        # extension, etc and redirecting us to the releases web page. Try to find the
        # correct release name in the HTML and make another API request with that.
        log.debug('Finding real release name in HTML:')
        soup = BeautifulSoup(r.text, features="html.parser")
        # log.debug(soup.prettify())
        release_name_tag = soup.find(id='release-name')
        if release_name_tag is not None:
            release_name = release_name_tag.get('value')
            if release_name:
                log.debug('Found correct release name: {}', release_name)
                return get_details(release_name)
    else:
        log.debug('Getting info from JSON:')
        files = json.get('archived-files', [])
        files_sorted = sorted(files, key=lambda f: f['name'].casefold())
        return json['name'], {f['name']: {'release_name': json['name'],
                                          'filename': f['name'],
                                          'size': f['size'],
                                          'crc': f['crc']}
                              for f in files_sorted}
    return '', {}


def _yield_file_info(path):
    """
    For each file in `path` yield a dictionary with the keys "release_name", "filename",
    "size" and "crc"

    If no info can be found, all values except for "filename" are `None` and "filename" is
    taken from `path` instead of the info returned by `get_details`.

    Raise APIError in case of connection or file system error.
    """
    # Cover the following cases:
    #   - path is directory (season) and scene released directory
    #   - path is directory and scene released individual file (episodes)
    #   - path is file and scene released individual file
    #   - path is file and scene released directory
    _, files = get_details(path)

    def default(filepath):
        return {'release_name': None, 'filename': os.path.basename(filepath), 'size': None, 'crc': None}

    if files:
        # Scene release is the same as this release (season pack or single episode)
        yield from files.values()

    elif not _isdir(path):
        # path is episode and scene release is season pack
        log.debug('Looking for episode from season pack')
        guess = _guessit(path)
        # Try to find whole season if we searched for single episode
        if 'release_group' in guess and 'season' in guess and 'episode' in guess:
            guess.pop('episode', None)
            results = search(guess)
            # If we find the exact season, pick episode info
            if len(results) == 1:
                _, files = get_details(results[0])
                yield files.get(os.path.basename(path), default(path))
            else:
                yield default(path)
        else:
            yield default(path)

    else:
        log.debug('Making season pack from individual episodes')
        # path is season and scene released single episodes
        try:
            files = _os_listdir(path)
        except OSError as e:
            raise APIError('%s: %s' % (path, e.strerror))
        else:
            log.debug('Found files:', files)
            for filename in sorted(files):
                _, files = get_details(filename)
                yield files.get(filename, default(filename))


@functools.lru_cache()
def _guessit(filepath):
    release_name = os.path.basename(filepath)
    if release_name.islower():
        match = re.search(r'^([a-z0-9]+)-(.+)\.([a-z0-9]{1,3})$', release_name)
        if match:
            release_name = '%s-%s.%s' % (match.group(2), match.group(1), match.group(3))
    return dict(guessit.guessit(release_name))


@functools.lru_cache()
def _get(path):
    url = srrdb + path
    log.debug('Requesting URL: {}', url)
    try:
        return requests.get(url)
    except requests.RequestException as e:
        log.debug('Request failed: {}', e)
        raise APIError(e)


def _get_basename_noext(path):
    # os.path.splitext() removes anything after the rightmost "." which is no good for
    # scene release names.
    return re.sub(r'\.[a-z0-9]{1,3}$$', '', os.path.basename(path))


def _isdir(path):
    # Not using system calls makes testing easier and just looking for file extension
    # should work pretty much always.
    return not bool(re.search(r'\.[a-zA-Z0-9]{1,3}$', os.path.basename(path)))


# Allow patching in texts without side effects.
_path_exists = os.path.exists
_path_getsize = os.path.getsize
_os_listdir = os.listdir
