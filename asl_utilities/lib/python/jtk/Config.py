import os

class ConfigException(Exception):
    pass
class ConfigArgumentException(ConfigException):
    pass
class ConfigNotAFileException(ConfigException):
    pass
class ConfigNotFoundException(ConfigException):
    pass
class ConfigReadError(ConfigException):
    pass
class InvalidConfigException(ConfigException):
    pass

def parse(config_file, groups=[], required=[]):
    if type(groups) not in (list,tuple):
        raise ConfigArgumentException("bad type for argument 'groups'")
    if type(required) not in (list,tuple):
        raise ConfigArgumentException("bad type for argument 'required'")
    if not os.path.exists(config_file):
        raise ConfigNotFoundException("config path '%s' does not exist" % config_file)
    if not os.path.isfile(config_file):
        raise ConfigNotAFileException("config path '%s' is not a regular file" % config_file)

    config = {}

    # prepare to track keys which allow multiple values
    group_map = {}
    for group in groups:
        group_map[group] = []

    required_map = {}
    for req in required:
        required_map[req] = True

    try:
        fh = open(config_file, 'r')
        line_index = 0

        # process all lines
        for line in fh:
            # increment for every line (event empty lines)
            line_index += 1
            line = line.strip()

            # ignore empty or comment lines
            if len(line) == 0:
                continue
            if line[0] == '#':
                continue

            # break each line apart, throws exception if '=' was not found
            parts = map(lambda p: p.strip(), line.split('=', 1))
            if len(parts) < 2:
                raise InvalidConfigException("bad entry on line %d" % line_index)

            key,value = parts
            # if this is a multi-value item, append it
            if group_map.has_key(key):
                group_map[key].append(value)
                continue

            # for single-value items, make sure there are no duplicates
            if config.has_key(key):
                raise InvalidConfigException("duplicate entry on line %d" % line_index)
            config[key] = value

        # check required single-value items
        for k in required_map.keys():
            if not config.has_key(k):
                raise RequiredConfigParameterException("required config parameter '%s' not found" % k)

        # add multi-value items to the config map
        for k,l in group_map.items():
            if len(l) < 1:
                # check required multi-value items
                if required.has_key(k):
                    raise RequiredConfigParameterException("required config parameter '%s' not found" % k)
                continue
            config[k] = l
    except:
        raise ConfigReadError("could not read config file '%s'" % config_file)

    return config

