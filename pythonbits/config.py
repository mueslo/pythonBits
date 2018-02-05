# -*- coding: utf-8 -*-
from os import path

import ConfigParser
import getpass
import appdirs

# todo: ensure 600 perms
CONFIG_NAME = 'pythonbits.cfg'
CONFIG_PATH = path.join(appdirs.user_config_dir("pythonbits"), CONFIG_NAME)

registry = {
    ('Tracker','announce_url'): "Please enter your personal announce URL",
    ('Tracker','username'): "Username",
    ('Tracker','password'): "Password",
    ('Tracker','domain'): "Please enter the tracker's domain, e.g. 'mydomain.net'",
        }

class Config():
    def __init__(self):
        self._config = ConfigParser.SafeConfigParser()
        
    def get(self, section, option, ask_to_save=False, use_getpass=False):
        self._config.read(CONFIG_PATH)
        try:
            return self._config.get(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            query_msg = "{}: ".format(
                registry.get((section, option),
                             "Please enter {}.{}".format(section, option)))
                
            if use_getpass:
                value = getpass.getpass(query_msg)
            else:
                value = raw_input(query_msg).strip()
            
            if ask_to_save and raw_input('Would you like to save this value in {}? [Y/n] '.format(CONFIG_PATH)).lower() == 'n':
                return value
            
            if not self._config.has_section(section):
                self._config.add_section(section)
            self._config.set(section, option, value)
            
            with open(CONFIG_PATH, 'wb') as configfile:
                self._config.write(configfile)
                
            return value

config = Config()
