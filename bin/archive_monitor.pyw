#!/usr/bin/python
import asl

import asyncore
import calendar
import os
import Queue
import re
import signal
import socket
import sys
import threading
import time

import pygtk
pygtk.require('2.0')
import gobject
import gtk

from jtk.Class import Class
from jtk.Thread import Thread
from jtk.Logger import LogThread

gobject.threads_init()

# === Notifier Class /*{{{*/
class Notifier(asyncore.dispatcher):
    def __init__(self):
        asyncore.dispatcher.__init__(self)
        self.sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_in.bind(('', 0))
        self.address = ('127.0.0.1', self.sock_in.getsockname()[1])
        self.sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.set_socket(self.sock_in)

    def notify(self):
        #print "%s::notify()" % self.__class__.__name__
        self.sock_out.sendto('CHANGED', self.address)

    def handle_read(self):
        #print "%s::handle_read()" % self.__class__.__name__
        msg = self.sock_in.recv(7)
        #print "%s::handle_read() read %d bytes" % (self.__class__.__name__, len(msg))
        return len(msg)

    def writable(self):
        return False

    def readable(self):
        return True
#/*}}}*/

# === Status Class /*{{{*/
class Status(asyncore.dispatcher):
    def __init__(self, master, log_queue=None):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.bind(('0.0.0.0', 0))
        self._buffers = []
        self._write_buffer = ''
        self._write_address = None
        self._last_activity = 0
        self._regex_status = re.compile('^\[(.*)\]<(.*)>$')
        self._master = master

    def check_status(self):
        #print "%s::check_status()" % self.__class__.__name__
        self._buffers.append(('[TIMESTAMP]<LAST-PACKET>', ('127.0.0.1', 4000)))

    def handle_read(self):
        #print "%s::handle_read()" % self.__class__.__name__
        try:
            packet,address = self.recvfrom(4096)
        except socket.error:
            time.sleep(1.0)
            return
        if not packet:
            return 0
        match = self._regex_status.search(packet)
        if match:
            id,message = match.groups()
        else:
            id = '0'
            message = packet

        try:
            if id == 'TIMESTAMP':
                self._last_activity = int(message)
                #print "Last packet received", int(message)
        except:
            pass
        return len(packet)

    def handle_write(self):
        #print "%s::handle_write()" % self.__class__.__name__
        bytes_written = 0
        if (self._write_address is None) or (not len(self._write_buffer)):
            if len(self._buffers):
                self._write_buffer,self._write_address = self._buffers.pop(0)
            else:
                self._write_buffer = ''
                self._write_address = None
        if (self._write_address is not None) and len(self._write_buffer):
            bytes_written = self.sendto(self._write_buffer, self._write_address)
        self._write_buffer = self._write_buffer[bytes_written:]

    def readable(self):
        return True

    def writable(self):
        if len(self._buffers):
            return True
        if len(self._write_buffer) and self._write_address is not None:
            return True
        return False

#/*}}}*/

# === CommThread Class /*{{{*/
class CommThread(Thread):
    def __init__(self, master, log_queue=None):
        Thread.__init__(self, queue_max=1024, log_queue=log_queue)
        self.daemon = True
        self._master = master
        self._running = False
        self._notifier = Notifier()
        self._status = Status(self)

    def halt_now(self):
        self.halt()

    def halt(self):
        #print "%s::halt()" % self.__class__.__name__
        self._log("thread halting...")
        self._running = False
        self._notifier.notify()

    def check_status(self):
        #print "%s::check_status()" % self.__class__.__name__
        self._status.check_status()
        self._notifier.notify()

    def get_last_activity(self):
        return self._status._last_activity

    def run(self):
        try:
            #print "%s::run()" % self.__class__.__name__
            self._running = True
            while self._running:
                map = {
                    self._notifier.socket : self._notifier,
                    self._status.socket   : self._status,
                }
                #asyncore.loop(timeout=30.0, use_poll=False, map=map, count=1)
                asyncore.loop(timeout=5.0, use_poll=False, map=map, count=1)

        except Exception, e:
            print "%s::run() caught an exception: %s" % (self.__class__.__name__,str(e))
# /*}}}*/

# === StatusThread Class /*{{{*/
class StatusThread(Thread):
    def __init__(self, master, log_queue=None):
        Thread.__init__(self, queue_max=1024, log_queue=log_queue)
        self.daemon = True
        self._master = master
        self._running = False

    def halt_now(self):
        self.halt()

    def halt(self):
        #print "%s::halt()" % self.__class__.__name__
        self._running = False
        self.queue.put('HALT')

    def run(self):
        try:
            #print "%s::run()" % self.__class__.__name__
            self._running = True
            while self._running:
                #print "%s::run() Requesting status update" % self.__class__.__name__
                self._master.check_status()
                self._master.update_time()
                try:
                    #print "%s::run() Sleeping" % self.__class__.__name__
                    self.queue.get(True,self._master.check_interval)
                except Queue.Empty:
                    pass
        except Exception, e:
            print "%s::run() caught an exception: %s" % (self.__class__.__name__,str(e))
# /*}}}*/

# === ArchiveIcon Class /*{{{*/
class ArchiveIcon:
    def __init__(self):
        self.status_icon = gtk.StatusIcon()
        self.status_icon.set_from_file('/opt/icons/box_inactive.png')
        self.status_icon.set_visible(True)
        self.status_icon.connect( "popup-menu", self.callback_menu, None )
        self.status_icon.connect( "activate", self.callback_activate, None )

        self.check_interval = 5.0

        self.menu = gtk.Menu()
        self.menu.set_title("Archive Monitor")

        self.image_restart = gtk.Image()
        self.image_restart.set_from_file('/opt/icons/restart.png')
        self.menuitem_restart = gtk.ImageMenuItem("Restart", "Restart")
        self.menuitem_restart.set_image(self.image_restart)
        self.menuitem_restart.connect("activate", self.callback_restart, None)
        self.menu.append(self.menuitem_restart)

        self.menu.show()
        self.menuitem_restart.show()

        self.warn_delay = 60
        self.last_activity = 0

        self.hbutton_update_time = gtk.Button()
        self.hbutton_update_time.connect('clicked', self.callback_update_time, None)

        self.comm_thread   = CommThread(self)
        self.status_thread = StatusThread(self)

        #print "Starting Threads..."
        self.comm_thread.start()
        self.status_thread.start()

# ===== Callback Methods =============================================
    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, None, data)

    def callback_restart(self, widget, event, data=None):
        self.dates.today()

    def callback_menu(self, widget, button, activate_time, data=None):
        self.menu.popup( None, None, None, button, activate_time, data )

    def callback_activate(self, widget, event, data=None):
        self.window.toggle()

    def callback_update_time(self, widget, event, data=None):
        #print "%s::callback_update_time()" % self.__class__.__name__
        delay = calendar.timegm(time.gmtime()) - self.comm_thread.get_last_activity()
        print "delay is %d seconds" % delay
        if delay >= self.warn_delay:
            self.status_icon.set_from_file('/opt/icons/box_inactive.png')
        else:
            self.status_icon.set_from_file('/opt/icons/box_active.png')

# ===== Methods ======================================================
    def close_application(self, widget, event, data=None):
        self.status_thread.halt_now()
        self.status_thread.join()

        self.comm_thread.halt_now()
        self.comm_thread.join()

        gtk.main_quit()
        return False

    def update_time(self):
        #print "%s::update_time()" % self.__class__.__name__
        gobject.idle_add(gobject.GObject.emit, self.hbutton_update_time, 'clicked')

    def check_status(self):
        #print "%s::check_status()" % self.__class__.__name__
        self.comm_thread.check_status()
#/*}}}*/

if __name__ == "__main__":
    try:
        app = ArchiveIcon()
        gtk.main()
    except KeyboardInterrupt:
        pass
