# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # noqa: F401, F403

import sys
from os import path
from argparse import ArgumentParser

from . import __version__ as version
from . import bb
from . import logging
from .submission import SubmissionAttributeError


def parse_args():
    parser = ArgumentParser(
        description=("A Python pretty printer for generating attractive movie "
                     "descriptions with screenshots."))
    parser.add_argument('--version', action='version', version=version)
    parser.add_argument("-v", action="count", default=0,
                        help="increase output verbosity")
    parser.add_argument("path", metavar='PATH',
                        help="File or directory of media")
    parser.add_argument("title", metavar='TITLE', nargs='?',
                        help=("Explicitly identify media title "
                              "(e.g. \"Lawrence of Arabia\" or \"The Walking "
                              "Dead S01\") (optional)"))

    cat_map = {'movie': bb.MovieSubmission,
               'tv': bb.TvSubmission}
    parser.add_argument("-c", "--category", choices=list(cat_map.keys()))
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
        'data_method': {'type': str, 'default': 'auto',
                        'choices': ['hard', 'sym', 'copy', 'move'],
                        'help': "Data method to use for placing media files"}
    }

    options = parser.add_argument_group(
        title="Tunables",
        description="Additional options such as number of screenshots")
    for name, vals in options_d.items():
        vals['help'] += " (default " + str(vals['default']) + ")"
        options.add_argument(n_to_p(name), **vals)

    args = parser.parse_args()
    logging.sh.level -= args.v
    logging.log.debug("Arguments: {}", args)

    args.options = {}
    for o in options_d.keys():
        args.options[o] = getattr(args, o)

    set_field = dict(args.set_field)

    Category = cat_map.get(args.category, bb.BbSubmission)

    set_field['options'] = args.options
    set_field['path'] = path.abspath(args.path)
    if args.title and sys.version_info[0] == 2:  # PY2 compatibility
        set_field['title_arg'] = args.title.decode('utf8')
    else:
        set_field['title_arg'] = args.title
    get_field = args.fields + args.fields_ex

    return Category, set_field, get_field


def _main(Category, set_fields, get_fields):
    sub = Category(**set_fields)

    while True:
        try:
            sub.show_fields(get_fields)
        except SubmissionAttributeError as e:
            logging.log.debug(type(e).__name__ + ': ' + str(e))
            _sub = sub.subcategorise()
            if type(_sub) == type(sub):
                raise
            sub = _sub
        else:
            break

    if sub.needs_finalization():
        if sub.confirm_finalization(get_fields):
            sub.finalize()
        else:
            return

    print(sub.show_fields(get_fields))


def main():
    Category, set_fields, get_fields = parse_args()
    with logging.log.catch_exceptions(
            "An exception occured.\nFull log stored at file://{}",
            logging.LOG_FILE):
        _main(Category, set_fields, get_fields)


if __name__ == '__main__':
    main()
