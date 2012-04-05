#!/usr/bin/python -W all
import asl

import glob
import inspect
import optparse
import os
import Queue
import re
import stat
import struct
import sys
import time
import threading

import pygtk
pygtk.require('2.0')
import gtk
import gobject
#gtk.gdk.threads_init()

from jtk.StatefulClass import StatefulClass

from jtk.gtk.DateTimeWindow import DateTimeWindow 
from jtk.gtk.utils import LEFT

class ORGUI:
    def __init__(self):
        home_dir = '.'
        if os.environ.has_key('HOME'):
            home_dir = os.environ['HOME']
        elif os.environ.has_key('USERPROFILE'):
            home_dir = os.environ['USERPROFILE']
        pref_file = os.path.abspath("%s/.or-gui-prefs.db" % home_dir)
        self._prefs = StatefulClass(pref_file)

        self._minimum_width  = 720
        self._minimum_height = 640
        self._default_width = self._prefs.recall_value('window-width', self._minimum_width)
        self._default_height = self._prefs.recall_value('window-height', self._minimum_height)

        self.stations = [
            'IU_AFI' , 'IU_ANMO', 'IU_CTAO', 'IU_DAV' , 'IU_FURI', 'IU_GNI' ,
            'IU_GUMO', 'IU_HNR' , 'IU_KOWA', 'IU_KMBO', 'IU_LVC' , 'IU_LSZ' ,
            'IU_MSKU', 'IU_NWAO', 'IU_PMG' , 'IU_PMSA', 'IU_PTGA', 'IU_QSPA',
            'IU_RAO' , 'IU_RAR' , 'IU_RCBR', 'IU_SDV' , 'IU_SFJD', 'IU_SJG' ,
            'IU_TEIG', 'IU_TSUM', 'US_ELK',  'US_NEW'
        ]

# ===== Widget Creation ============================================
      # Layout Control Widgets
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Outage Report - CTBTO Calibrations")
        self.window.set_geometry_hints(min_width=self._default_width, min_height=self._default_height)
        self.window.connect( "configure-event", self.callback_window_configured, None )
        self.window.connect( "screen-changed", self.callback_window_configured, None )
        self.window.connect( "window-state-event", self.callback_window_configured, None )

        self.vbox_main   = gtk.VBox()

        self.table_options = gtk.Table(rows=5, columns=4)
        self.hbox_message  = gtk.HBox()
        self.hbox_display  = gtk.HBox()
        self.hbox_control  = gtk.HBox()

      # User Interaction Widgets
        self.checkbutton_update = gtk.CheckButton()
        self.label_update       = gtk.Label("Update Message")

        self.label_station    = gtk.Label("Station:")
        self.combobox_stations = gtk.combo_box_new_text()

        self.label_submitter = gtk.Label("Submitter:")
        self.entry_submitter = gtk.Entry()
        self.entry_submitter._hint_text = "FULL NAME"

        self.label_start_time  = gtk.Label("Start Date:")
        self.entry_start_time  = gtk.Entry()
        self.button_start_time = gtk.Button()
        self.image_start_time  = gtk.Image()
        self.image_start_time.set_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_MENU)
        self.button_start_time.add(self.image_start_time)

        self.checkbutton_end_time = gtk.CheckButton()
        self.label_end_time       = gtk.Label("End Date:")
        self.entry_end_time       = gtk.Entry()
        self.button_end_time = gtk.Button()
        self.image_end_time  = gtk.Image()
        self.image_end_time.set_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_MENU)
        self.button_end_time.add(self.image_end_time)

        self.textbuffer_message = gtk.TextBuffer()
        self.textview_message   = gtk.TextView(buffer=self.textbuffer_message)
        self.scrolledwindow_message = gtk.ScrolledWindow()
        self.scrolledwindow_message.add(self.textview_message)

        self.textbuffer_display = gtk.TextBuffer()
        self.textview_display   = gtk.TextView(buffer=self.textbuffer_display)
        self.scrolledwindow_display = gtk.ScrolledWindow()
        self.scrolledwindow_display.add(self.textview_display)

        self.button_copy = gtk.Button(stock=None, use_underline=True)
        self.hbox_copy   = gtk.HBox()
        self.image_copy  = gtk.Image()
        self.image_copy.set_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)
        self.label_copy  = gtk.Label("Copy")
        self.button_copy.add(self.hbox_copy)
        self.hbox_copy.pack_start(self.image_copy, padding=1)
        self.hbox_copy.pack_start(self.label_copy, padding=1)

        self.button_send_email = gtk.Button(stock=None, use_underline=True)
        self.hbox_send_email   = gtk.HBox()
        self.image_send_email  = gtk.Image()
        self.image_send_email.set_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)
        self.label_send_email  = gtk.Label("E-mail")
        self.button_send_email.add(self.hbox_send_email)
        self.hbox_send_email.pack_start(self.image_send_email, padding=1)
        self.hbox_send_email.pack_start(self.label_send_email, padding=1)

        self.button_quit = gtk.Button(stock=None, use_underline=True)
        self.hbox_quit   = gtk.HBox()
        self.image_quit  = gtk.Image()
        self.image_quit.set_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)
        self.label_quit  = gtk.Label("Quit")
        self.button_quit.add(self.hbox_quit)
        self.hbox_quit.pack_start(self.image_quit, padding=1)
        self.hbox_quit.pack_start(self.label_quit, padding=1)

# ===== Layout Configuration =======================================
        self.window.add(self.vbox_main)
        self.window.set_size_request(350, 550)

        self.vbox_main.pack_start(self.table_options, False, True, 0)
        self.vbox_main.pack_start(self.hbox_message,  True,  True, 2)
        self.vbox_main.pack_start(self.hbox_display,  True,  True, 2)
        self.vbox_main.pack_start(self.hbox_control,  False, True, 0)

        # left, right, top, bottom, xoptions, yoptions, xpadding, ypadding
        self.table_options.attach(LEFT(self.checkbutton_update),   0, 1, 0, 1, gtk.FILL, 0, 1, 1)
        self.table_options.attach(LEFT(self.label_update),         1, 2, 0, 1, gtk.FILL, 0, 1, 1)

        self.table_options.attach(LEFT(self.label_station),        1, 2, 1, 2, gtk.FILL, 0, 1, 1)
        self.table_options.attach(LEFT(self.combobox_stations),    2, 3, 1, 2, gtk.FILL, 0, 1, 1)

        self.table_options.attach(LEFT(self.label_submitter),      1, 2, 2, 3, gtk.FILL, 0, 1, 1)
        self.table_options.attach(self.entry_submitter,      2, 3, 2, 3, gtk.FILL | gtk.EXPAND, 0, 1, 1)

        self.table_options.attach(LEFT(self.label_start_time),     1, 2, 3, 4, gtk.FILL, 0, 1, 1)
        self.table_options.attach(self.entry_start_time,     2, 3, 3, 4, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_options.attach(self.button_start_time,    3, 4, 3, 4, gtk.FILL, 0, 1, 1)

        self.table_options.attach(LEFT(self.checkbutton_end_time), 0, 1, 4, 5, gtk.FILL, 0, 1, 1)
        self.table_options.attach(LEFT(self.label_end_time),       1, 2, 4, 5, gtk.FILL, 0, 1, 1)
        self.table_options.attach(self.entry_end_time,       2, 3, 4, 5, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_options.attach(self.button_end_time,      3, 4, 4, 5, 0, 0, 1, 1)

        self.hbox_message.pack_start(self.scrolledwindow_message, True, True, 0)
        self.hbox_display.pack_start(self.scrolledwindow_display, True, True, 0)

        self.hbox_control.pack_start(self.button_copy, False, False, 0)
        self.hbox_control.pack_start(self.button_send_email, False, False, 0)
        self.hbox_control.pack_end(self.button_quit,   False, False, 0)

# ===== Widget Configurations ======================================
        self.checkbutton_update.set_active(False)

        for t in self.stations:
            self.combobox_stations.append_text(t)
        self.combobox_stations.set_active(0)

        self.entry_submitter.set_text('')

        self.entry_start_time.set_text(time.strftime("%Y/%m/%d 15:00:00", time.gmtime()))

        self.checkbutton_end_time.set_active(False)
        self.entry_end_time.set_text('')

        self.textbuffer_message.set_text('')
        self.textview_message.set_editable(True)
        self.textview_message.set_size_request(-1, 200)
        self.textview_message.set_wrap_mode(gtk.WRAP_WORD)

        self.textbuffer_display.set_text('')
        self.textview_display.set_editable(False)
        self.textview_display.set_size_request(-1, 200)

        self.button_copy.set_sensitive(False)
        self.button_send_email.set_sensitive(False)

# ===== Hidden Objects =============================================
        self.clipboard = gtk.Clipboard()
        self.window_start_time = DateTimeWindow()
        self.window_start_time.set_granularity("second")
        self.window_start_time.set_callback_complete(self.callback_start_time_complete)
        self.window_start_time.set_callback_cancel(self.callback_start_time_cancel)

        self.clipboard = gtk.Clipboard()
        self.window_end_time = DateTimeWindow()
        self.window_end_time.set_granularity("second")
        self.window_end_time.set_callback_complete(self.callback_end_time_complete)
        self.window_end_time.set_callback_cancel(self.callback_end_time_cancel)

# ===== Signal Bindings ============================================

# ===== Event Bindings =============================================
        self.window.connect("destroy-event", self.callback_quit, None)
        self.window.connect("delete-event",  self.callback_quit, None)

        #self.label_update.connect("button-release-event", self.callback_label_toggle, None, self.checkbutton_update)
        #self.label_end_time.connect("button-release-event", self.callback_label_toggle, None, self.checkbutton_end_time)
        self.checkbutton_update.connect("toggled", self.callback_toggled, None)
        self.checkbutton_end_time.connect("toggled", self.callback_toggled, None)

        self.combobox_stations.connect("changed", self.callback_generate, None)
        self.entry_submitter.connect("changed", self.callback_submitter_changed, None)
        self.entry_submitter.connect("focus-in-event", self.callback_entry_focus_in, None)
        self.entry_submitter.connect("focus-out-event", self.callback_entry_focus_out, None)
        self.entry_start_time.connect("changed", self.callback_start_time_changed, None)
        self.entry_end_time.connect("changed", self.callback_end_time_changed, None)
        self.button_start_time.connect("clicked", self.callback_start_time, None)
        self.button_end_time.connect("clicked", self.callback_end_time, None)
        self.textbuffer_message.connect("changed", self.callback_generate, None)

        self.button_copy.connect("clicked", self.callback_copy, None)
        self.button_send_email.connect("clicked", self.callback_email, None)
        self.button_quit.connect("clicked", self.callback_quit, None)

# ===== Event Bindings =============================================
        self.window.connect("key-press-event", self.callback_key_pressed)

      # Show widgets
        self.window.show_all()
        self.generate()
        self.update_interface()
        self.callback_start_time_changed(None, None, None)
        self.callback_end_time_changed(None, None, None)

      # Update with information from preferences
        if self._prefs.has_key('window-gravity'):
            g = int(self._prefs['window-gravity'])
            self.window.set_gravity(g)
        if self._prefs.has_key('window-position'):
            x,y = map(int,self._prefs['window-position'].split(',',1))
            self.window.move(x,y)
        if self._prefs.has_key('window-size'):
            w,h = map(int,self._prefs['window-size'].split(',',1))
            self.window.resize(w,h)
        if self._prefs.has_key('window-state'):
            state = self._prefs['window-state'].upper()
            if state == 'MAXIMIZED':
                self.window.maximize()
            elif state == 'FULLSCREEN':
                self.window.fullscreen()
        if self._prefs.has_key('entry-submitter'):
            self.entry_submitter.set_text(self._prefs['entry-submitter'])

      # Post preference widget configs
        self.hint_text_show(self.entry_submitter)
        self.verify_entry_populated(self.entry_submitter)

# ===== Callbacks ==================================================
    def callback_window_configured(self, widget, event, data=None):
        gravity  = str(int(self.window.get_gravity()))
        position = '%d,%d' % self.window.get_position()
        size     = '%d,%d' % self.window.get_size()
        state    = 'NORMAL'
        try:
            if self.window.get_state() & gtk.gdk.WINDOW_STATE_FULLSCREEN:
                state = 'FULLSCREEN'
            elif self.window.get_state() & gtk.gdk.WINDOW_STATE_MAXIMIZED:
                state = 'MAXIMIZED'
        except:
            pass
        self._prefs['window-gravity'] = gravity
        self._prefs['window-position'] = position
        self._prefs['window-size'] = size
        self._prefs['window-state'] = state

    def callback_key_pressed(self, widget, event, data=None):
        if event.state == gtk.gdk.MOD1_MASK:
            if event.keyval == ord('q'):
                self.callback_quit(widget, event, data)
            elif event.keyval == ord('c'):
                if not (self, self.button_copy.state & gtk.STATE_INSENSITIVE):
                    self.text_to_clipboard()
            self.update_interface()

    def callback_update_interface(self, widget, event, data=None):
        self.update_interface()

    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, event, data)

    def callback_copy(self, widget, event, data=None):
        self.text_to_clipboard()

    def entry_populated(self, widget):
        value = widget.get_text()
        if value == "":
            raise ValueError()
        if value == widget._hint_text:
            raise ValueError()
        return value

    def verify_entry_populated(self, widget):
        self.verify_entry(widget, self.entry_populated, widget)

    def verify_entry_float(self, widget):
        self.verify_entry(widget, float, widget.get_text())

    def verify_entry(self, widget, method, *args):
        try:
            method(*args)
            widget.modify_base(gtk.STATE_NORMAL, gtk.gdk.Color(45000, 65000, 45000)) #Green
            widget._valid = True
        except ValueError:
            widget.modify_base(gtk.STATE_NORMAL, gtk.gdk.Color(65000, 45000, 45000)) #Red
            widget._valid = False

    def callback_submitter_changed(self, widget, event, data=None):
        self._prefs['entry-submitter'] = widget.get_text()
        self.verify_entry_populated(widget)
        self.generate()

    def callback_generate(self, widget, event, data=None):
        self.generate()

    def callback_start_time_changed(self, widget, event, data=None):
        time_string = self.entry_start_time.get_text() + " UTC"
        try:
            date = time.strptime(time_string,"%Y/%m/%d %H:%M:%S %Z")
            self.window_start_time.set_date(date)
            self.generate()
        except ValueError:
            pass

    def callback_end_time_changed(self, widget, event, data=None):
        time_string = self.entry_end_time.get_text() + " UTC"
        try:
            date = time.strptime(time_string,"%Y/%m/%d %H:%M:%S %Z")
            self.window_end_time.set_date(date)
            self.generate()
        except ValueError:
            pass

    def callback_start_time(self, widget, event, data=None):
        self.window_start_time.create_window()
        self.generate()

    def callback_start_time_complete(self):
        self.entry_start_time.set_text(time.strftime("%Y/%m/%d %H:%M:%S", self.window_start_time.get_date()))

    def callback_start_time_cancel(self):
        time_string = self.entry_start_time.get_text() + " UTC"
        date = time.strptime(time_string,"%Y/%m/%d %H:%M:%S %Z")
        self.window_start_time.set_date(date)
        self.generate()

    def callback_end_time(self, widget, event, data=None):
        self.window_end_time.create_window()
        self.generate()

    def callback_end_time_complete(self):
        self.entry_end_time.set_text(time.strftime("%Y/%m/%d %H:%M:%S", self.window_end_time.get_date()))

    def callback_end_time_cancel(self):
        time_string = self.entry_end_time.get_text() + " UTC"
        date = time.strptime(time_string,"%Y/%m/%d %H:%M:%S %Z")
        self.window_end_time.set_date(date)
        self.generate()

    def callback_entry_focus_out(self, widget, event, data=None):
        self.hint_text_show(widget)

    def callback_entry_focus_in(self, widget, event, data=None):
        self.hint_text_hide(widget)

    def callback_toggled(self, widget, event, data=None):
        self.update_interface()
        self.generate()

    def callback_label_toggle(self, widget, event, data=None):
        print data
        if data:
            data.toggled()

    def callback_email(self, widget, event, data=None):
        self.mailto()

# ===== Methods ====================================================
    def generate(self):
        message = ""
        have_required = True
        s,e = self.textbuffer_message.get_bounds()
        msg = self.textbuffer_message.get_text(s,e)
        submitter = self.entry_submitter.get_text()
        if submitter == self.entry_submitter._hint_text:
            submitter = ""

        if not len(msg):
            have_required = False
        if not len(submitter):
            have_required = False

        if have_required:
            if self.checkbutton_update.get_active():
                message += "#Description:\n"
                message += "%s\n" % msg
                message += "\n"
                message += "#Submitted by\n"
                message += "%s\n" % submitter
                message += "\n"
                message += "#End\n"
                message += "\n"
            else:
                station = self.combobox_stations.get_active_text().split('_')[1]
                message += "#Report type\n"
                message += "Outage Request\n"
                message += "\n"
                message += "#Station code\n"
                message += "%s\n" % station
                message += "\n"
                message += "#Source\n"
                message += "Station - New Report\n"
                message += "\n"
                message += "#Submitted by\n"
                message += "%s\n" % submitter
                message += "\n"
                message += "#Heading\n"
                message += "Calibration of sensors at %s\n" % station
                message += "\n"
                message += "#Station reference\n"
                message += "OR %s\n" % station
                message += "\n"
                date = self.entry_start_time.get_text()
                if len(date) > 2:
                    date = date[:-3]
                message += "#Start date of requested outage\n"
                message += "%s\n" % date
                message += "\n"
                if self.checkbutton_end_time.get_active():
                    date = self.entry_end_time.get_text()
                    if len(date) > 2:
                        date = date[:-3]
                    message += "#End date of requested outage\n"
                    message += "%s\n" % date
                    message += "\n"
                message += "#Mission capable\n"
                message += "no\n"
                message += "\n"
                message += "#Data quality\n"
                message += "Calibration signals\n"
                message += "\n"
                message += "#Description\n"
                message += "%s\n" % msg
                message += "\n"
            #s,e = self.textbuffer_display.get_bounds()
            #self.textbuffer_display.delete(s,e)
        self.textbuffer_display.set_text(message)
        self.update_interface()
            

    def update_interface(self):
        if self.checkbutton_update.get_active():
            self.label_station.hide()
            self.combobox_stations.hide()
            self.label_start_time.hide()
            self.entry_start_time.hide()
            self.button_start_time.hide()
            self.checkbutton_end_time.hide()
            self.label_end_time.hide()
            self.entry_end_time.hide()
            self.button_end_time.hide()
        else:
            self.label_station.show()
            self.combobox_stations.show()
            self.label_start_time.show()
            self.entry_start_time.show()
            self.button_start_time.show()
            self.checkbutton_end_time.show()
            self.label_end_time.show()
            if self.checkbutton_end_time.get_active():
                self.entry_end_time.show()
                self.button_end_time.show()
                self.label_end_time.set_text('End Date:')
            else:
                self.entry_end_time.hide()
                self.button_end_time.hide()
                self.label_end_time.set_text('End Date')
        s,e = self.textbuffer_display.get_bounds()
        if len(self.textbuffer_display.get_text(s,e)):
            if self.checkbutton_update.get_active():
                self.button_send_email.set_sensitive(False)
            else:
                self.button_send_email.set_sensitive(True)
            self.button_copy.set_sensitive(True)
        else:
            self.button_copy.set_sensitive(False)
            self.button_send_email.set_sensitive(False)
        #w,h = self.window.size_request()
        #self.window.resize(w,h)
        self.window.resize_children()

    def hint_text_show(self, widget):
        if not len(widget.get_text()):
            widget.set_text(widget._hint_text)
            widget.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('#888888'))

    def hint_text_hide(self, widget):
        if widget.get_text() == widget._hint_text:
            widget.set_text('')
        widget.modify_text(gtk.STATE_NORMAL, gtk.gdk.Color())


    def text_to_clipboard(self):
        s,e = self.textbuffer_display.get_bounds()
        self.clipboard.set_text(self.textbuffer_display.get_text(s,e))

    def get_text_for_mail(self):
        s,e = self.textbuffer_display.get_bounds()
        return self.textbuffer_display.get_text(s,e)

    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        self._prefs.save_state()
        return False

    def mailto(self):
        from urllib import quote
        import webbrowser
        import string
        station = self.combobox_stations.get_active_text().split('_')[1]
        recipients = ['support@ctbto.org']
        field_map = {
            'replyto' : 'gsnmaint@usgs.gov',
            'cc' : 'gsn-%s@usgs.gov' % station,
            'subject' : quote('Report - Outage Request - %s' % station),
            'body' : quote(self.get_text_for_mail()),
        }
        recipient_str = map(string.strip, recipients)
        fields = []
        for k,v in field_map.items():
            fields.append('%s=%s' % (k,v))

        mailto_cmd = "mailto:%s?%s" % (','.join(recipients), '&'.join(fields))
        webbrowser.open(mailto_cmd)


if __name__ == "__main__":
    reader = ORGUI()
    gtk.main()

