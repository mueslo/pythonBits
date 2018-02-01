import ConfigParser

CONFIG_NAME = 'pythonbits.cfg'

registry = {
    ('Tracker','announce_url'): "Please enter your personal announce URL"
        }

class Config():
    def __init__(self):
        self._config = ConfigParser.SafeConfigParser()
        
    def get(self, section, option):
        self._config.read(CONFIG_NAME)
        try:
            return self._config.get(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            query_msg = "{}: ".format(
                registry.get((section, option),
                             "Please enter {}.{}".format(section, option)))
            value = raw_input(query_msg).strip()
            
            if not self._config.has_section(section):
                self._config.add_section(section)
            self._config.set(section, option, value)
            
            with open(CONFIG_NAME, 'wb') as configfile:
                self._config.write(configfile)
                
            return value
