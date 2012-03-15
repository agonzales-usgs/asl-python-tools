
class Counter(object):
    def __init__(self, default=0, step=1):
        object.__init__(self)
        self._default = default
        self._step    = step
        self.reset()

    def set_default(self, default):
        self._default = default

    def reset(self):
        self._count = self._default

    def set_value(self, value):
        self._count = value

    def set_step(self, step):
        self._step = step
    def set_stride(self, stride):
        self.set_step(stride)

    # pre-increment
    def p_inc(self):
        self._count += self._step
        return self._count
    def inc(self):
        return self.p_inc()

    # pre-decrement
    def p_dec(self):
        self._count -= self._step
        return self._count
    def dec(self):
        return self.p_dec()

    # post-increment
    def inc_p(self):
        tmp = self._count
        self._count += self._step
        return tmp

    # post-decrement
    def dec_p(self):
        tmp = self._count
        self._count -= self._step
        return tmp

