#!/usr/bin/env python
import asl

import base64
import calendar
import gc
import hashlib
import inspect
import multiprocessing as mp
import os
import Queue
import re
import socket
import string
import subprocess
import sys
import threading
import time
import urllib

import pygtk
pygtk.require('2.0')
import gobject
import gtk

from jtk.Logger import Logger
from jtk.gtk.Calendar import Calendar
from jtk.StatefulClass import StatefulClass
from jtk.file.utils import dir_from_file_path
from jtk.gtk.utils import select_file
from jtk.gtk.utils import select_save_file
from jtk.gtk.Dialog import Dialog
from jtk.gtk.GtkClass import GtkClass

#gtk.gdk.threads_init()
gobject.threads_init()

# === Monitor Class (User Interface) /*{{{*/
class Monitor(StatefulClass):
    def __init__(self):
        StatefulClass.__init__(self, os.path.abspath(asl.home_directory + '/.liss_monitor.db'))

        self.load_state()

        if not self.recall_value('host'):
            self.store_value('host', '136.177.120.21')
        if not self.recall_value('port'):
            self.store_value('port', '80')
        if not self.recall_value('path'):
            self.store_value('path', 'uptime/upgrade/telmon.txt')
        if not self.recall_value('file'):
            self.store_value('file', 'telmon.txt')
        if not self.recall_value('use-file'):
            self.store_value('use-file', 'FALSE')

        self.path = LISSPath()

        self.status_icon = gtk.StatusIcon()
        self.status_icon.set_from_pixbuf(asl.new_icon('circle_blue'))
        self.status_icon.set_visible(True)
        self.status_icon.connect( "popup-menu", self.callback_menu, None )
        self.status_icon.connect( "activate", self.callback_activate, None )

        self.menu = gtk.Menu()
        self.menu.set_title("LISS Monitor")
        self.menu.connect("selection-done", self.callback_selection_done, None)

        menu_list = [
            ('check',         'Check Now',        'add',          self.callback_check,           True),
            ('cancel',        'Cancel Check',     'cancel',       self.callback_cancel,          True),
            ('view',          'Open Viewer',      'notepad',      self.callback_view,            True),
            ('clear',         'Clear Warning',    'accept',       self.callback_clear_warn,      True),
            ('history',       'History Viewer',   'events',       self.callback_history,         False),
            ('server',        'Set Server',       'network',      self.callback_server,          True),
            ('open_database', 'Open Database',    'database',     self.callback_open_database,   True),
            ('new_database',  'New Database',     'database_add', self.callback_new_database,    True),
            ('save',          'Save State',       'save',         self.callback_save,            True),
            ('load',          'Restore State',    'load',         self.callback_load,            True),
            ('garbage',       'Print Garbage',    'trashcan_full',self.callback_print_garbage,   True),
            ('quit',          'Quit',             'exit',         self.callback_quit,            True),
        ]
        self.menu_items = {}

        for id,title,icon,callback,show in menu_list:
            item_dict = {}
            item_dict['widget'] = gtk.ImageMenuItem(title, id.capitalize())
            item_dict['image'] = gtk.Image()
            item_dict['image'].set_from_pixbuf(asl.new_icon(icon).scale_simple(16,16,gtk.gdk.INTERP_HYPER))
            item_dict['widget'].set_image(item_dict['image'])
            item_dict['callback'] = callback
            item_dict['widget'].connect("activate", self.callback_menu_selection, None, id)
            item_dict['show'] = show
            self.menu_items[id] = item_dict
            item_dict = None
            self.menu.append(self.menu_items[id]['widget'])

        self.image_default = gtk.Image()
        self.image_default.set_from_pixbuf(asl.new_icon('circle_blue').scale_simple(16, 16, gtk.gdk.INTERP_HYPER))

        self.menu.show()
        for key in self.menu_items.keys():
            if self.menu_items[key]['show']:
                self.menu_items[key]['widget'].show()

        self.viewer = Viewer(self)

      # Hidden Buttons (Used for Threaded GUI update)
        self.hbutton_status_update = gtk.Button()
        self.hbutton_status_update.connect('clicked', self.callback_status_update, None)
        self.hbutton_status_icon_active = gtk.Button()
        self.hbutton_status_icon_active.connect('clicked', self.callback_active, None)
        self.hbutton_status_icon_inactive = gtk.Button()
        self.hbutton_status_icon_inactive.connect('clicked', self.callback_inactive, None)
        self.hbutton_status_icon_warn = gtk.Button()
        self.hbutton_status_icon_warn.connect('clicked', self.callback_warn, None)
        self.hbutton_status_icon_clear_warn = gtk.Button()
        self.hbutton_status_icon_clear_warn.connect('clicked', self.callback_clear_warn, None)
        self.hbutton_status_icon_archive = gtk.Button()
        self.hbutton_status_icon_archive.connect('clicked', self.callback_archive, None)
        self.hbutton_status_icon_clear_archive = gtk.Button()
        self.hbutton_status_icon_clear_archive.connect('clicked', self.callback_clear_archive, None)

      # Station Processing
        self.menu_visible   = False
        self.startup_grace  = 1
        self.warn_threshold = 0.25 # hours
        self.stations       = []
        self.lock_status    = threading.Lock()
        self.checking       = False
        self.warning        = False
        self.archiving      = False
        self.data_time      = ''
        self.data           = None
        self.core           = Core(self)
        self.core.start()

# ===== Callback Methods =============================================
    def callback_print_garbage(self, widget, event, data=None):
        type_counts = {}
        #name_counts = {}
        for item in gc.get_objects():
            t = type(item) 
            #if hasattr(item, '__class__'):
            #    if hasattr(item.__class__, '__name__'):
            #        name = item.__class__.__name__
            #    else:
            #        name = 'unknown-class'
            #else:
            #    name = 'non-class-object'

            #try:    name_counts[name] += 1
            #except: name_counts[name]  = 1

            try:    type_counts[t] += 1
            except: type_counts[t]  = 1
            
        print "===================================================="
        print "===== OBJECTS ======================================"
        print "===================================================="
        print "Found", len(gc.get_objects()), "objects"
        print
        print "=== Types ================"
        #for t,c in sorted(type_counts.items(), lambda a,b: cmp(a[1],b[1])):
        #    print "% 6d : %s" % (c,t)
        #d = Dialog()
        #t = type(d)
        #d._disconnect_all
        #d.destroy()
        #del d
        #d = None
        #print "% 6d : %s" % (type_counts[t],t)
        print
        print "===================================================="
        print "===== GARBAGE ======================================"
        print "===================================================="
        print gc.garbage

    def callback_selection_done(self, menushell, data=None):
        self.menu_visible = False
    
    def callback_menu_selection(self, widget, event, data=None):
        self.menu_visible = False
        #print "menu selection data:", data
        if self.menu_items.has_key(data):
            self.menu_items[data]['callback'](widget, event, data)

    def callback_check(self, widget, event, data=None):
        #print "check now"
        self.core.check_now()

    def callback_cancel(self, widget, event, data=None):
        #print "cancel check"
        self.core.cancel_check()

    def callback_view(self, widget, event, data=None):
        #if self.viewer.is_dead():
        #    del self.viewer
        #    self.new_viewer()
        self.viewer.show()
        self.callback_clear_warn(None, None, None)

    def callback_quit(self, widget, event, data=None):
        #print "exit program"
        self.core.stop()
        self.close_application(widget, event, data)

    def callback_server(self, widget, event, data=None):
        dialog = Dialog(title="LISS Monitor Server")
        dialog.set_icon(asl.new_icon('network'))
        dialog.add_button_left("OK", self.callback_server_ok, focus=True)
        dialog.add_button_right("Cancel")

        dialog.hbox_uri = gtk.HBox()
        dialog.radio_uri   = gtk.RadioButton(group=None, label='http://')
        dialog.entry_host  = gtk.Entry()
        dialog.label_colon = gtk.Label(':')
        dialog.entry_port  = gtk.Entry()
        dialog.label_slash = gtk.Label('/')
        dialog.entry_path  = gtk.Entry()

        dialog.hbox_file = gtk.HBox()
        dialog.radio_file = gtk.RadioButton(group=dialog.radio_uri, label='File:')
        dialog.entry_file = gtk.Entry()
        dialog.button_file = gtk.Button(label='...')

        dialog.entry_host.set_width_chars(20)
        dialog.entry_port.set_width_chars(5)
        dialog.entry_path.set_width_chars(30)
        dialog.entry_file.set_width_chars(60)

        host = self.recall_value('host')
        port = self.recall_value('port')
        path = self.recall_value('path')
        file = self.recall_value('file')
        dialog.entry_host.set_text(host)
        dialog.entry_port.set_text(str(port))
        dialog.entry_path.set_text(path)
        dialog.entry_file.set_text(file)

        dialog.hbox_uri.pack_start(dialog.radio_uri,   False, False, 5)
        dialog.hbox_uri.pack_start(dialog.entry_host,  False, False, 5)
        dialog.hbox_uri.pack_start(dialog.label_colon, False, False, 5)
        dialog.hbox_uri.pack_start(dialog.entry_port,  False, False, 5)
        dialog.hbox_uri.pack_start(dialog.label_slash, False, False, 5)
        dialog.hbox_uri.pack_start(dialog.entry_path,  False, False, 5)

        dialog.hbox_file.pack_start(dialog.radio_file,  False, False, 5)
        dialog.hbox_file.pack_start(dialog.entry_file,  False, False, 5)
        dialog.hbox_file.pack_start(dialog.button_file, False, False, 5)

        dialog.vbox.pack_end(dialog.hbox_file)
        dialog.vbox.pack_end(dialog.hbox_uri)

        dialog._connect(dialog.radio_uri,   'toggled', self.callback_server_radio_toggle, None, 'FALSE')
        dialog._connect(dialog.radio_file,  'toggled', self.callback_server_radio_toggle, None, 'TRUE')
        dialog._connect(dialog.button_file, 'clicked', self.callback_server_select_file,  None)
        dialog.radio_uri._master = dialog
        dialog.radio_file._master = dialog
        dialog.button_file._master = dialog

        if self.recall_value('use-file').lower() == 'true':
            dialog.radio_file.set_active(True)
        else:
            dialog.radio_uri.set_active(True)

        dialog.hbox_uri.show_all()
        dialog.hbox_file.show_all()

        response = dialog.run()
        return

    def callback_server_select_file(self, widget, event, data=None):
        dialog = widget._master
        current_dir = dir_from_file_path(dialog.entry_file.get_text())
        if os.path.isdir(current_dir):
            dialog.entry_file.set_text(select_file(current_dir))
        else:
            dialog.entry_file.set_text(select_file())

    def callback_server_radio_toggle(self, widget, event, data):
        dialog = widget._master
        if data.lower() == 'true':
            dialog.entry_host.set_sensitive(False)
            dialog.entry_port.set_sensitive(False)
            dialog.entry_path.set_sensitive(False)
            dialog.entry_file.set_sensitive(True)
        else:
            dialog.entry_host.set_sensitive(True)
            dialog.entry_port.set_sensitive(True)
            dialog.entry_path.set_sensitive(True)
            dialog.entry_file.set_sensitive(False)

    def callback_server_ok(self, widget, event, data):
        host = widget.entry_host.get_text()
        port = widget.entry_port.get_text()
        path = widget.entry_path.get_text()
        file = widget.entry_file.get_text()
        use_file = widget.radio_file.get_active()
        del widget

        if use_file:
            if (file == ''):
                dialog = Dialog(title='Select File: Invalid File', message='Invalid File')
                dialog.set_icon(asl.new_icon('network'))
                dialog.add_button_right('OK', focus=True)
                dialog.run()
                return
            if not os.path.isfile(file):
                dialog = Dialog(title='Select File: No Such File', message='File \'%s\' does not exist' % file)
                dialog.set_icon(asl.new_icon('network'))
                dialog.add_button_right('OK', focus=True)
                dialog.run()
                return
            self.store_value('file', file)
            self.store_value('use-file', 'TRUE')

        else:
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

            self.store_value('host', host)
            self.store_value('port', str(port))
            self.store_value('path', path.lstrip('/'))
            self.store_value('use-file', 'False')

    def callback_new_database(self, widget, event, data=None):
        database_file = select_save_file()
        if database_file == '':
            return
        if os.path.exists(database_file):
            dialog = Dialog(title="Select Database: File Exists")
            dialog.set_icon(asl.new_icon('database'))
            dialog.add_button_right("No", focus=True)
            dialog.add_button_right("Yes", self.callback_open_database, database_file)
            dialog.set_message("The file you selected already exists, do you wish to replace it?")
            dialog.run()
            return
        else:
            self.attach_to_database(database_file)

    def callback_open_database(self, widget, event, data=None):
        if data == 'open_database':
            database_file = select_file()
            if database_file == '':
                return
            truncate = False
        else:
            database_file = data
            trunacte = True
        self.attach_to_database(database_file, truncate)

    def attach_to_database(self, database_file, truncate=False):
        old_database = self.keep.get_database_file_name()
        if not os.path.exists(database_file):
            message = "Could not create new database."
        else:
            message = "Could not attach to database."
        try:
            self.keep.select_database(database_file)
            self.keep.init()
            if truncate:
                self.save_state()
            else:
                self.load_state()
                self.viewer.apply_state()
        except:
            dialog = Dialog(title="Select Database: Failed")
            dialog.set_icon(asl.new_icon('database'))
            dialog.add_button_right("OK", focus=True)
            dialog.set_message(message)
            dialog.run()
            self.keep.select_database(old_database)
            self.keep.init()
            self.load_state()
            self.viewer.apply_state()
            return
        dialog = Dialog(title="Select Database: Success")
        dialog.set_icon(asl.new_icon('database'))
        dialog.add_button_right("OK", focus=True)
        dialog.set_message("Successfully attached to database.")
        dialog.run()

    def callback_save(self, widget, event, data=None):
        self.save_state()

    def callback_load(self, widget, event, data=None):
        self.load_state()
        self.viewer.apply_state()

    def callback_menu(self, widget, button, activate_time, data=None):
        #print "toggle menu"
        if self.menu_visible:
            self.menu.popdown()
            self.menu_visible = False
        else:
            self.menu.popup( None, None, None, button, activate_time, data )
            self.menu_visible = True

    def callback_active(self, widget, event, data=None):
        #print "status icon active"
        with self.lock_status:
            self.checking = True
            self.update_status_icon()

    def callback_inactive(self, widget, event, data=None):
        #print "status icon inactive"
        with self.lock_status:
            self.checking = False
            self.update_status_icon()

    def callback_warn(self, widget, event, data=None):
        #print "status icon warning"
        with self.lock_status:
            self.warning = True
            self.update_status_icon()

    def callback_clear_warn(self, widget, event, data=None):
        #print "status icon no-warning"
        with self.lock_status:
            self.warning = False
            self.update_status_icon()

    def callback_archive(self, widget, event, data=None):
        #print "status icon archiving"
        with self.lock_status:
            self.archiving = True
            self.update_status_icon()

    def callback_clear_archive(self, widget, event, data=None):
        #print "status icon not archiving"
        with self.lock_status:
            self.archiving = False
            self.update_status_icon()

    def callback_activate(self, wiget, event, data=None):
        #print "status icon activated"
        self.menu.popdown()
        self.menu_visible = False
        if self.viewer.is_dead():
            del self.viewer
            self.new_viewer()
        self.viewer.toggle()

    def callback_history(self, widget, event, data=None):
        #print "launching history viewer"
        os.spawnvp( os.P_NOWAIT, self.path.get('file_pythonw'), 
                    [self.path.get('file_pythonw'), 'history.pyw'])

    def callback_status_update(self, widget, event, data=None):
        #print "LISS status has been updated"
        self.update_stations()

    def new_viewer(self):
        self.viewer = Viewer(self)
        self.viewer.set_data(self.data)
        self.viewer.set_time(self.data_time)

    def close_application(self, widget, event, data=None):
        self.save_state()
        gtk.main_quit()
        return False

    def update_status_icon(self):
        if self.checking:
            self.status_icon.set_from_pixbuf(asl.new_icon('circle_green'))
            self.status_icon.set_blinking(True)
        elif self.archiving:
            self.status_icon.set_from_pixbuf(asl.new_icon('circle_orange'))
            self.status_icon.set_blinking(True)
        elif self.warning:
            self.status_icon.set_from_pixbuf(asl.new_icon('circle_red'))
            self.status_icon.set_blinking(True)
        else:
            self.status_icon.set_from_pixbuf(asl.new_icon('circle_blue'))
            self.status_icon.set_blinking(False)

    def update_stations(self):
        if self.data:
            alert_stations    = []
            restored_stations = []
            new_list          = []

            for item in self.data:
                name  = "%s_%s" % (item[0], item[1])
                downtime = item[4]
                if (downtime >= self.warn_threshold) or (downtime <= 24.0):
                    new_list.append(name)

            if len(self.stations):
                alert_stations    = filter( lambda x: x not in self.stations, new_list )
                restored_stations = filter( lambda x: x not in new_list, self.stations )
            else:
                alert_stations = new_list

            if len(alert_stations) or len(restored_stations): 
                str_sep = ", "
                self.warn(alert_stations,restored_stations)

            self.stations = new_list
        self.refresh_viewer()

    def refresh_viewer(self):
        if self.viewer.is_dead():
            del self.viewer
            self.new_viewer()
        if self.data:
            self.viewer.set_data_buffer(self.data)
        if self.data_time:
            self.viewer.set_time_buffer(self.data_time)
        self.viewer.auto_refresh()

    def warn(self, alert_stations, restored_stations):
        self.callback_warn(None, None, None)
        return #TODO: figure out how to add a popup notification
        if self.warn_window:
            self.warn_window.destroy()
        self._create_warn_window( show_down=len(alert_stations), 
                                  show_up=len(restored_stations) )
        str_sep = ", "
        if len(alert_stations):
            self.warn_label_list_down.configure(text=str_sep.join(sorted(alert_stations)))
        if len(restored_stations):
            self.warn_label_list_up.configure(text=str_sep.join(sorted(restored_stations)))
        self.warn_window.deiconify()
        self.status_icon.set_from_pixbuf(asl.new_icon('circle_red'))

    def current_time(self):
        return time.mktime(time.gmtime())

    def use_file(self):
        return self.recall_value('use-file').lower() == 'true'

    def get_file(self):
        return self.recall_value('file')

    def get_uri(self):
        return "http://%(host)s:%(port)s/%(path)s" % self.keep_dict
#/*}}}*/

# === Core Class /*{{{*/
class Core(threading.Thread):
    def __init__(self, gui):
        threading.Thread.__init__(self)
        self.gui             = gui
        self.queue           = mp.Queue()
        self.running         = False
        self.check_process   = None
        self.check_queue     = None
        self.lock_check      = threading.Lock()
        self.last_check      = 0
        self.check_interval  = 300 #Every 5 minutes
        self.archive_process = None
        self.archive_queue   = None
        self.lock_archive    = threading.Lock()

    def check_now(self):
        self.queue.put('CHECK_NOW')

    def cancel_check(self):
        self.queue.put('CANCEL_CHECK')

    def stop(self):
        self.cancel_check()
        self.queue.put('STOP')

    def run(self):
        self.running = True
        while self.running:
            now = calendar.timegm(time.gmtime())
            if (now - self.last_check) >= self.check_interval:
                self._start_check()
            try:
                message = self.queue.get(True, self.check_interval - (now - self.last_check))
            except Queue.Empty:
                pass

            request   = ''
            data      = None
            if type(message) == str:
                request = message
                data = None
            elif type(message) in (tuple, list):
                request = message[0]
                if len(message) > 2:
                    data = message[1:]
                elif len(message) > 1:
                    data = message[1]

            if request == 'STOP':
                self.running = False
            elif request == 'CHECK_FAILED':
                self.check_queue.put('THANKS')
                self.check_process.join()
                self._check_done()
                self._start_archive()
            elif request == 'CHECK_DONE':
                self.gui.data_time = data[0] + ' UTC'
                self.gui.data      = data[1]
                self.check_queue.put('THANKS')
                self.check_process.join()
                self._check_done()
                self._start_archive()
            elif request == 'ARCHIVE_DONE':
                self.archive_queue.put('THANKS')
                self.archive_process.join()
                self._archive_done()
            elif request == 'CHECK_NOW':
                self._start_check()
            elif request == 'CANCEL_CHECK':
                self._kill_check()

    def _start_check(self):
        if self.lock_check.acquire(0):
            gobject.idle_add(gobject.GObject.emit, self.gui.hbutton_status_icon_active, 'clicked')
            if self.check_queue:
                del self.check_queue
            self.check_queue = mp.Queue()
            use_file = self.gui.use_file()
            if use_file:
                uri = self.gui.get_file()
            else:
                uri = self.gui.get_uri()
            args = [self.check_queue, self.queue, uri, use_file]
            self.check_process = mp.Process(target=check, args=args)
            self.check_process.start()
            self.last_check = calendar.timegm(time.gmtime())

    def _check_done(self):
        if not self.lock_check.acquire(0):
            self.lock_check.release()
        gobject.idle_add(gobject.GObject.emit, self.gui.hbutton_status_icon_inactive, 'clicked')
        gobject.idle_add(gobject.GObject.emit, self.gui.hbutton_status_update, 'clicked')

    def _start_archive(self):
        if self.lock_archive.acquire(0):
            gobject.idle_add(gobject.GObject.emit, self.gui.hbutton_status_icon_archive, 'clicked')
            if self.archive_queue:
                del self.archive_queue
            self.archive_queue = mp.Queue()
            args = [self.archive_queue, self.queue, self.gui.data, self.gui.data_time, self.gui.path.get('path_data')]
            self.archive_process = mp.Process(target=archive, args=args)
            self.archive_process.start()

    def _archive_done(self):
        if not self.lock_archive.acquire(0):
            self.lock_archive.release()
        gobject.idle_add(gobject.GObject.emit, self.gui.hbutton_status_icon_clear_archive, 'clicked')

    def _kill_check(self):
        if self.check_process and self.check_process.is_alive():
            self.check_process.terminate()
            self.check_process.join()
            self._check_done()
#/*}}}*/

# === Check Function /*{{{*/
def check(check_queue, master_queue, uri, is_file=False):
    lines = []
    try:
        if is_file:
            reader = open(uri, 'r')
        else:
            reader = urllib.urlopen(uri)
        lines = reader.readlines()
        reader.close()
    except:
        if not lines: lines = []
    results = []

    # find the problem stations
    for line in lines:
        if line[0] == '#':
            continue
        try:
            s,n,l,c,t,d,y = tuple(map(lambda s:s.strip(), line.split(',')))
        except:
            try:
                s,n,l,c,t,y,d = tuple(map(lambda s:s.strip(), line.split(',', 6)) + [0])
            except:
                continue
        finally:
            try:
                results.append((n,s,l,c,t,d,y))
            except:
                pass

    if len(results):
        results = sorted(results, st_cmp)
        timestamp = results[-1][4]
        downtime = results[-1][6]
        if downtime > 0:
            try:
                timestamp = time.strftime('%Y %j %H:%M:%S', time.gmtime(float(calendar.timegm(time.strptime(timestamp, '%Y %j %H:%M:%S')) + (int(downtime) * 60))))
            except:
                pass

        master_queue.put(('CHECK_DONE', (timestamp, sorted(results, st_cmp))))
    else:
        master_queue.put('CHECK_FAILED')
    check_queue.get()
#/*}}}*/

# === Archive Function /*{{{*/
def archive(archive_queue, master_queue, data, timestamp, directory):
    master_queue.put('ARCHIVE_DONE')
    #archive_queue.get()
#/*}}}*/

# === Viewer Class  /*{{{*/
class Viewer(GtkClass):
    def __init__(self, master=None):
        GtkClass.__init__(self)

        self.list_store_data = None
        self.data_buffer = None
        self.time_buffer = None
        self.master = master

        self.regex_network  = None
        self.regex_station  = None
        self.regex_location = None
        self.regex_channel  = None

      # Widget Data 
        self.treestore = gtk.TreeStore( gobject.TYPE_STRING , # Station Name
                                        gobject.TYPE_STRING , # Channel Name
                                        gobject.TYPE_STRING , # Data Timestamp
                                        gobject.TYPE_STRING , # Latency
                                        gobject.TYPE_STRING , # Downtime
                                        gobject.TYPE_BOOLEAN) # Checkbutton
        self.treestore = self.treestore.filter_new()

        # Components
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("LISS Status Monitor - Viewer")

        self.window.set_icon(asl.new_icon('notepad'))

        self.vbox_main    = gtk.VBox()
        self.hbox_time    = gtk.HBox()
        self.hbox_tree    = gtk.HBox()
        self.hbox_filters = gtk.HBox()
        self.hbox_buttons = gtk.HBox()

        self.treeview              = gtk.TreeView()
        self.scrollwindow          = gtk.ScrolledWindow()
        self.label_time            = gtk.Label()
        self.checkbutton_refresh   = gtk.CheckButton('Auto Refresh')
        self.treeviewcol_station   = gtk.TreeViewColumn( "Station" )
        self.treeviewcol_channel   = gtk.TreeViewColumn( "Channel" )
        self.treeviewcol_timestamp = gtk.TreeViewColumn( "Outage Timestamp" )
        self.treeviewcol_latency   = gtk.TreeViewColumn( "Latency (Hours)" )
        self.treeviewcol_downtime  = gtk.TreeViewColumn( "Downtime (Hours)" )
        self.treeviewcol_viewed    = gtk.TreeViewColumn( "Viewed" )

        self.button_refresh = gtk.Button(stock=None, use_underline=True)
        self.hbox_refresh   = gtk.HBox()
        self.image_refresh  = gtk.Image()
        self.image_refresh.set_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_MENU)
        self.label_refresh  = gtk.Label('Refresh')
        self.button_refresh.add(self.hbox_refresh)
        self.hbox_refresh.pack_start(self.image_refresh, padding=1)
        self.hbox_refresh.pack_start(self.label_refresh, padding=1)

        self.button_close = gtk.Button(stock=None, use_underline=True)
        self.hbox_close   = gtk.HBox()
        self.image_close  = gtk.Image()
        self.image_close.set_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_MENU)
        self.label_close  = gtk.Label('Close')
        self.button_close.add(self.hbox_close)
        self.hbox_close.pack_start(self.image_close, padding=1)
        self.hbox_close.pack_start(self.label_close, padding=1)

        self.entry_filter_network  = gtk.Entry()
        self.entry_filter_station  = gtk.Entry()
        self.entry_filter_location = gtk.Entry()
        self.entry_filter_channel  = gtk.Entry()
        self.checkbutton_scale_unchecked = gtk.CheckButton()
        self.checkbutton_scale_checked = gtk.CheckButton()
        self.hscale_checked = gtk.HScale()
        self.button_erase = gtk.Button(stock=None, use_underline=True)
        self.hbox_erase   = gtk.HBox()
        self.image_erase  = gtk.Image()
        self.image_erase.set_from_pixbuf(asl.new_icon('erase').scale_simple(16, 16, gtk.gdk.INTERP_HYPER))
        #self.label_erase  = gtk.Label('Erase')
        self.button_erase.add(self.hbox_erase)
        self.hbox_erase.pack_start(self.image_erase, padding=1)
        #self.hbox_erase.pack_start(self.label_erase, padding=1)
        self.treestore.set_visible_func(self.filter)

        self.crtext_station   = gtk.CellRendererText()
        self.crtext_channel   = gtk.CellRendererText()
        self.crtext_timestamp = gtk.CellRendererText()
        self.crtext_latency   = gtk.CellRendererText()
        self.crtext_downtime  = gtk.CellRendererText()
        self.crtoggle_viewed  = gtk.CellRendererToggle()
        self.crtoggle_viewed.set_property('activatable', True)
        self._connect(self.crtoggle_viewed, 'toggled', self.callback_toggled, None)

# ===== Layout Configuration ==============================================
        self.window.add(self.vbox_main)
        self.window.set_size_request(300,400)
        self.vbox_main.pack_start(self.hbox_time,    expand=False, fill=True,  padding=1)
        self.vbox_main.pack_start(self.hbox_tree,    expand=True,  fill=True,  padding=2)
        self.vbox_main.pack_start(self.hbox_filters, expand=False, fill=True,  padding=1)
        self.vbox_main.pack_start(self.hbox_buttons, expand=False, fill=True,  padding=1)

        self.hbox_time.pack_start(self.checkbutton_refresh, expand=False,  fill=False,  padding=2)
        self.hbox_time.pack_end(self.label_time, expand=False,  fill=True,  padding=2)
        self.hbox_tree.pack_start(self.scrollwindow, expand=True, fill=True, padding=2)
        self.hbox_filters.pack_start(self.entry_filter_network,  expand=True,  fill=True,  padding=1)
        self.hbox_filters.pack_start(self.entry_filter_station,  expand=True,  fill=True,  padding=1)
        self.hbox_filters.pack_start(self.entry_filter_location, expand=True,  fill=True,  padding=1)
        self.hbox_filters.pack_start(self.entry_filter_channel,  expand=True,  fill=True,  padding=1)
        self.hbox_filters.pack_end(self.button_erase,            expand=False, fill=True, padding=1)
        self.hbox_buttons.pack_start(self.button_refresh, expand=False, fill=True, padding=1)
        self.hbox_buttons.pack_start(self.checkbutton_scale_unchecked, expand=False,  fill=False,  padding=1)
        self.hbox_buttons.pack_start(self.hscale_checked, expand=True,  fill=True,  padding=1)
        self.hbox_buttons.pack_start(self.checkbutton_scale_checked, expand=False,  fill=False,  padding=1)
        self.hbox_buttons.pack_end(self.button_close, expand=False, fill=False, padding=1)

        self.scrollwindow.add(self.treeview)
        self.treeview.append_column(self.treeviewcol_station)
        self.treeview.append_column(self.treeviewcol_channel)
        self.treeview.append_column(self.treeviewcol_timestamp)
        self.treeview.append_column(self.treeviewcol_latency)
        self.treeview.append_column(self.treeviewcol_downtime)
        self.treeview.append_column(self.treeviewcol_viewed)

# ===== Attribute Configuration ===========================================
        self.scrollwindow.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )
        self.treeview.set_model( self.treestore )
        self.treeviewcol_station.pack_start(self.crtext_station, True)
        self.treeviewcol_station.add_attribute(self.crtext_station, 'text', 0)
        self.treeviewcol_station.set_cell_data_func(self.crtext_station, self.cdf_format_station, None)
        self.treeviewcol_channel.pack_start(self.crtext_channel, True)
        self.treeviewcol_channel.add_attribute(self.crtext_channel, 'text', 1)
        self.treeviewcol_channel.set_cell_data_func(self.crtext_channel, self.cdf_format_channel, None)
        self.treeviewcol_timestamp.pack_start(self.crtext_timestamp, True)
        self.treeviewcol_timestamp.add_attribute(self.crtext_timestamp, 'text', 2)
        self.treeviewcol_timestamp.set_cell_data_func(self.crtext_timestamp, self.cdf_format_timestamp, None)
        self.treeviewcol_latency.pack_start(self.crtext_latency, True)
        self.treeviewcol_latency.add_attribute(self.crtext_latency, 'text', 3)
        self.treeviewcol_latency.set_cell_data_func(self.crtext_latency, self.cdf_format_latency, None)
        self.treeviewcol_downtime.pack_start(self.crtext_downtime, True)
        self.treeviewcol_downtime.add_attribute(self.crtext_downtime, 'text', 4)
        self.treeviewcol_downtime.set_cell_data_func(self.crtext_downtime, self.cdf_format_downtime, None)
        self.treeviewcol_viewed.pack_start(self.crtoggle_viewed, True)
        self.treeviewcol_viewed.set_cell_data_func(self.crtoggle_viewed, self.cdf_format_viewed, None)

        model = self.treeview.get_selection()
        model.set_mode(gtk.SELECTION_NONE)

        self.entry_filter_network._filter_title  = 'Network'
        self.entry_filter_station._filter_title  = 'Station'
        self.entry_filter_location._filter_title = 'Location'
        self.entry_filter_channel._filter_title  = 'Channel'
        self.hscale_checked.set_range(0.0,2.0)
        self.hscale_checked.set_digits(0)
        self.hscale_checked.set_draw_value(False)
        self.hscale_checked.set_increments(1.0,1.0)
        if self.master.recall_temp_value('viewer-filter-checked'):
            self.hscale_checked.set_value(float(self.master.recall_temp_value('viewer-filter-checked')))
        else:
            self.hscale_checked.set_value(1.0)
        self.checkbutton_scale_unchecked.set_sensitive(False)
        self.checkbutton_scale_unchecked.set_active(False)
        self.checkbutton_scale_checked.set_sensitive(False)
        self.checkbutton_scale_checked.set_active(True)
    
        self.checkbutton_refresh.set_active(False)
        if self.master.recall_value('viewer-refresh-auto'):
            if self.master.recall_value('viewer-refresh-auto').upper() == 'TRUE':
                self.checkbutton_refresh.set_active(True)

        if self.master.recall_temp_value('viewer-filter-network'):
            self.entry_filter_network.set_text(self.master.recall_temp_value('viewer-filter-network'))
        if self.master.recall_temp_value('viewer-filter-station'):
            self.entry_filter_station.set_text(self.master.recall_temp_value('viewer-filter-station'))
        if self.master.recall_temp_value('viewer-filter-location'):
            self.entry_filter_location.set_text(self.master.recall_temp_value('viewer-filter-location'))
        if self.master.recall_temp_value('viewer-filter-channel'):
            self.entry_filter_channel.set_text(self.master.recall_temp_value('viewer-filter-channel'))

# ===== Event Bindings
        self._connect(self.window,  "destroy-event",      self.callback_destroy, None)
        self._connect(self.window,  "delete-event",       self.callback_destroy, None)
        self._connect(self.window,  "configure-event",    self.callback_window_configured, None)
        self._connect(self.window,  "screen-changed",     self.callback_window_configured, None)
        self._connect(self.window,  "window-state-event", self.callback_window_configured, None)

        self._connect(self.checkbutton_refresh, "toggled", self.callback_toggle_refresh_auto, None)

        self._connect(self.button_refresh, "clicked", self.callback_refresh, None)
        self._connect(self.button_close,   "clicked", self.callback_close, None)

        self._connect(self.entry_filter_network, "changed", self.callback_filter_changed, None, "network")
        self._connect(self.entry_filter_station, "changed", self.callback_filter_changed, None, "station")
        self._connect(self.entry_filter_location,"changed", self.callback_filter_changed, None, "location")
        self._connect(self.entry_filter_channel, "changed", self.callback_filter_changed, None, "channel")
        self._connect(self.entry_filter_network, "focus-in-event", self.callback_filter_focus_in, None)
        self._connect(self.entry_filter_station, "focus-in-event", self.callback_filter_focus_in, None)
        self._connect(self.entry_filter_location,"focus-in-event", self.callback_filter_focus_in, None)
        self._connect(self.entry_filter_channel, "focus-in-event", self.callback_filter_focus_in, None)
        self._connect(self.entry_filter_network, "focus-out-event", self.callback_filter_focus_out, None)
        self._connect(self.entry_filter_station, "focus-out-event", self.callback_filter_focus_out, None)
        self._connect(self.entry_filter_location,"focus-out-event", self.callback_filter_focus_out, None)
        self._connect(self.entry_filter_channel, "focus-out-event", self.callback_filter_focus_out, None)
        self._connect(self.hscale_checked,       "value-changed", self.callback_scale_show_checked, None)
        self._connect(self.button_erase,         "clicked", self.callback_erase_filters, None)

        self.filter_hint_show(self.entry_filter_network)
        self.filter_hint_show(self.entry_filter_station)
        self.filter_hint_show(self.entry_filter_location)
        self.filter_hint_show(self.entry_filter_channel)

        # Show widgets
        self.window.show_all()
        if self.master.recall_value('viewer-hidden'):
            if self.master.recall_value('viewer-hidden').upper() == 'TRUE':
                self.hide()
            else:
                self.show()
        else:
            self.hide()
        self.dead = False

# ===== Cell Data Methods ============================================
    def cdf_format_station(self, column, cell, model, iter, data=None):
        downtime = float(model.get_value(iter, 4))
        if downtime > 1.0:
            cell.set_property("foreground", "#bb0000")
        else:
            cell.set_property("foreground", "#00bb00")

    def cdf_format_channel(self, column, cell, model, iter, data=None):
        downtime = float(model.get_value(iter, 4))
        if downtime > 1.0:
            cell.set_property("foreground", "#bb0000")
        else:
            cell.set_property("foreground", "#00bb00")

    def cdf_format_latency(self, column, cell, model, iter, data=None):
        latency = float(model.get_value(iter, 3))
        if latency > (7.0 * 24.0):
            cell.set_property("background", "#cc0000")
        elif latency > 24.0:
            cell.set_property("background", "#ff6600")
        elif latency > 1.0:
            cell.set_property("background", "#ffcc00")
        else:
            cell.set_property("background", "#ffffff")

    def cdf_format_downtime(self, column, cell, model, iter, data=None):
        downtime = float(model.get_value(iter, 4))
        if downtime > (7.0 * 24.0):
            cell.set_property("background", "#cc0000")
        elif downtime > 24.0:
            cell.set_property("background", "#ff6600")
        elif downtime > 1.0:
            cell.set_property("background", "#ffcc00")
        else:
            cell.set_property("background", "#ffffff")

    def cdf_format_timestamp(self, column, cell, model, iter, data=None):
        latency = float(model.get_value(iter, 3))
        if latency > (7.0 * 24.0):
            cell.set_property("background", "#cc0000")
        elif latency > 24.0:
            cell.set_property("background", "#ff6600")
        elif latency > 1.0:
            cell.set_property("background", "#ffcc00")
        else:
            cell.set_property("background", "#ffffff")

    def cdf_format_viewed(self, column, cell, model, iter, data=None):
        cell.set_active(model.get_value(iter, 5))

# ===== Callback Methods =============================================
    def callback_close(self, widget, event, data=None):
        self.hide()

    def callback_destroy(self, widget, event, data=None):
        self.hide()
        return True
        #self.dead = True
        #self._disconnect_all()

    def callback_toggle_refresh_auto(self, widget, event, data=None):
        if self.checkbutton_refresh.get_active():
            self.master.store_value('viewer-refresh-auto', 'True')
        else:
            self.master.store_value('viewer-refresh-auto', 'False')

    def callback_refresh(self, widget, event, data=None):
        if self.data_buffer:
            self.set_data(self.data_buffer)
            self.data_buffer = None
        if self.time_buffer:
            self.set_time(self.time_buffer)
            self.time_buffer = None
        if self.master:
            self.master.callback_clear_warn(None, None, None) 

    def callback_scale_show_checked(self, widget, event, data=None):
        self.master.store_temp_value('viewer-filter-checked', str(self.hscale_checked.get_value()))
        self.treestore.refilter()
        filter_iter = self.treestore.get_iter_first()
        if filter_iter:
            iter = self.treestore.convert_iter_to_child_iter(filter_iter)
            if iter:
                path = self.treestore.get_model().get_path(iter)
                self.treeview.scroll_to_cell(path)

    def callback_toggled(self, renderer, path, params=None):
        filter_iter = self.treestore.iter_nth_child(None, int(path))
        iter = self.treestore.convert_iter_to_child_iter(filter_iter)
        model = self.treestore.get_model()
        value = model.get_value(iter, 5)
        ns = model.get_value(iter, 0)
        lc = model.get_value(iter, 1)
        n_s = ns.strip().split('_',1)
        if len(n_s) < 2:
            n = ''
            s = n_s[0]
        else:
            n,s = n_s
        l_c = lc.strip().split('-',1)
        if len(l_c) < 2:
            l = ''
            c = l_c[0]
        else:
            l,c = l_c
        key = '%s-%s-%s-%s' % (n,s,l,c)
        if value:
            model.set_value(iter, 5, False)
            self.master.store_value(key, 'False')
        else:
            model.set_value(iter, 5, True)
            self.master.store_value(key, 'True')

    def callback_filter_changed(self, widget, event, data=None):
        text = widget.get_text()
        if text == widget._filter_title:
            text = ''
        regex = None
        if text == '':
            regex = None
        else:
            try: regex = re.compile(text, re.IGNORECASE)
            except: regex = None
        if data == 'network':
            self.regex_network = regex
            self.master.store_temp_value('viewer-filter-network', text)
        elif data == 'station':
            self.regex_station = regex
            self.master.store_temp_value('viewer-filter-station', text)
        elif data == 'location':
            self.regex_location = regex
            self.master.store_temp_value('viewer-filter-location', text)
        elif data == 'channel':
            self.regex_channel = regex
            self.master.store_temp_value('viewer-filter-channel', text)
        self.treestore.refilter()
        filter_iter = self.treestore.get_iter_first()
        if filter_iter:
            iter = self.treestore.convert_iter_to_child_iter(filter_iter)
            if iter:
                path = self.treestore.get_model().get_path(iter)
                self.treeview.scroll_to_cell(path)

    def callback_window_configured(self, widget, event, data=None):
        #screen_id = self.window.get_screen().get_number() 
        #display_name = self.window.get_screen().get_display().get_name()

        gravity  = str(int(self.window.get_gravity()))
        position = '%d,%d' % self.window.get_position()
        size     = '%d,%d' % self.window.get_size()
        #screen   = '%s,%d' % (display_name,screen_id)

        #print "gravity: ", gravity
        #print "position:", position
        #print "screen:  ", screen
        #print "size:    ", size

        if not self.hidden:
            self.master.store_value('viewer-gravity', gravity)
            self.master.store_value('viewer-position', position)
            self.master.store_value('viewer-size', size)
            #self.master.store_value('viewer-screen', screen)

    def callback_filter_focus_out(self, widget, event, data=None):
        self.filter_hint_show(widget)

    def callback_filter_focus_in(self, widget, event, data=None):
        self.filter_hint_hide(widget)

    def callback_erase_filters(self, widget, event, data=None):
        self.entry_filter_network.set_text('')
        self.entry_filter_station.set_text('')
        self.entry_filter_location.set_text('')
        self.entry_filter_channel.set_text('')
        self.filter_hint_show(self.entry_filter_network)
        self.filter_hint_show(self.entry_filter_station)
        self.filter_hint_show(self.entry_filter_location)
        self.filter_hint_show(self.entry_filter_channel)
        self.hscale_checked.set_value(1)


# ===== General Methods ==============================================
    def auto_refresh(self):
        if self.checkbutton_refresh.get_active():
            self.button_refresh.clicked()

    def filter_hint_show(self, widget):
        if not len(widget.get_text()):
            widget.set_text(widget._filter_title)
            widget.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('#888888'))

    def filter_hint_hide(self, widget):
        if widget.get_text() == widget._filter_title:
            widget.set_text('')
        widget.modify_text(gtk.STATE_NORMAL, gtk.gdk.Color())

    def show(self):
        self.window.show()
        if self.master.recall_value('viewer-gravity'):
            g = int(self.master.recall_value('viewer-gravity'))
            #print "gravity =", g
            self.window.set_gravity(g)
        if self.master.recall_value('viewer-position'):
            x,y = map(int,self.master.recall_value('viewer-position').split(',',1))
            #print "position =", x, y
            self.window.move(x,y)
        if self.master.recall_value('viewer-size'):
            w,h = map(int,self.master.recall_value('viewer-size').split(',',1))
            #print "size =", w, h
            self.window.resize(w,h)
        if self.master.recall_value('viewer-fullscreen'):
            fullscreen = self.master.recall_value('viewer-fullscreen')
            if fullscreen == 'TRUE':
                self.window.fullscreen()
            else:
                self.window.unfullscreen()
        #if self.master.recall_value('viewer-screen'):
            #d,s = self.master.recall_value('viewer-screen').split(',',1)
            #print "screen =", d, s
            #display = gtk.gdk.Display(d)
            #print "display:", display
            #screen = display.get_screen(int(s))
            #print "screen:", screen
            #print "dir", dir(screen)
            #self.window.set_screen(gtk.gdk.Screen(gtk.gdk.Display(d).get_screen(int(s))))
        self.master.store_value('viewer-hidden', 'False')
        self.hidden = False

    def apply_state(self):
        was_hidden = self.hidden
        self.show()
        if was_hidden:
            self.hide()
        self.set_data(self._data)

    def hide(self):
        self.master.store_value('viewer-hidden', 'True')
        self.hidden = True
        self.window.hide()

    def toggle(self):
        if self.hidden:
            self.show()
        else:
            self.hide()

    def get_visible(self):
        refs = []
        model = self.treestore.get_model()
        filter = self.treestore
        filter_iter = filter.get_iter_first()
        while filter_iter:
            iter = filter.convert_iter_to_child_iter(filter_iter)
            path = model.get_path(iter)
            refs.append(gtk.TreeRowReference(model, path))
            filter_iter = filter.iter_next(filter_iter)
        return refs

    def get_selected(self):
        selection = self.treeview.get_selection().get_selected_rows()
        refs = []
        model = self.treestore.get_model()
        filter = self.treestore
        for filter_path in selection[1]:
            path = filter.convert_path_to_child_path(filter_path)
            refs.append(gtk.TreeRowReference(model, path))
        return refs

    def filter(self, model, iter, user_data=None):
        #if self.checkbutton_checked.get_active():
        #    if not model.get_value(iter, 4):
        #        return False
        if self.hscale_checked.get_value() < 0.66:
            if model.get_value(iter, 5):
                return False
        if self.hscale_checked.get_value() > 1.33:
            if not model.get_value(iter, 5):
                return False
        if self.regex_network:
            parts = model.get_value(iter, 0).split('_', 1)
            if len(parts) == 1:
                value = ''
            else:
                value = parts[0]
            if not self.regex_network.search(value):
                return False
        if self.regex_station:
            value = model.get_value(iter, 0).split('_', 1)[-1]
            if not self.regex_station.search(value):
                return False
        if self.regex_location:
            parts = model.get_value(iter, 1).split('-', 1)
            if len(parts) == 1:
                value = ''
            else:
                value = parts[0]
            if not self.regex_location.search(value):
                return False
        if self.regex_channel:
            value = model.get_value(iter, 1).split('-', 1)[-1]
            if not self.regex_channel.search(value):
                return False
        return True

    def is_dead(self):
        return self.dead

    def set_data(self, data):
        if data:
            self._data = data
            self.treestore.get_model().clear()
            for (n,s,l,c,t,d,y) in data:
                name = "%s_%s" % (n,s)
                if not l:
                    channel = c
                else:
                    channel = "%s-%s" % (l,c)
                #downtime = "%s (%0.2f)" % (d, int(d)/60.0)
                downtime = "%0.2f" % (int(d)/60.0,)
                latency = "%0.2f" % (int(y)/60.0,)
                timestamp = t
                key = "%s-%s-%s-%s" % (n,s,l,c)
                checked = False
                if self.master.recall_value(key):
                    if self.master.recall_value(key).upper() == 'TRUE':
                        checked = True
                self.treestore.get_model().append(None, [name, channel, timestamp, latency, downtime, checked])

    def set_time(self, time):
        #print "setting time"
        if time:
            self.label_time.set_text(time)

    # This allows the parent program to set the latest data without 
    # messing up the data we are working with. This replaces the 
    # working data when the 'refresh' button is pressed.
    def set_data_buffer(self, data):
        if data:
            self.data_buffer = data

    def set_time_buffer(self, time):
        if time:
            self.time_buffer = time
#/*}}}*/

# === LISSDatabase Class /*{{{*/
class LISSDatabase(object):
    def __init__(self):
        self.db  = None
        self.cur = None
        self.foreign_iterator = None

    def _hash(self, text):
        sha_obj = hashlib.sha1()
        sha_obj.update( text )
        return base64.urlsafe_b64encode( sha_obj.digest() )

    def select_database(self, file):
        self.db = None
        self.db = sqlite.connect(file)
        self.cur = self.db.cursor()

    def add_status(self, foreign_iterator):
        self.foreign_iterator = foreign_iterator
        self.cur.executemany("INSERT OR IGNORE INTO Station(station_hash, network, name) VALUES (?,?,?)", self.iterator_station())
        self.cur.executemany("INSERT OR REPLACE INTO LinkStatus(check_time, liss_time, liss_delay, station_hash) VALUES (?,?,?,?)", self.iterator_status())
        self.db.commit()

    def iterator_station(self):
        for (network, name, check_time, liss_time, liss_delay) in self.foreign_iterator():
            hash = self._hash( network + "_" + name )
            yield (hash, network, name)

    def iterator_status(self):
        for (network, name, check_time, liss_time, liss_delay) in self.foreign_iterator():
            hash = self._hash( network + "_" + name )
            yield (check_time, liss_time, liss_delay, hash)

    def add_status_change(self, station_net, station_name, timestamp, status):
        station_hash = self._hash( station_net + "_" + station_name )
        self.cur.execute( "INSERT OR IGNORE INTO Station(station_hash, network, name) VALUES (?,?,?)", (station_hash, station_net, station_name) )
        self.cur.execute( "INSERT OR REPLACE INTO LinkStatusChange(timestamp, type, station_hash) VALUES (?,?,?)", (timestamp, status, station_hash) )
        self.db.commit()

    def get_station_networks(self, name=None):
        self.rules = ""
        if ( name ):
            self.rules += " WHERE name = '%(name)s'" % {'name': name}
        self.cur.execute( "SELECT DISTINCT network FROM Station %(rules)s ORDER BY network" % {'rules': self.rules} )
        return self.cur.fetchall()

    def get_station_names(self, network=None):
        self.rules = ""
        if ( network ):
            self.rules += " WHERE network = '%(network)s'" % {'network': network}
        self.cur.execute( "SELECT DISTINCT name FROM Station %(rules)s ORDER BY name" % {'rules': self.rules} )
        return self.cur.fetchall()

    def get_stations(self):
        self.cur.execute( "SELECT DISTINCT network, name FROM Station ORDER BY network, name" )
        return self.cur.fetchall()

    def get_status(self, station_net, station_name, 
                         start_time=None, end_time=None):
        validate = ["", None]
        if (station_net in validate) or (station_name in validate):
            return None
        station_hash = self._hash( station_net + "_" + station_name )
        rules = ""
        if ( start_time ):
            rules += " AND check_time <= '%(time)s'" % {'time': start_time}
        if ( end_time ):
            rules += " AND check_time >= '%(time)s'" % {'time': end_time}
        #print "%s_%s [%s]" % (station_net, station_name, station_hash)
        query_string = "SELECT check_time, liss_time, liss_delay FROM LinkStatus WHERE station_hash='%(hash)s' %(rules)s" % {'rules': rules, 'hash': station_hash} 
        self.cur.execute( query_string )
        return self.cur.fetchall()

    def get_all(self):
        self.cur.execute( "SELECT network, name, check_time, liss_time, liss_delay FROM LinkStatus INNER JOIN Station ON LinkStatus.station_hash=Station.station_hash" )
        return self.cur.fetchall()

    def get_query(self, query):
        self.cur.execute( query )
        return self.cur.fetchall()

    def get_status_changes(self, station_net, station_name):
        station_hash = self._hash( station_net + "_" + station_name )

    def init(self):
        result = self.cur.executescript("""
            CREATE TABLE IF NOT EXISTS Station (
                station_hash varchar(29),
                network TEXT,
                name TEXT,
                PRIMARY KEY (station_hash)
            );

            CREATE TABLE IF NOT EXISTS LinkStatus (
                link_status_id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_time INTEGER,
                liss_time INTEGER,
                liss_delay INTEGER,
                station_hash VARCHAR(29)
            );
            """)
#/*}}}*/

# === LISSPath Class /*{{{*/
class LISSPath(object):
    def __init__(self):
        self.path = { 'file_python' : "python",
                      'file_pythonw': "python" }
        if os.name in ('nt', 'win32', 'win64'):
            self.path['file_python']  = "python.exe"
            self.path['file_pythonw'] = "pythonw.exe"

      # Directories
        self.path['path_liss']     = os.path.abspath("%s/utils/liss_monitor" % asl.path)
        self.path['path_data']     = os.path.abspath("%(path_liss)s/sdata" % self.path)
        self.path['path_icon']     = os.path.abspath("%(path_liss)s/sicons" % self.path)
      # Config & Archive
        self.path['file_config']   = os.path.abspath("%(path_liss)s/slissmon.cfg" % self.path)
        self.path['file_history']  = os.path.abspath("%(path_data)s/shistory.db" % self.path)

    def get(self, key):
        if self.path.has_key(key):
            return self.path[key]
        return ""
#/*}}}*/

# === History Class  /*{{{*/
class History(object):
    def __init__(self):
        self.path = LISSPath()
        self.history_database = LISSDatabase()
        self.history_database.select_database( self.path.get('file_history') )
        self.history_database.init()

        self.date_format = "%Y/%m/%d %H:%M:%S"
        self.date_expr   = '\d{4}[/]\d{2}[/]\d{2}[ ]\d{2}[:]\d{2}[:]\d{2}'

        # Widget data
        self.data_networks = gtk.ListStore( str )
        self.data_stations = gtk.ListStore( str )
        self.data_outages  = gtk.ListStore( str , # LISS Date
                                            str , # Status (connected, disconnected)
                                            str ) # Duration (hours)
        #self.data_all      = gtk.ListStore( gobject.TYPE_STRING, # Check Date
        #                                    gobject.TYPE_STRING, # LISS Date
        #                                    gobject.TYPE_FLOAT ) # Delay (hours)

# ===== Widget Creation ===========================================
      # Layout Control Widgets
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("LISS Status Monitor - History")

        self.vbox_main = gtk.VBox()

        self.vbox_top = gtk.VBox()
        self.vbox_bottom = gtk.VBox()

        self.hbox_station = gtk.HBox()
        self.table_times = gtk.Table(rows=2, columns=3)
        self.hbox_tree = gtk.HBox()
        self.hbox_control = gtk.HBox()

      # User Interaction Widgets
        # Station selection
        self.combobox_network = gtk.ComboBox()
        self.combobox_station = gtk.ComboBox()

        # Time period selection
        self.label_start = gtk.Label( "Start Time:" )
        self.label_end = gtk.Label( "End Time:" )
        self.entry_start = gtk.Entry( max=20 )
        self.entry_end = gtk.Entry( max=20 )
        self.button_cal_start = gtk.Button( label="..." )
        self.button_cal_end = gtk.Button( label="..." )

        # Main control
        self.button_update = gtk.Button( label="Update" )
        self.button_quit = gtk.Button( label="Quit" )

        # Viewing Area
        self.scrollwindow = gtk.ScrolledWindow()
        self.treeview = gtk.TreeView()
        self.treeviewcol_time = gtk.TreeViewColumn( "Time" )
        self.treeviewcol_status = gtk.TreeViewColumn( "Status" )
        self.treeviewcol_duration = gtk.TreeViewColumn( "Duration (Hours)" )
        self.crtext_time = gtk.CellRendererText()
        self.crtext_status = gtk.CellRendererText()
        self.crtext_duration = gtk.CellRendererText()
        self.crtext_network = gtk.CellRendererText()
        self.crtext_station = gtk.CellRendererText()

# ===== Layout Configuration ==============================================
      # Primary Containers
        self.window.add( self.vbox_main )
        self.window.set_size_request(300,400)

        self.vbox_main.pack_start( self.vbox_top, expand=False, fill=False )
        self.vbox_main.pack_end( self.vbox_bottom, expand=True, fill=True )

        self.vbox_top.pack_start( self.hbox_station, expand=False, fill=False )
        self.vbox_top.pack_end( self.table_times, expand=False, fill=False )
        self.vbox_bottom.pack_start( self.scrollwindow, expand=True, fill=True, padding=2 )
        self.vbox_bottom.pack_end( self.hbox_control, expand=False, fill=False )

      # UI Widget Attachments
        self.hbox_station.pack_start( self.combobox_network, expand=False, fill=False, padding=1 )
        self.hbox_station.pack_start( self.combobox_station, expand=False, fill=True, padding=1 )

        self.table_times.attach( self.label_start, 0, 1, 0, 1, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )
        self.table_times.attach( self.entry_start, 1, 2, 0, 1, xpadding=1, ypadding=1 )
        self.table_times.attach( self.button_cal_start, 2, 3, 0, 1, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )
        self.table_times.attach( self.label_end, 0, 1, 1, 2, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )
        self.table_times.attach( self.entry_end, 1, 2, 1, 2, xpadding=1, ypadding=1 )
        self.table_times.attach( self.button_cal_end, 2, 3, 1, 2, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )

        #self.hbox_tree.pack_start( self.scrollwindow, expand=True, fill=False, padding=1 )
        self.scrollwindow.add( self.treeview )

        self.hbox_control.pack_start( self.button_update, expand=False, fill=True, padding=1 )
        self.hbox_control.pack_end( self.button_quit, expand=False, fill=False, padding=1 )

        self.treeview.append_column( self.treeviewcol_time )
        self.treeview.append_column( self.treeviewcol_status )
        self.treeview.append_column( self.treeviewcol_duration )

# ===== Widget Configurations ===================================================
        # Station selection
        self.combobox_network.set_model( self.data_networks )
        self.combobox_network.pack_start( self.crtext_network, True )
        self.combobox_network.add_attribute( self.crtext_network, 'text', 0 )
        self.combobox_station.set_model( self.data_stations )
        self.combobox_station.pack_end( self.crtext_station, True )
        self.combobox_station.add_attribute( self.crtext_station,'text', 0 )
        self.combobox_station.set_wrap_width(4)

        # Time selection
        self.label_start.set_justify( gtk.JUSTIFY_LEFT )
        self.label_end.set_justify( gtk.JUSTIFY_LEFT )
        
        # Treeview
        self.scrollwindow.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )
        self.treeview.set_model( self.data_outages )
        self.treeviewcol_time.pack_start(self.crtext_time, True)
        self.treeviewcol_time.add_attribute(self.crtext_time, 'text', 0)
        self.treeviewcol_status.pack_start(self.crtext_status, True)
        self.treeviewcol_status.add_attribute(self.crtext_status, 'text', 1)
        self.treeviewcol_status.set_cell_data_func(self.crtext_status, self.cdf_status_color, None)
        self.treeviewcol_duration.pack_start(self.crtext_duration, True)
        self.treeviewcol_duration.add_attribute(self.crtext_duration, 'text', 2)
        self.treeviewcol_duration.set_cell_data_func(self.crtext_duration, self.cdf_format_float, None)

# ===== Signal Bindings =========================================================
        self.calendar_start = Calendar()
        self.calendar_start.set_callback( self.callback_populate_time, (self.calendar_start, self.entry_start) )
        self.calendar_start.set_granularity('day')
        self.calendar_start.set_default_high( False )

        self.calendar_end = Calendar()
        self.calendar_end.set_callback( self.callback_populate_time, (self.calendar_end, self.entry_end) )
        self.calendar_end.set_granularity('day')
        self.calendar_end.set_default_high( True )

        self.button_cal_start.connect( "clicked", self.callback_show_calendar, (self.calendar_start, self.entry_start) )
        self.button_cal_end.connect( "clicked", self.callback_show_calendar, (self.calendar_end, self.entry_end) )
        self.button_update.connect( "clicked", self.callback_update, None )
        self.button_quit.connect( "clicked", self.callback_quit, None )
        self.combobox_network.connect( "changed", self.callback_populate_stations, None )

# ===== Event Bindings
        self.window.connect( "destroy-event", self.callback_quit, None )
        self.window.connect( "delete-event", self.callback_quit, None )

        # Show widgets
        self.window.show_all()
        self.populate_networks()

    def get_active_text(self, combobox):
        model = combobox.get_model()
        active = combobox.get_active()
        if active < 0:
            return None
        return model[active][0]

    def populate_networks(self):
        #print "Populating Station Network List"
        list = self.history_database.get_station_networks()
        list.sort()
        list.insert(0,['All'])
        #list.insert(0,['Network'])
        for element in list:
            self.data_networks.append(element)

# ===== Cell Data Methods ============================================
    def cdf_format_float(self, column, cell, model, iter, data=None):
        value = model.get_value( iter, 2 )
        status = model.get_value( iter, 1 )
        if status == "disconnected":
            if float(value) > 24.0:
                cell.set_property("background", "#bb4444")
            elif float(value) > 1.0:
                cell.set_property("background", "#bbbb44")
            else:
                cell.set_property("background", "#ffffff")
        else:
            cell.set_property("background", "#ffffff")

    def cdf_status_color(self, column, cell, model, iter, data=None):
        value = model.get_value( iter, 1 )
        if value == "disconnected":
            cell.set_property("foreground", "#bb0000")
        elif value == "connected":
            cell.set_property("foreground", "#00bb00")
        else:
            cell.set_property("foreground", "#ffffff")

# ===== Callback Methods =============================================
    def callback_quit(self, widget, event, data=None):
        #print "Exit Program"
        self.close_application(widget, event, data)

    def callback_populate_stations(self, widget, data=None ):
        #print "Populating Station Name List"
        self.data_stations.clear()
        network = self.get_active_text(self.combobox_network)
        #print "Selected network is", network
        list = []
        if network == 'All' or network == 'Network': 
            st_list = self.history_database.get_stations()
            if st_list:
                for (net, name) in st_list:
                    list.append(["%s_%s" % (net,name)])
        else:
            list = self.history_database.get_station_names( network )
        if list:
            #print list
            #list.insert(0,['Station'])
            for element in list:
                self.data_stations.append(element)

    def callback_update(self, widget, data=None ):
        regex = re.compile( self.date_expr )
        self.data_outages.clear()

        network = self.get_active_text( self.combobox_network )
        station = self.get_active_text( self.combobox_station )
        date_str_start = self.entry_start.get_text()
        date_str_end = self.entry_end.get_text()

        if regex.match( date_str_start ):
            date_start = time.mktime( time.strptime( date_str_start, self.date_format ) )
        else:
            date_start = None

        if  regex.match( date_str_end ):
            date_end = time.mktime( time.strptime( date_str_end, self.date_format ) )
        else:
            date_end = None

        if (not network) or (network == "") or (not station) or (station == ""):
            return
        if (network == "All") or (network == "Network"):
            set = station.split('_')
            network = set[0]
            station = set[1]
        #print "[%s] Getting status list..." % time.strftime("%Y-%j %H:%M:%S")
        results = self.history_database.get_status( network, station, date_start, date_end )
        #print "[%s] Calculating outages..." % time.strftime("%Y-%j %H:%M:%S")
        outages = self.get_outages( results )
        #print "[%s] Populating tree..." % time.strftime("%Y-%j %H:%M:%S")
        for (timestamp, type, duration) in outages:
            self.data_outages.append( [timestamp, type, duration] )
        #print "[%s] All Done." % time.strftime("%Y-%j %H:%M:%S")
        #print "%d entries for %s_%s" % (len(results), network, station)

    def callback_show_calendar(self, widget, data):
        (calendar, entry) = data
        self.propogate_time(data)
        calendar.prompt()

    def callback_populate_time(self, data):
        (calendar, widget) = data
        value = time.strftime(self.date_format, calendar.get_date())
        widget.set_text( value )

    def propogate_time(self, data):
        (calendar, widget) = data
        regex = re.compile( self.date_expr )
        if regex.match( widget.get_text() ):
            value = time.strptime(widget.get_text(), self.date_format)
            calendar.set_date( value )
        
    def get_outages(self, list):
        filtered = []
        last_time = 0
        restore_time = 0
        change_time = 0
        event_time = 0
        duration = 0
        status_changed = False
        connected = True
        for (check_time, liss_time, delay) in list:
            if liss_time == last_time:
                if connected:
                    connected = False
                    status_changed = True
                    duration = liss_time - change_time
                    event_time = change_time
                    change_time = last_time
            elif not connected:
                connected = True
                status_changed = True
                duration = liss_time - change_time 
                event_time = change_time
                change_time = liss_time
            #else:
            #    print "[",time.strftime("%Y-%j %H:%M:%S", time.gmtime(liss_time)),"]>",time.strftime("%Y-%j %H:%M:%S", time.gmtime(last_time))
            if status_changed:
                status_changed = False
                status = 'disconnected'
                if not connected:
                    status = status[3:]
                filtered.append( (time.strftime("%Y-%j %H:%M:%S", time.gmtime(event_time)), status, "%.2f" % (float(duration) / 3600.0)) )
            last_time = liss_time
        filtered.reverse()
        return filtered

    def query(self):
        name     = self.combobox_name._entryfield.getvalue()
        network  = self.combobox_network._entryfield.getvalue()
        if network == 'All':
            parts = name.split('_')
            network = parts[0]
            name = parts[1] 
        start    = self.time_start.get()
        end      = self.time_end.get()
        list     = self.history_database.get_status( network, name )
        list_len = 0
        if list:
            list_len = len(list)
        #print "%(net)s_%(name)s has %(count)d entries" % { 'net'  : network,
                                                           #'name' : name,
                                                           #'count': list_len }

    def get_file(self):
        self.file.set( askopenfilename() )

    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        return False
#/*}}}*/

def st_cmp(arr1, arr2):
    val1 = calendar.timegm(time.strptime(arr1[4], '%Y %j %H:%M:%S'))
    val2 = calendar.timegm(time.strptime(arr2[4], '%Y %j %H:%M:%S'))
    if val1 == val2:
        return cmp(arr1[0]+arr1[1]+arr1[2]+arr1[3], arr2[0]+arr2[1]+arr2[2]+arr2[3])
    return cmp(val1, val2)

def main():
    app = Monitor()
    gtk.main()

if __name__ == "__main__":
    main()
