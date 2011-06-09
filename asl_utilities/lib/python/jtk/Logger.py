import os
import Queue
import stat
import sys
import time

from Thread import Thread
from permissions import Permissions

class Logger(object):
    def __init__(self, directory='.', prefix='', postfix='', extension='log', note='', yday=False):
        self.log_to_file    = True
        self.log_to_screen  = False
        self.log_fh         = None
        self.note_first     = True
        self.log_debug      = False
        self.yday           = yday

        self._note          = note
        self._log_pid       = False
        self._pid           = str(os.getpid())
        self._file_name     = ''
        self._file_set      = False
        self._file_changed  = False

        self.categories = {
            'dbg'     : 'DEBUG',
            'debug'   : 'DEBUG',
            'err'     : 'ERROR',
            'error'   : 'ERROR',
            'info'    : 'INFO',
            'default' : 'INFO',
            'warn'    : 'WARNING',
            'warning' : 'WARNING',
        }

        if directory == '':
            directory = '.'
        self.log_context = {
            'directory' : directory,
            'prefix'    : prefix,
            'postfix'   : postfix,
            'extension' : extension,
            'date'      : '',
        }

# ===== The Log Routine =============================================
    def log(self, string, cat_key="default"):
        category = "UNKNOWN"
        screen_fh = sys.stdout
        if self.categories.has_key(cat_key):
            category = self.categories[cat_key]
        else:
            try:
                category = str(cat_key)
            except:
                pass

        if category == "ERROR":
            screen_fh = sys.stderr
        elif (category == "DEBUG") and (not self.log_debug):
            return

        if self.yday:
            timestamp_text = time.strftime("%Y,%j-%H:%M:%S", time.gmtime())
            file_date = timestamp_text[0:4] + '_' + timestamp_text[5:8]
        else:
            timestamp_text = time.strftime("%Y/%m/%d-%H:%M:%S", time.gmtime())
            file_date = timestamp_text[0:4] + timestamp_text[5:7] + timestamp_text[8:10]

        text = ""
        note = self._note
        if self._log_pid:
            if note:
                note = "%s:%s" % (self._pid,note)
            else:
                note = self._pid
        if self.note_first:
            if note:
                text = "[%s @ %s] %s>" % (note, timestamp_text, category)
            else:
                text = "[%s] %s>" % (timestamp_text, category)
        else:
            text = "[%s @ %s] %s>" % (category, timestamp_text, note)
        text += " %s\n" % string.strip('\n')

        if self.log_to_file:
            self._prepare_log(file_date)
            if self.log_fh:
                self.log_fh.write( text )
                self.log_fh.flush()
        if self.log_to_screen:
            screen_fh.write( text )
            screen_fh.flush()

# ===== Settings Mutators ===================
    def set_log_to_file(self, enabled):
        self.log_to_file = enabled

    def set_log_to_screen(self, enabled):
        self.log_to_screen = enabled

    def set_log_debug(self, enabled):
        self.log_debug = enabled

    def set_log_path(self, path=''):
        self.log_context['directory'] = path
        self._file_changed = True

    def set_log_file(self, name=''):
        if name == '':
            self._file_set = False
        else:
            self._file_set  = True
            self._file_name = name
        self._file_changed = True

    def set_log_note(self, note=''):
        self._note = note

    def set_log_pid(self, pid):
        self._log_pid = pid
        
    def set_note_first(self, enabled):
        self.note_first = enabled


# ===== Settings Accessors ==================
    def get_log_to_file(self):
        return self.log_to_file

    def get_log_to_screen(self):
        return self.log_to_screen

    def get_log_debug(self):
        return self.log_debug

    def get_log_path(self):
        return self.log_context['directory']

    def get_log_file(self):
        if self._file_set:
            return self._file_name
        return None

    def get_log_note(self):
        return self._note

    def get_log_pid(self):
        return self._log_pid

    def get_note_first(self):
        return self.note_first


# ===== Internal Methods =============================================
    def _open_log(self):
        if not self._file_set:
            if not os.path.exists(self.log_context['directory']):
                try:
                    os.makedirs(self.log_context['directory'])
                except:
                    raise IOError("Could not create directory '%(directory)s'" % self.log_context)
            elif not os.path.isdir(self.log_context['directory']):
                raise IOError("Path '%(directory)s' exists, but is not a directory." % self.log_context)
            if self.log_context['extension']:
                self._file_name = "%(directory)s/%(prefix)s%(date)s%(postfix)s.%(extension)s" % self.log_context
            else:
                self._file_name = "%(directory)s/%(prefix)s%(date)s%(postfix)s" % self.log_context
        if os.path.exists(self._file_name) and (not os.path.isfile(self._file_name)):
            raise IOError("Path '%s' exists, but is not a regular file." % self._file_name)
        self.log_fh = open( self._file_name, 'a' )

        Permissions("EEIEEIEII", 1).process([self._file_name])

    def _close_log(self):
        if self.log_fh:
            self.log_fh.close()
        self.log_fh = None

    def _prepare_log(self, file_date):
        if (not self._file_changed) and (file_date == self.log_context['date']) and self.log_fh:
            return
        else:
            self._file_changed = False
            self.log_context['date'] = file_date
            self._close_log()
            self._open_log()


class LogThread(Thread):
    def __init__(self, directory='.', prefix='', postfix='', extension='log', note='LOGGER', yday=False, pid=False):
        Thread.__init__(self)
        self.file_handles = {}
        self.logger = Logger(directory=directory, prefix=prefix, postfix=postfix, extension=extension, note=note, yday=yday)
        self._log_note = note
        self.logger.set_log_debug(False)
        #self.logger.set_log_debug(True)
        self.logger.set_log_to_file(False)
        self.logger.set_log_to_screen(True)
        self.logger.set_log_note(note)
        self.logger.set_note_first(True)
        self.logger.set_log_pid(pid)

    def _run(self, message, data):
        try:
            if type(message) == str:
                self.logger.set_log_note(message)
            else:
                self.logger.set_log_note(self._log_note)
            self.logger.log(data[0], data[1])
        except KeyboardInterrupt:
            pass
        except Exception, e:
            self._log("_run() Exception: %s" % str(e))

