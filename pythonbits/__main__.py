#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from argparse import ArgumentParser

from . import __version__ as version
from . import submission


def parse_args():
    parser = ArgumentParser(
        version=version,
        description=("A Python pretty printer for generating attractive movie "
                     "descriptions with screenshots."))

    parser.add_argument("path", metavar='PATH',
                        help="File or directory of media")
    parser.add_argument("title", metavar='TITLE', nargs='?',
                        help=("Explicitly identify media title "
                              "(e.g. \"Lawrence of Arabia\" or \"The Walking "
                              "Dead S01\") (optional)"))

    parser.add_argument("-c", "--category", choices=("tv", "movie"))
    parser.add_argument("-u", "--set-field", nargs=2, action='append',
                        metavar=('FIELD', 'VALUE'), default=[],
                        help="Use supplied values to use for fields, e.g. "
                             "torrentfile /path/to/torrentfile")

    def n_to_p(x): return "--" + x.replace('_', '-')

    # shorthand features
    feature_d = {
        # todo: these default values can vary by Submission.default_fields and
        #      wouldn't make sense for e.g. music
        'description': {'short_param': '-d', 'default': True,
                        'help': "Generate description of media"},
        'mediainfo': {'short_param': '-i', 'default': True,
                      'help': "Generate mediainfo output"},
        'screenshots': {'short_param': '-s', 'default': True,
                        'help': "Generate screenshots and upload to imgur"},
        'torrentfile': {'short_param': '-t', 'default': False,
                        'help': "Create torrent file"},
        'submit': {'short_param': '-b', 'default': False,
                   'help': "Generate complete submission and post it"},
    }

    feature_toggle = parser.add_argument_group(
        title="Feature toggle",
        description="Enables only the selected features, "
                    "while everything else will not be executed.")

    for name, vals in feature_d.items():
        short = vals.pop('short_param')
        default = vals.pop('default')
        vals['help'] += " (default " + str(default) + ")"
        feature_toggle.add_argument(short, n_to_p(name), action='append_const',
                                    const=name, dest='fields', default=[],
                                    **vals)

    # explicit/extra features
    feature_toggle.add_argument(
        '-f', '--features', action='store', default=[], dest='fields_ex',
        nargs='+', metavar='FIELD',
        help="Output values of any field(s), e.g. tags")

    # todo: move to submission.py
    options_d = {
        'num_screenshots': {'type': int, 'default': 2,
                            'help': "Number of screenshots"},
        'num_cast': {'type': int, 'default': 5,
                     'help': "Number of actors to use in tags"},
        'dry_run': {'default': False, 'action': 'store_true',
                    'help': "Do not upload anything"},
    }

    options = parser.add_argument_group(
        title="Tunables",
        description="Additional options such as number of screenshots")
    for name, vals in options_d.items():
        vals['help'] += " (default " + str(vals['default']) + ")"
        options.add_argument(n_to_p(name), **vals)

    args = parser.parse_args()

    args.options = {}
    for o in options_d.keys():
        args.options[o] = getattr(args, o)

    set_field = dict(args.set_field)

    if args.category:
        set_field['category'] = args.category
    set_field['options'] = args.options
    set_field['path'] = args.path
    set_field['title_arg'] = args.title
    get_field = args.fields + args.fields_ex

    return set_field, get_field


def main():
    set_fields, get_fields = parse_args()

    # only video submissions for now
    sub = submission.VideoSubmission(**set_fields)
    if sub['category'] == 'tv':
        sub = submission.TvSubmission(**sub.fields)
    elif sub['category'] == 'movie':
        sub = submission.MovieSubmission(**sub.fields)
    else:
        raise Exception('Unknown category', sub['category'])

    consolewidth = 80
    get_fields = get_fields or sub.default_fields
    sub.cache_fields(get_fields)
    for field in get_fields:
        v = sub[field]
        print ("  " + field + "  ").center(consolewidth, "=")
        print v


if __name__ == '__main__':
    main()
