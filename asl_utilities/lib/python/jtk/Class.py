import Queue

class Class(object):
    def __init__(self, log_queue=None):
        object.__init__(self)
        self.log_queue = log_queue
        self.log = self._log

    def get_log_queue(self):
        return self.log_queue

    def _log(self, log_str, category='default', note=None):
        if self.log_queue:
            if note is None:
                note = self.__class__.__name__
            self.log_queue.put_nowait((note, (log_str, category)))
