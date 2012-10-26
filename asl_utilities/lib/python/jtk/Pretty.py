
def pretty(target, indent=4, sort=True, level=1, pad=True, pre="", post=""):
    pretty_str = ""
    s_pad = indent * (level-1) * ' '
    v_pad = indent * level * ' '
    if type(target) == dict:
        t_pad = s_pad
        if not pad: t_pad = ''
        pretty_str += "%s%s{\n" % (pre,t_pad)
        pairs = target.items()
        if sort:
            pairs = sorted(pairs)
        for key,value in pairs:
            if type(key) == str:
                key = "'%s'" % key
            pretty_str += "%s%s:" % (v_pad,key)
            # Recursive call for maps
            pretty_str += pretty(value, indent=indent, sort=sort, level=level+1, pad=False, post=',')
        pretty_str += "%s}%s\n" % (s_pad,post)
    elif type(target) in (list,tuple):
        t_pad = s_pad
        if not pad: t_pad = ''
        pretty_str += "%s%s[\n" % (pre,t_pad)
        if sort:
            target = sorted(target)
        for value in target:
            # Recursive call for lists and tuples
            pretty_str += pretty(value, indent=indent, sort=sort, level=level+1, post=',')
        pretty_str += "%s]%s\n" % (s_pad,post)
    else:
        if type(target) == str:
            target = "'%s'" % target
        t_pad = v_pad
        if not pad: t_pad = ''
        pretty_str += "%s%s%s%s\n" % (t_pad, pre, target, post)

    return pretty_str

