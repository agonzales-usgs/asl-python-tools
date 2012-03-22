
def print_map(map, indent=4, sort=True, level=1):
    try:
        keys = map.keys()
        if sort:
            keys = sorted(keys)
        print '{'
        for key in keys:
            print "%s%s:" % (level*indent*' ',key),
            print_map(map[key], indent, sort, level+1)
        print '%s}' % ((level-1)*indent*' ',)
    except AttributeError:
        print map

