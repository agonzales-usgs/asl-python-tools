
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

    def reset():
        self._count = self._default

    def ie():
        self._count += self._step
        return self._count

    def de():
        self._count -= self._step
        return self._count

    def ei():
        tmp = self._count
        self._count += self._step
        return tmp

    def ed():
        tmp = self._count
        self._count -= self._step
        return tmp

