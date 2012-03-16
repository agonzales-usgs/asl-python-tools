#!/usr/bin/python -W all
import asl

import glob
import inspect
import math
import optparse
import os
import Queue
import re
import stat
import string
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
from jtk.gtk.Calendar import Calendar
from jtk.gtk.Dialog import Dialog
from jtk.StatefulClass import StatefulClass
from jtk.Counter import Counter
from jtk.Responses import Responses
from jtk.Responses import ResponsesThread
from jtk.Calib import Calib
from jtk.Thread import Thread


# === Progress Tools /*{{{*/
class ProgressThread(Thread):
    def __init__(self, dialog, pulse_interval=0.25):
        Thread.__init__(self, 1024, timeout=pulse_interval, timeout_message='PULSE')
        self.dialog = dialog

    def _run(self, status, data):
        count = -1
        total = -1
        done = False
        if data is not None:
            count,total,done = data
        self.dialog.update_progress(status, count, total)

    def _post(self):
        self.dialog.work_done()

class ProgressDialog(Dialog):
    def __init__(self, parent, callback, callback_data=None):
        Dialog.__init__(self, "Acquiring Reponse Data", modal=True, exit_callback=self.callback_exit, exit_data=callback_data)
        self.queue = Queue.Queue(1024)
        self.mode = "PULSE"
        self.status_counter = Counter()
        self._callback = callback

        self.progress_bar = gtk.ProgressBar()

        self.hbox_buttons.pack_start(self.progress_bar, True, True, 2)
        self.add_button_right("Cancel", self.callback_cancel)
        
        self.add_button_hidden("update", self.callback_update_progress, hide=False)
        self.add_button_hidden("done", self.callback_done)

        self.status_bar = gtk.Statusbar()
        self.vbox_main.pack_end(self.status_bar, False, True, 2)

        self.result = "UNKNOWN"

    def work_done(self):
        gobject.idle_add(gobject.GObject.emit, self._hidden_buttons['done'], 'clicked')

    def update_progress(self, message, count, total):
        self.queue.put_nowait((message, count, total))
        gobject.idle_add(gobject.GObject.emit, self._hidden_buttons['update'], 'clicked')

    def callback(self):
        self._callback(self)

    def callback_exit(self, widget, event, data=None):
        self.result = "EXITED"
        self.callback()

    def callback_update_progress(self, widget, event, data=None):
        self.update_progress_bar()

    def callback_cancel(self, widget, event, data=None):
        if self.result == "CANCELLED":
            return
        self.result = "CANCELLED"
        self.callback()

    def callback_done(self, widget, event, data=None):
        self.result = "COMPLETED"
        self.callback()

    def update_progress_bar(self):
        while not self.queue.empty():
            status,count,total = self.queue.get_nowait()
            if status == "DONE":
                self.hide_calibs_progress()
                self._calibs_thread_active = False
                break
            elif status == "PULSE":
                if self.mode == "PULSE":
                    self.progress_bar.pulse()
            else:
                self.mode = "PULSE"
                fraction = 0.0
                percent = 0.0
                show_percent = False

                progress = ""
                if count > -1:
                    if (total > 0) and (count <= total):
                        fraction = float(count) / float(total)
                        percent = fraction * 100.0
                        progress = "%d/%d (%0.1f%%)" % (count, total, percent)
                        show_percent = True
                    else:
                        progress = "%d" % count
                else:
                    progress = ""

                self.status_bar.pop(self.status_counter.value())
                self.status_bar.push(self.status_counter.inc(), status)
                self.progress_bar.set_text(progress)
                if show_percent:
                    self.progress_bar.set_fraction(fraction)
                    self.mode = "FRACTION"
                else:
                    self.progress_bar.set_pulse_step(0.5)
                    self.mode = "PULSE"
#/*}}}*/

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

        self._calibs_thread_active = False
        self._calibs_up_to_date = False

        self._responses = {}
        self._correct = False

        self.commands = [
            'CALIBRATE_START',
            'CALIBRATE_CONFIRM',
            'CALIBRATE_RESULT',
        ]

        self.channels = ['HH', 'BH', 'SH', 'LH', 'VH', 'UH']
        self.axes     = ['Z', '1', '2', 'N', 'E']

        self.stations = [
            'IU_AFI' , 'IU_ANMO', 'IU_CTAO', 'IU_DAV' , 'IU_FURI', 'IU_GNI' ,
            'IU_GUMO', 'IU_HNR' , 'IU_KOWA', 'IU_KMBO', 'IU_LVC' , 'IU_LSZ' ,
            'IU_MSKU', 'IU_NWAO', 'IU_PMG' , 'IU_PMSA', 'IU_PTGA', 'IU_QSPA',
            'IU_RAO' , 'IU_RAR' , 'IU_RCBR', 'IU_SDV' , 'IU_SFJD', 'IU_SJG' ,
            'IU_TEIG', 'IU_TSUM', 'US_ELK',  'US_NEW'
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

        self.hbox_add_channels = gtk.HBox()
        self.hbox_calper = gtk.HBox()

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
        self.spacer_channels = gtk.Label("")

        self.checkbutton_sensor = gtk.CheckButton(label="Include Sensor")

        self.label_calper = gtk.Label("CALPER: ")
        self.entry_calper = gtk.Entry()
        self.button_generate_calibs = gtk.Button(stock=None, use_underline=True)
        self.hbox_generate_calibs   = gtk.HBox()
        self.image_generate_calibs  = gtk.Image()
        self.image_generate_calibs.set_from_stock(gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU)
        self.label_generate_calibs  = gtk.Label('Derived Calibs')
        self.button_generate_calibs.add(self.hbox_generate_calibs)
        self.hbox_generate_calibs.pack_start(self.image_generate_calibs, padding=1)
        self.hbox_generate_calibs.pack_start(self.label_generate_calibs, padding=1)
        self.button_corrected_calibs = gtk.Button(stock=None, use_underline=True)
        self.hbox_corrected_calibs   = gtk.HBox()
        self.image_corrected_calibs  = gtk.Image()
        self.image_corrected_calibs.set_from_stock(gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU)
        self.label_corrected_calibs  = gtk.Label('Corrected Calibs')
        self.button_corrected_calibs.add(self.hbox_corrected_calibs)
        self.hbox_corrected_calibs.pack_start(self.image_corrected_calibs, padding=1)
        self.hbox_corrected_calibs.pack_start(self.label_corrected_calibs, padding=1)

        self.label_duration = gtk.Label("Duration:")
        self.sample_duration = gtk.Entry()
        self.adjustment_duration = gtk.Adjustment(value=86400.0, lower=0, upper=2**32, step_incr=60, page_incr=3600)
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
        self.vbox_bottom.pack_start(self.hbox_display, True,  True, 2)
        self.vbox_bottom.pack_start(self.hbox_control, False, True, 0)

        self.table_parts.attach(LEFT(self.label_command),       0, 1, 0, 1, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(LEFT(self.combobox_command),    1, 4, 0, 1, gtk.FILL, 0, 1, 1)

        self.boxes['MSG_ID'] = []
        self.boxes['REF_ID'] = []

        self.boxes['EMAIL'] = [self.label_email, self.entry_email]
        self.table_parts.attach(LEFT(self.label_email),         0, 1, 1, 2, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(self.entry_email,               1, 5, 1, 2, gtk.FILL | gtk.EXPAND, 0, 1, 1)

        self.boxes['START_TIME'] = [self.label_start_time, self.button_start_time, self.entry_start_time]
        self.table_parts.attach(LEFT(self.label_start_time),    0, 1, 2, 3, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(self.entry_start_time,          1, 5, 2, 3, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_parts.attach(self.button_start_time,         5, 6, 2, 3, 0, 0, 1, 1)

        self.boxes['STA_LIST'] = [self.label_stations, self.combobox_stations]
        self.table_parts.attach(LEFT(self.label_stations),      0, 1, 3, 4, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(LEFT(self.combobox_stations),   1, 5, 3, 4, gtk.FILL, 0, 1, 1)

        self.boxes['SENSOR'] = [self.checkbutton_sensor]
        self.table_parts.attach(LEFT(self.checkbutton_sensor),  0, 5, 4, 5, gtk.FILL, 0, 1, 1)

        self.boxes['TYPE'] = []
        #self.boxes['TYPE'] = [self.label_cal_type, self.combobox_cal_type]
        #self.table_parts.attach(LEFT(self.label_cal_type),      0, 1, 5, 6, gtk.FILL, 0, 1, 1)
        #self.table_parts.attach(LEFT(self.combobox_cal_type),   1, 4, 5, 6, gtk.FILL, 0, 1, 1)

        self.boxes['CALIB_PARAM'] = [self.label_duration, self.spinbutton_duration, self.sample_duration, self.spacer_duration]
        self.table_parts.attach(LEFT(self.label_duration),      0, 1, 6, 7, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(LEFT(self.sample_duration),     1, 2, 6, 7, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(LEFT(self.spinbutton_duration), 2, 3, 6, 7, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(self.spacer_duration,           3, 5, 6, 7, gtk.FILL | gtk.EXPAND, 0, 1, 1)

        self.boxes['CALPER'] = [self.label_calper, self.hbox_calper]
        self.hbox_calper.pack_start(self.entry_calper, False, False, 0)
        self.hbox_calper.pack_start(self.button_generate_calibs, False, False, 2)
        self.hbox_calper.pack_start(self.button_corrected_calibs, False, False, 2)
        self.table_parts.attach(LEFT(self.label_calper), 0, 1, 7, 8, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(LEFT(self.hbox_calper),  1, 4, 7, 8, gtk.FILL, 0, 1, 1)

        self.boxes['CALIB'] = []

        self.boxes['IN_SPEC'] = [self.checkbutton_spec]
        self.table_parts.attach(LEFT(self.checkbutton_spec),    0, 4, 9, 10, gtk.FILL, 0, 1, 1)

        self.boxes['CHAN_LIST'] = [self.label_channels, self.hbox_add_channels]
        self.hbox_add_channels.pack_start(self.button_add_channel, False, False, 0)
        self.hbox_add_channels.pack_start(self.spacer_channels, True, True, 0)
        self.table_parts.attach(LEFT(self.label_channels), 0, 1, 10, 11, gtk.FILL, 0, 1, 1)
        self.table_parts.attach(self.hbox_add_channels,    1, 5, 10, 11, gtk.FILL | gtk.EXPAND, 0, 1, 1)

        self.hbox_display.pack_start(self.scrolledwindow_display, True, True, 0)

        self.hbox_control.pack_start(self.button_copy, False, False, 0)
        self.hbox_control.pack_start(self.button_send_email, False, False, 0)
        self.hbox_control.pack_end(self.button_quit,   False, False, 0)

# ===== Widget Configurations ======================================
        for t in self.commands:
            self.combobox_command.append_text(t)
        self.combobox_command.set_active(2)
        self.entry_email.set_text('gsnmaint@usgs.gov')
        self.entry_start_time.set_text(time.strftime("%Y/%m/%d 15:00:00", time.gmtime()))
        for t in self.stations:
            self.combobox_stations.append_text(t)
        self.combobox_stations.set_active(0)
        self.checkbutton_sensor.set_active(True)
        self.checkbutton_spec.set_active(True)
        self.textbuffer_display.set_text('')
        self.textview_display.set_editable(False)
        self.entry_calper.set_text('1')
        self.sample_duration.set_editable(False)
        self.button_copy.set_sensitive(False)
        self.button_send_email.set_sensitive(False)

        self.textview_display.set_size_request(-1, 300)
        self.display_duration()

# ===== Hidden Objects =============================================
        self.clipboard = gtk.Clipboard()
        self.time_window = Calendar()
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
        self.entry_calper.connect(       "changed", self.callback_calper_changed, None)
        self.verify_entry_float(self.entry_calper)
        self.button_add_channel.connect( "clicked", self.callback_add_channel,  None)
        self.checkbutton_sensor.connect( "toggled", self.callback_generate,     None)
        self.checkbutton_spec.connect(   "toggled", self.callback_generate,     None)
        self.spinbutton_duration.connect("value-changed", self.callback_duration_changed, None)
        self.button_generate_calibs.connect("clicked", self.callback_generate_calibs, None)
        self.button_corrected_calibs.connect("clicked", self.callback_corrected_calibs, None)

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

    def callback_duration_changed(self, widget, event, data=None):
        self.display_duration()
        self.generate()

    def callback_add_channel(self, widget, event, data=None):
        self._add_channel()
        self.generate()
        #self.update_interface()

    def callback_delete_channel(self, widget, event, data=None):
        self._del_channel(data)
        self.generate()
        #self.update_interface()
                
    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, event, data)

    def callback_location_changed(self, widget, event, data=None):
        self.flush_calib(data)
        self.callback_location_update(widget, event, data)

    def callback_location_update(self, widget, event, data=None):
        if widget.get_value() < 10:
            widget.set_text("%02d" % widget.get_value())
        self.callback_generate(widget, event, data)

    def callback_class_changed(self, widget, event, data=None):
        self.flush_calib(data)
        self.callback_generate(widget, event, data)

    def callback_axes_changed(self, widget, event, data=None):
        self.flush_calib(data)
        self.callback_generate(widget, event, data)

    def callback_refid_changed(self, widget, event, data=None):
        self.verify_entry_populated(widget)
        self.generate()

    def callback_command(self, widget, event, data=None):
        self.update_interface()
        self.callback_generate(widget, event, data)

    def callback_copy(self, widget, event, data=None):
        self.text_to_clipboard()

    def callback_email(self, widget, event, data=None):
        self.mailto()

    def callback_calper_changed(self, widget, event, data=None):
        self.verify_entry_float(widget)
        self.button_generate_calibs.set_sensitive(widget._valid)
        self.button_corrected_calibs.set_sensitive(widget._valid)
        self.flush_calibs()
        self.generate()

    def callback_calib_changed(self, widget, event, data=None):
        self.verify_entry_float(widget)

    def callback_generate_calibs(self, widget, event, data=None):
        self.generate_calibs(False)

    def callback_corrected_calibs(self, widget, event, data=None):
        self.generate_calibs(True)

    def generate_calibs(self, correct):
        if not self.entry_calper._valid:
            return
        self.button_add_channel.set_sensitive(0)
        self._correct = correct

        resp_list = []
        station_map = {}
        network,station = self.combobox_stations.get_active_text().split('_', 1)
        for key,chan in self.channel_widgets.items():
            location = "%02d" % int(chan['spinbutton'].get_value())
            channel = chan['combobox-class'].get_active_text() + \
                      chan['combobox-axes'].get_active_text()
            key = "%s-%s-%s-%s" % (network,station,location,channel)
            if not self._responses.has_key(key):
                self._responses[key] = Responses(network, station, location, channel)
            if not station_map.has_key(key):
                resp_list.append(self._responses[key])
                station_map[key] = None
        
        dialog = ProgressDialog(self.window, self.callback_responses_complete, station_map.keys())
        self.progress_thread = ProgressThread(dialog)
        self.responses_thread = ResponsesThread(self.progress_thread.queue, resp_list)

        response = dialog.run()
        _,h = dialog.get_size()
        dialog.resize(600,h)

        self.progress_thread.start()
        self.responses_thread.start()

        self.button_add_channel.set_sensitive(1)

    def callback_responses_complete(self, dialog, data=None):
        self.button_add_channel.set_sensitive(0)

        result = dialog.result
        if result in ("CANCELLED", "EXITED"):
            self.responses_thread.halt_now(join=True)
            self.progress_thread.halt_now(join=True)
        if result == "COMPLETED":
            calper = float(self.entry_calper.get_text())
            network,station = self.combobox_stations.get_active_text().split('_', 1)
            for key,chan in self.channel_widgets.items():
                location = "%02d" % int(chan['spinbutton'].get_value())
                channel = chan['combobox-class'].get_active_text() + \
                          chan['combobox-axes'].get_active_text()
                key = "%s-%s-%s-%s" % (network,station,location,channel)
                if self._responses.has_key(key):
                    calib = Calib(self._responses[key])
                    calib.calculate_calib(calper, self._correct)
                    chan['entry-calib'].set_text(str(calib.calib))

        self.generate()
        self.button_add_channel.set_sensitive(1)


    def callback_generate(self, widget, event, data=None):
        self.generate()

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

    def callback_calarg_focus_out(self, widget, event, data=None):
        self.hint_text_show(widget)

    def callback_calarg_focus_in(self, widget, event, data=None):
        self.hint_text_hide(widget)

# ===== Methods ====================================================
    def display_duration(self):
        duration = float(self.spinbutton_duration.get_value())
        hours = duration / 3600
        minutes = (duration % 3600) / 60
        seconds = duration % 60
        self.sample_duration.set_text("%02d:%02d:%02d" % (hours, minutes, seconds))

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
        except:
            widget.modify_base(gtk.STATE_NORMAL, gtk.gdk.Color(65000, 45000, 45000)) #Red
            widget._valid = False


    def generate(self):
        self.textbuffer_display.set_text("")

        command = self.combobox_command.get_active_text()
        box = self.box_keys[command]

        if command == 'CALIBRATE_RESULT':
            if not self.entry_calper._valid:
                return
            for key,channel in self.channel_widgets.items():
                if not channel['entry-calib']._valid:
                    return
                if not channel['entry-refid']._valid:
                    return

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
                if axis_text == '1':
                    axis_text = 'N'
                elif axis_text == '2':
                    axis_text = 'E'
                channel_string = "%s%s%s" % (location_text, class_text, axis_text)
                calib_string = channel['entry-calib'].get_text()
                refid_string = channel['entry-refid'].get_text()
                if refid_string == channel['entry-refid']._hint_text:
                    refid_string = ""

              # === Construct IMS Message
                message += "BEGIN IMS2.0\n"
                message += "MSG_TYPE %s\n" % box['message-type']
                station = self.combobox_stations.get_active_text().split('_')[1]
                message += "MSG_ID %s\n" % (station+ "_" +command+ "_" +channel_string+ "_" +time.strftime("%Y/%m/%d_%H:%M:%S", time.gmtime()),)
                if box.has_key("REF_ID"):
                    message += "REF_ID %s\n" % refid_string

                if box.has_key("EMAIL"):
                    message += "EMAIL %s\n" % self.entry_email.get_text()
                if box.has_key("TIME_STAMP"):
                    message += "TIME_STAMP %s\n" % time.strftime("%Y/%m/%d %H:%M:%S", time.gmtime())
                if box.has_key("START_TIME") and (command == 'CALIBRATE_START'):
                    message += "START_TIME %s\n" % self.entry_start_time.get_text()
                if box.has_key("STA_LIST"):
                    message += "STA_LIST %s\n" % station
                if box.has_key("CHAN_LIST"):
                    message += "CHAN_LIST %s\n" % channel_string
                if box.has_key("START_TIME") and (command == 'CALIBRATE_CONFIRM'):
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
                    message += "CALIB_PARAM %.1f\n" % duration
                message += "%s\n" % command
                if box.has_key("IN_SPEC"):
                    if self.checkbutton_spec.get_active():
                        message += "IN_SPEC YES\n"
                    else:
                        message += "IN_SPEC NO\n"
                if box.has_key("CALIB") and len(calib_string):
                    message += "CALIB %s\n" % calib_string
                if box.has_key("CALPER") and (len(self.entry_calper.get_text()) > 0):
                    message += "CALPER %s\n" % self.entry_calper.get_text()
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
        channel['entry-refid'] = gtk.Entry()

        button_remove = gtk.Button(stock=None, use_underline=True)
        hbox_remove   = gtk.HBox()
        image_remove  = gtk.Image()
        image_remove.set_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
        label_remove  = gtk.Label('remove')
        button_remove.add(hbox_remove)
        hbox_remove.pack_start(image_remove, padding=1)
        hbox_remove.pack_start(label_remove, padding=1)
        channel['button-remove'] = button_remove

        self.vbox_channels.pack_start(channel['hbox'], False, True, 1)
        channel['hbox'].pack_start(channel['checkbutton-channel'], False, False, 0)
        channel['hbox'].pack_start(channel['spinbutton'], False, False, 0)
        channel['hbox'].pack_start(channel['combobox-class'], False, False, 0)
        channel['hbox'].pack_start(channel['combobox-axes'], False, False, 0)
        channel['hbox'].pack_start(channel['entry-calib'], False, False, 0)
        channel['hbox'].pack_start(channel['entry-refid'], True, True, 0)
        channel['hbox'].pack_start(channel['button-remove'], False, False, 0)

        channel['checkbutton-channel'].set_active(False)
        channel['combobox-class'].set_active(1)
        channel['combobox-axes'].set_active(0)

        calib_identifier = str(channel_key)+":entry-calib"
        channel['entry-calib'].set_width_chars(15)
        channel['entry-calib'].set_editable(False)
        channel['entry-calib'].connect("changed", self.callback_calib_changed, None, calib_identifier)
        self.verify_entry_float(channel['entry-calib'])

        refid_identifier = str(channel_key)+":entry-refid"
        channel['entry-refid']._hint_text = "REF_ID"
        channel['entry-refid'].connect("changed", self.callback_refid_changed, None, refid_identifier)
        channel['entry-refid'].connect("focus-in-event", self.callback_calarg_focus_in, None)
        channel['entry-refid'].connect("focus-out-event", self.callback_calarg_focus_out, None)
        self.hint_text_show(channel['entry-refid'])
        self.verify_entry_populated(channel['entry-refid'])

        channel['checkbutton-channel'].connect('toggled', self.callback_channel_toggle, None, channel_key)
        channel['spinbutton'].connect('value-changed', self.callback_location_changed, None, channel_key)
        channel['spinbutton'].connect('changed', self.callback_location_update, None)
        channel['combobox-class'].connect('changed', self.callback_class_changed, None, channel_key)
        channel['combobox-axes'].connect('changed', self.callback_axes_changed, None, channel_key)
        channel['button-remove'].connect('clicked', self.callback_delete_channel, None, channel_key)
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

    def flush_calib(self, channel_key):
        if self.channel_widgets.has_key(channel_key):
            self.channel_widgets[channel_key]['entry-calib'].set_text("")

    def flush_calibs(self):
        for key in self.channel_widgets.keys():
            self.flush_calib(key)

    def update_interface(self):
        command_key = self.combobox_command.get_active_text()
        for key in self.box_keys['ALL'].keys():
            if self.box_keys[command_key].has_key(key):
                for widget in self.boxes[key]:
                    widget.show_all()
            else:
                for widget in self.boxes[key]:
                    widget.hide_all()

        for key,channel in self.channel_widgets.items():
            if command_key == 'CALIBRATE_RESULT':
                channel['entry-calib'].show()
            else:
                channel['entry-calib'].hide()

        self.update_buttons()
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
        command = self.combobox_command.get_active_text()
        ims_cmd = self.box_keys[command]['message-type']
        station = self.combobox_stations.get_active_text().split('_')[1]
        recipients = ['calibration@ctbto.org']
        field_map = {
            'replyto' : 'gsnmaint@usgs.gov',
            'cc' : 'gsn-%s@usgs.gov' % station,
            'subject' : quote('%s_%s' % (command, station)),
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

