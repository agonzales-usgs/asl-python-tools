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
gtk.gdk.threads_init()

from jtk.gtk.utils import LEFT,RIGHT
from jtk.StatefulClass import StatefulClass

# === DateTimeWindow Class /*{{{*/
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
# /*}}}*/

# === Counter Class /*{{{*/
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
# /*}}}*/

# === IMSGUI Class /*{{{*/
class IMSGUI:
    def __init__(self):
        home_dir = '.'
        if os.environ.has_key('HOME'):
            home_dir = os.environ['HOME']
        elif os.environ.has_key('USERPROFILE'):
            home_dir = os.environ['USERPROFILE']
        pref_file = os.path.abspath("%s/.ims-gui-prefs.db" % home_dir)
        self._prefs = StatefulClass(pref_file)

        self._minimum_width  = 640
        self._minimum_height = 640
        self._default_width = self._prefs.recall_value('window-width', self._minimum_width)
        self._default_height = self._prefs.recall_value('window-height', self._minimum_height)

        self.commands = [
            'CALIBRATE_START',
            'CALIBRATE_CONFIRM',
            'CALIBRATE_RESULT',
        ]

        self.channels = ['HH', 'BH', 'SH', 'LH', 'VH', 'UH']
        self.axes     = ['Z', '1', '2', 'N', 'E']

        self.stations = [
            'AFI' , 'ANMO', 'CTAO', 'DAV' , 'FURI', 'GNI' ,
            'GUMO', 'HNR' , 'KOWA', 'KMBO', 'LVC' , 'LSZ' ,
            'MSKU', 'NWAO', 'PMG' , 'PMSA', 'PTGA', 'QSPA',
            'RAO' , 'RAR' , 'RCBR', 'SDV' , 'SFJD', 'SJG' ,
            'TEIG', 'TSUM',
        ]

        key_counter = Counter()

        self.box_keys = {
            'ALL' : {
                'MSG_ID'        : key_counter.inc_p(),
                'REF_ID'        : key_counter.inc_p(),
                'EMAIL'         : key_counter.inc_p(),
                'START_TIME'    : key_counter.inc_p(),
                'CALIB_PARAM'   : key_counter.inc_p(),
                'STA_LIST'      : key_counter.inc_p(),
                'CHAN_LIST'     : key_counter.inc_p(),
                'CHANNELS'      : key_counter.inc_p(),
                'SENSOR'        : key_counter.inc_p(),
                'TYPE'          : key_counter.inc_p(),
                'CALIB'         : key_counter.inc_p(),
                'CALPER'        : key_counter.inc_p(),
                #'RESPONSE'      : key_counter.inc_p(),
                'IN_SPEC'       : key_counter.inc_p(),
            },
            'CALIBRATE_START' : {
                'message-type' : 'COMMAND_REQUEST',
                'EMAIL' : None,
                'START_TIME' : None,
                'CALIB_PARAM' : None,
                'STA_LIST' : None,
                'CHAN_LIST' : None,
                'CHANNELS' : None,
                'SENSOR' : None,
                #'TYPE' : None,
            },
            'CALIBRATE_CONFIRM' : {
                'message-type' : 'COMMAND_RESPONSE',
                'REF_ID' : None,
                'STA_LIST' : None,
                'CHAN_LIST' : None,
                'START_TIME' : None,
                'CHANNELS' : None,
            },
            'CALIBRATE_RESULT' : {
                'message-type' : 'COMMAND_RESPONSE',
                'REF_ID' : None,
                'STA_LIST' : None,
                'CHAN_LIST' : None,
                'CHANNELS' : None,
                'IN_SPEC' : None,
                'CALIB' : None,
                'CALPER' : None,
                #'RESPONSE' : None,
            },
        }

# ===== Widget Creation ============================================
      # Layout Control Widgets
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Calibrations")
        self.window.set_geometry_hints(min_width=self._default_width, min_height=self._default_height)
        self.window.connect( "configure-event", self.callback_window_configured, None )
        self.window.connect( "screen-changed", self.callback_window_configured, None )
        self.window.connect( "window-state-event", self.callback_window_configured, None )

        self.vbox_main   = gtk.VBox()
        self.vbox_top    = gtk.VBox()
        self.vbox_bottom = gtk.VBox()

        self.table_parts = gtk.Table()
        self.vbox_channels = gtk.VBox()
        self.hbox_display = gtk.HBox()
        self.hbox_control = gtk.HBox()

        self.boxes = {}
        self.boxes['CHANNELS'] = [self.vbox_channels]

      # User Interaction Widgets
        self.label_command = gtk.Label("Command:")
        self.combobox_command = gtk.combo_box_new_text()

        self.label_email = gtk.Label("E-mail:")
        self.entry_email = gtk.Entry()

        self.label_start_time  = gtk.Label("Start Time:")
        self.entry_start_time  = gtk.Entry()
        self.button_start_time = gtk.Button()
        self.image_start_time  = gtk.Image()
        self.image_start_time.set_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_MENU)
        self.button_start_time.add(self.image_start_time)

        self.label_stations     = gtk.Label("Station:")
        self.combobox_stations  = gtk.combo_box_new_text()

        self.label_channels     = gtk.Label("Channels:")
        self.button_add_channel = gtk.Button(stock=None, use_underline=True)
        self.hbox_add_channel   = gtk.HBox()
        self.image_add_channel  = gtk.Image()
        self.image_add_channel.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_MENU)
        self.label_add_channel  = gtk.Label('Add Channel')
        self.button_add_channel.add(self.hbox_add_channel)
        self.hbox_add_channel.pack_start(self.image_add_channel, padding=1)
        self.hbox_add_channel.pack_start(self.label_add_channel, padding=1)

        self.checkbutton_sensor = gtk.CheckButton(label="Include Sensor")

        self.label_duration = gtk.Label("Duration:")
        self.sample_duration = gtk.Entry()
        self.adjustment_duration = gtk.Adjustment(value=85680.0, lower=0, upper=2**32, step_incr=60, page_incr=3600)
        self.spinbutton_duration = gtk.SpinButton(self.adjustment_duration)
        self.spacer_duration = gtk.Label("")

        #self.label_cal_type    = gtk.Label("Cal. Type:")
        #self.combobox_cal_type = gtk.combo_box_new_text()

        self.checkbutton_spec = gtk.CheckButton(label="In Specification")

        self.textbuffer_display = gtk.TextBuffer()
        self.textview_display   = gtk.TextView(buffer=self.textbuffer_display)
        self.scrolledwindow_display = gtk.ScrolledWindow()
        self.scrolledwindow_display.add(self.textview_display)

        self.button_copy = gtk.Button(stock=None, use_underline=True)
        self.hbox_copy   = gtk.HBox()
        self.image_copy  = gtk.Image()
        self.image_copy.set_from_stock(gtk.STOCK_COPY, gtk.ICON_SIZE_MENU)
        self.label_copy  = gtk.Label('Copy')
        self.button_copy.add(self.hbox_copy)
        self.hbox_copy.pack_start(self.image_copy, padding=1)
        self.hbox_copy.pack_start(self.label_copy, padding=1)

        self.button_send_email = gtk.Button(stock=None, use_underline=True)
        self.hbox_send_email   = gtk.HBox()
        self.image_send_email  = gtk.Image()
        self.image_send_email.set_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)
        self.label_send_email  = gtk.Label('E-mail')
        self.button_send_email.add(self.hbox_send_email)
        self.hbox_send_email.pack_start(self.image_send_email, padding=1)
        self.hbox_send_email.pack_start(self.label_send_email, padding=1)

        self.button_quit = gtk.Button(stock=None, use_underline=True)
        self.hbox_quit   = gtk.HBox()
        self.image_quit  = gtk.Image()
        self.image_quit.set_from_stock(gtk.STOCK_QUIT, gtk.ICON_SIZE_MENU)
        self.label_quit  = gtk.Label('Quit')
        self.button_quit.add(self.hbox_quit)
        self.hbox_quit.pack_start(self.image_quit, padding=1)
        self.hbox_quit.pack_start(self.label_quit, padding=1)

# ===== Layout Configuration =======================================
        self.window.add(self.vbox_main)

        self.vbox_main.pack_start(self.vbox_top,    False, True, 0)
        self.vbox_main.pack_start(self.vbox_bottom, True,  True, 0)

        self.vbox_top.pack_start(self.table_parts, False, True, 0)
        self.vbox_top.pack_start(self.vbox_channels, False, True, 0)
        self.vbox_bottom.pack_start(self.hbox_display, True,  True, 0)
        self.vbox_bottom.pack_start(self.hbox_control, False, True, 0)

        self.table_parts.attach(LEFT(self.label_command),       0, 1, 0, 1, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(LEFT(self.combobox_command),    1, 4, 0, 1, gtk.FILL, 0, 1, 1)

        self.boxes['MSG_ID'] = []
        self.boxes['REF_ID'] = []

        self.boxes['EMAIL'] = [self.label_email, self.entry_email]
        self.table_parts.attach(LEFT(self.label_email),         0, 1, 1, 2, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(self.entry_email,               1, 4, 1, 2, gtk.FILL | gtk.EXPAND, 0, 1, 1)

        self.boxes['START_TIME'] = [self.label_start_time, self.button_start_time, self.entry_start_time]
        self.table_parts.attach(LEFT(self.label_start_time),    0, 1, 2, 3, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(self.entry_start_time,          1, 4, 2, 3, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_parts.attach(self.button_start_time,         4, 5, 2, 3, 0, 0, 1, 1)

        self.boxes['STA_LIST'] = [self.label_stations, self.combobox_stations]
        self.table_parts.attach(LEFT(self.label_stations),      0, 1, 3, 4, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(LEFT(self.combobox_stations),   1, 4, 3, 4, gtk.FILL, 0, 1, 1)

        self.boxes['SENSOR'] = [self.checkbutton_sensor]
        self.table_parts.attach(LEFT(self.checkbutton_sensor),  0, 4, 4, 5, gtk.FILL, 0, 1, 1)

        self.boxes['TYPE'] = []
        #self.boxes['TYPE'] = [self.label_cal_type, self.combobox_cal_type]
        #self.table_parts.attach(LEFT(self.label_cal_type),      0, 1, 5, 6, gtk.FILL, 0, 1, 1)
        #self.table_parts.attach(LEFT(self.combobox_cal_type),   1, 4, 5, 6, gtk.FILL, 0, 1, 1)

        self.boxes['CALIB_PARAM'] = [self.label_duration, self.spinbutton_duration, self.sample_duration]
        self.table_parts.attach(LEFT(self.label_duration),      0, 1, 6, 7, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(LEFT(self.sample_duration),     1, 2, 6, 7, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(LEFT(self.spinbutton_duration), 2, 3, 6, 7, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(self.spacer_duration,           3, 4, 6, 7, gtk.FILL | gtk.EXPAND, 0, 1, 1)

        self.boxes['CALIB'] = []
        self.boxes['CALPER'] = []

        self.boxes['IN_SPEC'] = [self.checkbutton_spec]
        self.table_parts.attach(LEFT(self.checkbutton_spec),    0, 4, 7, 8, gtk.FILL, 0, 1, 1)

        self.boxes['CHAN_LIST'] = [self.label_channels, self.button_add_channel]
        self.table_parts.attach(LEFT(self.label_channels),      0, 1, 8, 9, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(RIGHT(self.button_add_channel),3, 5, 8, 9, gtk.FILL, 0, 1, 1)

        self.hbox_display.pack_start(self.scrolledwindow_display, True, True, 0)

        self.hbox_control.pack_start(self.button_copy, False, False, 0)
        self.hbox_control.pack_start(self.button_send_email, False, False, 0)
        self.hbox_control.pack_end(self.button_quit,   False, False, 0)

# ===== Widget Configurations ======================================
        for t in self.commands:
            self.combobox_command.append_text(t)
        self.combobox_command.set_active(1)
        self.entry_email.set_text('gsnmaint@usgs.gov')
        self.entry_start_time.set_text(time.strftime("%Y/%m/%d 15:00:00", time.gmtime()))
        for t in self.stations:
            self.combobox_stations.append_text(t)
        self.combobox_stations.set_active(0)
        self.checkbutton_sensor.set_active(True)
        self.checkbutton_spec.set_active(True)
        self.textbuffer_display.set_text('')
        self.textview_display.set_editable(False)
        self.sample_duration.set_editable(False)
        self.button_copy.set_sensitive(False)
        self.button_send_email.set_sensitive(False)

        self.textview_display.set_size_request(-1, 300)

# ===== Hidden Objects =============================================
        self.clipboard = gtk.Clipboard()
        self.time_window = DateTimeWindow()
        self.time_window.set_granularity("second")
        self.time_window.set_callback_complete(self.callback_time_window_complete)
        self.time_window.set_callback_cancel(self.callback_time_window_cancel)

# ===== Signal Bindings ============================================

# ===== Event Bindings =============================================
        self.window.connect("destroy-event", self.callback_quit, None)
        self.window.connect("delete-event",  self.callback_quit, None)

        self.combobox_command.connect(   "changed", self.callback_command,      None)
        self.entry_email.connect(        "changed", self.callback_generate,     None)
        self.entry_start_time.connect(   "changed", self.callback_time_changed, None)
        self.button_start_time.connect(  "clicked", self.callback_start_time,   None)
        self.combobox_stations.connect(  "changed", self.callback_generate,     None)
        self.button_add_channel.connect("clicked", self.callback_add_channel,  None)
        self.checkbutton_sensor.connect( "toggled", self.callback_generate,     None)
        self.checkbutton_spec.connect(   "toggled", self.callback_generate,     None)
        self.spinbutton_duration.connect("value-changed", self.callback_generate, None)

        self.button_copy.connect("clicked", self.callback_copy, None)
        self.button_send_email.connect("clicked", self.callback_email, None)
        self.button_quit.connect("clicked", self.callback_quit, None)

# ===== Event Bindings =============================================
        self.window.connect("key-press-event", self.callback_key_pressed)

      # Show widgets
        self.window.show_all()
        self.channel_counter = Counter()
        self.channel_widgets = {}
        self.generate()
        self.update_interface()
        self.callback_time_changed(None, None, None)

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

# ===== Callbacks ==================================================
    def callback_window_configured(self, widget, event, data=None):
        gravity  = str(int(self.window.get_gravity()))
        position = '%d,%d' % self.window.get_position()
        size     = '%d,%d' % self.window.get_size()
        state    = 'NORMAL'
        if self.window.get_state() & gtk.gdk.WINDOW_STATE_FULLSCREEN:
            state = 'FULLSCREEN'
        elif self.window.get_state() & gtk.gdk.WINDOW_STATE_MAXIMIZED:
            state = 'MAXIMIZED'
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

    def callback_add_channel(self, widget, event, data=None):
        self._add_channel()
        self.generate()
        self.update_interface

    def callback_delete_channel(self, widget, event, data=None):
        self._del_channel(data)
        self.generate()
        self.update_interface
                
    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, event, data)

    def callback_location(self, widget, event, data=None):
        if widget.get_value() < 10:
            widget.set_text("%02d" % widget.get_value())
        self.callback_generate(widget, event, data)

    def callback_command(self, widget, event, data=None):
        self.update_interface()
        self.callback_generate(widget, event, data)

    def callback_copy(self, widget, event, data=None):
        self.text_to_clipboard()

    def callback_email(self, widget, event, data=None):
        self.mailto()

    def callback_generate(self, widget, event, data=None):
        self.generate()
        self.update_interface

    def callback_time_changed(self, widget, event, data=None):
        time_string = self.entry_start_time.get_text() + " UTC"
        try:
            date = time.strptime(time_string,"%Y/%m/%d %H:%M:%S %Z")
            self.time_window.set_date(date)
            self.generate()
            self.update_interface()
        except ValueError:
            pass

    def callback_start_time(self, widget, event, data=None):
        self.time_window.create_window()
        self.generate()
        self.update_interface()

    def callback_channel_toggle(self, widget, event, data=None):
        if data:
            channel = self.channel_widgets[data]
            channel['spinbutton'].set_sensitive(channel['checkbutton-channel'].get_active())
        self.generate()
        self.update_interface()

    def callback_time_window_complete(self):
        self.entry_start_time.set_text(time.strftime("%Y/%m/%d %H:%M:%S", self.time_window.get_date()))

    def callback_time_window_cancel(self):
        time_string = self.entry_start_time.get_text() + " UTC"
        date = time.strptime(time_string,"%Y/%m/%d %H:%M:%S %Z")
        self.time_window.set_date(date)
        self.generate()
        self.update_interface()

    def callback_calarg_changed(self, widget, event, data=None):
        #text = widget.get_text()
        #if data is not None:
        #    chan_key,entry = data.split(':', 1)
        #    channel = self.channel_widgets[int(chan_key)]
        #    if text == widget._hint_text:
        #        text = ''
        self.generate()

    def callback_calarg_focus_out(self, widget, event, data=None):
        self.hint_text_show(widget)

    def callback_calarg_focus_in(self, widget, event, data=None):
        self.hint_text_hide(widget)


# ===== Methods ====================================================
    def hint_text_show(self, widget):
        if not len(widget.get_text()):
            widget.set_text(widget._hint_text)
            widget.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('#888888'))

    def hint_text_hide(self, widget):
        if widget.get_text() == widget._hint_text:
            widget.set_text('')
        widget.modify_text(gtk.STATE_NORMAL, gtk.gdk.Color())

    def box_keys_ordered(self, group='ALL'):
        raw_pairs = self.box_keys[group].items()
        indexed = map(lambda p: p[::-1], raw_pairs)
        ordered = sorted(indexed)
        keys_only = map(lambda p: p[1], ordered)
        return keys_only

    def generate(self):
        message_type = self.combobox_command.get_active_text()
        box = self.box_keys[message_type]

      # === Prepare channel list
        channel_keys = self.channel_widgets.keys()
        message = ""
        if channel_keys and len(channel_keys):
            for key in channel_keys:
                channel = self.channel_widgets[key]
                location_text = ""
                if channel["checkbutton-channel"].get_active():
                    location_text = "%02d-" % int(channel['spinbutton'].get_value())
                class_text = channel['combobox-class'].get_active_text()
                axis_text = channel['combobox-axes'].get_active_text()
                channel_string = "%s%s%s" % (location_text, class_text, axis_text)
                calib_string = channel['entry-calib'].get_text()
                if calib_string == channel['entry-calib']._hint_text:
                    calib_string = ""
                calper_string = channel['entry-calper'].get_text()
                if calper_string == channel['entry-calper']._hint_text:
                    calper_string = ""
                refid_string = channel['entry-refid'].get_text()
                if refid_string == channel['entry-refid']._hint_text:
                    refid_string = ""

              # === Construct IMS Message
                message += "BEGIN IMS2.0\n"
                message += "MSG_TYPE %s\n" % box['message-type']
                station = ''.join(self.combobox_stations.get_active_text().split('_'))
                message += "MSG_ID %s\n" % (station+ "_" +message_type+ "_" +channel_string+ "_" +time.strftime("%Y/%m/%d_%H:%M:%S", time.gmtime()),)
                if box.has_key("REF_ID"):
                    message += "REF_ID %s\n" % refid_string

                if box.has_key("EMAIL"):
                    message += "EMAIL %s\n" % self.entry_email.get_text()
                if box.has_key("TIME_STAMP"):
                    message += "TIME_STAMP %s\n" % time.strftime("%Y/%m/%d %H:%M:%S", time.gmtime())
                if box.has_key("START_TIME") and (message_type == 'CALIBRATE_START'):
                    message += "START_TIME %s\n" % self.entry_start_time.get_text()
                if box.has_key("STA_LIST"):
                    message += "STA_LIST %s\n" % self.combobox_stations.get_active_text()
                if box.has_key("CHAN_LIST"):
                    message += "CHAN_LIST %s\n" % channel_string
                if box.has_key("START_TIME") and (message_type == 'CALIBRATE_CONFIRM'):
                    message += "START_TIME %s\n" % self.entry_start_time.get_text()
                if box.has_key("SENSOR"):
                    if self.checkbutton_sensor.get_active():
                        message += "SENSOR YES\n"
                    else:
                        message += "SENSOR NO\n"
                if box.has_key("TYPE"):
                    message += "TYPE RANDOM\n"
                if box.has_key("CALIB_PARAM"):
                    duration = float(self.spinbutton_duration.get_value())
                    hours = duration / 3600
                    minutes = (duration % 3600) / 60
                    seconds = duration % 60
                    self.sample_duration.set_text("%02d:%02d:%02d" % (hours, minutes, seconds))
                    message += "CALIB_PARAM %.1f\n" % duration
                message += "%s\n" % message_type
                if box.has_key("IN_SPEC"):
                    if self.checkbutton_spec.get_active():
                        message += "IN_SPEC YES\n"
                    else:
                        message += "IN_SPEC NO\n"
                if box.has_key("CALIB") and len(calib_string):
                    message += "CALIB %s\n" % calib_string
                if box.has_key("CALPER") and len(calper_string):
                    message += "CALPER %s\n" % calper_string
                #if box.has_key("RESPONSE"):
                #    message += "RESPONSE\n"
                message += "STOP\n"
                message += "\n"

        self.textbuffer_display.set_text(message)
        self.update_buttons()
            

    def _add_channel(self):
        channel_key = self.channel_counter.inc()
        channel = {}
        channel['hbox'] = gtk.HBox()
        channel['checkbutton-channel'] = gtk.CheckButton()
        channel['adjustment'] = gtk.Adjustment(value=0, lower=0, upper=99, step_incr=10, page_incr=1)
        channel['spinbutton'] = gtk.SpinButton(channel['adjustment'])
        channel['combobox-class'] = gtk.combo_box_new_text()
        for c in self.channels:
            channel['combobox-class'].append_text(c)
        channel['combobox-axes'] = gtk.combo_box_new_text()
        for axis in self.axes:
            channel['combobox-axes'].append_text(axis)
        channel['entry-calib'] = gtk.Entry()
        channel['entry-calper'] = gtk.Entry()
        channel['entry-refid'] = gtk.Entry()

        button_remove = gtk.Button(stock=None, use_underline=True)
        hbox_remove   = gtk.HBox()
        image_remove  = gtk.Image()
        image_remove.set_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
        label_remove  = gtk.Label('remove')
        button_remove.add(hbox_remove)
        hbox_remove.pack_start(image_remove, padding=1)
        hbox_remove.pack_start(label_remove, padding=1)
        channel['button'] = button_remove

        self.vbox_channels.pack_start(channel['hbox'], False, True,  0)
        channel['hbox'].pack_start(channel['checkbutton-channel'], False, False, 0)
        channel['hbox'].pack_start(channel['spinbutton'], False, False, 0)
        channel['hbox'].pack_start(channel['combobox-class'], False, False, 0)
        channel['hbox'].pack_start(channel['combobox-axes'], False, False, 0)
        channel['hbox'].pack_start(channel['entry-calib'], False, False, 0)
        channel['hbox'].pack_start(channel['entry-calper'], False, False, 0)
        channel['hbox'].pack_start(channel['entry-refid'], True, True, 0)
        channel['hbox'].pack_start(channel['button'], False, False, 0)

        channel['checkbutton-channel'].set_active(False)
        channel['spinbutton'].set_sensitive(channel['checkbutton-channel'].get_active())
        channel['combobox-class'].set_active(1)
        channel['combobox-axes'].set_active(0)
        calib_identifier = str(channel_key)+":entry-calib"
        channel['entry-calib'].set_width_chars(8)
        channel['entry-calib']._hint_text = "CALIB"
        channel['entry-calib'].connect("changed", self.callback_calarg_changed, None, calib_identifier)
        channel['entry-calib'].connect("focus-in-event", self.callback_calarg_focus_in, None)
        channel['entry-calib'].connect("focus-out-event", self.callback_calarg_focus_out, None)
        self.hint_text_show(channel['entry-calib'])

        calper_identifier = str(channel_key)+":entry-calper"
        channel['entry-calper'].set_width_chars(8)
        channel['entry-calper']._hint_text = "CALPER"
        channel['entry-calper'].connect("changed", self.callback_calarg_changed, None, calper_identifier)
        channel['entry-calper'].connect("focus-in-event", self.callback_calarg_focus_in, None)
        channel['entry-calper'].connect("focus-out-event", self.callback_calarg_focus_out, None)
        self.hint_text_show(channel['entry-calper'])

        refid_identifier = str(channel_key)+":entry-refid"
        channel['entry-refid']._hint_text = "REF_ID"
        channel['entry-refid'].connect("changed", self.callback_calarg_changed, None, refid_identifier)
        channel['entry-refid'].connect("focus-in-event", self.callback_calarg_focus_in, None)
        channel['entry-refid'].connect("focus-out-event", self.callback_calarg_focus_out, None)
        self.hint_text_show(channel['entry-refid'])

        channel['checkbutton-channel'].connect('toggled', self.callback_channel_toggle, None, channel_key)
        channel['spinbutton'].connect('value-changed', self.callback_location, None)
        channel['combobox-class'].connect('changed', self.callback_generate, None)
        channel['combobox-axes'].connect('changed', self.callback_generate, None)
        channel['button'].connect('clicked', self.callback_delete_channel, None, channel_key)
        channel['hbox'].show_all()
        channel['spinbutton'].set_text('00')

        self.channel_widgets[channel_key] = channel
        self.update_interface()

    def _del_channel(self, key):
        #if self.channel_widgets.has_key(key):
        self.channel_widgets[key]['hbox'].hide_all()
        self.vbox_channels.remove(self.channel_widgets[key]['hbox'])
        for k in self.channel_widgets[key].keys():
            del self.channel_widgets[key][k]
        del self.channel_widgets[key]
        self.update_interface()

    def update_interface(self):
        for key in self.box_keys['ALL']:
            for widget in self.boxes[key]:
                widget.hide_all()

        command_key = self.combobox_command.get_active_text()
        for key in self.box_keys['ALL'].keys():
            if self.box_keys[command_key].has_key(key):
                for widget in self.boxes[key]:
                    widget.show_all()

        self.update_buttons()
        #w,h = self.window.size_request()
        #self.window.resize(w,h)
        self.window.resize_children()

    def update_buttons(self):
        s,e = self.textbuffer_display.get_bounds()
        if len(self.textbuffer_display.get_text(s,e)) > 0:
            self.button_copy.set_sensitive(True)
            self.button_send_email.set_sensitive(True)
        else:
            self.button_copy.set_sensitive(False)
            self.button_send_email.set_sensitive(False)

    def text_to_clipboard(self):
        s,e = self.textbuffer_display.get_bounds()
        self.clipboard.set_text(self.textbuffer_display.get_text(s,e))

    def get_text_for_mail(self):
        s,e = self.textbuffer_display.get_bounds()
        return self.textbuffer_display.get_text(s,e)

    def mailto(self):
        from urllib import quote
        import webbrowser
        import string
        message_type = self.combobox_command.get_active_text()
        ims_cmd = self.box_keys[message_type]['message-type']
        station = ''.join(self.combobox_stations.get_active_text().split('_'))
        recipients = ['calibration@ctbto.org']
        field_map = {
            'replyto' : 'gsnmaint@usgs.gov',
            'cc' : 'gsn-%s@usgs.gov' % station,
            'subject' : quote('%s_%s' % (ims_cmd, station)),
            'body' : quote(self.get_text_for_mail()),
        }
        recipient_str = map(string.strip, recipients)
        fields = []
        for k,v in field_map.items():
            fields.append('%s=%s' % (k,v))

        mailto_cmd = "mailto:%s?%s" % (','.join(recipients), '&'.join(fields))
        webbrowser.open(mailto_cmd)

    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        self._prefs.save_state()
        return False
#/*}}}*/

if __name__ == "__main__":
    reader = IMSGUI()
    gtk.main()

