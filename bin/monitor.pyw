#!/usr/bin/env python
import asl

import base64
import calendar
import hashlib
import inspect
import multiprocessing as mp
import os
import Queue
import re
import string
import subprocess
import sys
import threading
import time
import urllib

from pysqlite2 import dbapi2 as sqlite

import pygtk
pygtk.require('2.0')
import gobject
import gtk

from jtk.Logger import Logger
from jtk.gtk.Calendar import Calendar

#gtk.gdk.threads_init()
gobject.threads_init()

# === Monitor Class (User Interface) /*{{{*/
class Monitor(object):
    def __init__(self):

        self.path = LISSPath()
        self.link = "http://aslwww.cr.usgs.gov/cgi-bin/LISSstat7.pl"

        self.status_icon = gtk.StatusIcon()
        self.status_icon.set_from_file( self.path.get('icon_default') )
        self.status_icon.set_visible(True)
        self.status_icon.connect( "popup-menu", self.callback_menu, None )
        self.status_icon.connect( "activate", self.callback_activate, None )

        self.menu = gtk.Menu()
        self.menu.set_title("LISS Monitor")

        self.image_default = gtk.Image()
        self.image_check   = gtk.Image()
        self.image_cancel  = gtk.Image()
        self.image_view    = gtk.Image()
        self.image_clear   = gtk.Image()
        self.image_history = gtk.Image()
        self.image_quit    = gtk.Image()

        self.image_default.set_from_file( self.path.get('icon_default') )
        self.image_check.set_from_file( self.path.get('icon_check') )
        self.image_cancel.set_from_file( self.path.get('icon_cancel') )
        self.image_view.set_from_file( self.path.get('icon_view') )
        self.image_clear.set_from_file( self.path.get('icon_clear') )
        self.image_history.set_from_file( self.path.get('icon_history') )
        self.image_quit.set_from_file( self.path.get('icon_quit') )

        self.menuitem_check = gtk.ImageMenuItem("Check Now", "Check")
        self.menuitem_cancel = gtk.ImageMenuItem("Cancel Check", "Cancel")
        self.menuitem_view = gtk.ImageMenuItem("Open Viewer", "View")
        self.menuitem_clear = gtk.ImageMenuItem("Clear Warning", "Clear")
        self.menuitem_history = gtk.ImageMenuItem("History Viewer", "History")
        self.menuitem_quit = gtk.ImageMenuItem("Quit", "Quit")

        self.menuitem_check.set_image(self.image_check)
        self.menuitem_cancel.set_image(self.image_cancel)
        self.menuitem_view.set_image(self.image_view)
        self.menuitem_clear.set_image(self.image_clear)
        self.menuitem_history.set_image(self.image_history)
        self.menuitem_quit.set_image(self.image_quit)

        self.menuitem_check.connect(  "activate", self.callback_menu_selection, None, 'check' )
        self.menuitem_cancel.connect( "activate", self.callback_menu_selection, None, 'cancel' )
        self.menuitem_view.connect(   "activate", self.callback_menu_selection, None, 'view' )
        self.menuitem_clear.connect(  "activate", self.callback_menu_selection, None, 'clear' )
        self.menuitem_history.connect("activate", self.callback_menu_selection, None, 'history' )
        self.menuitem_quit.connect(   "activate", self.callback_menu_selection, None, 'quit' )

        self.menu_callbacks = {
            'check'   : self.callback_check,
            'cancel'  : self.callback_cancel,
            'view'    : self.callback_view,
            'clear'   : self.callback_clear_warn,
            'history' : self.callback_history,
            'quit'    : self.callback_quit,
            }

        self.menu.append(self.menuitem_check)
        self.menu.append(self.menuitem_cancel)
        self.menu.append(self.menuitem_view)
        self.menu.append(self.menuitem_clear)
        self.menu.append(self.menuitem_history)
        self.menu.append(self.menuitem_quit)

        self.menu.show()
        self.menuitem_check.show()
        self.menuitem_cancel.show()
        self.menuitem_view.show()
        self.menuitem_clear.show()
        self.menuitem_history.show()
        self.menuitem_quit.show()

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
        self.menu_visible = False
        self.startup_grace = 1
        self.warn_threshold = 0.25 # hours
        self.stations = []
        self.lock_status = threading.Lock()
        self.checking  = False
        self.warning   = False
        self.archiving = False
        self.data_time = ''
        self.data = None
        self.core = Core(self)
        self.core.start()

# ===== Callback Methods =============================================
    
    def callback_menu_selection(self, widget, event, data=None):
        self.menu_visible = False
        print "menu selection data:", data
        if self.menu_callbacks.has_key(data):
            self.menu_callbacks[data](widget, event, data)

    def callback_check(self, widget, event, data=None):
        print "check now"
        self.core.check_now()

    def callback_cancel(self, widget, event, data=None):
        print "cancel check"
        self.core.cancel_check()

    def callback_view(self, widget, event, data=None):
        print "viewer launched"
        if self.viewer.is_dead():
            self.new_viewer()
        self.viewer.show()
        self.callback_clear_warn(None, None, None)

    def callback_quit(self, widget, event, data=None):
        print "exit program"
        self.core.stop()
        self.close_application(widget, event, data)

    def callback_menu(self, widget, button, activate_time, data=None):
        print "toggle menu"
        if self.menu_visible:
            self.menu.popdown()
            self.menu_visible = False
        else:
            self.menu.popup( None, None, None, button, activate_time, data )
            self.menu_visible = True

    def callback_active(self, widget, event, data=None):
        print "status icon active"
        with self.lock_status:
            self.checking = True
            self.update_status_icon()

    def callback_inactive(self, widget, event, data=None):
        print "status icon inactive"
        with self.lock_status:
            self.checking = False
            self.update_status_icon()

    def callback_warn(self, widget, event, data=None):
        print "status icon warning"
        with self.lock_status:
            self.warning = True
            self.update_status_icon()

    def callback_clear_warn(self, widget, event, data=None):
        print "status icon no-warning"
        with self.lock_status:
            self.warning = False
            self.update_status_icon()

    def callback_archive(self, widget, event, data=None):
        print "status icon archiving"
        with self.lock_status:
            self.archiving = True
            self.update_status_icon()

    def callback_clear_archive(self, widget, event, data=None):
        print "status icon not archiving"
        with self.lock_status:
            self.archiving = False
            self.update_status_icon()

    def callback_activate(self, wiget, event, data=None):
        print "status icon activated"
        if self.viewer.is_dead():
            self.new_viewer()
        self.viewer.toggle()

    def callback_history(self, widget, event, data=None):
        print "launching history viewer"
        os.spawnvp( os.P_NOWAIT, self.path.get('file_pythonw'), 
                    [self.path.get('file_pythonw'), 'history.pyw'])

    def callback_status_update(self, widget, event, data=None):
        print "LISS status has been updated"
        self.update_stations()

    def new_viewer(self):
        self.viewer = Viewer(self)
        self.viewer.set_data(self.data)
        self.viewer.set_time(self.data_time)

    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        return False

    def update_status_icon(self):
        if self.checking:
            self.status_icon.set_from_file( self.path.get('icon_checking') )
            self.status_icon.set_blinking(True)
        elif self.archiving:
            self.status_icon.set_from_file( self.path.get('icon_archive') )
            self.status_icon.set_blinking(True)
        elif self.warning:
            self.status_icon.set_from_file( self.path.get('icon_warn') )
            self.status_icon.set_blinking(True)
        else:
            self.status_icon.set_from_file( self.path.get('icon_default') )
            self.status_icon.set_blinking(False)

    def update_stations(self):
        if self.data:
            alert_stations    = []
            restored_stations = []
            new_list          = []

            for item in self.data:
                name  = "%s_%s" % (item[0], item[1])
                delay = item[4]
                if (delay >= self.warn_threshold) or (delay <= 24.0):
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
        if self.data:
            self.viewer.set_data_buffer(self.data)
        if self.data_time:
            self.viewer.set_time_buffer(self.data_time)

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
        self.status_icon.set_from_file( self.path.get('icon_warn') )

    def current_time(self):
        return time.mktime(time.gmtime())
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
            elif request == 'CHECK_DONE':
                self.gui.data_time = data[0]
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
            args = [self.check_queue, self.queue]
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
def check(check_queue, master_queue):
    test = False
    #test = True
    
    if test:
        uri = "liss-test-data.html"
        reader = open(uri, 'r')
    else:
        uri = "http://aslwww.cr.usgs.gov/cgi-bin/LISSstat7.pl"
        #uri = "http://136.177.121.191:13031/liss_stat/liss_stat.html"
        reader = urllib.urlopen( uri )
    xml = string.join(reader.readlines())
    reader.close()

    # one serious regex
    # 0) Network
    # 1) Station
    # 2) Channel
    # 3) Timestamp
    # 4) --garbage
    # 5) Delay
    # 6) Units
    # 7) --garbage
    # 8) Channel
    # 9) Timestamp
    # 10) Delay

    regex = re.compile( \
        '<\s*?[Tt][Rr][^>]*?>.*?' + \
        '<\s*?[Tt][Dd][^>]*?>(.*?)<\/[Tt][Dd]>.*?' + \
        '<\s*?[Tt][Dd][^>]*?>(.*?)<\/[Tt][Dd]>.*?' + \
        '<\s*?[Tt][Dd][^>]*?>(.*?)<\/[Tt][Dd]>.*?' + \
        '<\s*?[Tt][Dd][^>]*?>(.*?)<\/[Tt][Dd]>.*?' + \
        '<\s*?[Tt][Dd][^>]*?>'  + \
            '[^<>]*?(<\s*?[^Tt]?[^>]*?>)*?' + \
            '([0-9.]+)'         + \
            '\s*?([a-zA-Z]*?)'     + \
            '(<\s*?[^Tt]?[^>]*?>)*?'    + \
            '<\/[Tt][Dd]>.*?'   + \
        '<\s*?[Tt][Dd][^>]*?>(.*?)<\/[Tt][Dd]>.*?' + \
        '<\s*?[Tt][Dd][^>]*?>(.*?)<\/[Tt][Dd]>.*?' + \
        '<\s*?[Tt][Dd][^>]*?>(.*?)<\/[Tt][Dd]>.*?' + \
        '<\/[Tt][Rr]>', re.S)

    regex_timestamp = re.compile('As Of[:] (\d+\/\d+\/\d+ \(\d+,\d+\) \d+[:]\d+)', re.S)
    regex_no_files  = re.compile('no files found')
    
    # find the problem stations
    matches = regex.findall(xml)
    results = []
    for match in matches:
        n,s,c,t,_,d,u,_,_,_,_ = match
        if regex_no_files.search(t):
            d = float(123456789.0)
            t = 'No Files Found'
        elif u[0:6] == 'minute':
            d = float(d) / 60.0
        else:
            d = float(d)
        results.append((n,s,c,t,d))

    match = regex_timestamp.search(xml)
    timestamp = ''
    if match:
        print "FOUND TIME!!"
        timestamp = match.group(1)
    else:
        print "BAD TIME REGEX!!"

    master_queue.put(('CHECK_DONE', (timestamp, sorted(results, st_cmp))))
    check_queue.get()
#/*}}}*/

# === Archive Function /*{{{*/
def archive(archive_queue, master_queue, data, timestamp, directory):
    master_queue.put('ARCHIVE_DONE')
    #archive_queue.get()
#/*}}}*/

# === Viewer Class  /*{{{*/
class Viewer(object):
    def __init__(self, master=None):
        self.list_store_data = None
        self.data_buffer = None
        self.time_buffer = None
        self.master = master

      # Widget Data 
        self.data_outages = gtk.TreeStore( gobject.TYPE_STRING , # Station Name
                                           gobject.TYPE_STRING , # Downtime
                                           gobject.TYPE_STRING , # Outage Start Timestamp
                                           gobject.TYPE_BOOLEAN) # Checkbutton

        # Components
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("LISS Status Monitor - Viewer")

        #self.pixbuf_window_icon = gtk.gdk.pixbuf_new_from_file(self.master.path.get('icon_default'))
        #self.window.set_icon_list([self.pixbuf_window_icon])

        self.vbox_main    = gtk.VBox()
        self.hbox_time    = gtk.HBox()
        self.hbox_tree    = gtk.HBox()
        self.hbox_buttons = gtk.HBox()

        self.scrollwindow          = gtk.ScrolledWindow()
        self.treeview              = gtk.TreeView()
        self.label_time            = gtk.Label()
        self.treeviewcol_station   = gtk.TreeViewColumn( "Station" )
        self.treeviewcol_delay     = gtk.TreeViewColumn( "Delay (Hours)" )
        self.treeviewcol_timestamp = gtk.TreeViewColumn( "Outage Timestamp" )
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

        self.crtext_station   = gtk.CellRendererText()
        self.crtext_delay     = gtk.CellRendererText()
        self.crtext_timestamp = gtk.CellRendererText()
        self.crtoggle_viewed  = gtk.CellRendererToggle()
        self.crtoggle_viewed.set_property('activatable', True)
        self.crtoggle_viewed.connect('toggled', self.callback_toggled, None)

# ===== Layout Configuration ==============================================
        self.window.add(self.vbox_main)
        self.window.set_size_request(300,400)
        self.vbox_main.pack_start(self.hbox_time,    expand=False, fill=True,  padding=1)
        self.vbox_main.pack_start(self.hbox_tree,    expand=True,  fill=True,  padding=2)
        self.vbox_main.pack_start(self.hbox_buttons, expand=False, fill=True,  padding=1)

        self.hbox_time.pack_start(self.label_time)
        self.hbox_tree.pack_start(self.scrollwindow, expand=True, fill=True, padding=2)
        self.hbox_buttons.pack_start(self.button_refresh, expand=False, fill=True, padding=1)
        self.hbox_buttons.pack_end(self.button_close, expand=False, fill=False, padding=1)

        self.scrollwindow.add(self.treeview)
        self.treeview.append_column(self.treeviewcol_station)
        self.treeview.append_column(self.treeviewcol_delay)
        self.treeview.append_column(self.treeviewcol_timestamp)
        self.treeview.append_column(self.treeviewcol_viewed)

# ===== Attribute Configuration ===========================================
        self.scrollwindow.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )
        self.treeview.set_model( self.data_outages )
        self.treeviewcol_station.pack_start(self.crtext_station, True)
        self.treeviewcol_station.add_attribute(self.crtext_station, 'text', 0)
        self.treeviewcol_station.set_cell_data_func(self.crtext_station, self.cdf_format_station, None)
        self.treeviewcol_delay.pack_start(self.crtext_delay, True)
        self.treeviewcol_delay.add_attribute(self.crtext_delay, 'text', 1)
        self.treeviewcol_delay.set_cell_data_func(self.crtext_delay, self.cdf_format_delay, None)
        self.treeviewcol_timestamp.pack_start(self.crtext_timestamp, True)
        self.treeviewcol_timestamp.add_attribute(self.crtext_timestamp, 'text', 2)
        self.treeviewcol_timestamp.set_cell_data_func(self.crtext_timestamp, self.cdf_format_timestamp, None)
        self.treeviewcol_viewed.pack_start(self.crtoggle_viewed, True)
        self.treeviewcol_viewed.add_attribute(self.crtoggle_viewed, 'radio', 3)
        self.treeviewcol_viewed.set_cell_data_func(self.crtoggle_viewed, self.cdf_format_viewed, None)

        model = self.treeview.get_selection()
        model.set_mode(gtk.SELECTION_NONE)
        

# ===== Event Bindings
        self.button_refresh.connect("clicked", self.callback_refresh, None)
        self.button_close.connect("clicked", self.callback_close, None)

        self.window.connect( "destroy-event", self.callback_destroy, None )
        self.window.connect( "delete-event", self.callback_destroy, None )

        # Show widgets
        self.window.show_all()
        self.window.hide()
        self.hidden = True
        self.dead   = False

# ===== Cell Data Methods ============================================
    def cdf_format_station(self, column, cell, model, iter, data=None):
        delay = float(model.get_value(iter, 1))
        station = model.get_value(iter, 0)
        if delay > 1.0:
            cell.set_property("foreground", "#bb0000")
        else:
            cell.set_property("foreground", "#00bb00")

    def cdf_format_delay(self, column, cell, model, iter, data=None):
        delay = float(model.get_value(iter, 1))
        if delay > (7.0 * 24.0):
            cell.set_property("background", "#cc0000")
        elif delay > 24.0:
            cell.set_property("background", "#ff6600")
        elif delay > 1.0:
            cell.set_property("background", "#ffcc00")
        else:
            cell.set_property("background", "#ffffff")

    def cdf_format_timestamp(self, column, cell, model, iter, data=None):
        delay = float(model.get_value(iter, 1))
        timestamp = model.get_value(iter, 2)
        if delay > (7.0 * 24.0):
            cell.set_property("background", "#cc0000")
        elif delay > 24.0:
            cell.set_property("background", "#ff6600")
        elif delay > 1.0:
            cell.set_property("background", "#ffcc00")
        else:
            cell.set_property("background", "#ffffff")

    def cdf_format_viewed(self, column, cell, model, iter, data=None):
        cell.set_active(model.get_value(iter, 3))

# ===== Callback Methods =============================================
    def callback_close(self, widget, event, data=None):
        self.window.hide()

    def callback_destroy(self, widget, event, data=None):
        self.dead = True

    def callback_refresh(self, widget, event, data=None):
        if self.data_buffer:
            self.set_data(self.data_buffer)
            self.data_buffer = None
        if self.time_buffer:
            self.set_time(self.time_buffer)
            self.time_buffer = None
        if self.master:
            self.master.callback_clear_warn(None, None, None) 

    def callback_toggled(self, renderer, path, params=None):
        iter = self.data_outages.iter_nth_child(None, int(path))
        value = self.data_outages.get_value(iter, 3)
        if value:
            self.data_outages.set_value(iter, 3, False)
        else:
            self.data_outages.set_value(iter, 3, True)

# ===== General Methods ==============================================
    def show(self):
        self.hidden = False
        self.window.show()

    def hide(self):
        self.hidden = True
        self.window.hide()

    def toggle(self):
        if self.hidden:
            self.show()
        else:
            self.hide()

    def is_dead(self):
        return self.dead

    def set_data(self, data):
        if data:
            self.data_outages.clear()
            for (n,s,c,t,d) in data:
                name = "%s_%s" % (n,s)
                delay = "%0.2f" % d
                timestamp = t
                self.data_outages.append(None, [name, delay, timestamp, False])

    def set_time(self, time):
        print "setting time"
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
      # Icons
        self.path['icon_about']    = os.path.abspath("%(path_icon)s/sabout.ico" % self.path)
        self.path['icon_archive']  = os.path.abspath("%(path_icon)s/sarchive.ico" % self.path)
        self.path['icon_cancel']   = os.path.abspath("%(path_icon)s/scancel.ico" % self.path)
        self.path['icon_check']    = os.path.abspath("%(path_icon)s/scheck.ico" % self.path)
        self.path['icon_checking'] = os.path.abspath("%(path_icon)s/schecking.ico" % self.path)
        self.path['icon_clear']    = os.path.abspath("%(path_icon)s/sclear.ico" % self.path)
        self.path['icon_default']  = os.path.abspath("%(path_icon)s/sdefault.ico" % self.path)
        self.path['icon_history']  = os.path.abspath("%(path_icon)s/shistory.ico" % self.path)
        self.path['icon_gliss']    = os.path.abspath("%(path_icon)s/sgliss.ico" % self.path)
        self.path['icon_quit']     = os.path.abspath("%(path_icon)s/squit.ico" % self.path)
        self.path['icon_save']     = os.path.abspath("%(path_icon)s/ssave.ico" % self.path)
        self.path['icon_view']     = os.path.abspath("%(path_icon)s/sview.ico" % self.path)
        self.path['icon_warn']     = os.path.abspath("%(path_icon)s/swarn.ico" % self.path)

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
        print "Populating Station Network List"
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
        print "Exit Program"
        self.close_application(widget, event, data)

    def callback_populate_stations(self, widget, data=None ):
        print "Populating Station Name List"
        self.data_stations.clear()
        network = self.get_active_text(self.combobox_network)
        print "Selected network is", network
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
        print "[%s] Getting status list..." % time.strftime("%Y-%j %H:%M:%S")
        results = self.history_database.get_status( network, station, date_start, date_end )
        print "[%s] Calculating outages..." % time.strftime("%Y-%j %H:%M:%S")
        outages = self.get_outages( results )
        print "[%s] Populating tree..." % time.strftime("%Y-%j %H:%M:%S")
        for (timestamp, type, duration) in outages:
            self.data_outages.append( [timestamp, type, duration] )
        print "[%s] All Done." % time.strftime("%Y-%j %H:%M:%S")
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
    val1 = arr1[4]
    val2 = arr2[4]
    if val1 == val2:
        return cmp(arr1[0]+arr1[1], arr2[0]+arr2[1])
    return cmp(val2, val1)

def main():
    app = Monitor()
    gtk.main()

if __name__ == "__main__":
    main()