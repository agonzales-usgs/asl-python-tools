#!/usr/bin/env python
import asl

import asyncore
import calendar
import optparse
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

from jtk.StatefulClass import StatefulClass
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
        self._address = ('127.0.0.1', 4000)

    def check_status(self):
        #print "%s::check_status()" % self.__class__.__name__
        self._buffers.append(('[TIMESTAMP]<LAST-PACKET>', self._address))

    def set_address(self, address):
        tmp_address = self._address
        try:
            self._address = (socket.gethostbyname(address[0]),int(address[1]))
        except:
            self._address = tmp_address
            return False
        return True

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
        self._status.set_port(self._master.get_address())

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
            #print "%s::run() caught an exception: %s" % (self.__class__.__name__,str(e))
            pass
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
            #print "%s::run() caught an exception: %s" % (self.__class__.__name__,str(e))
            pass
# /*}}}*/

# === RestartThread Class /*{{{*/
class RestartThread(Thread):
    def __init__(self, master, log_queue=None):
        Thread.__init__(self, queue_max=1024, log_queue=log_queue)
        self.daemon = True
        self._master = master
        self._running = False

    def _run(self, message, data):
        #print "got message %s" % message
        if message == 'RESTART':
            try:
                if os.path.exists('/tmp/archive.pid'):
                    tpid = open('/tmp/archive.pid', 'r').read(32).strip()
                    if self._find_proc(tpid):
                        #print "archive.py process [%s] found" % tpid
                        try:
                            fh = open('/opt/var/archive/restart/%s' % tpid, 'w+')
                            fh.write(tpid)
                            fh.close()
                        except:
                            self._kill_proc()
            except Exception, e:
                #print "%s::_run() caught exception: %s" % (self.__class__.__name__,str(e))
                pass

    def _kill_proc(self, tpid):
        if self._find_proc(tpid):
            #print "archive.py process [%s] found" % tpid
            #print "sending SIGTERM to archive.py process [%s]" % tpid
            os.kill(int(tpid), 15)
            count = 60
            while 1:
                if not self._find_proc(tpid):
                    #print "archive.py process [%s] has died" % tpid
                    break
                count -= 1
                if count <= 0:
                    #print "sending SIGKILL to archive.py process [%s]" % tpid
                    os.kill(int(tpid), 9)
                    break
                try:
                   message,data = self.gueue.get(True, 1.0)
                   #print "received message %s while in process kill" % message
                   if message == 'HALT':
                       self.queue.put((message,data))
                       return
                except Queue.Empty:
                    pass

    def _find_proc(self, tpid):
        tpid = str(tpid)
        proc = os.popen('ps ax -o pid,args | grep %s' % tpid)
        for line in proc.readlines():
            pid,exe = line.strip().split(' ', 1)
            if tpid == pid:
                if re.search('archive[.]py', exe):
                    return True
        return False

# /*}}}*/

# === ArchiveIcon Class /*{{{*/
class ArchiveIcon:
    def __init__(self, address=('127.0.0.1', 4000)):
        signal.signal(signal.SIGTERM, self.halt_now)

        self._address = address

        self.status_icon = gtk.StatusIcon()
        self.status_icon.set_from_pixbuf(asl.new_icon('box'))
        self.status_icon.set_visible(True)
        self.status_icon.connect( "popup-menu", self.callback_menu, None )
        self.status_icon.connect( "activate", self.callback_activate, None )

        self.check_interval = 5.0

        self.menu = gtk.Menu()
        self.menu.set_title("Archive Monitor")

        self.menuitem_delay = gtk.MenuItem("Delay: 0 seconds")
        self.menu.append(self.menuitem_delay)

        self.image_restart = gtk.Image()
        self.image_restart.set_from_pixbuf(asl.new_icon('restart').scale_simple(16, 16, gtk.gdk.INTERP_HYPER))
        self.menuitem_restart = gtk.ImageMenuItem("Restart", "Restart")
        self.menuitem_restart.set_image(self.image_restart)
        self.menuitem_restart.connect("activate", self.callback_restart, None)
        self.menu.append(self.menuitem_restart)

        self.image_server = gtk.Image()
        self.image_server.set_from_pixbuf(asl.new_icon('network').scape_simple(16, 16, gtk.gdk.INTERP_HYPER))
        self.menuitem_server = gtk.ImageMenuItem("Server", "Server")
        self.menuitem_server.set_iamte(self.image_server)
        self.menuitem_server.connect("activate", self.callback_server, None)
        self.menu.append(self.menuitem_server)

        self.image_exit = gtk.Image()
        self.image_exit.set_from_pixbuf(asl.new_icon('stop').scale_simple(16, 16, gtk.gdk.INTERP_HYPER))
        self.menuitem_exit = gtk.ImageMenuItem("Exit", "Exit")
        self.menuitem_exit.set_image(self.image_exit)
        self.menuitem_exit.connect("activate", self.callback_quit, None)
        self.menu.append(self.menuitem_exit)

        self.menu.show()
        self.menuitem_delay.show()
        self.menuitem_restart.show()
        self.menuitem_exit.show()

        self.warn_delay = 60

        self.hbutton_update_time = gtk.Button()
        self.hbutton_update_time.connect('clicked', self.callback_update_time, None)

        self.comm_thread    = CommThread(self)
        self.status_thread  = StatusThread(self)
        self.restart_thread = RestartThread(self)

        #print "Starting Threads..."
        self.comm_thread.start()
        self.status_thread.start()
        self.restart_thread.start()

# ===== Callback Methods =============================================
    def callback_quit(self, widget, event, data=None):
        self.close_application()

    def callback_restart(self, widget, event, data=None):
        self.restart_thread.queue.put(('RESTART', None))

    def callback_server(self, widget, event, data=None):
        dialog = Dialog(title="Archive Status Server")
        dialog.set_icon(asl.new_icon('network'))
        dialog.add_button_left("OK", self.callback_server_ok, focus=True)
        dialog.add_button_right("Cancel")

        dialog_hbox = gtk.HBox()
        dialog.entry_host  = gtk.Entry()
        dialog_label_colon = gtk.Label(':')
        dialog.entry_port  = gtk.Entry()

        dialog.entry_host.set_width_chars(20)
        dialog.entry_port.set_width_chars(5)

        host,port = self._address
        dialog.entry_host.set_text(host)
        dialog.entry_port.set_text(str(port))

        dialog_hbox.pack_start(dialog.entry_host,  False, False, 5)
        dialog_hbox.pack_start(dialog_label_colon, False, False, 5)
        dialog_hbox.pack_start(dialog.entry_port,  False, False, 5)

        dialog.vbox.pack_end(dialog_hbox)
        dialog_hbox.show_all()

        response = dialog.run()
        return

    def callback_server_ok(self, widget, event, data):
        host = widget.entry_host.get_text()
        port = widget.entry_port.get_text()
        del widget

        if host == '':
            dialog = Dialog(title='Select Host: Invalid Host', message='Invalid Host')
            dialog.set_icon(asl.new_icon('network'))
            dialog.add_button_right('OK', focus=True)
            dialog.run()
            return

        try:
            port = int(port)
            assert port > 0
            assert port < 65536
        except:
            dialog = Dialog(title='Select Host: Invalid Port', message='Invalid Port')
            dialog.set_icon(asl.new_icon('network'))
            dialog.add_button_right('OK', focus=True)
            dialog.run()
            return

        self._address = (host, port)

    def callback_menu(self, widget, button, activate_time, data=None):
        self.menu.popup(None, None, None, button, activate_time, data)

    def callback_activate(self, widget, event, data=None):
        self.menu2.popup(None, None, None, button, calendar.timegm(time.gmtime()), data)

    def callback_update_time(self, widget, event, data=None):
        #print "%s::callback_update_time()" % self.__class__.__name__
        delay = calendar.timegm(time.gmtime()) - self.comm_thread.get_last_activity()
        #print "delay is %d seconds" % delay
        self.menuitem_delay.set_label("Delay: %d seconds" % delay)
        if delay >= self.warn_delay:
            self.status_icon.set_from_pixbuf(asl.new_icon('box'))
        else:
            self.status_icon.set_from_pixbuf(asl.new_icon('box_download'))

# ===== Methods ======================================================
    def close_application(self):
        self.status_thread.halt_now()
        self.status_thread.join()

        self.comm_thread.halt_now()
        self.comm_thread.join()

        self.restart_thread.halt_now()
        self.restart_thread.join()

        gtk.main_quit()
        return False

    def update_time(self):
        #print "%s::update_time()" % self.__class__.__name__
        gobject.idle_add(gobject.GObject.emit, self.hbutton_update_time, 'clicked')

    def check_status(self):
        #print "%s::check_status()" % self.__class__.__name__
        self.comm_thread.check_status()

    def get_address(self):
        return self._address

    def halt_now(self):
        self.close_application()
#/*}}}*/

# === main/*{{{*/
def main():
    try:
        default_port = 4000
        default_host = '127.0.0.1'

        use_message = """usage: %prog [options]"""
        option_list = []
        option_list.append(optparse.make_option("-c", "--config-file", dest="config_file", action="store", help="use this configuration file instead of the default"))
        option_list.append(optparse.make_option("-H", "--host", dest="host", action="store", help="use this host instead of the default (%s)" % default_host))
        option_list.append(optparse.make_option("-p", "--port", dest="port", action="store", type="int", help="monitor on this port instead of the default (%d)" % default_port))
        parser = optparse.OptionParser(option_list=option_list, usage=use_message)
        options, args = parser.parse_args()

        host = ''
        port = -1
        configuration = []
        config_file = ''
        if options.config_file:
            config_file = options.config_file
        if not os.path.exists(config_file):
            if os.environ.has_key('SEED_ARCHIVE_CONFIG'):
                config_file = os.environ['SEED_ARCHIVE_CONFIG']
        if not os.path.exists(config_file):
            config_file = 'archive.config'
        if not os.path.exists(config_file):
            config_file = '/opt/etc/archive.config'
        if os.path.isfile(config_file):
            try:
                fh = open(config_file, 'r')
                lines = fh.readlines()
                for line in lines:
                    if line[0] == '#':
                        continue
                    line = line.split('#',1)[0]
                    parts = tuple(map(lambda p: p.strip(), line.split('=',1)))
                    if len(parts) != 2:
                        continue
                    k,v = parts
                    configuration[k] = v
                if configuration.has_key('status-port'):
                    port = int(configuration['status-port'])
            except:
                pass
        if options.port:
            try:
                port = int(options.port)
            except:
                pass
        if options.host:
            try:
                host = socket.gethostbyname(options.host)
            except:
                pass

        if 0 > port > 65535:
            port = default_port
        if not host:
            host = default_host

        app = ArchiveIcon()
        gtk.main()
    except KeyboardInterrupt:
        pass
#/*}}}*/

if __name__ == "__main__":
    main()

