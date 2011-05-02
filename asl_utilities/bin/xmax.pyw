#!/usr/bin/env python
import asl

import glob
import os
import re
import stat
import struct
import subprocess
import sys
import threading
import time
import traceback

import pygtk
pygtk.require('2.0')
import gtk
import gobject

from jtk.gtk.Calendar import Calendar
from jtk.gtk.utils import LEFT
from jtk.gtk.utils import RIGHT
from jtk.file.utils import dir_from_file_path
from jtk.gtk.utils import select_file
from jtk.gtk.utils import select_directory


class XmaxGui:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("XMAX")
        self.window.set_icon(asl.new_icon('xmax'))

        self.os_type = 'UNIX'
        if os.name in ('nt','win32','win64'):
            self.os_type = 'WIN'

        self.home_directory = '.'
        if os.environ.has_key('HOME'):
            self.home_directory = os.environ['HOME']
        elif os.environ.has_key('USERPROFILE'):
            self.home_directory = os.environ['USERPROFILE']

        self.xmax_directory = ''
        if os.environ.has_key('XMAX_DIRECTORY'):
            self.xmax_directory = os.environ['XMAX_DIRECTORY']
        if not os.path.exists(self.xmax_directory):
            try:
                self.xmax_directory = os.path.abspath("%s/utils/xmax" % asl.path)
            except:
                pass
        if not os.path.exists(self.xmax_directory):
            self.xmax_directory = '/opt/xmax'
        if not os.path.exists(self.xmax_directory):
            self.xmax_directory = os.path.abspath("%s/opt/xmax" % self.home_directory)
        if not os.path.exists(self.xmax_directory):
            self.xmax_directory = os.path.abspath("%s/.xmax" % self.home_directory)
        if not os.path.exists(self.xmax_directory):
            self.xmax_directory = os.path.abspath("%s/xmax" % self.home_directory)
        if not os.path.exists(self.xmax_directory):
            self.xmax_directory = self.home_directory

        self.xmax_config = ''
        if os.environ.has_key('XMAX_CONFIG'):
            self.xmax_config = os.environ['XMAX_CONFIG']
        if not os.path.exists(self.xmax_config):
            self.xmax_config = os.path.abspath('%s/.xmax/config.xml' % self.home_directory)
        if not os.path.exists(self.xmax_config):
            self.xmax_config = '/etc/xmax/config.xml'
        if not os.path.exists(self.xmax_config):
            self.xmax_config = '/opt/etc/xmax/config.xml'
        if not os.path.exists(self.xmax_config):
            self.xmax_config = ''

        self.archive_directory = ''
        if os.environ.has_key('SEED_ARCHIVE_DIRECTORY'):
            self.archive_directory = os.environ['SEED_ARCHIVE_DIRECTORY']
        if not os.path.exists(self.archive_directory):
            if os.path.exists('/opt/data/archive'):
                self.archive_directory = '/opt/data/archive'
        if not os.path.exists(self.archive_directory):
            self.archive_directory = self.home_directory

        self.dict_unit = {
            'None'         : (0, None),
            'Trace'        : (1, 0   ),
            'Station'      : (2, 1   ),
            'Channel'      : (3, 2   ),
            'Channel Type' : (4, 3   ),
            'All'          : (5, 4   ),
            }

        self.dict_order = {
            'Default'                    : (0, None),
            'Trace Name'                 : (0, 0   ),
            'Network/Station/SampleRate' : (0, 1   ),
            'Channel'                    : (0, 2   ),
            'Channel Type'               : (0, 3   ),
            'Event'                      : (0, 4   ),
            }

        self.dict_format = {
            'Auto'                                     : (0 ,  None   ),
            '16-bit Integer (Short)'                   : (1 , 'SHORT' ),
            '24-bit Integer'                           : (2 , 'INT24' ),
            '32-bit Integer (Long)'                    : (3 , 'INT32' ),
            '32-bit Floating Point (Single Precision)' : (4 , 'FLOAT' ),
            '64-bit Floating Point (Double Precision)' : (5 , 'FLOAT' ),
            'Steim-1 Compression'                      : (6 , 'STEIM1'),
            'Steim-2 Compression'                      : (7 , 'STEIM2'),
            'CDSN Format'                              : (8 , 'CDSN'  ),
            'RSTN Format'                              : (9 , 'RSTN'  ),
            'DWW Format'                               : (10, 'DWW'   ),
            'SRO Format'                               : (11, 'SRO'   ),
            'ASRO Format'                              : (12, 'ASRO'  ),
            'HGLP Format'                              : (13, 'HGLP'  ),
            }

        self.dict_block = {
            'Auto' : (0, None),
            '256'  : (1, 256 ),
            '512'  : (2, 512 ),
            '1024' : (3, 1024),
            '2048' : (4, 2048),
            '4096' : (5, 4096),
            '8192' : (6, 8192),
            }

        self.date_format = '%Y,%j,%H:%M:%S'
        self.date_expr   = '\d{4},\d{3},\d{2}[:]\d{2}[:]\d{2}'

# ===== Widget Creation ============================================
        self.vbox_main             = gtk.VBox()
        self.hbox_notebook         = gtk.HBox()
        self.hbox_control          = gtk.HBox()
        self.notebook              = gtk.Notebook()
        self.page_data             = gtk.Table()
        self.page_filters          = gtk.Table()
        self.page_supplemental     = gtk.Table()
        self.page_xmax             = gtk.Table()

      # User Interaction Widgets
        self.radiobutton_data_dir  = gtk.RadioButton(None, "Data Directory: ")
        self.entry_data_dir        = gtk.Entry()
        self.button_data_dir       = gtk.Button()
        self.image_data_dir        = gtk.Image()
        self.image_data_dir.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        self.button_data_dir.add(self.image_data_dir)
        self.radiobutton_data_file = gtk.RadioButton(self.radiobutton_data_dir, "Data File: ")
        self.entry_data_file       = gtk.Entry()
        self.button_data_file      = gtk.Button()
        self.image_data_file       = gtk.Image()
        self.image_data_file.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        self.button_data_file.add(self.image_data_file)
        self.label_format          = gtk.Label("Data Format: ")
        self.combobox_format       = gtk.combo_box_new_text()
        self.label_block           = gtk.Label("Block Size: ")
        self.combobox_block        = gtk.combo_box_new_text()
        self.label_start           = gtk.Label("Start Date: ")
        self.entry_start           = gtk.Entry(max=17)
        self.button_start          = gtk.Button()
        self.image_start           = gtk.Image()
        self.image_start.set_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_MENU)
        self.button_start.add(self.image_start)
        self.label_end             = gtk.Label("End Date: ")
        self.entry_end             = gtk.Entry(max=17)
        self.button_end            = gtk.Button()
        self.image_end             = gtk.Image()
        self.image_end.set_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_MENU)
        self.button_end.add(self.image_end)
        self.checkbutton_merge     = gtk.CheckButton(label="Merge Locations")
        self.checkbutton_temp      = gtk.CheckButton(label="Include Temp. Data")

        self.label_network_filter  = gtk.Label("Network: ")
        self.entry_network_filter  = gtk.Entry()
        self.label_station_filter  = gtk.Label("Station: ")
        self.entry_station_filter  = gtk.Entry()
        self.label_location_filter = gtk.Label("Location: ")
        self.entry_location_filter = gtk.Entry()
        self.label_channel_filter  = gtk.Label("Channel: ")
        self.entry_channel_filter  = gtk.Entry()

        self.label_picks           = gtk.Label("Picks Database: ")
        self.entry_picks           = gtk.Entry()
        self.button_picks          = gtk.Button()
        self.image_picks           = gtk.Image()
        self.image_picks.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        self.button_picks.add(self.image_picks)
        self.label_description     = gtk.Label("Description File: ")
        self.entry_description     = gtk.Entry()
        self.button_description    = gtk.Button()
        self.image_description     = gtk.Image()
        self.image_description.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        self.button_description.add(self.image_description)
        self.label_earthquake      = gtk.Label("Earthquake Files: ")
        self.entry_earthquake      = gtk.Entry()
        self.button_earthquake     = gtk.Button()
        self.image_earthquake      = gtk.Image()
        self.image_earthquake.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        self.button_earthquake.add(self.image_earthquake)
        self.label_qcfile          = gtk.Label("QC Data Files: ")
        self.entry_qcfile          = gtk.Entry()
        self.button_qcfile         = gtk.Button()
        self.image_qcfile          = gtk.Image()
        self.image_qcfile.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        self.button_qcfile.add(self.image_qcfile)

        self.label_config          = gtk.Label("Config. File: ")
        self.entry_config          = gtk.Entry()
        self.button_config         = gtk.Button()
        self.image_config          = gtk.Image()
        self.image_config.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        self.button_config.add(self.image_config)
        self.label_order           = gtk.Label("Panel Order: ")
        self.combobox_order        = gtk.combo_box_new_text()
        self.label_unit            = gtk.Label("Panel Count Unit: ")
        self.combobox_unit         = gtk.combo_box_new_text()
        self.label_display         = gtk.Label("Units to Display: ")
        self.combobox_display      = gtk.combo_box_new_text()

        self.button_run            = gtk.Button(stock=None, use_underline=True)
        self.hbox_run              = gtk.HBox()
        self.image_run             = gtk.Image()
        self.image_run.set_from_stock(gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU)
        self.label_run             = gtk.Label('Run XMAX')
        self.button_run.add(self.hbox_run)
        self.hbox_run.pack_start(self.image_run, padding=1)
        self.hbox_run.pack_start(self.label_run, padding=1)

        self.button_dump           = gtk.Button(stock=None, use_underline=True)
        self.hbox_dump             = gtk.HBox()
        self.image_dump            = gtk.Image()
        self.image_dump.set_from_stock(gtk.STOCK_SAVE_AS, gtk.ICON_SIZE_MENU)
        self.label_dump            = gtk.Label('Dump Temp Data')
        self.button_dump.add(self.hbox_dump)
        self.hbox_dump.pack_start(self.image_dump, padding=1)
        self.hbox_dump.pack_start(self.label_dump, padding=1)

        self.button_quit           = gtk.Button(stock=None, use_underline=True)
        self.hbox_quit             = gtk.HBox()
        self.image_quit            = gtk.Image()
        self.image_quit.set_from_stock(gtk.STOCK_QUIT, gtk.ICON_SIZE_MENU)
        self.label_quit            = gtk.Label('Quit')
        self.button_quit.add(self.hbox_quit)
        self.hbox_quit.pack_start(self.image_quit, padding=1)
        self.hbox_quit.pack_start(self.label_quit, padding=1)


# ===== Layout Configuration =======================================
        self.window.add(self.vbox_main)

        self.vbox_main.pack_start(self.hbox_notebook, False, True,  0)
        self.vbox_main.pack_start(self.hbox_control,  True,  True,  0)

        self.hbox_notebook.pack_start(self.notebook,  True,  True,  0)

        self.notebook.append_page(self.page_data,         tab_label=gtk.Label("Data"))
        self.notebook.append_page(self.page_filters,      tab_label=gtk.Label("Filters"))
        self.notebook.append_page(self.page_supplemental, tab_label=gtk.Label("Supplemental Data Sources"))
        self.notebook.append_page(self.page_xmax,         tab_label=gtk.Label("XMAX"))

        self.page_data.attach(LEFT(self.radiobutton_data_dir),       0, 1, 0, 1, gtk.FILL, 0, 1, 1)
        self.page_data.attach(self.entry_data_dir,                   1, 2, 0, 1, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.page_data.attach(self.button_data_dir,                  2, 3, 0, 1, 0, 0, 1, 1)
        self.page_data.attach(LEFT(self.radiobutton_data_file),      0, 1, 1, 2, gtk.FILL, 0, 1, 1)
        self.page_data.attach(self.entry_data_file,                  1, 2, 1, 2, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.page_data.attach(self.button_data_file,                 2, 3, 1, 2, 0, 0, 1, 1)
        self.page_data.attach(LEFT(self.label_format),               0, 1, 2, 3, gtk.FILL, 0, 1, 1)
        self.page_data.attach(LEFT(self.combobox_format),            1, 3, 2, 3, gtk.FILL, 0, 1, 1)
        self.page_data.attach(LEFT(self.label_block),                0, 1, 3, 4, gtk.FILL, 0, 1, 1)
        self.page_data.attach(LEFT(self.combobox_block),             1, 3, 3, 4, gtk.FILL, 0, 1, 1)
        self.page_data.attach(LEFT(self.label_start),                0, 1, 4, 5, gtk.FILL, 0, 1, 1)
        self.page_data.attach(self.entry_start,                      1, 2, 4, 5, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.page_data.attach(self.button_start,                     2, 3, 4, 5, 0, 0, 1, 1)
        self.page_data.attach(LEFT(self.label_end),                  0, 1, 5, 6, gtk.FILL, 0, 1, 1)
        self.page_data.attach(self.entry_end,                        1, 2, 5, 6, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.page_data.attach(self.button_end,                       2, 3, 5, 6, 0, 0, 1, 1)
        self.page_data.attach(LEFT(self.checkbutton_merge),          0, 3, 6, 7, gtk.FILL, 0, 1, 1)
        self.page_data.attach(LEFT(self.checkbutton_temp),           0, 3, 7, 8, gtk.FILL, 0, 1, 1)

        self.page_filters.attach(LEFT(self.label_network_filter),    0, 1, 0, 1, gtk.FILL, 0, 1, 1)
        self.page_filters.attach(self.entry_network_filter,          1, 2, 0, 1, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.page_filters.attach(LEFT(self.label_station_filter),    0, 1, 1, 2, gtk.FILL, 0, 1, 1)
        self.page_filters.attach(self.entry_station_filter,          1, 2, 1, 2, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.page_filters.attach(LEFT(self.label_location_filter),   0, 1, 2, 3, gtk.FILL, 0, 1, 1)
        self.page_filters.attach(self.entry_location_filter,         1, 2, 2, 3, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.page_filters.attach(LEFT(self.label_channel_filter),    0, 1, 3, 4, gtk.FILL, 0, 1, 1)
        self.page_filters.attach(self.entry_channel_filter,          1, 2, 3, 4, gtk.FILL | gtk.EXPAND, 0, 1, 1)

        self.page_supplemental.attach(LEFT(self.label_picks),        0, 1, 0, 1, gtk.FILL, 0, 1, 1)
        self.page_supplemental.attach(self.entry_picks,              1, 2, 0, 1, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.page_supplemental.attach(self.button_picks,             2, 3, 0, 1, 0, 0, 1, 1)
        self.page_supplemental.attach(LEFT(self.label_description),  0, 1, 1, 2, gtk.FILL, 0, 1, 1)
        self.page_supplemental.attach(self.entry_description,        1, 2, 1, 2, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.page_supplemental.attach(self.button_description,       2, 3, 1, 2, 0, 0, 1, 1)
        self.page_supplemental.attach(LEFT(self.label_earthquake),   0, 1, 2, 3, gtk.FILL, 0, 1, 1)
        self.page_supplemental.attach(self.entry_earthquake,         1, 2, 2, 3, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.page_supplemental.attach(self.button_earthquake,        2, 3, 2, 3, 0, 0, 1, 1)
        self.page_supplemental.attach(LEFT(self.label_qcfile),       0, 1, 3, 4, gtk.FILL, 0, 1, 1)
        self.page_supplemental.attach(self.entry_qcfile,             1, 2, 3, 4, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.page_supplemental.attach(self.button_qcfile,            2, 3, 3, 4, 0, 0, 1, 1)

        self.page_xmax.attach(LEFT(self.label_config),               0, 1, 0, 1, gtk.FILL, 0, 1, 1)
        self.page_xmax.attach(self.entry_config,                     1, 2, 0, 1, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.page_xmax.attach(self.button_config,                    2, 3, 0, 1, 0, 0, 1, 1)
        self.page_xmax.attach(LEFT(self.label_order),                0, 1, 1, 2, gtk.FILL, 0, 1, 1)
        self.page_xmax.attach(LEFT(self.combobox_order),             1, 3, 1, 2, gtk.FILL, 0, 1, 1)
        self.page_xmax.attach(LEFT(self.label_unit),                 0, 1, 2, 3, gtk.FILL, 0, 1, 1)
        self.page_xmax.attach(LEFT(self.combobox_unit),              1, 3, 2, 3, gtk.FILL, 0, 1, 1)
        self.page_xmax.attach(LEFT(self.label_display),              0, 1, 3, 4, gtk.FILL, 0, 1, 1)
        self.page_xmax.attach(LEFT(self.combobox_display),           1, 3, 3, 4, gtk.FILL, 0, 1, 1)

        self.hbox_control.pack_start(self.button_run,  False, False, 0)
        self.hbox_control.pack_start(self.button_dump, False, False, 0)
        self.hbox_control.pack_end(self.button_quit,   False, False, 0)

# ===== Widget Configurations ======================================
        self.entry_data_dir.set_text(self.archive_directory)
        self.entry_data_dir.grab_focus()
        self.radiobutton_data_dir.set_active(True)
        self.entry_data_file.set_text(self.archive_directory)

        CMP = lambda a, b: cmp(a[1][0], b[1][0])

        for k,_ in sorted(self.dict_format.items(), CMP):
            self.combobox_format.append_text(k)
        self.combobox_format.set_active(0)

        for k,_ in sorted(self.dict_block.items(), CMP):
            self.combobox_block.append_text(k)
        self.combobox_block.set_active(0)

        for k,_ in sorted(self.dict_unit.items(), CMP):
            self.combobox_unit.append_text(k)
        self.combobox_unit.set_active(len(self.dict_unit) - 1)

        for k,_ in sorted(self.dict_unit.items(), CMP):
            self.combobox_display.append_text(k)
        self.combobox_display.set_active(len(self.dict_unit) - 1)

        for k,_ in sorted(self.dict_order.items(), CMP):
            self.combobox_order.append_text(k)
        self.combobox_order.set_active(0)

        self.calendar_start = Calendar()
        self.calendar_start.set_callback( self.callback_populate_time, (self.calendar_start, self.entry_start) )
        self.calendar_start.set_granularity('second')
        self.calendar_start.set_default_high( False )

        self.calendar_end = Calendar()
        self.calendar_end.set_callback( self.callback_populate_time, (self.calendar_end, self.entry_end) )
        self.calendar_end.set_granularity('second')
        self.calendar_end.set_default_high( True )

# ===== Event Bindings =============================================
        self.window.connect("destroy-event", self.callback_quit, None)
        self.window.connect("delete-event",  self.callback_quit, None)

        self.button_data_dir.connect(   "clicked", self.callback_select_data_dir,    None)
        self.button_data_file.connect(  "clicked", self.callback_select_data_file,   None)
        self.button_picks.connect(      "clicked", self.callback_select_picks,       None)
        self.button_description.connect("clicked", self.callback_select_description, None)
        self.button_earthquake.connect( "clicked", self.callback_select_earthquake,  None)
        self.button_qcfile.connect(     "clicked", self.callback_select_qcfile,      None)
        self.button_config.connect(     "clicked", self.callback_select_config,      None)

        self.radiobutton_data_dir.connect(  "toggled", self.callback_radio, None)
        self.radiobutton_data_file.connect( "toggled", self.callback_radio, None)

        self.button_start.connect("clicked", self.callback_show_calendar, (self.calendar_start, self.entry_start))
        self.button_end.connect(  "clicked", self.callback_show_calendar, (self.calendar_end,   self.entry_end))

        self.checkbutton_temp.connect("toggled", self.callback_toggle_temp, None)
        self.button_run.connect(  "clicked", self.callback_run,  None)
        self.button_dump.connect( "clicked", self.callback_dump, None)
        self.button_quit.connect( "clicked", self.callback_quit, None)

        self.window.connect("key-press-event", self.callback_key_pressed)

      # Show widgets
        self.window.show_all()
        self.update_interface()

# ===== Callbacks ==================================================
    def callback_key_pressed(self, widget, event, data=None):
        if event.state == gtk.gdk.MOD1_MASK:
            if event.keyval == ord('q'):
                self.callback_quit(widget, event, data)
            elif event.keyval == ord('d'):
                if not (self.button_dump.state & gtk.STATE_INSENSITIVE):
                    self.callback_dump(widget, event, data)
            elif event.keyval == ord('r'):
                if not (self.button_run.state & gtk.STATE_INSENSITIVE):
                    self.callback_run(widget, event, data)
        self.update_interface()

    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, event, data)

    def callback_toggle_temp(self, widget, event, data=None):
        if self.checkbutton_temp.get_active():
            self.button_dump.set_sensitive(False)
        else:
            self.button_dump.set_sensitive(True)

    def callback_radio(self, widget, event, data=None):
        self.update_interface()

    def callback_select_data_dir(self, widget, event, data=None):
        last_location = self.entry_data_file.get_text()
        current_dir = self.entry_data_dir.get_text()
        if not os.path.isdir(current_dir):
            current_dir = dir_from_file_path(current_dir)
        if os.path.isdir(current_dir):
            self.entry_data_dir.set_text(select_directory(current_dir))
        else:
            self.entry_data_dir.set_text(select_directory())
        if self.entry_data_dir.get_text() == '':
            self.entry_data_dir.set_text(last_location)
        self.update_interface()

    def callback_select_data_file(self, widget, event, data=None):
        last_location = self.entry_data_file.get_text()
        current_dir = self.entry_data_file.get_text()
        if not os.path.isdir(current_dir):
            current_dir = dir_from_file_path(current_dir)
        if os.path.isdir(current_dir):
            self.entry_data_file.set_text(select_file(current_dir, filter_id='seed'))
        else:
            self.entry_data_file.set_text(select_file(filter_id='seed'))
        if self.entry_data_file.get_text() == '':
            self.entry_data_file.set_text(last_location)
        self.update_interface()

    def callback_select_picks(self, widget, event, data=None):
        current_dir = dir_from_file_path(self.entry_picks.get_text())
        if os.path.isdir(current_dir):
            self.entry_picks.set_text(select_file(current_dir, filter_id='seed'))
        else:
            self.entry_picks.set_text(select_file(filter_id='seed'))
        self.update_interface()

    def callback_select_description(self, widget, event, data=None):
        current_dir = dir_from_file_path(self.entry_description.get_text())
        if os.path.isdir(current_dir):
            self.entry_description.set_text(select_file(current_dir, filter_id='seed'))
        else:
            self.entry_description.set_text(select_file(filter_id='seed'))
        self.update_interface()

    def callback_select_earthquake(self, widget, event, data=None):
        current_dir = dir_from_file_path(self.entry_earthquake.get_text())
        if os.path.isdir(current_dir):
            self.entry_earthquake.set_text(select_file(current_dir, filter_id='seed'))
        else:
            self.entry_earthquake.set_text(select_file(filter_id='seed'))
        self.update_interface()

    def callback_select_qcfile(self, widget, event, data=None):
        current_dir = dir_from_file_path(self.entry_qcfile.get_text())
        if os.path.isdir(current_dir):
            self.entry_qcfile.set_text(select_file(current_dir, filter_id='seed'))
        else:
            self.entry_qcfile.set_text(select_file(filter_id='seed'))
        self.update_interface()

    def callback_select_config(self, widget, event, data=None):
        current_dir = dir_from_file_path(self.entry_config.get_text())
        if os.path.isdir(current_dir):
            self.entry_config.set_text(select_file(current_dir, filter_id='seed'))
        else:
            self.entry_config.set_text(select_file(filter_id='seed'))
        self.update_interface()

    def callback_run(self, widget, event, data=None):
        self.run_xmax()
        self.update_interface()

    def callback_dump(self, widget, event, data=None):
        self.run_xmax(dump=True)
        self.update_interface()

  # Calendar Callbacks
    def callback_show_calendar(self, widget, data):
        (calendar, entry) = data
        self.propogate_time(data)
        calendar.prompt()

    def callback_populate_time(self, data):
        (calendar, widget) = data
        value = time.strftime(self.date_format, calendar.get_date())
        widget.set_text( value )


# ===== Methods ====================================================
    def update_interface(self):
        if self.radiobutton_data_dir.get_active():
            self.button_data_dir.set_sensitive(True)
            self.entry_data_dir.set_sensitive(True)
            if len(self.entry_data_dir.get_text()):
                self.button_run.set_sensitive(True)
            else:
                self.button_run.set_sensitive(False)
        else:
            self.button_data_dir.set_sensitive(False)
            self.entry_data_dir.set_sensitive(False)

        if self.radiobutton_data_file.get_active():
            self.button_data_file.set_sensitive(True)
            self.entry_data_file.set_sensitive(True)
            if len(self.entry_data_file.get_text()):
                self.button_run.set_sensitive(True)
            else:
                self.button_run.set_sensitive(False)
        else:
            self.button_data_file.set_sensitive(False)
            self.entry_data_file.set_sensitive(False)
        
    def propogate_time(self, data):
        (calendar, widget) = data
        regex = re.compile(self.date_expr)
        if regex.match(widget.get_text()):
            value = time.strptime(widget.get_text(), self.date_format)
            calendar.set_date(value)

    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        return False

    def get_xmax_options(self, dump):
        option_list = []

        arg_unit = self.dict_unit[self.combobox_unit.get_active_text()][1]
        if arg_unit is not None:
            option_list.append('-u')
            option_list.append(str(arg_unit))

        arg_order = self.dict_order[self.combobox_order.get_active_text()][1]
        if arg_order is not None:
            option_list.append('-o')
            option_list.append(str(arg_order))

        if self.checkbutton_temp.get_active():
            option_list.append('-t')

        arg_channel = self.entry_channel_filter.get_text() 
        if arg_channel:
            option_list.append('-c')
            option_list.append(arg_channel)

        arg_location = self.entry_location_filter.get_text()
        if arg_location:
            option_list.append('-l')
            option_list.append(arg_location)

        arg_network = self.entry_network_filter.get_text()
        if arg_network:
            option_list.append('-n')
            option_list.append(arg_network)

        arg_station = self.entry_station_filter.get_text()
        if arg_station:
            option_list.append('-s')
            option_list.append(arg_station)

        arg_display = self.dict_unit[self.combobox_display.get_active_text()][1]
        if arg_display is not None:
            option_list.append('-f')
            option_list.append(str(arg_display))

        arg_format = self.dict_format[self.combobox_format.get_active_text()][1]
        if arg_format is not None:
            option_list.append('-F')
            option_list.append(arg_format)

        arg_block = self.dict_block[self.combobox_block.get_active_text()][1]
        if arg_block is not None:
            option_list.append('-L')
            option_list.append(str(arg_block))

        if dump:
            option_list.append('-T')

        arg_start = self.entry_start.get_text()



        if self.radiobutton_data_dir.get_active():
            arg_data = self.entry_data_dir.get_text()
        elif self.radiobutton_data_file.get_active():
            arg_data = self.entry_data_file.get_text()
        if arg_data:
            option_list.append('-d')
            option_list.append(arg_data)

        arg_end = self.entry_end.get_text()

      # Date Verification
        regex = re.compile(self.date_expr)
        if regex.match(arg_start):
            date_start = time.mktime(time.strptime(arg_start, self.date_format))
        else:
            date_start = None
        if regex.match(arg_end):
            date_end = time.mktime(time.strptime(arg_end, self.date_format))
        else:
            date_end = None
        if date_start and date_end and date_start >= date_end:
            date_start = None
            date_end = None
        if date_start:
            option_list.append('-b')
            option_list.append(arg_start)
        if date_end:
            option_list.append('-e')
            option_list.append(arg_end)

        arg_config = self.entry_config.get_text()
        if arg_config:
            option_list.append('-g')
            option_list.append(arg_config)
        elif self.xmax_config:
            option_list.append('-g')
            option_list.append(self.xmax_config)

        arg_description = self.entry_description.get_text()
        if arg_description:
            option_list.append('-i')
            option_list.append(arg_description)

        arg_earthquake = self.entry_earthquake.get_text()
        if arg_earthquake:
            option_list.append('-k')
            option_list.append(arg_earthquake)

        if self.checkbutton_merge.get_active():
            option_list.append('-m')

        arg_picks = self.entry_picks.get_text()
        if arg_picks:
            option_list.append('-p')
            option_list.append(arg_picks)

        arg_qcfile = self.entry_qcfile.get_text()
        if arg_qcfile:
            option_list.append('-q')
            option_list.append(arg_qcfile)

        return option_list


    def run_xmax(self, dump=False):
        option_list = self.get_xmax_options(dump)
        os.chdir(self.xmax_directory)
        if self.os_type == 'WIN':
            self.run_win(option_list)
        else:
            self.run_unix(option_list)

    def run_win(self, option_list):
        xmax_jar = os.path.abspath("%s/xmax.jar" % self.xmax_directory)
        os.chdir(self.xmax_directory)
        arguments = ["java", "-Xms512M", "-Xmx512M", "-jar", xmax_jar]
        arguments.extend(option_list)
        #print "argument list:", arguments
        process = subprocess.Popen(arguments)
        return process

    def run_unix(self, option_list):
        executable = '/usr/bin/xterm'
        arguments  = ['xterm', '-T', '\"XMAX\"', '-sl', '10240', '-e', "\"cd %s; java -Xms512M -Xmx512M -jar xmax.jar %s && read -n 1 -p 'Press any key to continue...'\"" % (self.xmax_directory, ' '.join(option_list))]
        #print "Command:", ' '.join(arguments)
        os.popen(' '.join(arguments))
        return None
        #process = subprocess.Popen(arguments)
        #return process

def main():
    app = XmaxGui()
    gtk.main()

if __name__ == "__main__":
    main()

