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
        self.context['log'] = LogThread(prefix='update_', note='UPDATE', pid=True)
        self.context['log'].start()
        self.log_queue = self.context['log'].queue
        self.metadata_path = ''

    def start(self):
        try:
            use_message = """usage: %prog [options]"""
            option_list = []
            option_list.append(optparse.make_option("-m", "--metadata-directory", dest="metadata_directory", action="store", help="Place metadata in this directory instead of the default."))
            parser = optparse.OptionParser(option_list=option_list, usage=use_message)
            options, args = parser.parse_args()

            if options.metadata_directory:
                self.metadata_path = options.metadata_directory
            else:
                self.metadata_path = '/opt/metadata'
            if not os.path.exists(self.metadata_path):
                raise IOError("%s: path does not exist" % self.metadata_path)
            if not os.path.isdir(self.metadata_path):
                raise IOError("%s: path is not a directory" % self.metadata_path)
                
            self.context['log'].logger.set_log_path(self.metadata_path)
            self.context['log'].logger.set_log_to_screen(False)
            self.context['log'].logger.set_log_to_file(True)
            self.context['log'].logger.set_log_debug(False)
            # INFO: Should use the self._log() method after this point only  

            self._log("Logging has begun")

            update_file = os.path.abspath('%s/update' % self.metadata_path)
            update = False
            if os.path.exists(update_file):
                if os.path.isfile(update_file):
                    update = True
                else:
                    self._log("Invalid type for update file %s" % update_file)
            if not update:
                raise KeyboardInterrupt

            self._run_update()
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
        drive = "/media/SAW_UPDATE"
        if not os.path.isdir(drive):
            self._log("Could not locate flash drive (expected path %s)" % drive)
            return

        update_dir = drive + "/metadata"
        update_file = metadata_dir + "/.effective"
        metadata_file = self.metadata_path + "/.effective"

        if self._should_update(metadata_file, update_file):
            self._log("Updating metadata..." % drive)

            self._log("  removing old metadata..." % drive)
            for file in os.listdir(self.metadat_path):
                path = self.metadata_path + "/" + file
                shutil.rmtree(path)

            self._log("  copying new metadata..." % drive)
            for file in os.listdir(update_dir):
                src = update_dir + "/" + file
                dst = self.metadata_path + "/" + file
                shutil.copytree(src, dst)
            self._log("Metadata update complete." % drive)

        # The update module included with the flash drive performs the upgrade
        sys.path.insert(0, drive)
        try:
            import saw_update
            saw_update.update()
        except ImportError, e:
            self._log("Module 'saw_update' could not be located on the flash drive")
            return
        except AttributeError, e:
            self._log("Module 'saw_update' appears to be invalid or corrupt")
            return
        return

    def _should_update(self, existing, newer):
        if not os.path.isfile(newer):
            return False
        if not os.path.isfile(existing):
            return True
        update_effective   = time.mktime(time.strptime(open(update_file).readline().strip(), "%Y/%m/%d %H:%M:%S"))
        metadata_effective = time.mktime(time.strptime(open(metadata_file).readline().strip(), "%Y/%m/%d %H:%M:%S"))
        if update_effective > metadata_effective:
            return True
        return False

    def _update_content(self, src, dst):
        if not os.path.exists(src):
            self._log("_update_content(): Could not locate source path '%s'" % src)
        if os.path.isdir(src):
            if not os.path.exists(dst):
                try:
                    os.mkdir(dst)
                except:
                    self._log("_update_content(): Could not create destination path '%s'" % dst)
            if os.path.isdir(dst):
                _update_content(dst)
            elif os.path.isfile(dst):
                self._log("_update_content(): Could not create destination path '%s'" % dst)
        elif os.path.isfile(src):
            if not os.path.exists(dst):
                shutil.copy(src, dst)
            elif not os.path.isfile(dst):
                self.log("_update_content(): Source '%s' is a file but destination '%s' is not" % (src, dst))
            else:
                # replace with new content only
                pass

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
        

