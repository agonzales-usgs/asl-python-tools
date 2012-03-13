#!/usr/bin/python
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
#import threading

import pygtk
pygtk.require('2.0')
import gtk
import gobject
#gtk.gdk.threads_init()

class DateTimeWindow:
    def __init__(self):
        self.completion_callback = None
        self.completion_data = None
        self.cancel_callback = None
        self.cancel_data = None
        self.time_high = True
        self.granularity = "day"
        self.granules  = { 'day'    : 4 ,
                           'hour'   : 3 ,
                           'minute' : 2 ,
                           'second' : 1 } 
        times = time.gmtime()
        self.timestamp = { 'year'   : times[0] ,
                           'month'  : times[1] ,
                           'day'    : times[2] ,
                           'hour'   : times[3] ,
                           'minute' : times[4] ,
                           'second' : times[5] }
        self.pushing = False
        self.running = False

    def create_window(self):
        if self.running:
            return
        self.running = True
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.vbox_date_time = gtk.VBox()
        self.hbox_time = gtk.HBox()
        self.vbox_hour = gtk.VBox()
        self.vbox_minute = gtk.VBox()
        self.vbox_second = gtk.VBox()
        self.hbox_control = gtk.HBox()

        self.label_hour   = gtk.Label("Hour")
        self.label_minute = gtk.Label("Minute")
        self.label_second = gtk.Label("Second")
        self.spinbutton_hour   = gtk.SpinButton()
        self.spinbutton_minute = gtk.SpinButton()
        self.spinbutton_second = gtk.SpinButton()
        self.button_today  = gtk.Button(label="Today",  stock=None, use_underline=True)
        self.button_ok     = gtk.Button(label="OK",     stock=None, use_underline=True)
        self.button_cancel = gtk.Button(label="Cancel", stock=None, use_underline=True)

        self.calendar = gtk.Calendar()

        self.window.add( self.vbox_date_time )
        self.vbox_date_time.add( self.calendar )
        self.vbox_date_time.add( self.hbox_time )
        self.vbox_date_time.add( self.hbox_control )
        self.hbox_time.add( self.vbox_hour )
        self.hbox_time.add( self.vbox_minute )
        self.hbox_time.add( self.vbox_second )

        self.vbox_hour.add( self.label_hour )
        self.vbox_hour.add( self.spinbutton_hour )
        self.vbox_minute.add( self.label_minute )
        self.vbox_minute.add( self.spinbutton_minute )
        self.vbox_second.add( self.label_second )
        self.vbox_second.add( self.spinbutton_second )
        self.hbox_control.pack_start( self.button_today,  True, True, 0 )
        self.hbox_control.pack_start( self.button_ok,     True, True, 0 )
        self.hbox_control.pack_end(   self.button_cancel, True, True, 0 )

        self.spinbutton_hour.set_range(0,23)
        self.spinbutton_minute.set_range(0,59)
        self.spinbutton_second.set_range(0,59)

        self.spinbutton_hour.set_increments(1,5)
        self.spinbutton_minute.set_increments(1,5)
        self.spinbutton_second.set_increments(1,5)

        # Setup our signals
        self.window.connect( "destroy_event", self.callback_complete, None )
        self.window.connect( "delete_event", self.callback_complete, None )

        self.calendar.connect( "day-selected", self.callback_update_time, None )
        self.calendar.connect( "day-selected-double-click", self.callback_update_time, None )
        self.calendar.connect( "month-changed", self.callback_update_time, None )
        self.calendar.connect( "next-month", self.callback_update_time, None )
        self.calendar.connect( "prev-month", self.callback_update_time, None )
        self.calendar.connect( "next-year", self.callback_update_time, None )
        self.calendar.connect( "prev-year", self.callback_update_time, None )
        self.spinbutton_hour.connect( "value-changed", self.callback_update_time, None )
        self.spinbutton_minute.connect( "value-changed", self.callback_update_time, None )
        self.spinbutton_second.connect( "value-changed", self.callback_update_time, None )
        self.button_today.connect(  "clicked", self.callback_today,    None )
        self.button_ok.connect(     "clicked", self.callback_complete, None )
        self.button_cancel.connect( "clicked", self.callback_cancel,   None )

        # Show our contents
        self.window.show_all()
        self.push_time()

    def set_granularity(self, granule):
        if self.granules.has_key(granule):
            self.granularity = granule

    def get_granularity(self):
        return self.granularity

    def get_granule(self, granule):
        if self.granules.has_key(granule):
            return self.granules[granule]
        return 0

    def current_granule(self):
        if self.granules.has_key(self.granularity):
            return self.granules[self.granularity]
        return 0

    def set_default_high(self, high=True):
        self.time_high = high

    def get_default_high(self):
        return self.time_high
        
    def delete_window(self):
        if not self.running:
            return
        self.window.hide_all()
        del self.window
        self.window = None
        self.running = False

    def callback_update_time(self, widget, event, data=None):
        if not self.calendar or self.pushing:
            return
        (year, month, day) = self.calendar.get_date()
        self.timestamp['year']   = year
        self.timestamp['month']  = month + 1
        self.timestamp['day']    = day
        if self.current_granule() <= self.get_granule('hour'):
            self.timestamp['hour'] = int(self.spinbutton_hour.get_value())
        elif self.time_high:
            self.timestamp['hour'] = 23
        else:
            self.timestamp['hour'] = 0

        if self.current_granule() <= self.get_granule('minute'):
            self.timestamp['minute'] = int(self.spinbutton_minute.get_value())
        elif self.time_high:
            self.timestamp['minute'] = 59
        else:
            self.timestamp['minute'] = 0

        if self.current_granule() <= self.get_granule('second'):
            self.timestamp['second'] = int(self.spinbutton_second.get_value())
        elif self.time_high:
            self.timestamp['second'] = 59
        else:
            self.timestamp['second'] = 0

    def callback_today(self, widget=None, event=None, data=None):
        times = time.gmtime()
        self.timestamp = { 'year'   : times[0] ,
                           'month'  : times[1] ,
                           'day'    : times[2] ,
                           'hour'   : times[3] ,
                           'minute' : times[4] ,
                           'second' : times[5] }
        self.push_time()

    def callback_complete(self, widget=None, event=None, data=None):
        if self.completion_data is None:
            self.completion_callback()
        else:
            self.completion_callback( self.completion_data )
        self.delete_window()

    def set_callback_complete(self, callback, data=None):
        self.completion_callback = callback
        self.completion_data = data

    def callback_cancel(self, widget=None, event=None, data=None):
        if self.cancel_data is None:
            self.cancel_callback()
        else:
            self.cancel_callback( self.completion_data )
        self.delete_window()

    def set_callback_cancel(self, callback, data=None):
        self.cancel_callback = callback
        self.cancel_data = data

    def push_time(self):
        self.pushing = True
        self.calendar.select_month(self.timestamp['month'] - 1, self.timestamp['year'])
        self.calendar.select_day(self.timestamp['day'])
        if self.current_granule() <= self.get_granule('hour'):
            self.spinbutton_hour.set_value(self.timestamp['hour'])
        if self.current_granule() <= self.get_granule('minute'):
            self.spinbutton_minute.set_value(self.timestamp['minute'])
        if self.current_granule() <= self.get_granule('second'):
            self.spinbutton_second.set_value(self.timestamp['second'])
        self.pushing = False

    def prompt(self):
        self.create_window()

    def get_date(self):
        date_str = "%(year)04d/%(month)02d/%(day)02d %(hour)02d:%(minute)02d:%(second)02d UTC" % self.timestamp
        date = time.strptime(date_str,"%Y/%m/%d %H:%M:%S %Z")
        return date

    def set_date(self, date):
        self.timestamp['year']   = date[0]
        self.timestamp['month']  = date[1]
        self.timestamp['day']    = date[2]
        if self.current_granule() <= self.get_granule('hour'):
            self.timestamp['hour']   = date[3]
        elif self.time_high:
            self.timestamp['hour'] = 23
        else:
            self.timestamp['hour'] = 0

        if self.current_granule() <= self.get_granule('minute'):
            self.timestamp['minute'] = date[4]
        elif self.time_high:
            self.timestamp['minute'] = 59
        else:
            self.timestamp['minute'] = 0

        if self.current_granule() <= self.get_granule('second'):
            self.timestamp['second'] = date[5]
        elif self.time_high:
            self.timestamp['second'] = 59
        else:
            self.timestamp['second'] = 0


class Counter:
    def __init__(self, value=0, stride=1):
        self.stride = stride
        self.original = value
        self.reset()

    def reset(self):
        self.value = self.original

    def set_value(self, value):
        self.value = value

    def set_stride(self, stride):
        self.stride = stride

    def inc(self):
        self.value += 1
        return self.value

    def dec(self):
        self.value -= 1
        return self.value

    def inc_p(self):
        temp = self.value
        self.value += 1
        return temp

    def dec_p(self):
        temp = self.value
        self.value -= 1
        return temp


class ORGUI:
    def __init__(self):
        self.stations = [
            'AFI' , 'ANMO', 'DAV' , 'FURI', 'GNI' , 'GUMO', 
            'HNR' , 'KOWA', 'KMBO', 'LVC' , 'LSZ' , 'MSKU', 
            'PMG' , 'PMSA', 'PTGA', 'QSPA', 'RAO' , 'RAR' , 
            'RCBR', 'SDV' , 'SFJD', 'SJG' , 'TEIG', 'TSUM',
        ]

# ===== Widget Creation ============================================
      # Layout Control Widgets
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Calibrations")

        self.vbox_main   = gtk.VBox()

        self.table_options = gtk.Table(rows=5, columns=4)
        self.hbox_message  = gtk.HBox()
        self.hbox_display  = gtk.HBox()
        self.hbox_control  = gtk.HBox()

      # User Interaction Widgets
        self.checkbutton_update = gtk.CheckButton()
        self.label_update       = gtk.Label("Update Message")

        self.label_station    = gtk.Label("Station:")
        self.combobox_station = gtk.combo_box_new_text()

        self.label_submitter = gtk.Label("Submitter:")
        self.entry_submitter = gtk.Entry()

        self.label_start_date  = gtk.Label("Start Date:")
        self.entry_start_date  = gtk.Entry()
        self.button_start_date = gtk.Button(label="...", stock=None, use_underline=True)

        self.checkbutton_end_date = gtk.CheckButton()
        self.label_end_date       = gtk.Label("End Date:")
        self.entry_end_date       = gtk.Entry()
        self.button_end_date      = gtk.Button(label="...", stock=None, use_underline=True)

        self.textbuffer_message = gtk.TextBuffer()
        self.textview_message   = gtk.TextView(buffer=self.textbuffer_message)
        self.scrolledwindow_message = gtk.ScrolledWindow()
        self.scrolledwindow_message.add(self.textview_message)

        self.textbuffer_display = gtk.TextBuffer()
        self.textview_display   = gtk.TextView(buffer=self.textbuffer_display)
        self.scrolledwindow_display = gtk.ScrolledWindow()
        self.scrolledwindow_display.add(self.textview_display)

        self.button_copy = gtk.Button(label="Copy", stock=None, use_underline=True)
        self.button_quit = gtk.Button(label="Quit", stock=None, use_underline=True)

# ===== Layout Configuration =======================================
        self.window.add(self.vbox_main)
        #self.window.set_size_request(350, 550)

        self.vbox_main.pack_start(self.table_options, False, True, 0)
        self.vbox_main.pack_start(self.hbox_message,  True,  True, 0)
        self.vbox_main.pack_start(self.hbox_display,  True,  True, 0)
        self.vbox_main.pack_start(self.hbox_control,  False, True, 0)

        # left, right, top, bottom, xoptions, yoptions, xpadding, ypadding
        self.table_options.attach(align(self.checkbutton_update),   0, 1, 0, 1, gtk.FILL, 0, 1, 1)
        self.table_options.attach(align(self.label_update),         1, 2, 0, 1, gtk.FILL, 0, 1, 1)

        self.table_options.attach(align(self.label_station),        1, 2, 1, 2, gtk.FILL, 0, 1, 1)
        self.table_options.attach(align(self.combobox_station),     2, 3, 1, 2, gtk.FILL, 0, 1, 1)

        self.table_options.attach(align(self.label_submitter),      1, 2, 2, 3, gtk.FILL, 0, 1, 1)
        self.table_options.attach(align(self.entry_submitter),      2, 3, 2, 3, gtk.FILL, 0, 1, 1)

        self.table_options.attach(align(self.label_start_date),     1, 2, 3, 4, gtk.FILL, 0, 1, 1)
        self.table_options.attach(align(self.entry_start_date),     2, 3, 3, 4, gtk.FILL, 0, 1, 1)
        self.table_options.attach(align(self.button_start_date),    3, 4, 3, 4, gtk.FILL, 0, 1, 1)

        self.table_options.attach(align(self.checkbutton_end_date), 0, 1, 4, 5, gtk.FILL, 0, 1, 1)
        self.table_options.attach(align(self.label_end_date),       1, 2, 4, 5, gtk.FILL, 0, 1, 1)
        self.table_options.attach(align(self.entry_end_date),       2, 3, 4, 5, gtk.FILL, 0, 1, 1)
        self.table_options.attach(align(self.button_end_date),      3, 4, 4, 5, gtk.FILL, 0, 1, 1)

        self.hbox_message.pack_start(self.scrolledwindow_message, True, True, 0)
        self.hbox_display.pack_start(self.scrolledwindow_display, True, True, 0)

        self.hbox_control.pack_start(self.button_copy, False, False, 0)
        self.hbox_control.pack_end(self.button_quit,   False, False, 0)

# ===== Widget Configurations ======================================
        self.checkbutton_update.set_active(False)

        for t in self.stations:
            self.combobox_station.append_text(t)
        self.combobox_station.set_active(0)

        self.entry_submitter.set_text('Joel Edwards')

        self.entry_start_date.set_max_length(19)
        self.entry_start_date.set_text(time.strftime("%Y/%m/%d 15:00:00", time.gmtime()))

        self.checkbutton_end_date.set_active(False)
        self.entry_end_date.set_max_length(19)
        self.entry_end_date.set_text('')

        self.textbuffer_message.set_text('')
        self.textview_message.set_editable(True)
        self.textview_message.set_size_request(-1, 200)

        self.textbuffer_display.set_text('')
        self.textview_display.set_editable(False)
        self.textview_display.set_size_request(-1, 200)

        self.button_copy.set_sensitive(False)

# ===== Hidden Objects =============================================
        self.clipboard = gtk.Clipboard()
        self.window_start_date = DateTimeWindow()
        self.window_start_date.set_granularity("second")
        self.window_start_date.set_callback_complete(self.callback_start_date_complete)
        self.window_start_date.set_callback_cancel(self.callback_start_date_cancel)

        self.clipboard = gtk.Clipboard()
        self.window_end_date = DateTimeWindow()
        self.window_end_date.set_granularity("second")
        self.window_end_date.set_callback_complete(self.callback_end_date_complete)
        self.window_end_date.set_callback_cancel(self.callback_end_date_cancel)

# ===== Signal Bindings ============================================

# ===== Event Bindings =============================================
        self.window.connect("destroy-event", self.callback_quit, None)
        self.window.connect("delete-event",  self.callback_quit, None)

        #self.label_update.connect("button-release-event", self.callback_label_toggle, None, self.checkbutton_update)
        #self.label_end_date.connect("button-release-event", self.callback_label_toggle, None, self.checkbutton_end_date)
        self.checkbutton_update.connect("toggled", self.callback_toggled, None)
        self.checkbutton_end_date.connect("toggled", self.callback_toggled, None)

        self.combobox_station.connect("changed", self.callback_generate, None)
        self.entry_submitter.connect("changed", self.callback_generate, None)
        self.entry_start_date.connect("changed", self.callback_start_date_changed, None)
        self.entry_end_date.connect("changed", self.callback_end_date_changed, None)
        self.button_start_date.connect("clicked", self.callback_start_date, None)
        self.button_end_date.connect("clicked", self.callback_end_date, None)
        self.textbuffer_message.connect("changed", self.callback_generate, None)

        self.button_copy.connect("clicked", self.callback_copy, None)
        self.button_quit.connect("clicked", self.callback_quit, None)

# ===== Event Bindings =============================================
        self.window.connect("key-press-event", self.callback_key_pressed)

      # Show widgets
        self.window.show_all()
        self.update_interface()
        self.generate()
        self.callback_start_date_changed(None, None, None)
        self.callback_end_date_changed(None, None, None)

# ===== Callbacks ==================================================
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

    def callback_generate(self, widget, event, data=None):
        self.generate()

    def callback_start_date_changed(self, widget, event, data=None):
        time_string = self.entry_start_date.get_text() + " UTC"
        try:
            date = time.strptime(time_string,"%Y/%m/%d %H:%M:%S %Z")
            self.window_start_date.set_date(date)
            self.generate()
        except ValueError:
            pass

    def callback_end_date_changed(self, widget, event, data=None):
        time_string = self.entry_end_date.get_text() + " UTC"
        try:
            date = time.strptime(time_string,"%Y/%m/%d %H:%M:%S %Z")
            self.window_end_date.set_date(date)
            self.generate()
        except ValueError:
            pass

    def callback_start_date(self, widget, event, data=None):
        self.window_start_date.create_window()
        self.generate()

    def callback_start_date_complete(self):
        self.entry_start_date.set_text(time.strftime("%Y/%m/%d %H:%M:%S", self.window_start_date.get_date()))

    def callback_start_date_cancel(self):
        time_string = self.entry_start_date.get_text() + " UTC"
        date = time.strptime(time_string,"%Y/%m/%d %H:%M:%S %Z")
        self.window_start_date.set_date(date)
        self.generate()

    def callback_end_date(self, widget, event, data=None):
        self.window_end_date.create_window()
        self.generate()

    def callback_end_date_complete(self):
        self.entry_end_date.set_text(time.strftime("%Y/%m/%d %H:%M:%S", self.window_end_date.get_date()))

    def callback_end_date_cancel(self):
        time_string = self.entry_end_date.get_text() + " UTC"
        date = time.strptime(time_string,"%Y/%m/%d %H:%M:%S %Z")
        self.window_end_date.set_date(date)
        self.generate()

    def callback_toggled(self, widget, event, data=None):
        self.update_interface()
        self.generate()

    def callback_label_toggle(self, widget, event, data=None):
        print data
        if data:
            data.toggled()

# ===== Methods ====================================================
    def generate(self):
        message = ""
        s,e = self.textbuffer_message.get_bounds()
        msg = self.textbuffer_message.get_text(s,e)
        if self.checkbutton_update.get_active():
            message += "#Description:\n"
            message += "%s\n" % msg
            message += "\n"
            message += "#Submitted by\n"
            message += "%s\n" % self.entry_submitter.get_text()
            message += "\n"
            message += "#End\n"
            message += "\n"
        else:
            station  = self.combobox_station.get_active_text()
            message += "TO:   support@ctbto.org\n"
            message += "SUBJ: Report - Outage Request - %s\n" % station
            message += "\n"
            message += "-------------------------------------------------\n"
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
            message += "%s\n" % self.entry_submitter.get_text()
            message += "\n"
            message += "#Heading\n"
            message += "Calibration of sensors at %s\n" % station
            message += "\n"
            message += "#Station reference\n"
            message += "OR %s\n" % station
            message += "\n"
            date = self.entry_start_date.get_text()
            if len(date) > 2:
                date = date[:-3]
            message += "#Start date of requested outage\n"
            message += "%s\n" % date
            message += "\n"
            if self.checkbutton_end_date.get_active():
                date = self.entry_end_date.get_text()
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
            message += "#Description: reason for outage\n"
            message += "%s\n" % msg
            message += "\n"
        #s,e = self.textbuffer_display.get_bounds()
        #self.textbuffer_display.delete(s,e)
        self.textbuffer_display.set_text(message)
            

    def update_interface(self):
        if self.checkbutton_update.get_active():
            self.label_station.hide()
            self.combobox_station.hide()
            self.label_start_date.hide()
            self.entry_start_date.hide()
            self.button_start_date.hide()
            self.checkbutton_end_date.hide()
            self.label_end_date.hide()
            self.entry_end_date.hide()
            self.button_end_date.hide()
        else:
            self.label_station.show()
            self.combobox_station.show()
            self.label_start_date.show()
            self.entry_start_date.show()
            self.button_start_date.show()
            self.checkbutton_end_date.show()
            self.label_end_date.show()
            if self.checkbutton_end_date.get_active():
                self.entry_end_date.show()
                self.button_end_date.show()
                self.label_end_date.set_text('End Date:')
            else:
                self.entry_end_date.hide()
                self.button_end_date.hide()
                self.label_end_date.set_text('End Date')
        s,e = self.textbuffer_display.get_bounds()
        if len(self.textbuffer_display.get_text(s,e)):
            self.button_copy.set_sensitive(True)
        else:
            self.button_copy.set_sensitive(False)
        #w,h = self.window.size_request()
        #self.window.resize(w,h)
        self.window.resize_children()

    def text_to_clipboard(self):
        s,e = self.textbuffer_display.get_bounds()
        self.clipboard.set_text(self.textbuffer_display.get_text(s,e))

    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        return False

def align(widget):
    alignment = gtk.Alignment()
    alignment.add(widget)
    return alignment

if __name__ == "__main__":
    reader = ORGUI()
    gtk.main()

