import time

class Timer():
    def __init__(self):
        self._start = 0
        self._end = 0
        self._last = 0

    def start(self):
        self._start = time.time()
        self._last = self._start
        return self._start

    def stop(self):
        self._end = time.time()
        return self._end

    def split(self):
        self._end = time.time()
        split = self._end - self._last 
        self._last = time.time()
        return split
        
    def span(self):
        return self._end - self._start


