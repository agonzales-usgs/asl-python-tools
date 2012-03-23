
def pretty(target, indent=4, sort=True, level=1, pad=True, pre="", post=""):
    s_pad = indent * (level-1) * ' '
    v_pad = indent * level * ' '
    if type(target) == dict:
        t_pad = s_pad
        if not pad: t_pad = ''
        print "%s%s{" % (pre,t_pad)
        pairs = target.items()
        if sort:
            pairs = sorted(pairs)
        for key,value in pairs:
            if type(key) == str:
                key = "'%s'" % key
            print "%s%s:" % (v_pad,key),
            pretty(value, indent=indent, sort=sort, level=level+1, pad=False, post=',')
        print "%s}%s" % (s_pad,post)
    elif type(target) in (list,tuple):
        t_pad = s_pad
        if not pad: t_pad = ''
        print "%s%s[" % (pre,t_pad)
        if sort:
            target = sorted(target)
        for value in target:
            pretty(value, indent=indent, sort=sort, level=level+1, post=',')
        print "%s]%s" % (s_pad,post)
    else:
        if type(target) == str:
            target = "'%s'" % target
        t_pad = v_pad
        if not pad: t_pad = ''
        print "%s%s%s%s" % (t_pad, pre, target, post)

