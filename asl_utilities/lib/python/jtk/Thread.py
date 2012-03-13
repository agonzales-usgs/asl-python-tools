import Queue
import threading

from Class import Class

class Thread(threading.Thread, Class):
    def __init__(self, queue_max=-1, log_queue=None, name=None):
        if name is None:
            name = self.__class__.__name__
        threading.Thread.__init__(self, name=name)
        Class.__init__(self, log_queue)
        self.daemon = True
        self.running = False
        self.queue = Queue.Queue(queue_max)
        self.queue_halt = Queue.Queue()

    def halt_now(self):
        self.running = False # Forces thread to halt on the next iteration
        self.queue.put(('HALT', None)) # Forces the next iteration if there is no waiting data
        self.queue_halt.get()

    def halt(self):
        self.queue.put(('HALT', None)) # Asks the process to halt, but only once this request is reached
        self.queue_halt.get()

    def run(self):
        self._pre()
        self.running = True
        self._log('Thread Started', 'dbg')
        try:
            while self.running:
                message, data = self.queue.get()
                if message == 'HALT':
                    self.running = False
                elif message == 'DONE':
                    self.running = False
                else:
                    self._run(message, data)
        except KeyboardInterrupt:
            pass
        except Exception, e:
            self._log("run() Exception: %s" % str(e), 'err')
        self.queue_halt.put('DONE')
        self._post()

    def _pre(self):
        pass

    def _run(self, message, data):
        raise Exception("BaseThread::_run() must be overridden.")

    def _post(self):
        pass
