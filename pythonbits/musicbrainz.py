# -*- coding: utf-8 -*-
import musicbrainzngs
import terminaltables

from . import __title__ as appname, __version__ as version, _github as github


musicbrainzngs.set_useragent(appname, version, github)


def get_artwork(release_group_id):
    try:
        data = musicbrainzngs.get_release_group_image_list(release_group_id)
    except musicbrainzngs.musicbrainz.ResponseError:
        return None

    for image in data["images"]:
        if "Front" in image["types"] and image["approved"]:
            return image["thumbnails"]["large"]


def find_release_group(release_title, artist=None):
    results = musicbrainzngs.search_release_groups(
        release_title, artist=artist, limit=10)['release-group-list']
    table_data = [('Index', 'Artist', 'Title', 'Type')]
    # max_width = table.column_max_width(2)
    for i, r in enumerate(results):
        # title = '\n'.join(wrap(r['title'], max_width))
        table_data.append((i, r['artist-credit-phrase'],
                           r['title'], r.get('type', '?')))

    print(terminaltables.SingleTable(table_data).table)
    while True:
        choice = input(
            "Select the release group (or enter a different query): ")
        try:
            choice = int(choice)
        except ValueError:
            if choice != '':
                return find_release_group(choice)
            continue

        try:
            choice = results[choice]
        except IndexError:
            pass
        else:
            return choice


def find_release(release_title, artist=None):
    release_group = find_release_group(release_title, artist=artist)

    results = musicbrainzngs.search_releases(
        'rgid:'+release_group['id'])['release-list']

    table_data = [
        ('Index', 'Title', '# Tracks', 'Date', 'CC', 'Label', 'Status',
         'Format'), ]

    for i, r in enumerate(results):
        try:
            label = r['label-info-list'][0]['label']['name']
        except KeyError:
            label = '?'
        table_data.append((i, r['title'], r['medium-list'][0]['track-count'],
                           r.get('date', '?'), r.get('country', '?'),
                           label, r.get('status', '?'),
                           r['medium-list'][0]['format']))

    print(terminaltables.SingleTable(table_data).table)
    while True:
        choice = input(
            "Select the exact release, if known: ")
        try:
            choice = results[int(choice)]
        except (IndexError, ValueError):
            if choice == '':
                return release_group, None
        else:
            release = musicbrainzngs.get_release_by_id(
                choice['id'], includes=['media', 'recordings'])['release']
            return release_group, release
