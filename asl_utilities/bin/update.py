#!/usr/bin/env python
import asl

import calendar
import optparse
import os
import Queue
import re
import sys
import time

from jtk.Class import Class
from jtk.Thread import Thread
from jtk.Logger import LogThread

# === Main Class /*{{{*/
class Main(Class):
    def __init__(self):
        Class.__init__(self)
        self.context = {}
        self.context['log'] = LogThread(prefix='archive_', note='ARCHIVE', pid=True)
        self.context['log'].start()
        self.log_queue = self.context['log'].queue
        # INFO: Can use the self._log() method after this point only  

    def start(self):
        try:
            use_message = """usage: %prog [options]"""
            option_list = []
            option_list.append(optparse.make_option("-m", "--metadata-directory", dest="metadata_directory", action="store", help="Place metadata in this directory instead of the default."))
            parser = optparse.OptionParser(option_list=option_list, usage=use_message)
            options, args = parser.parse_args()

            if options.metadata_directory:
                metadata_path = options.metadata_directory
            else:
                metadata_path = '/opt/metadata'
            if not os.path.exists(metadata_path):
                raise IOError("%s: path does not exist" % metadata_path)
            if not os.path.isdir(metadata_path):
                raise IOError("%s: path is not a directory" % metadata_path)
                
            log_path = '%s/update.log' % metadata_path

            self.context['log'].logger.set_log_path(log_path)
            self.context['log'].logger.set_log_to_screen(False)
            self.context['log'].logger.set_log_to_file(True)
            self.context['log'].logger.set_log_debug(False)

            update_file = os.path.abspath('%s/update' % metadata_path)
            update = False
            if os.path.exists(update_file):
                if os.path.isfile(update_file):
                    update = True
                else:
                    self._log("Invalid type for update file %s" % update_file)
            if not update:
                raise KeyboardInterrupt

            # This is only if we died part way through the update
            # If there was nothing to update, we remove the file
            if self._run_update():
                os.remove(update_file)

        except KeyboardInterrupt:
            pass

        halted = False
        while not halted:
            try:
                self.halt()
                halted = True
            except KeyboardInterrupt:
                pass

    def _run_update(self):
        success = True
        # TODO: update logic here
        # - Check for USB Drive
        # - Copy over any metdata that is more recent
        # - 
        drive = "/media/SAW_UPDATE"
        if not os.path.isdir(drive):
            self._log("Could not locate flash drive (expected path %s)" % drive)
            # check if local files are older than those on the flash drive,
            # if they are, update them.
            # copy metadata/ to /opt/metadata/

        return success

    def halt(self, now=False):
        check_alive = lambda c,k: c.has_key(k) and c[k] and c[k].isAlive()
        thread_list = ['log']
        for key in thread_list:
            if check_alive(self.context, key):
                if now:
                    self.context[key].halt_now()
                else:
                    self.context[key].halt()
                self.context[key].join()

    def halt_now(self, signal=None, frame=None):
        self.halt(True)
#/*}}}*/

def main():
    main = Main()
    main.start()

if __name__ == '__main__':
    main()
        

