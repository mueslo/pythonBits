#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
import os
from argparse import ArgumentParser

from . import __version__ as version
from . import submission


def main():
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
    
    category = parser.add_argument("-c", "--category",choices=("tv","movie"))
    
    n_to_p = lambda x: "--"+x.replace('_','-')
    default_fields = ["form_title", "tags", "cover"]
    feature_d = {
        'description': {'short_param': '-d', 'default': True,
                        'help': "Generate description of media"},
        'mediainfo':   {'short_param': '-i', 'default': True,
                        'help': "Generate mediainfo output"},
        'screenshots': {'short_param': '-s', 'default': True,
                        'help': "Generate screenshots and upload to imgur"},
        'torrentfile': {'short_param': '-t', 'default': False,
                        'help': "Generate torrent file from PATH"},
        'submit':      {'short_param': '-b', 'default': False,
                        'help': "Submit generated description and torrent"},
        }
        
    
    feature_toggle = parser.add_argument_group(title="Feature toggle", description="Enables only the selected features, while everything else will not be executed.")

    for name, vals in feature_d.items():
        short = vals.pop('short_param')
        default = vals.pop('default')
        vals['help'] += " (default "+str(default)+")"
        if default:
            default_fields.append(name)
        feature_toggle.add_argument(short, n_to_p(name), action='append_const',
                                    const=name, dest='fields', **vals)
    
    #explicit/extra features
    feature_toggle.add_argument('-f', '--features', action='store',
                                dest='fields_ex', nargs='+', metavar='FIELD',
                                help="Enable custom fields")
    
    options_d = {
        'num_screenshots': {'type': int, 'default': 2,
                            'help': "Number of screenshots"},
        'num_cast':        {'type': int, 'default': 5,
                            'help': "Number of actors to use in tags"},
        'dry_run':         {'default': False, 'action': 'store_true',
                            'help': "Do not upload anything"},
        }    
    
    options = parser.add_argument_group(
        title="Tunables",
        description="Additional options such as number of screenshots")
    for name, vals in options_d.items():
        vals['help'] += " (default "+str(vals['default'])+")"
        options.add_argument(n_to_p(name), **vals)
    
    args = parser.parse_args()
    if args.fields_ex:
        args.fields = args.fields or []
        args.fields += args.fields_ex
    
    args.options = {}
    for o in options_d.keys():
        args.options[o] = getattr(args, o)
    
    if args.fields is None:
        args.fields = default_fields

    if args.category == 'tv':
        sub = submission.TvSubmission(path=args.path, title_arg=args.title,
                                      options=args.options)
    elif args.category == 'movie':
        sub = submission.MovieSubmission(path=args.path, title_arg=args.title,
                                         options=args.options)
    elif args.category is None:
        sub = submission.VideoSubmission(path=args.path, title_arg=args.title,
                                         options=args.options)
        if sub['category'] == 'tv':
            sub = submission.TvSubmission(**sub.fields)
        elif sub['category'] == 'movie':
            sub = submission.MovieSubmission(**sub.fields)
        else:
            raise Exception('Unknown category')
    else:
        raise Exception('Unknown category')
    
    consolewidth = 80
    sub.validate(args.fields) #also caches values
    for field in args.fields:
        #print "="*consolewidth
        v = sub[field]
        print ("  "+field+"  ").center(consolewidth, "=")
        print v

if __name__ == '__main__':
    main()
