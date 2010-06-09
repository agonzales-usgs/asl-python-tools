import Queue

class Class(object):
    def __init__(self):
        object.__init__(self)
        self.log_queue = None

    def _log(self, log_str, category='default', note=None):
        if self.log_queue:
            self.log_queue.put_nowait((self.__class__.__name__, (log_str, category)))
