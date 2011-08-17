
class Counter(object):
    def __init__(self):
        object.__init__(self)
        self._default = 0
        self._count   = 0
        self._step    = 1

    def set_step(self, step):
        self._step = step

    def set_default(self, default):
        self._default = default

    def reset(self):
        self._count = self._default

    def p_inc(self):
        self._count += self._step
        return self._count

    def p_dec(self):
        self._count -= self._step
        return self._count

    def inc_p(self):
        tmp = self._count
        self._count += self._step
        return tmp

    def dec_p(self):
        tmp = self._count
        self._count -= self._step
        return tmp

