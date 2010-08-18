import sys
import thread
import time
import traceback
import signal

class Interval(object):
    # Create Timer Object
    def __init__(self, interval, function, use_signals, *args, **kwargs):
        self.__lock = thread.allocate_lock()
        self.__interval = interval
        self.__function = function
        self.__args = args
        self.__kwargs = kwargs
        self.__loop = False
        self.__alive = False
        self.__use_signals = use_signals 
        if self.__use_signals:
            signal.signal(signal.SIGALRM, self.__run_signal)

    # Start Timer Object
    def start(self):
        self.__lock.acquire()
        if not self.__alive:
            self.__loop = True
            self.__alive = True
            if self.__use_signals:
                self.__reset()
            else:
                thread.start_new_thread(self.__run_thread, ())
        self.__lock.release()

    # Stop Timer Object
    def stop(self):
        self.__lock.acquire()
        self.__loop = False
        self.__lock.release()

    # Private Thread Function
    def __run_thread(self):
        while self.__loop:
            #try:
            self.__function(*self.__args, **self.__kwargs)
            #except Exception, e:
            #    print "Interval::_run() caught exception: %s" % e.__str__()
            #    traceback.print_tb( sys.last_traceback )
            #    tblist = traceback.extract_tb(sys.exc_info()[2])
            #    tblist = filter(self.__filter_not_pexpect, tblist)
            #    tblist = traceback.format_list(tblist)
            #    print ''.join(tblist)
            time.sleep(self.__interval)
        self.__alive = False

    # Run the user's function
    def __run_signal(self, signum=None, stkfrm=None):
        if self.__loop:
            self.__function(*self.__args, **self.__kwargs)
            self.__reset()
        else:
            self.__alive = False

    # Set Next Callback
    def __reset(self):
        signal.alarm(self.__interval)

