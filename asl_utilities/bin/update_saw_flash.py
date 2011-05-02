#!/usr/bin/env python
import asl

import calendar
import ftplib
import optparse
import os
import Queue
import re
import socket
import sys
import time

from jtk.Class import Class

networks = ('CU', 'IC', 'IU')

# === Main Class /*{{{*/
class Main(Class):
    def __init__(self):
        Class.__init__(self)

        self._handle = None

    def start(self):
        try:
            use_message = """usage: %prog [options]"""
            option_list = []
            option_list.append(optparse.make_option("-v", dest="verbosity", action="count", help="Specify multiple time to increase verbosity."))
            parser = optparse.OptionParser(option_list=option_list, usage=use_message)
            options, args = parser.parse_args()

            self._run_update()

        except KeyboardInterrupt:
            print


    def _retrieve_file(self, conn, src, dst):
        max_tries = 5
        tries = 0
        while tries < max_tries:
            tries += 1
            try:
                print "[Try #%d] retrieving file '%s'" % (tries,src),
                conn.retrbinary("RETR "+src, open(dst, 'w+').write)
                tries = max_tries
                print "DONE."
            except socket.timeout, e:
                print "FAILED! (socket.timeout)"
            except socket.error, e:
                print "FAILED! (socket.error)"


    def _update_metadata(self, dir):
      # establish connection with FTP server
        conn = ftplib.FTP("aslftp.cr.usgs.gov", "ftp", "", timeout=20)
        conn.set_pasv(True)

      # get dataless files
        conn.cwd("pub/dataless")
        for file in conn.nlst():
            if file[0:9] != "DATALESS.":
                print "skipping file '%s'" % file
                continue
            if file.split('.', 1)[1].split('_', 1)[0] not in networks:
                print "skipping file '%s'" % file
                continue
            self._retrieve_file(file, dir + "/dataless" + file)

        conn.cwd('/')

      # get response files
        conn.cwd("pub/responses")
        for file in conn.nlst():
            if file[0:5] != "RESP.":
                print "skipping file '%s'" % file
                continue
            if file.split('.')[1] not in networks:
                print "skipping file '%s'" % file
                continue
            self._retrieve_file(file, dir + "/dataless" + file)

      # terminate FTP session
        conn.quit()


    def _process_block(self, block):
        self._handle.write(block)

    def _run_update(self):
        drive = "/media/SAW_UPDATE"
        if not os.path.isdir(drive):
            "Could not locate flash drive (expected path %s)." % drive
            return

        update_dir = drive + "/metadata"
        if not os.path.exists(update_dir):
            try:
                os.makedirs(update_dir)
            except:
                print "Unable to create metadata directory '%s'." % update_dir
        elif not os.path.isdir(update_dir):
            print "Path '%s' exists, but is not a directory." % update_dir

        dataless_dir = update_dir + "/dataless"
        if not os.path.exists(dataless_dir):
            try:
                os.makedirs(dataless_dir)
            except:
                print "Unable to create metadata directory '%s'." % dataless_dir
        elif not os.path.isdir(dataless_dir):
            print "Path '%s' exists, but is not a directory." % dataless_dir

        responses_dir = update_dir + "/responses"
        if not os.path.exists(responses_dir):
            try:
                os.makedirs(responses_dir)
            except:
                print "Unable to create metadata directory '%s'." % responses_dir
        elif not os.path.isdir(responses_dir):
            print "Path '%s' exists, but is not a directory." % responses_dir

        update_file = responses_dir + "/.effective"

        print "downloading metadata from ftp site ..."
        self._update_metadata(update_dir)

        print "updating effective date in '%s' ..." % update_file

        wh = open(update_file, 'w+')
        wh.write(time.strftime("%Y/%m/%d %H:%M:%S\n", time.gmtime()))
        wh.close()

        print "Update Complete."

    def _should_update(self, existing, newer):
        if not os.path.isfile(newer):
            return False
        if not os.path.isfile(existing):
            return True
        update_effective   = calendar.timegm(time.strptime(open(newer).readline().strip(), "%Y/%m/%d %H:%M:%S"))
        metadata_effective = calendar.timegm(time.strptime(open(existing).readline().strip(), "%Y/%m/%d %H:%M:%S"))
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
        

