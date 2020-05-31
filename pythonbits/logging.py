# -*- coding: utf-8 -*-
import os
import sys

import appdirs
import logbook.more

from . import __title__ as appname


class StreamHandler(logbook.more.ColorizingStreamHandlerMixin,
                    logbook.StreamHandler):
    pass


def issue_logging():
    """Logs to disk only when error occurs"""
    def factory(record, handler):
        return logbook.FileHandler(LOG_FILE, level='DEBUG',
                                   mode='w', bubble=True)
    return logbook.FingersCrossedHandler(factory, bubble=True)


LOG_DIR = appdirs.user_log_dir(appname.lower())
LOG_FILE = os.path.join(LOG_DIR, appname.lower() + '.log')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, 0o700)

sh = StreamHandler(sys.stdout, level='NOTICE', bubble=True)
sh.push_application()
issue_logging().push_application()

log = logbook.Logger(appname)
