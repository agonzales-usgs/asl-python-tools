import Queue
import multiprocessing

from Class import Class

class Process(multiprocessing.Process, Class):
    def __init__(self, queue_max=-1, log_queue=None, name=None, timeout=None, timeout_message="", timeout_data=None, queue=None):
        if name is None:
            name = self.__class__.__name__
        multiprocessing.Process.__init__(self, name=name)
        Class.__init__(self, log_queue)
        self.daemon = False
        self.running = False
        self.timeout = timeout
        self.timeout_message = timeout_message
        self.timeout_data = timeout_data
        if queue is None:
            self.queue = Queue.Queue(queue_max)
        else:
            self.queue = queue

  # Forces the thread to halt immediately
    def halt_now(self, join=True):
        self.running = False
        self.halt(join)

  # Asks the process to halt, but only once this request is reached
  # This allows it to finish processing all outstanding requests before stopping
    def halt(self, join=True):
        self.queue.put(('HALT', None))
        if join:
            try:
                self.join()
            except RuntimeError, err:
                self._log("halt() RuntimeError: %s" % str(err), 'err')
                pass # handle the situation where halt() is called by this thread

    def run(self):
        self._pre()
        self.running = True
        self._log('Process Started', 'dbg')
        try:
            while self.running:
                try:
                    message,data = self.queue.get(block=True, timeout=self.timeout)
                except Queue.Empty, e:
                    message = self.timeout_message
                    data = self.timeout_data
                if message == 'HALT':
                    self.running = False
                elif message == 'DONE':
                    self.running = False
                else:
                    self._run(message, data)
        except KeyboardInterrupt:
            pass
        except Exception, ex:
            self._log("run() Exception: %s" % str(ex), 'err')
            #raise #XXX: Un-comment to debug multiprocessing issues
        self._post()

    def _pre(self):
        pass

    def _run(self, message, data):
        raise Exception("Process::_run() must be overridden.")

    def _post(self):
        pass
