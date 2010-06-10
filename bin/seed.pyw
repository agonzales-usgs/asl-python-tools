#!/usr/bin/env python
import calendar
import glob
import optparse
import os
import Queue
import re
import stat
import struct
import sys
import threading
import time
import traceback

import pygtk
pygtk.require('2.0')
import gtk
import gobject
gobject.threads_init()

from jtk.Class import Class
from jtk.Thread import Thread
from jtk.Logger import LogThread
from jtk.file.utils import scan_directories
from jtk.file.utils import dir_from_file_path
from jtk.gtk.utils import LEFT
from jtk.gtk.utils import RIGHT
from jtk.gtk.Calendar import Calendar
from jtk.gtk.utils import select_files
from jtk.gtk.utils import select_save_file
from jtk.gtk.utils import select_directory
from jtk.gtk.utils import select_directories
from jtk.seed.utils import CMP_SEED_TIMES

# === Exceptions /*{{{*/
class ExFileExists(Exception):
    pass
class ExDirDNE(Exception):
    pass
# /*}}}*/

# === SEED Options GUI /*{{{*/
class SeedGui(Class):
    def __init__(self):
        Class.__init__(self)

        self.home_directory = '.'
        if os.environ.has_key('HOME'):
            self.home_directory = os.environ['HOME']
        elif os.environ.has_key('USERPROFILE'):
            self.home_directory = os.environ['USERPROFILE']

        self.archive_directory = ''
        if os.environ.has_key('ARCHIVE_DIRECTORY'):
            self.archive_directory = os.environ['ARCHIVE_DIRECTORY']
        if not os.path.exists(self.archive_directory):
            if os.path.exists('/opt/data/archive'):
                self.archive_directory = '/opt/data/archive'
        if not os.path.exists(self.archive_directory):
            self.archive_directory = self.home_directory

        self.output_directory = ''
        if os.environ.has_key('OUTPUT_DIRECTORY'):
            self.output_directory = os.environ['OUTPUT_DIRECTORY']
        if not os.path.exists(self.output_directory):
            if os.path.exists('/opt/data/temp_data'):
                self.output_directory = '/opt/data/temp_data'
        if not os.path.exists(self.output_directory):
            self.output_directory = self.home_directory

        self.scanning            = False
        self.writing             = False
        self.auto_writing        = False
        self.last_path           = None
        self.read_thread         = None
        self.scan_thread         = None
        self.package_thread      = None
        self.auto_package_thread = None
        self.write_thread        = None
        self.queue_channels      = Queue.Queue()
        self.queue_file_count    = Queue.Queue()
        self.queue_byte_count    = Queue.Queue()
        self.log_thread          = LogThread()
        self.log_queue           = self.log_thread.queue
        self.log_thread.start()

        self.context_file_exists = ''
        self.context_dir_dne     = ''

        self.date_format = '%Y,%j,%H:%M:%S'
        self.date_expr   = '\d{4},\d{3},\d{2}[:]\d{2}[:]\d{2}'

        self.scan_files         = {}
        self.package_files      = {}
        self.package_channels   = {}
        self.package_start_time = None
        self.package_end_time   = None

        self.auto_package_channels = {}

        self.scan_channels      = None
        self.scan_start_time    = None
        self.scan_end_time      = None

        self.regex_network  = None
        self.regex_station  = None
        self.regex_location = None
        self.regex_channel  = None

# ===== GUI Build-up ========================================
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("SEED Re-Packager")

        self.treestore_files         = gtk.TreeStore(gobject.TYPE_STRING)
        self.treestore_channels      = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING,
                                                     gobject.TYPE_STRING, gobject.TYPE_STRING,
                                                     gobject.TYPE_BOOLEAN)
        self.treestore_channels      = self.treestore_channels.filter_new()

        self.treeviewcol_files       = gtk.TreeViewColumn('Input File List')
        self.treeviewcol_network     = gtk.TreeViewColumn('Network')
        self.treeviewcol_station     = gtk.TreeViewColumn('Station')
        self.treeviewcol_location    = gtk.TreeViewColumn('Location')
        self.treeviewcol_channel     = gtk.TreeViewColumn('Channel')

        self.crtext_files            = gtk.CellRendererText()
        self.crtext_network          = gtk.CellRendererText()
        self.crtext_station          = gtk.CellRendererText()
        self.crtext_location         = gtk.CellRendererText()
        self.crtext_channel          = gtk.CellRendererText()

        try:
            self.tooltips            = gtk.Tooltips()
        except:
            self.tooltips            = None

# ===== Widget Creation ============================================
        self.vbox_main               = gtk.VBox()
        self.hbox_notebook           = gtk.HBox()
        self.hbox_control            = gtk.HBox()
        self.notebook                = gtk.Notebook()
        self.page_input              = gtk.VBox()
        self.page_selection          = gtk.VBox()
        self.page_output             = gtk.VBox()
        self.table_output            = gtk.Table()

        self.hbox_input_files        = gtk.HBox()
        self.hbox_input_treeview     = gtk.HBox()
        self.xbox_progress           = gtk.VBox()
        self.hbox_input_controls     = gtk.HBox()

        self.hbox_selection_filters  = gtk.HBox()
        self.hbox_selection_channels = gtk.HBox()
        self.table_selection_buttons = gtk.Table()

        self.hbox_button_add_all_channels         = gtk.HBox()
        self.hbox_button_add_filtered_channels    = gtk.HBox()
        self.hbox_button_add_selected_channels    = gtk.HBox()
        self.hbox_button_remove_all_channels      = gtk.HBox()
        self.hbox_button_remove_filtered_channels = gtk.HBox()
        self.hbox_button_remove_selected_channels = gtk.HBox()

# ===== User Interaction Widgets =====
      # Input Page
        self.button_add_files = gtk.Button(stock=None, use_underline=True)
        self.hbox_add_files   = gtk.HBox()
        self.image_add_files  = gtk.Image()
        self.image_add_files.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_MENU)
        self.label_add_files  = gtk.Label('Add Files')
        self.button_add_files.add(self.hbox_add_files)
        self.hbox_add_files.pack_start(self.image_add_files, padding=1)
        self.hbox_add_files.pack_start(self.label_add_files, padding=1)

        self.button_add_directories = gtk.Button(stock=None, use_underline=True)
        self.hbox_add_directories   = gtk.HBox()
        self.image_add_directories  = gtk.Image()
        self.image_add_directories.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_MENU)
        self.label_add_directories  = gtk.Label('Add Directories')
        self.button_add_directories.add(self.hbox_add_directories)
        self.hbox_add_directories.pack_start(self.image_add_directories, padding=1)
        self.hbox_add_directories.pack_start(self.label_add_directories, padding=1)

        self.button_remove_files = gtk.Button(stock=None, use_underline=True)
        self.hbox_remove_files   = gtk.HBox()
        self.image_remove_files  = gtk.Image()
        self.image_remove_files.set_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
        self.label_remove_files  = gtk.Label('Remove Selected')
        self.button_remove_files.add(self.hbox_remove_files)
        self.hbox_remove_files.pack_start(self.image_remove_files, padding=1)
        self.hbox_remove_files.pack_start(self.label_remove_files, padding=1)

        self.button_select_all_files = gtk.Button(stock=None, use_underline=True)
        self.hbox_select_all_files   = gtk.HBox()
        self.image_select_all_files  = gtk.Image()
        self.image_select_all_files.set_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
        self.label_select_all_files  = gtk.Label('Select All')
        self.button_select_all_files.add(self.hbox_select_all_files)
        self.hbox_select_all_files.pack_start(self.image_select_all_files, padding=1)
        self.hbox_select_all_files.pack_start(self.label_select_all_files, padding=1)

        self.treeview_files     = gtk.TreeView()
        self.scrollwindow_files = gtk.ScrolledWindow()
        self.scrollwindow_files.add(self.treeview_files)
        self.scrollwindow_files.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.button_scan = gtk.Button(stock=None, use_underline=True)
        self.hbox_scan   = gtk.HBox()
        self.image_scan  = gtk.Image()
        self.image_scan.set_from_stock(gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU)
        self.label_scan  = gtk.Label('Scan')
        self.button_scan.add(self.hbox_scan)
        self.hbox_scan.pack_start(self.image_scan, padding=1)
        self.hbox_scan.pack_start(self.label_scan, padding=1)

        self.button_rescan = gtk.Button(stock=None, use_underline=True)
        self.hbox_rescan   = gtk.HBox()
        self.image_rescan  = gtk.Image()
        self.image_rescan.set_from_stock(gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU)
        self.label_rescan  = gtk.Label('Re-Scan')
        self.button_rescan.add(self.hbox_rescan)
        self.hbox_rescan.pack_start(self.image_rescan, padding=1)
        self.hbox_rescan.pack_start(self.label_rescan, padding=1)

        self.button_cancel_scan = gtk.Button(stock=None, use_underline=True)
        self.hbox_cancel_scan   = gtk.HBox()
        self.image_cancel_scan  = gtk.Image()
        self.image_cancel_scan.set_from_stock(gtk.STOCK_CANCEL, gtk.ICON_SIZE_MENU)
        self.label_cancel_scan  = gtk.Label('Cancel Scan')
        self.button_cancel_scan.add(self.hbox_cancel_scan)
        self.hbox_cancel_scan.pack_start(self.image_cancel_scan, padding=1)
        self.hbox_cancel_scan.pack_start(self.label_cancel_scan, padding=1)

      # Channel Page
        self.label_filters         = gtk.Label("Filters:")
        self.entry_filter_network  = gtk.Entry()
        self.entry_filter_station  = gtk.Entry()
        self.entry_filter_location = gtk.Entry()
        self.entry_filter_channel  = gtk.Entry()

        self.treeview_channels     = gtk.TreeView()
        self.scrollwindow_channels = gtk.ScrolledWindow()
        self.scrollwindow_channels.add(self.treeview_channels)
        self.scrollwindow_channels.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)

        self.label_add_channels = gtk.Label("Add:")

        self.button_add_all_channels   = gtk.Button(stock=None, use_underline=True)
        self.hbox_add_all_channels     = gtk.HBox()
        self.image_add_all_channels    = gtk.Image()
        self.image_add_all_channels.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_MENU)
        self.label_add_all_channels    = gtk.Label('All')
        self.button_add_all_channels.add(self.hbox_add_all_channels)
        self.hbox_add_all_channels.pack_start(LEFT(self.image_add_all_channels), padding=1)
        self.hbox_add_all_channels.pack_start(self.label_add_all_channels, padding=1)

        self.button_add_visible_channels   = gtk.Button(stock=None, use_underline=True)
        self.hbox_add_visible_channels     = gtk.HBox()
        self.image_add_visible_channels    = gtk.Image()
        self.image_add_visible_channels.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_MENU)
        self.label_add_visible_channels    = gtk.Label('Visible')
        self.button_add_visible_channels.add(self.hbox_add_visible_channels)
        self.hbox_add_visible_channels.pack_start(LEFT(self.image_add_visible_channels), padding=1)
        self.hbox_add_visible_channels.pack_start(self.label_add_visible_channels, padding=1)

        self.button_add_selected_channels   = gtk.Button(stock=None, use_underline=True)
        self.hbox_add_selected_channels     = gtk.HBox()
        self.image_add_selected_channels    = gtk.Image()
        self.image_add_selected_channels.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_MENU)
        self.label_add_selected_channels  = gtk.Label('Selected')
        self.button_add_selected_channels.add(self.hbox_add_selected_channels)
        self.hbox_add_selected_channels.pack_start(LEFT(self.image_add_selected_channels), padding=1)
        self.hbox_add_selected_channels.pack_start(self.label_add_selected_channels, padding=1)

        self.label_remove_channels = gtk.Label("Remove:")

        self.button_remove_all_channels = gtk.Button(stock=None, use_underline=True)
        self.hbox_remove_all_channels   = gtk.HBox()
        self.image_remove_all_channels  = gtk.Image()
        self.image_remove_all_channels.set_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
        self.label_remove_all_channels  = gtk.Label('All')
        self.button_remove_all_channels.add(self.hbox_remove_all_channels)
        self.hbox_remove_all_channels.pack_start(LEFT(self.image_remove_all_channels), padding=1)
        self.hbox_remove_all_channels.pack_start(self.label_remove_all_channels, padding=1)

        self.button_remove_visible_channels = gtk.Button(stock=None, use_underline=True)
        self.hbox_remove_visible_channels   = gtk.HBox()
        self.image_remove_visible_channels  = gtk.Image()
        self.image_remove_visible_channels.set_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
        self.label_remove_visible_channels  = gtk.Label('Visible')
        self.button_remove_visible_channels.add(self.hbox_remove_visible_channels)
        self.hbox_remove_visible_channels.pack_start(LEFT(self.image_remove_visible_channels), padding=1)
        self.hbox_remove_visible_channels.pack_start(self.label_remove_visible_channels, padding=1)

        self.button_remove_selected_channels = gtk.Button(stock=None, use_underline=True)
        self.hbox_remove_selected_channels   = gtk.HBox()
        self.image_remove_selected_channels  = gtk.Image()
        self.image_remove_selected_channels.set_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
        self.label_remove_selected_channels  = gtk.Label('Selected')
        self.button_remove_selected_channels.add(self.hbox_remove_selected_channels)
        self.hbox_remove_selected_channels.pack_start(LEFT(self.image_remove_selected_channels), padding=1)
        self.hbox_remove_selected_channels.pack_start(self.label_remove_selected_channels, padding=1)

      # Output Page
        self.label_scan_first_time = gtk.Label("First Record Time:")
        self.label_scan_start_time = gtk.Label()
        self.button_set_start_time = gtk.Button(stock=None, use_underline=True)
        self.hbox_set_start_time   = gtk.HBox()
        self.image_set_start_time  = gtk.Image()
        self.image_set_start_time.set_from_stock(gtk.STOCK_GOTO_FIRST, gtk.ICON_SIZE_MENU)
        self.label_set_start_time  = gtk.Label('Set Start Time')
        self.button_set_start_time.add(self.hbox_set_start_time)
        self.hbox_set_start_time.pack_start(self.image_set_start_time, padding=1)
        self.hbox_set_start_time.pack_start(self.label_set_start_time, padding=1)
        self.hbox_m_set_start_time = gtk.HBox()
        self.hbox_m_set_start_time.pack_end(self.button_set_start_time, False, False, 0)

        self.label_scan_last_time  = gtk.Label("Last Record Time:")
        self.label_scan_end_time   = gtk.Label()
        self.button_set_end_time   = gtk.Button(stock=None, use_underline=True)
        self.hbox_set_end_time     = gtk.HBox()
        self.image_set_end_time    = gtk.Image()
        self.image_set_end_time.set_from_stock(gtk.STOCK_GOTO_LAST, gtk.ICON_SIZE_MENU)
        self.label_set_end_time    = gtk.Label('Set End Time')
        self.button_set_end_time.add(self.hbox_set_end_time)
        self.hbox_set_end_time.pack_start(self.image_set_end_time, padding=1)
        self.hbox_set_end_time.pack_start(self.label_set_end_time, padding=1)
        self.hbox_m_set_end_time = gtk.HBox()
        self.hbox_m_set_end_time.pack_end(self.button_set_end_time, False, False, 0)

        self.label_start_time  = gtk.Label("Start Time: ")
        self.entry_start_time  = gtk.Entry(max=17)
        self.button_start_time = gtk.Button()
        self.image_start_time  = gtk.Image()
        self.image_start_time.set_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_MENU)
        self.button_start_time.add(self.image_start_time)

        self.label_end_time    = gtk.Label("End Time: ")
        self.entry_end_time    = gtk.Entry(max=17)
        self.button_end_time   = gtk.Button()
        self.image_end_time    = gtk.Image()
        self.image_end_time.set_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_MENU)
        self.button_end_time.add(self.image_end_time)

        self.label_target_dir  = gtk.Label("Target Directory: ")
        self.entry_target_dir  = gtk.Entry()
        self.button_target_dir = gtk.Button()
        self.image_target_dir  = gtk.Image()
        self.image_target_dir.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        self.button_target_dir.add(self.image_target_dir)

        self.radiobutton_merge = gtk.RadioButton(group=None, label="Merge")
        self.label_merge_file  = gtk.Label("Merge File: ")
        self.entry_merge_file  = gtk.Entry()
        self.button_merge_file = gtk.Button()
        self.image_merge_file  = gtk.Image()
        self.image_merge_file.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        self.button_merge_file.add(self.image_merge_file)
        self.radiobutton_split = gtk.RadioButton(group=self.radiobutton_merge, label="Split")

        self.checkbutton_legacy = gtk.CheckButton(label="Legacy Read Algorithm")
        self.checkbutton_input_files = gtk.CheckButton(label="Only Use Files from Input File List")

      # Progress Indicators
        self.progress_file = gtk.ProgressBar()
        self.progress_byte = gtk.ProgressBar()

      # Controls
        self.button_write = gtk.Button(stock=None, use_underline=True)
        self.hbox_write   = gtk.HBox()
        self.image_write  = gtk.Image()
        self.image_write.set_from_stock(gtk.STOCK_SAVE_AS, gtk.ICON_SIZE_MENU)
        self.label_write  = gtk.Label('Write')
        self.button_write.add(self.hbox_write)
        self.hbox_write.pack_start(self.image_write, padding=1)
        self.hbox_write.pack_start(self.label_write, padding=1)

        self.button_auto_write = gtk.Button(stock=None, use_underline=True)
        self.hbox_auto_write   = gtk.HBox()
        self.image_auto_write  = gtk.Image()
        self.image_auto_write.set_from_stock(gtk.STOCK_SAVE_AS, gtk.ICON_SIZE_MENU)
        self.label_auto_write  = gtk.Label('Auto-Write')
        self.button_auto_write.add(self.hbox_auto_write)
        self.hbox_auto_write.pack_start(self.image_auto_write, padding=1)
        self.hbox_auto_write.pack_start(self.label_auto_write, padding=1)

        self.button_cancel_write = gtk.Button(stock=None, use_underline=True)
        self.hbox_cancel_write   = gtk.HBox()
        self.image_cancel_write  = gtk.Image()
        self.image_cancel_write.set_from_stock(gtk.STOCK_CANCEL, gtk.ICON_SIZE_MENU)
        self.label_cancel_write  = gtk.Label('Cancel Write')
        self.button_cancel_write.add(self.hbox_cancel_write)
        self.hbox_cancel_write.pack_start(self.image_cancel_write, padding=1)
        self.hbox_cancel_write.pack_start(self.label_cancel_write, padding=1)

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

        self.vbox_main.pack_start(self.hbox_notebook, True,  True,  5)
        self.vbox_main.pack_start(self.xbox_progress, False, True,  0)
        self.vbox_main.pack_start(self.hbox_control,  False, True,  0)

        self.hbox_notebook.pack_start(self.notebook,  True,  True,  1)

        self.notebook.append_page(self.page_input,     tab_label=gtk.Label("Input"))
        self.notebook.append_page(self.page_selection, tab_label=gtk.Label("Channels"))
        self.notebook.append_page(self.page_output,    tab_label=gtk.Label("Output"))

        self.page_output.pack_start(             self.table_output,            True,  True,  2)

        self.page_input.pack_start(              self.hbox_input_files,        False, True,  2)
        self.page_input.pack_start(              self.hbox_input_treeview,     True,  True,  2)
        self.page_input.pack_start(              self.hbox_input_controls,     False, True,  2)

        self.hbox_input_files.pack_start(        self.button_add_files,        False, False, 1)
        self.hbox_input_files.pack_start(        self.button_add_directories,  False, False, 1)
        self.hbox_input_files.pack_end(          self.button_remove_files,     False, False, 1)
        self.hbox_input_files.pack_end(          self.button_select_all_files, False, False, 1)
        self.hbox_input_treeview.pack_start(     self.scrollwindow_files,      True,  True,  1)
        self.hbox_input_controls.pack_start(     self.button_scan,             False, False, 1)
        self.hbox_input_controls.pack_start(     self.button_rescan,           False, False, 1)
        self.hbox_input_controls.pack_end(       self.button_cancel_scan,      False, False, 1)

        self.page_selection.pack_start(          self.hbox_selection_filters,  False, True,  2)
        self.page_selection.pack_start(          self.hbox_selection_channels, True,  True,  2)
        self.page_selection.pack_start(          self.table_selection_buttons, False, True,  2)

        self.hbox_selection_filters.pack_start(  self.label_filters,           False, True,  0)
        self.hbox_selection_filters.pack_start(  self.entry_filter_network,    False, True,  0)
        self.hbox_selection_filters.pack_start(  self.entry_filter_station,    False, True,  0)
        self.hbox_selection_filters.pack_start(  self.entry_filter_location,   False, True,  0)
        self.hbox_selection_filters.pack_start(  self.entry_filter_channel,    False, True,  0)
        self.hbox_selection_channels.pack_start( self.scrollwindow_channels,   True,  True,  0)

        self.table_selection_buttons.attach( LEFT(self.label_add_channels),        0, 1, 0, 1, gtk.FILL, 0, 1, 1)
        self.table_selection_buttons.attach( self.button_add_all_channels,         1, 2, 0, 1, 0, 0, 1, 1)
        self.table_selection_buttons.attach( self.button_add_visible_channels,     2, 3, 0, 1, 0, 0, 1, 1)
        self.table_selection_buttons.attach( self.button_add_selected_channels,    3, 4, 0, 1, 0, 0, 1, 1)
        self.table_selection_buttons.attach( LEFT(self.label_remove_channels),     0, 1, 1, 2, gtk.FILL, 0, 1, 1)
        self.table_selection_buttons.attach( self.button_remove_all_channels,      1, 2, 1, 2, 0, 0, 1, 1)
        self.table_selection_buttons.attach( self.button_remove_visible_channels,  2, 3, 1, 2, 0, 0, 1, 1)
        self.table_selection_buttons.attach( self.button_remove_selected_channels, 3, 4, 1, 2, 0, 0, 1, 1)

        self.table_output.attach( LEFT(self.label_scan_first_time),    0, 1, 0, 1, gtk.FILL, 0, 1, 1)
        self.table_output.attach( LEFT(self.label_scan_start_time),    1, 2, 0, 1, gtk.FILL, 0, 1, 1)
        self.table_output.attach( LEFT(self.hbox_m_set_start_time),    2, 3, 0, 1, gtk.FILL, 0, 1, 1)
        self.table_output.attach( LEFT(self.label_scan_last_time),     0, 1, 1, 2, gtk.FILL, 0, 1, 1)
        self.table_output.attach( LEFT(self.label_scan_end_time),      1, 2, 1, 2, gtk.FILL, 0, 1, 1)
        self.table_output.attach( LEFT(self.hbox_m_set_end_time),      2, 3, 1, 2, gtk.FILL, 0, 1, 1)
        self.table_output.attach( LEFT(self.label_start_time),         0, 1, 2, 3, gtk.FILL, 0, 1, 1)
        self.table_output.attach( self.entry_start_time,               1, 3, 2, 3, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_output.attach( self.button_start_time,              3, 4, 2, 3, 0, 0, 1, 1)
        self.table_output.attach( LEFT(self.label_end_time),           0, 1, 3, 4, gtk.FILL, 0, 1, 1)
        self.table_output.attach( self.entry_end_time,                 1, 3, 3, 4, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_output.attach( self.button_end_time,                3, 4, 3, 4, 0, 0, 1, 1)
        self.table_output.attach( LEFT(self.label_target_dir),         0, 1, 4, 5, gtk.FILL, 0, 1, 1)
        self.table_output.attach( self.entry_target_dir,               1, 3, 4, 5, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_output.attach( self.button_target_dir,              3, 4, 4, 5, 0, 0, 1, 1)
        self.table_output.attach( LEFT(self.radiobutton_merge),        0, 1, 5, 6, gtk.FILL, 0, 1, 1)
        self.table_output.attach( self.entry_merge_file,               1, 3, 5, 6, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_output.attach( self.button_merge_file,              3, 4, 5, 6, 0, 0, 1, 1)
        self.table_output.attach( LEFT(self.radiobutton_split),        0, 1, 6, 7, gtk.FILL, 0, 1, 1)
        self.table_output.attach( LEFT(self.checkbutton_legacy),       0, 4, 7, 8, gtk.FILL, 0, 1, 1)
        self.table_output.attach( LEFT(self.checkbutton_input_files),  0, 4, 8, 9, gtk.FILL, 0, 1, 1)

        self.hbox_control.pack_start( self.button_write,        False, False,  0)
        self.hbox_control.pack_start( self.button_auto_write,   False, False,  0)
        self.hbox_control.pack_start( self.button_cancel_write, False, False,  0)
        self.hbox_control.pack_end(   self.button_quit,         False, False,  0)

        self.xbox_progress.pack_start( self.progress_file, True, True, 5)
        self.xbox_progress.pack_start( self.progress_byte, True, True, 5)

        self.treeview_files.append_column(     self.treeviewcol_files)
        self.treeview_channels.append_column(  self.treeviewcol_network)
        self.treeview_channels.append_column(  self.treeviewcol_station)
        self.treeview_channels.append_column(  self.treeviewcol_location)
        self.treeview_channels.append_column(  self.treeviewcol_channel)

# ===== Widget Configurations ======================================
        self.calendar_start = Calendar()
        self.calendar_start.set_callback(self.callback_populate_time, (self.calendar_start, self.entry_start_time))
        self.calendar_start.set_granularity('second')
        self.calendar_start.set_default_high(False)

        self.calendar_end = Calendar()
        self.calendar_end.set_callback(self.callback_populate_time, (self.calendar_end, self.entry_end_time))
        self.calendar_end.set_granularity('second')
        self.calendar_end.set_default_high(True)

        self.entry_filter_network.set_width_chars(15)
        self.entry_filter_station.set_width_chars(15)
        self.entry_filter_location.set_width_chars(15)
        self.entry_filter_channel.set_width_chars(15)

        # Default to splitting data into individual files
        self.radiobutton_split.set_active(True)

        self.treeview_files.set_model(     self.treestore_files)
        self.treeview_channels.set_model(  self.treestore_channels)

        self.treestore_channels.set_visible_func(self.filter_channels)

        self.treeviewcol_files.pack_start(     self.crtext_files,     True)
        self.treeviewcol_network.pack_start(   self.crtext_network,   True)
        self.treeviewcol_station.pack_start(   self.crtext_station,   True)
        self.treeviewcol_location.pack_start(  self.crtext_location,  True)
        self.treeviewcol_channel.pack_start(   self.crtext_channel,   True)

        self.treeviewcol_files.add_attribute(     self.crtext_files,     'text', 0)
        self.treeviewcol_network.add_attribute(   self.crtext_network,   'text', 0)
        self.treeviewcol_station.add_attribute(   self.crtext_station,   'text', 1)
        self.treeviewcol_location.add_attribute(  self.crtext_location,  'text', 2)
        self.treeviewcol_channel.add_attribute(   self.crtext_channel,   'text', 3)

        self.treeview_files.get_selection().set_mode(     gtk.SELECTION_MULTIPLE)
        self.treeview_channels.get_selection().set_mode(  gtk.SELECTION_MULTIPLE)

        self.treestore_files.set_sort_func(0, self.sort_files)
        self.treestore_channels.get_model().set_sort_func(0, self.sort_channels, "network")
        self.treestore_channels.get_model().set_sort_func(1, self.sort_channels, "station")
        self.treestore_channels.get_model().set_sort_func(2, self.sort_channels, "location")
        self.treestore_channels.get_model().set_sort_func(3, self.sort_channels, "channel")

        self.treeviewcol_network.set_cell_data_func(  self.crtext_network,  self.cdf_format_channels, None)
        self.treeviewcol_station.set_cell_data_func(  self.crtext_station,  self.cdf_format_channels, None)
        self.treeviewcol_location.set_cell_data_func( self.crtext_location, self.cdf_format_channels, None)
        self.treeviewcol_channel.set_cell_data_func(  self.crtext_channel,  self.cdf_format_channels, None)

        self.checkbutton_legacy.set_active(False)
        self.checkbutton_input_files.set_active(False)

        self.label_scan_start_time.set_markup(self.time_markup("None"))
        self.label_scan_end_time.set_markup(self.time_markup("None"))

# ===== Tooltips ===================================================

        self.apply_tooltip(self.button_add_files,            "Add one or more files to the list")
        self.apply_tooltip(self.button_add_directories,      "Add all files in one or more directories to the list")
        self.apply_tooltip(self.button_select_all_files,     "Highlight all files in the file list")
        self.apply_tooltip(self.button_remove_files,         "Remove highlighted files from the file list")
        self.apply_tooltip(self.button_scan,                 "Scans all files, adding channels, and updating the time range")
        self.apply_tooltip(self.button_rescan,               "Scans all files, replacing the channels and time range")
        self.apply_tooltip(self.button_cancel_scan,          "Cancel the scan operation")

        self.apply_tooltip(self.entry_filter_network,        "Filter by network ID")
        self.apply_tooltip(self.entry_filter_station,        "Filter by station name")
        self.apply_tooltip(self.entry_filter_location,       "Filter by location code")
        self.apply_tooltip(self.entry_filter_channel,        "Filter by channel name")
        self.apply_tooltip(self.button_add_all_channels,     "Select all channels for writing, including those hidden by filters")
        self.apply_tooltip(self.button_add_visible_channels, "Select all non-hidden channels for writing")
        self.apply_tooltip(self.button_add_visible_channels, "Select all highlighted channels for writing")
        self.apply_tooltip(self.button_add_all_channels,     "De-select all channels for writing, including those hidden by filters")
        self.apply_tooltip(self.button_add_visible_channels, "De-select all non-hidden channels for writing")
        self.apply_tooltip(self.button_add_visible_channels, "De-select all highlighted channels for writing")

        self.apply_tooltip(self.label_scan_start_time,       "Start time for oldest SEED record")
        self.apply_tooltip(self.label_scan_end_time,         "End time for youngest SEED record")
        self.apply_tooltip(self.entry_start_time,            "Only write SEED records that contain data newer than this date")
        self.apply_tooltip(self.button_start_time,           "Open a calendar to specify start time")
        self.apply_tooltip(self.entry_end_time,              "Only write SEED records that contain data older than this date")
        self.apply_tooltip(self.button_end_time,             "Open a calendar to specify end time")
        self.apply_tooltip(self.entry_target_dir,            "Location to store output files if we are splitting")
        self.apply_tooltip(self.button_target_dir,           "Open a directory chooser to specify the target directory")
        self.apply_tooltip(self.entry_merge_file,            "File in which to store all ouput records if we are merging")
        self.apply_tooltip(self.button_merge_file,           "Open a file chooser to specify the merge file")
        self.apply_tooltip(self.radiobutton_merge,           "Merge all output SEED records in the specified merge file")
        self.apply_tooltip(self.radiobutton_split,           "Split all output into files by network, station, location and channel. " +
                                                                "These files are stored in the target directory")
        self.apply_tooltip(self.checkbutton_legacy,          "Use the older read algorithm (faster, but less flexible)")
        self.apply_tooltip(self.checkbutton_input_files,     "If this is not selected, the program will use all files that have been scanned, even if they are no longer in the input file list.")

        self.apply_tooltip(self.button_write,                "Standard write operation (requires a pre-scan and channel selections)")
        self.apply_tooltip(self.button_auto_write,           "Write data that matches filter entries and dates")
        self.apply_tooltip(self.button_cancel_write,         "Cancel a write or auto-write operation")
        self.apply_tooltip(self.button_quit,                 "Close the application (Alt + q)")

# ===== Event Bindings =============================================
        self.window.connect("destroy-event", self.callback_quit, None)
        self.window.connect("delete-event",  self.callback_quit, None)

        self.button_add_files.connect(        "clicked", self.callback_add_files,        None)
        self.button_add_directories.connect(  "clicked", self.callback_add_directories,  None)
        self.button_remove_files.connect(     "clicked", self.callback_remove_files,     None)
        self.button_select_all_files.connect( "clicked", self.callback_select_all_files, None)
        self.button_scan.connect(             "clicked", self.callback_scan,             None)
        self.button_rescan.connect(           "clicked", self.callback_rescan,           None)
        self.button_cancel_scan.connect(      "clicked", self.callback_cancel_scan,      None)

        self.button_add_all_channels.connect(         "clicked", self.callback_add_all_channels,         None)
        self.button_add_visible_channels.connect(     "clicked", self.callback_add_visible_channels,     None)
        self.button_add_selected_channels.connect(    "clicked", self.callback_add_selected_channels,    None)
        self.button_remove_all_channels.connect(      "clicked", self.callback_remove_all_channels,      None)
        self.button_remove_visible_channels.connect(  "clicked", self.callback_remove_visible_channels,  None)
        self.button_remove_selected_channels.connect( "clicked", self.callback_remove_selected_channels, None)

        self.button_target_dir.connect(       "clicked", self.callback_target_dir,      None)
        self.button_merge_file.connect(       "clicked", self.callback_merge_file,      None)
        self.button_write.connect(            "clicked", self.callback_write,           None)
        self.button_auto_write.connect(       "clicked", self.callback_auto_write,      None)
        self.button_cancel_write.connect(     "clicked", self.callback_cancel_write,    None)
        self.button_quit.connect(             "clicked", self.callback_quit,            None)
        self.button_add_all_channels.connect( "clicked", self.callback_add_all_channels, None)

        self.radiobutton_split.connect(      "toggled", self.callback_radio,           None)
        self.radiobutton_merge.connect(      "toggled", self.callback_radio,           None)

        self.window.connect("key-press-event", self.callback_key_pressed)

        self.button_set_start_time.connect( "clicked", self.callback_set_start_time, None)
        self.button_set_end_time.connect(   "clicked", self.callback_set_end_time,   None)

        self.button_start_time.connect( "clicked", self.callback_show_calendar, (self.calendar_start, self.entry_start_time))
        self.button_end_time.connect(   "clicked", self.callback_show_calendar, (self.calendar_end,   self.entry_end_time))

        self.entry_start_time.connect(  "changed", self.callback_update_times, None)
        self.entry_end_time.connect(    "changed", self.callback_update_times, None)

        self.treeview_files.get_selection().connect(     "changed", self.callback_selection, None)
        self.treeview_channels.get_selection().connect(  "changed", self.callback_selection, None)

        self.entry_filter_network.connect(  "changed", self.callback_filter_changed, None, "network")
        self.entry_filter_station.connect(  "changed", self.callback_filter_changed, None, "station")
        self.entry_filter_location.connect( "changed", self.callback_filter_changed, None, "location")
        self.entry_filter_channel.connect(  "changed", self.callback_filter_changed, None, "channel")

      # Hidden Buttons (Used for Threaded GUI update)
        self.hbutton_channel_added       = gtk.Button()
        self.hbutton_scan_complete       = gtk.Button()
        self.hbutton_write_complete      = gtk.Button()
        self.hbutton_auto_write_complete = gtk.Button()
        self.hbutton_file_count          = gtk.Button()
        self.hbutton_byte_count          = gtk.Button()
        self.hbutton_dir_dne             = gtk.Button()
        self.hbutton_file_exists         = gtk.Button()

        self.hbutton_channel_added.connect(       'clicked', self.callback_channel_added,       None)
        self.hbutton_scan_complete.connect(       'clicked', self.callback_scan_complete,       None)
        self.hbutton_write_complete.connect(      'clicked', self.callback_write_complete,      None)
        self.hbutton_auto_write_complete.connect( 'clicked', self.callback_auto_write_complete, None)
        self.hbutton_file_count.connect(          'clicked', self.callback_file_count,          None)
        self.hbutton_byte_count.connect(          'clicked', self.callback_byte_count,          None)
        self.hbutton_dir_dne.connect(             'clicked', self.callback_dir_dne,             None)
        self.hbutton_file_exists.connect(         'clicked', self.callback_file_exists,         None)

      # Show widgets
        self.window.show_all()
        self.window.resize(540, 480)
        self.update_interface()
        self.xbox_progress.hide_all()

    def apply_tooltip(self, widget, tip):
        try:
            widget.set_tooltip_text(tip)
        except:
            self.tooltips.set_tip(widget, tip) 

# ===== Callbacks ==================================================
    def callback_key_pressed(self, widget, event, data=None):
        if event.state == gtk.gdk.MOD1_MASK:
            if event.keyval == ord('q'):
                self.callback_quit(widget, event, data)
        self.update_interface()

    def callback_filter_changed(self, widget, event, data=None):
        text = widget.get_text()
        regex = None
        if text == '':
            regex = None
        else:
            try: regex = re.compile(text, re.IGNORECASE)
            except: regex = None
        if data == 'network':
            self.regex_network = regex
        elif data == 'station':
            self.regex_station = regex
        elif data == 'location':
            self.regex_location = regex
        elif data == 'channel':
            self.regex_channel = regex
        self.treestore_channels.refilter()
        self.update_interface()

    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, event, data)

    def callback_write(self, widget, event, data=None):
        self.write()
        self.update_interface()

    def callback_auto_write(self, widget, event, data=None):
        self.auto_write()
        self.update_interface()

    def callback_cancel_write(self, widget, event, data=None):
        if self.writing:
            self.cancel_write()
        if self.auto_writing:
            self.cancel_auto_write()
        self.update_interface()

    def callback_add_files(self, widget, event, data=None):
        self.add_files()
        self.update_interface()

    def callback_add_directories(self, widget, event, data=None):
        self.add_directories()
        self.update_interface()

    def callback_remove_files(self, widget, event, data=None):
        self.remove_files()
        self.update_interface()

    def callback_select_all_files(self, widget, event, data=None):
        self.select_all_files()
        self.update_interface()

    def callback_add_all_channels(self, widget, event, data=None):
        self.add_all_channels()
        self.update_interface()

    def callback_add_visible_channels(self, widget, event, data=None):
        self.add_visible_channels()
        self.update_interface()

    def callback_add_selected_channels(self, widget, event, data=None):
        self.add_selected_channels()
        self.update_interface()

    def callback_remove_all_channels(self, widget, event, data=None):
        self.remove_all_channels()
        self.update_interface()

    def callback_remove_visible_channels(self, widget, event, data=None):
        self.remove_visible_channels()
        self.update_interface()

    def callback_remove_selected_channels(self, widget, event, data=None):
        self.remove_selected_channels()
        self.update_interface()

    def callback_scan(self, widget, event, data=None):
        self.scan(all=False)
        self.update_interface()

    def callback_rescan(self, widget, event, data=None):
        self.scan(all=True)
        self.update_interface()

    def callback_cancel_scan(self, widget, event, data=None):
        self.cancel_scan()
        self.update_interface()

    def callback_target_dir(self, widget, event, data=None):
        self.entry_target_dir.set_text(select_directory(self.output_directory))
        self.update_interface()

    def callback_merge_file(self, widget, event, data=None):
        self.entry_merge_file.set_text(select_save_file(self.output_directory, filter_id='seed'))
        self.update_interface()

    def callback_radio(self, widget, event, data=None):
        self.update_interface()

    def callback_selection(self, widget, event, data=None):
        self.update_interface()

    def callback_channel_added(self, widget, event, data=None):
        self.channel_added()

    def callback_scan_complete(self, widget, event, data=None):
        self.scan_complete()

    def callback_write_complete(self, widget, event, data=None):
        self.cancel_write()

    def callback_auto_write_complete(self, widget, event, data=None):
        self.cancel_auto_write()

    def callback_file_count(self, widget, event, data=None):
        self.file_count()

    def callback_byte_count(self, widget, event, data=None):
        self.byte_count()

    def callback_set_start_time(self, widget, event, data=None):
        if self.scan_start_time is not None:
            self.entry_start_time.set_text(time.strftime("%Y,%j,%H:%M:%S", time.gmtime(self.scan_start_time / 10000)))
            self.update_package_times()

    def callback_set_end_time(self, widget, event, data=None):
        if self.scan_end_time is not None:
            self.entry_end_time.set_text(time.strftime("%Y,%j,%H:%M:%S", time.gmtime(self.scan_end_time / 10000)))
            self.update_package_times()

    def callback_dir_dne(self, widget, event, data=None):
        if self.writing:
            self.cancel_write()
        if self.auto_writing:
            self.cancel_auto_write()
        message = gtk.MessageDialog(parent=self.window, type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK)
        message.set_markup("Output directory '%s' does not exist.\nWrite operation cancelled." % self.context_dir_dne)
        message.run()
        message.destroy()

    def callback_file_exists(self, widget, event, data=None):
        if self.writing:
            self.cancel_write()
        if self.auto_writing:
            self.cancel_auto_write()
        message = gtk.MessageDialog(parent=self.window, type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK)
        message.set_markup("Output file '%s' already exists.\nWrite operation cancelled." % self.context_file_exists)
        message.run()
        message.destroy()

  # Calendar Callbacks
    def callback_show_calendar(self, widget, data):
        (calendar, entry) = data
        self.propogate_time(data)
        calendar.prompt()

    def callback_populate_time(self, data):
        (calendar, widget) = data
        value = time.strftime(self.date_format, calendar.get_date())
        widget.set_text( value )
        self.update_package_times()

    def callback_update_times(self, widget, event, data=None):
        self.update_package_times()

# ===== Cell Data Methods ============================================
    def cdf_format_channels(self, column, cell, model, iter, data=None):
        if model.get_value(iter, 4):
            cell.set_property("foreground", "#bb0000")
            cell.set_property("background", "#cccccc")
        else:
            cell.set_property("foreground", "#000000")
            cell.set_property("background", "#ffffff")

# ===== TreeView Methods ===========================================
    def sort_files(self, treemodel, iter1, iter2, user_data=None):
        cmp(treemodel.get_value(iter1, 0), treemodel.get_value(iter2, 0))

    def sort_channels(self, treemodel, iter1, iter2, user_data=None):
        if   user_data == "network" : column = 0
        elif user_data == "station" : column = 1
        elif user_data == "location": column = 2
        elif user_data == "channel" : column = 3
        v1 = treemodel.get_value(iter1, column)
        v2 = treemodel.get_value(iter2, column)
        return cmp(v1, v2)

    def filter_channels(self, model, iter, user_data=None):
        if self.regex_network and not self.regex_network.search(model.get_value(iter, 0)):
            return False
        if self.regex_station and not self.regex_station.search(model.get_value(iter, 1)):
            return False
        if self.regex_location and not self.regex_location.search(model.get_value(iter, 2)):
            return False
        if self.regex_channel and not self.regex_channel.search(model.get_value(iter, 3)):
            return False
        return True

# ===== Methods ====================================================
    def flush_queue(self, queue):
        while not queue.empty():
            queue.get()

    def flush_queues(self):
        # This must be run when cancelling an operation. This ensures
        # that we do not have residual data in our queues.
        self.flush_queue(self.queue_channels)
        self.flush_queue(self.queue_file_count)
        self.flush_queue(self.queue_byte_count)

    def update_interface(self):
        # Users shouldn't be doing anything if we are processing data
        if self.writing or self.scanning or self.auto_writing:
            self.button_add_files.set_sensitive(False)
            self.button_add_directories.set_sensitive(False)
            self.entry_filter_network.set_sensitive(False)
            self.entry_filter_station.set_sensitive(False)
            self.entry_filter_location.set_sensitive(False)
            self.entry_filter_channel.set_sensitive(False)
            self.entry_start_time.set_sensitive(False)
            self.button_set_start_time.set_sensitive(False)
            self.button_set_end_time.set_sensitive(False)
            self.button_start_time.set_sensitive(False)
            self.entry_end_time.set_sensitive(False)
            self.button_end_time.set_sensitive(False)
            self.radiobutton_merge.set_sensitive(False)
            self.radiobutton_split.set_sensitive(False)

            self.button_rescan.set_sensitive(False)
            self.button_scan.set_sensitive(False)
            self.button_write.set_sensitive(False)
            self.button_auto_write.set_sensitive(False)
            self.button_cancel_scan.set_sensitive(False)
            self.button_cancel_write.set_sensitive(False)
            self.checkbutton_legacy.set_sensitive(False)
            self.checkbutton_input_files.set_sensitive(False)

            self.button_add_all_channels.set_sensitive(False)
            self.button_add_visible_channels.set_sensitive(False)
            self.button_add_selected_channels.set_sensitive(False)
            self.button_remove_all_channels.set_sensitive(False)
            self.button_remove_visible_channels.set_sensitive(False)
            self.button_remove_selected_channels.set_sensitive(False)
            self.button_select_all_files.set_sensitive(False)
            self.button_remove_files.set_sensitive(False)
            self.entry_target_dir.set_sensitive(False)
            self.button_target_dir.set_sensitive(False)
            self.entry_merge_file.set_sensitive(False)
            self.button_merge_file.set_sensitive(False)

            if self.writing or self.auto_writing:
                self.button_cancel_write.set_sensitive(True)
            elif self.scanning:
                self.button_cancel_scan.set_sensitive(True)
        else:
            self.button_add_files.set_sensitive(True)
            self.button_add_directories.set_sensitive(True)
            self.entry_filter_network.set_sensitive(True)
            self.entry_filter_station.set_sensitive(True)
            self.entry_filter_location.set_sensitive(True)
            self.entry_filter_channel.set_sensitive(True)
            self.button_set_start_time.set_sensitive(True)
            self.button_set_end_time.set_sensitive(True)
            self.entry_start_time.set_sensitive(True)
            self.button_start_time.set_sensitive(True)
            self.entry_end_time.set_sensitive(True)
            self.button_end_time.set_sensitive(True)
            self.radiobutton_merge.set_sensitive(True)
            self.radiobutton_split.set_sensitive(True)
            self.checkbutton_legacy.set_sensitive(True)
            self.checkbutton_input_files.set_sensitive(True)

            self.button_rescan.set_sensitive(True)
            self.button_scan.set_sensitive(True)
            self.button_write.set_sensitive(True)
            self.button_auto_write.set_sensitive(True)
            self.button_cancel_scan.set_sensitive(False)
            self.button_cancel_write.set_sensitive(False)

            # enable target output directory/file depending on
            # output method selected
            if self.radiobutton_merge.get_active():
                self.entry_merge_file.set_sensitive(True)
                self.button_merge_file.set_sensitive(True)
                self.entry_target_dir.set_sensitive(False)
                self.button_target_dir.set_sensitive(False)
            elif self.radiobutton_split.get_active():
                self.entry_merge_file.set_sensitive(False)
                self.button_merge_file.set_sensitive(False)
                self.entry_target_dir.set_sensitive(True)
                self.button_target_dir.set_sensitive(True)

            if self.treeview_files.get_selection().count_selected_rows():
                self.button_remove_files.set_sensitive(True)
            else:
                self.button_remove_files.set_sensitive(False)

            if self.treestore_files.get_iter_first():
                self.button_select_all_files.set_sensitive(True)
                self.button_scan.set_sensitive(True)
            else:
                self.button_select_all_files.set_sensitive(False)
                self.button_scan.set_sensitive(False)

            if self.treeview_channels.get_selection().count_selected_rows():
                self.button_add_selected_channels.set_sensitive(True)
                self.button_remove_selected_channels.set_sensitive(True)
            else:
                self.button_add_selected_channels.set_sensitive(False)
                self.button_remove_selected_channels.set_sensitive(False)

            if self.treestore_channels.get_iter_first():
                self.button_add_visible_channels.set_sensitive(True)
                self.button_remove_visible_channels.set_sensitive(True)
            else:
                self.button_add_visible_channels.set_sensitive(False)
                self.button_remove_visible_channels.set_sensitive(False)

            if self.treestore_channels.get_model().get_iter_first():
                self.button_add_all_channels.set_sensitive(True)
                self.button_remove_all_channels.set_sensitive(True)
            else:
                self.button_add_all_channels.set_sensitive(False)
                self.button_remove_all_channels.set_sensitive(False)

            if self.radiobutton_merge.get_active():
                if not len(self.entry_merge_file.get_text()):
                    self.button_write.set_sensitive(False)
                    self.button_auto_write.set_sensitive(False)
            elif not os.path.exists(self.entry_target_dir.get_text()):
                self.button_write.set_sensitive(False)
                self.button_auto_write.set_sensitive(False)
            if not self.treestore_files.get_iter_first():
                self.button_write.set_sensitive(False)
                self.button_auto_write.set_sensitive(False)

    def time_markup(self, text):
        return '<span foreground="#0000bb">%s</span>' % text

    def count_markup(self, text):
        return '<span foreground="#0000bb">%s</span>' % text

    def propogate_time(self, data):
        (calendar, widget) = data
        regex = re.compile(self.date_expr)
        if regex.match(widget.get_text()):
            value = time.strptime(widget.get_text(), self.date_format)
            calendar.set_date(value)
        self.update_package_times()

    def update_package_times(self):
        regex     = re.compile(self.date_expr)
        start_str = self.entry_start_time.get_text()
        end_str   = self.entry_end_time.get_text()
        if regex.match(start_str):
            self.package_start_time = float(calendar.timegm(time.strptime(start_str, self.date_format)) * 10000)
        else:
            self.package_start_time = None
        if regex.match(end_str):
            self.package_end_time = float(calendar.timegm(time.strptime(end_str, self.date_format)) * 10000)
        else:
            self.package_end_time = None

    def update_scanned_files(self, file):
        self.scan_files[file] = 1

    def update_file_count(self, count, total):
        self.queue_file_count.put((count, total))
        self.notify_file_count()

    def update_byte_count(self, count, total):
        self.queue_byte_count.put((count, total))
        self.notify_byte_count()

    def notify_file_count(self):
        gobject.idle_add(gobject.GObject.emit, self.hbutton_file_count, 'clicked')

    def notify_byte_count(self):
        gobject.idle_add(gobject.GObject.emit, self.hbutton_byte_count, 'clicked')

    def file_count(self):
        if self.writing or self.auto_writing:
            count,total = self.queue_file_count.get()
            self.progress_file.set_text("reading file %d of %d" % (count,total))
            self.progress_file.set_fraction(float(count)/float(total))
            self.xbox_progress.show_all()
        elif self.scanning:
            count,total = self.queue_file_count.get()
            self.progress_file.set_text("scanning file %d of %d" % (count,total))
            self.progress_file.set_fraction(float(count)/float(total))
            self.xbox_progress.show_all()
        else:
            self.progress_file.set_text('')
            self.xbox_progress.hide_all()

    def byte_count(self):
        if self.writing or self.auto_writing:
            count,total = self.queue_byte_count.get()
            self.progress_byte.set_text("%d of %d bytes read" % (count,total))
            self.progress_byte.set_fraction(float(count)/float(total))
            self.xbox_progress.show_all()
        elif self.scanning:
            count,total = self.queue_byte_count.get()
            self.progress_byte.set_text("%d of %d bytes scanned" % (count,total))
            self.progress_byte.set_fraction(float(count)/float(total))
            self.xbox_progress.show_all()
        else:
            self.progress_byte.set_text('')
            self.xbox_progress.hide_all()

# ===== Scan Thread 
    def scan(self, all):
        # Launch scan thread
        if self.scanning or self.writing or self.auto_writing:
            return
        file_list = []
        if all:
            self.delete_all_channels()
            self.scan_start_time = None
            self.scan_end_time   = None
            self.package_files   = {}
            file_list = self.get_row_list(self.treestore_files)
        else:
            for file in self.get_row_list(self.treestore_files):
                if self.scan_files.has_key(file) and self.scan_files[file] == 0:
                    file_list.append(file)
        self.scan_thread = ScanThread(self, self.log_thread.queue)
        self.reader = SEEDReader(self, self.scan_thread.queue, self.log_thread.queue)
        self.reader.add_files(file_list)
        #self.reader.set_finish_callback(self.scan_done)
        self.reader.set_header_info_only(True)
        self.reader.set_use_legacy_algorithm(self.checkbutton_legacy.get_active())
        self.read_thread = ReadThread(self.log_thread.queue)
        self.read_thread.set_reader(self.reader)
        self.scanning = True
        self.scan_thread.start()
        self.read_thread.start()

    def get_row_list(self, treestore):
        rows = []
        iter = treestore.get_iter_first()
        while iter is not None:
            rows.append(treestore.get_value(iter, 0))
            iter = treestore.iter_next(iter)
        return rows

    def notify_scan_complete(self):
        # Halt the scan thread once the ReadThread is finished
        gobject.idle_add(gobject.GObject.emit, self.hbutton_scan_complete, 'clicked')

    def scan_complete(self):
        self.cancel_scan()

    def cancel_scan(self):
        # Terminate scan thread
        if self.read_thread and self.read_thread.isAlive():
            self.read_thread.halt()
            self.read_thread.join()
        if self.scan_thread and self.scan_thread.isAlive():
            self.scan_thread.halt()
            self.scan_thread.join()
        del self.read_thread
        del self.scan_thread
        self.read_thread = None
        self.scan_thread = None
        self.scanning = False
        if self.scan_start_time is not None:
            self.label_scan_start_time.set_markup(self.time_markup(time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(self.scan_start_time / 10000))))
        else:
            self.label_scan_start_time.set_markup(self.time_markup('None'))
        if self.scan_end_time is not None:
            self.label_scan_end_time.set_markup(self.time_markup(time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(self.scan_end_time / 10000))))
        else:
            self.label_scan_end_time.set_markup(self.time_markup('None'))
        #self.treeview_channels.sort_column_changed()
        self.progress_file.set_text('')
        self.progress_byte.set_text('')
        self.xbox_progress.hide_all()
        self.flush_queues()
        self.update_interface()

# ===== Input File Management
    def add_files(self):
        # Add files to the file list treestore
        if (type(self.last_path) == str) and os.path.isdir(self.last_path):
            files = select_files(self.last_path, filter_id='seed')
        else:
            files = select_files(self.archive_directory, filter_id='seed')
        self.treeview_files.set_model(None)
        for file in files:
            if not self.scan_files.has_key(file):
                self.scan_files[file] = 0
                self.treestore_files.append(None, [file])
                self.last_path = dir_from_file_path(file)
        self.treeview_files.set_model(self.treestore_files)

    def add_directories(self):
        # Add all files from these directories to the file list treestore
        if (type(self.last_path) == str) and os.path.isdir(self.last_path):
            dirs = select_directories(self.last_path)
        else:
            dirs = select_directories(self.archive_directory)
        self.treeview_files.set_model(None)
        for file in scan_directories(dirs, -1):
            if not self.scan_files.has_key(file):
                self.scan_files[file] = 0
                self.treestore_files.append(None, [file])
                self.last_path = dir_from_file_path(file)
        self.treeview_files.set_model(self.treestore_files)

    def remove_files(self):
        # Remove selected files from the file list treestore
        selection = self.treeview_files.get_selection().get_selected_rows()
        refs = []
        model = self.treestore_files
        for path in selection[1]:
            refs.append(gtk.TreeRowReference(model, path))

        for ref in refs:
            path = ref.get_path()
            iter = model.get_iter(path)
            key  = model.get_value(iter, 0)
            if self.scan_files.has_key(key):
                del self.scan_files[key]
            model.remove(iter)

    def select_all_files(self):
        self.treeview_files.grab_focus()
        self.treeview_files.emit('select-all')

    def notify_dir_dne(self):
        gobject.idle_add(gobject.GObject.emit, self.hbutton_dir_dne, 'clicked')

    def notify_file_exists(self):
        gobject.idle_add(gobject.GObject.emit, self.hbutton_file_exists, 'clicked')

# ===== Channel Management
    def channel_added(self):
        # Add channels to the channels treestore via the queue
        n,s,l,c = tuple(map(str.strip, self.queue_channels.get()))
        self.treestore_channels.get_model().append(None, [n, s, l, c, False])

    def notify_channel_added(self):
        gobject.idle_add(gobject.GObject.emit, self.hbutton_channel_added, 'clicked')

    def get_all_channels(self):
        refs = []
        model = self.treestore_channels.get_model()
        iter = model.get_iter_first()
        while iter:
            path = model.get_path(iter)
            refs.append(gtk.TreeRowReference(model, path))
            iter = model.iter_next(iter)
        return refs

    def get_visible_channels(self):
        refs = []
        model = self.treestore_channels.get_model()
        filter = self.treestore_channels
        filter_iter = filter.get_iter_first()
        while filter_iter:
            iter = filter.convert_iter_to_child_iter(filter_iter)
            path = model.get_path(iter)
            refs.append(gtk.TreeRowReference(model, path))
            filter_iter = filter.iter_next(filter_iter)
        return refs

    def get_selected_channels(self):
        selection = self.treeview_channels.get_selection().get_selected_rows()
        refs = []
        model = self.treestore_channels.get_model()
        filter = self.treestore_channels
        for filter_path in selection[1]:
            path = filter.convert_path_to_child_path(filter_path)
            refs.append(gtk.TreeRowReference(model, path))
        return refs

    def add_channels(self, refs):
        model = self.treestore_channels.get_model()
        for ref in refs:
            path = ref.get_path()
            iter = model.get_iter(path)
            model.set_value(iter, 4, True)
            n = model.get_value(iter, 0)
            s = model.get_value(iter, 1)
            l = model.get_value(iter, 2)
            c = model.get_value(iter, 3)
            key = '-'.join(map(str.strip,[n,s,l,c]))
            self.package_channels[key] = True

    def add_all_channels(self):
        self.add_channels(self.get_all_channels())

    def add_visible_channels(self):
        self.add_channels(self.get_visible_channels())

    def add_selected_channels(self):
        self.add_channels(self.get_selected_channels())

    def remove_channels(self, refs):
        # Remove every selected channel from the list of selected channels
        model = self.treestore_channels.get_model()
        for ref in refs:
            path = ref.get_path()
            iter = model.get_iter(path)
            model.set_value(iter, 4, False)
            n = model.get_value(iter, 0)
            s = model.get_value(iter, 1)
            l = model.get_value(iter, 2)
            c = model.get_value(iter, 3)
            key = '-'.join(map(str.strip,[n,s,l,c]))
            self.package_channels[key] = False

    def remove_all_channels(self):
        self.remove_channels(self.get_all_channels())

    def remove_visible_channels(self):
        self.remove_channels(self.get_visible_channels())

    def remove_selected_channels(self):
        self.remove_channels(self.get_selected_channels())

    def delete_channels(self, refs):
        # Remove every selected channel from the list of selected channels
        model = self.treestore_channels.get_model()
        for ref in refs:
            path = ref.get_path()
            iter = model.get_iter(path)
            n = model.get_value(iter, 0)
            s = model.get_value(iter, 1)
            l = model.get_value(iter, 2)
            c = model.get_value(iter, 3)
            key = '-'.join(map(str.strip,[n,s,l,c]))
            del self.package_channels[key]
            model.remove(iter)

    def delete_all_channels(self):
        self.delete_channels(self.get_all_channels())

    def delete_visible_channels(self):
        self.delete_channels(self.get_visible_channels())

    def delete_selected_channels(self):
        self.delete_channels(self.get_selected_channels())

# ===== Write Thread
    def write(self):
        # Launch the Package, Read and Write threads to re-package 
        # the SEED data as specified, and write the data out to
        # the specified files
        #self._log("Scanning: %s" % str(self.scanning), 'dbg')
        #self._log("Writing:  %s" % str(self.writing), 'dbg')
        if self.scanning or self.writing or self.auto_writing:
            return
        self.write_thread = WriteThread(self, self.log_thread.queue)
        self.package_thread = PackageThread(self, self.write_thread.queue, self.log_thread.queue)
        self.reader = SEEDReader(self, self.package_thread.queue, self.log_thread.queue)
        temp_file_dict = {}
        for (key,value) in self.package_channels.items():
            if value:
                if not self.package_files.has_key(key):
                    self._log("key mismatch on '%s' between package_channels and package_files" % key, "err")
                else:
                    for file in self.package_files[key].keys():
                        if not self.checkbutton_input_files.get_active() or self.scan_files.has_key(file):
                            temp_file_dict[file] = 0
        file_list = temp_file_dict.keys()
        self.reader.add_files(file_list)
        self.reader.set_header_info_only(False)
        self.reader.set_use_legacy_algorithm(self.checkbutton_legacy.get_active())
        self.read_thread = ReadThread()
        self.read_thread.set_reader(self.reader)
        if self.radiobutton_merge.get_active():
            self.write_thread.set_mode('MERGE')
            self.write_thread.set_merge_file(self.entry_merge_file.get_text())
        elif self.radiobutton_split.get_active():
            self.write_thread.set_mode('SPLIT')
            self.write_thread.set_target_dir(self.entry_target_dir.get_text())
        self.writing = True
        self.write_thread.start()
        self.package_thread.start()
        self.read_thread.start()

    def notify_write_complete(self):
        # Halt the WriteThread once the PackageThread & ReadThread are finished
        gobject.idle_add(gobject.GObject.emit, self.hbutton_write_complete, 'clicked')

    def cancel_write(self):
        # Terminate the Package, Read and Write threads
        if self.read_thread and self.read_thread.isAlive():
            self.read_thread.halt()
            self.read_thread.join()
        if self.package_thread and self.package_thread.isAlive():
            self.package_thread.halt()
            self.package_thread.join()
        if self.write_thread and self.write_thread.isAlive():
            self.write_thread.halt()
            self.write_thread.join()
        del self.read_thread
        del self.package_thread
        del self.write_thread
        self.read_thread = None
        self.package_thread = None
        self.write_thread = None
        self.writing = False
        self.progress_file.set_text('')
        self.progress_byte.set_text('')
        self.xbox_progress.hide_all()
        self.flush_queues()
        self.update_interface()

# ===== Auto-Write Thread
    def auto_write(self):
        # Launch the Package, Read and Write threads to re-package 
        # the SEED data as specified, and write the data out to
        # the specified files
        #self._log("Scanning: %s" % str(self.scanning), 'dbg')
        #self._log("Writing:  %s" % str(self.writing), 'dbg')
        if self.scanning or self.writing or self.auto_writing:
            return
        self.write_thread = WriteThread(self, self.log_thread.queue)
        self.auto_package_thread = AutoPackageThread(self, self.write_thread.queue, self.log_thread.queue)
        self.reader = SEEDReader(self, self.auto_package_thread.queue, self.log_thread.queue)
        self.reader.add_files(self.get_row_list(self.treestore_files))
        self.reader.set_header_info_only(False)
        self.reader.set_use_legacy_algorithm(self.checkbutton_legacy.get_active())
        self.read_thread = ReadThread()
        self.read_thread.set_reader(self.reader)
        if self.radiobutton_merge.get_active():
            self.write_thread.set_mode('MERGE')
            self.write_thread.set_merge_file(self.entry_merge_file.get_text())
        elif self.radiobutton_split.get_active():
            self.write_thread.set_mode('SPLIT')
            self.write_thread.set_target_dir(self.entry_target_dir.get_text())
        self.auto_writing = True
        self.auto_package_channels = {}
        self.write_thread.start()
        self.auto_package_thread.start()
        self.read_thread.start()

    def notify_auto_write_complete(self):
        gobject.idle_add(gobject.GObject.emit, self.hbutton_auto_write_complete, 'clicked')

    def cancel_auto_write(self):
        if self.read_thread and self.read_thread.isAlive():
            self.read_thread.halt()
            self.read_thread.join()
        if self.auto_package_thread and self.auto_package_thread.isAlive():
            self.auto_package_thread.halt()
            self.auto_package_thread.join()
        if self.write_thread and self.write_thread.isAlive():
            self.write_thread.halt()
            self.write_thread.join()
        del self.read_thread
        del self.auto_package_thread
        del self.write_thread
        self.read_thread = None
        self.auto_package_thread = None
        self.write_thread = None
        self.auto_package_channels = {}
        self.auto_writing = False
        self.progress_file.set_text('')
        self.progress_byte.set_text('')
        self.xbox_progress.hide_all()
        self.flush_queues()
        self.update_interface()


# ===== Quit Application
    def close_application(self, widget, event, data=None):
        if self.writing:
            self.cancel_write()
        if self.auto_writing:
            self.cancel_auto_write()
        if self.scanning:
            self.cancel_scan()
        if self.log_thread and self.log_thread.isAlive():
            self.log_thread.halt()
            self.log_thread.join()
        gtk.main_quit()
        return False

    def halt_all_threads(self):
        if self.read_thread and self.read_thread.isAlive():
            self.read_thread.halt()
            self.read_thread.join()
        if self.write_thread and self.write_thread.isAlive():
            self.write_thread.halt()
            self.write_thread.join()
        if self.auto_package_thread and self.auto_package_thread.isAlive():
            self.auto_package_thread.halt()
            self.auto_package_thread.join()
        if self.package_thread and self.package_thread.isAlive():
            self.package_thread.halt()
            self.package_thread.join()
        if self.log_thread and self.log_thread.isAlive():
            self.log_thread.halt()
            self.log_thread.join()
#/*}}}*/

# === SEEDReader Class /*{{{*/
class SEEDReader(Class):
    def __init__(self, gui, record_queue, log_queue):
        Class.__init__(self)
        self.gui = gui
        self.log_queue = log_queue
        self.record_queue = record_queue

        self.files = []
        self.verbosity = 0
        self.succinct = False
        self.print_unknowns = False
        self.circular = False
        self.reading = False
        self.report_file_names = False
        self.start_callback = None
        self.finish_callback = None
        self.header_info_only = False
        self.record_length = 256
        self.file_name = ''
        self.use_legacy_algorithm = False

    def stop(self):
        self.reading = False

    def run(self):
        self.reading = True
        if self.start_callback:
            self.start_callback()
        self._run()
        if self.finish_callback:
            self.finish_callback()
        self.reading = False

    def _run(self):
        count = 0
        total = len(self.files)
        self._log("Preparing to process %d files..." % len(self.files), 'info')
        for file in self.files:
            count += 1
            self.gui.update_file_count(count, total)
            if not self.reading:
                self._log('File processing canceled.\n', 'dbg')
                break
            if self.use_legacy_algorithm:
                self._log('Using legacy read algorithm.\n', 'dbg')
                self._process_file_legacy(file)
            else:
                self._log('Using default read algorithm.\n', 'dbg')
                self.file_name = file
                self._process_file()
            if self.reading:
                self.gui.update_scanned_files(file)
        self.reading = False
        if not self.succinct:
            self._log('Done.\n', 'dbg')
        self.record_queue.put(('DONE', None))

    def is_running(self):
        return self.reading

    def clear_files(self):
        self.files = []

    def add_file(self, file):
        if not self.is_running():
            self.files.append(file)

    def add_files(self, files):
        if not self.is_running():
            self.files.extend(files)

    def set_start_callback(self, callback):
        if not callable(callback):
            raise TypeError("SEEDReader::set_start_callback(callback): argument must be callable")
        self.finish_callback = callback

    def set_finish_callback(self, callback):
        if not callable(callback):
            raise TypeError("SEEDReader::set_finish_callback(callback): argument must be callable")
        self.finish_callback = callback

    def set_header_info_only(self, header_only):
        self.header_info_only = header_only

    def set_use_legacy_algorithm(self, enabled):
        self.use_legacy_algorithm = enabled == True

    def read_record(self):
        if self.record_length < 256:
            self.record_length = 256
        record = self.fh.read(self.record_length)
        if len(record) == 0:
            self._log("File '%s': reached the end of the file.\n" % self.file_name, 'dbg')
            return ('EOF', None)
        if len(record) < 256:
            self._log("File '%s': incomplete record. Record size is less than 256 bytes.\n" % self.file_name, 'warn')
            return ('EOF', None)
        index = struct.unpack('>H', record[46:48])[0]
        if index >= len(record) - 48:
            self._log("File '%s': invalid record. Index of first blockette is out of range.\n" % self.file_name, 'err')
            return ('INVALID', None)
        blockette_type = struct.unpack('>H', record[index:index+2])[0]
        if blockette_type != 1000:
            self._log("File '%s': invalid record. First blockette of a SEED record should always be type 1000.\n" % self.file_name, 'err')
            return ('INVALID', None)
        record_length = 2 ** struct.unpack('>B', record[index+6:index+7])[0]
        if record_length < 256:
            self._log("File '%s': invalid record. Record length field must be 256 bytes or greater.\n" % self.file_name, 'err')
            return ('INVALID', None)
        # If we need more data, get it
        if record_length > self.record_length:
            record += self.fh.read(record_length - self.record_length)
        # If we don't have enough data for a full record, we are at the end of the file
        if len(record) < record_length:
            self._log("File '%s': incomplete record. Record size is less than '%d' bytes.\n" % (self.file_name, record_length), 'warn')
            return ('EOF', None)
        # If we got too much data, correct the record size, and fix file seek position
        if record_length < self.record_length:
            record = record[0:record_length]
            self.fh.seek(self.fh.tell() - (self.record_length - record_length), 0)
        # Fix the default record length for next time
        if record_length != self.record_length:
            self.record_length = record_length
        return ('VALID', record)

    def _process_file(self):
        byte_count = 0
        byte_total = 0
        byte_step  = 0
        byte_next  = 0

        file_stats = os.stat(self.file_name)
        if file_stats[stat.ST_SIZE] < 256:
            self._log("File '%s' is too small to contain SEED data.\n" % self.file_name, 'err')
            return

        byte_total = file_stats[stat.ST_SIZE]
        byte_step = float(byte_total) / 100.0

        self.fh = open(self.file_name, 'rb')
        msg,rec = self.read_record()
        if msg in ('INVALID', 'EOF'):
            return
        record_length = len(rec)

        circular = False
        idx_last = 0
        idx_max  = 0
        seek_pos = 0
        if self.file_name[-4:] == '.buf' and os.path.isfile(self.file_name[:-4] + '.idx'):
            index_file = self.file_name[:-4] + '.idx'
            ifh   = open(index_file, 'r')
            lines = ifh.readlines()
            ifh.close()
            if (type(lines) != list) or (len(lines) != 3):
                self._log("'%s' file does not contain three lines.\n" % index_file, 'dbg')
            elif not ((lines[0] == lines[1]) and (lines[0] == lines[2])):
                self._log("'%s' lines do not match.\n" % index_file, 'dbg')
            else:
                total_records = file_stats[stat.ST_SIZE] / record_length
                total_file_bytes = record_length * total_records
                try:
                    idx_last,idx_max = tuple(map(int, lines[0].strip().split(' ', 1)))
                except ValueError:
                    self._log("'%s' lines are invalid.\n" % index_file, 'dbg')
                if not idx_max:
                    self._log("'%s' states circular buffer max size is 0.\n" % index_file, 'dbg')
                elif idx_last > idx_max:
                    self._log("'%s' last index greater than max size.\n" % index_file, 'dbg')
                elif idx_last > total_records:
                    self._log("'%s' last index greater than buffer file size.\n" % index_file, 'dbg')
                elif idx_max > total_records:
                    self._log("'%s' is not full, so it will be treated like a flat file.\n" % index_file, 'dbg')
                else:
                    circular = True
                    self._log("File '%s' has a valid .idx file, and will be treated as a circular buffer" % self.file_name, 'dbg')
                    seek_pos = idx_last * record_length
                    self.fh.seek(seek_pos,0)
                    record_count = 0
                    first = True
                    timestamp = None
                    while 1:
                        if not self.reading: return # Check for SEEDReader termination

                        # Give us a little cheat room
                        if record_count >= (total_records + 2):
                            break
                        msg,record = self.read_record()
                        if msg == 'EOF':
                            self._log("Circular buffer pre-processing failed (mis-calculated file size, whoops).\n", 'warn')
                            circular = False
                            break
                        if total_file_bytes == self.fh.tell():
                            self.fh.seek(0,0)
                        old_timestamp = timestamp
                        record_count += 1
                        timestamp = tuple(struct.unpack('>HHBBBBH', record[20:30]))
                        if first:
                            first = False
                        else:
                            if CMP_SEED_TIMES(old_timestamp, timestamp) < 0:
                                index = self.fh.tell()
                                if index <= record_length:
                                    seek_pos = (total_records - 1) * record_length
                                else:
                                    seek_pos = index - record_length
                                break
                                self._log("Scanned %d records looking for first in circular buffer\n" % record_count, 'dbg')

        self._log("Starting read of file '%s' at position %d" % (self.file_name, seek_pos), 'dbg')
        self.fh.seek(seek_pos, 0)
        record_count = 0
        while 1:
            if not self.reading: return # Check for SEEDReader termination

            if circular: 
                if record_count >= total_records:
                    self._log("Done reading file (reached record count limit).\n", 'dbg')
                    break

            msg,record = self.read_record()
            if msg == 'EOF':
                self._log("Done reading file (reached end of file).\n", 'dbg')
                break
            elif msg == 'INVALID':
                return
            record_count += 1

            byte_count += len(record)
            if byte_count >= byte_next:
                self.gui.update_byte_count(byte_count, byte_total)
                byte_next += byte_step

            seq_num, _, _, st_name, ch_loc, ch_name, st_net, y, d, h, m, s, _, t, sample_count, rate_factor, rate_multiplier, activity_flags, _, _, _, time_correction, _, _ = struct.unpack('>6scc5s2s3s2sHHBBBBHHhhBBBBlHH', record[0:48]) 

            if rate_factor == 0:
                self._log("Found sample rate factor of zero.\n", 'dbg')
                rate = 0
            elif rate_multiplier == 0:
                self._log("Found sample rate multiplier of zero.\n", 'dbg')
                rate = 0
            else:
                if rate_factor > 0:
                    if rate_multiplier < 0:
                        rate = 1.0 / float(rate_factor) / float(rate_multiplier)
                    else:
                        rate = 1.0 / float(rate_factor) * float(rate_multiplier)
                else:
                    if rate_multiplier < 0:
                        rate = float(rate_factor) / float(rate_multiplier)
                    else:
                        rate = float(rate_factor) * float(rate_multiplier)
                #self._log("Record # %s (%s_%s %s-%s) %u,%u %02u:%02u:%02u.%04u (count[%d] factor[%d] multiplier[%d])" % (seq_num, st_net, st_name, ch_loc, ch_name, y, d, h, m, s, t, sample_count, rate_factor, rate_multiplier))
                rate *= 10000

            if y < 1 or d < 1:
                self._log("Found a bad date (%04u,%03u %02u:%02u:%02u.%04u).\n" % (y,d,h,m,s,t), 'warn')
                b_time = 0
            else:
                b_time = int(calendar.timegm(time.strptime("%04u,%03u,%02u:%02u:%02u" % (y,d,h,m,s), "%Y,%j,%H:%M:%S"))) * 10000 + t

            if (activity_flags & 0x02) == 0:
                b_time += time_correction
            e_time = b_time + rate * (sample_count - 1)

            # Send record to handler thread
            if self.header_info_only:
                self.record_queue.put(('READ',(self.file_name,seq_num,st_net,st_name,ch_loc,ch_name,b_time,e_time,None)))
            else:
                self.record_queue.put(('READ',(self.file_name,seq_num,st_net,st_name,ch_loc,ch_name,b_time,e_time,record)))

            if self.verbosity > 3:
                year,jday,hour,min,sec,_,tmsec = b_time
                position = self.fh.tell()
                self._log("Record %d [%d:%d] {%d:%d} " % (record_count,(position-record_length)/record_length,position/record_length,position-record_length,position))
                if self.verbosity > 4:
                    self._log("[%04u,%03u %02u:%02u:%02u.%04u]" % (year, jday, hour, min, sec, tmsec))
                self._log("\n")

            # Cycle back around if we have reached the end of the file
            if circular and (total_file_bytes <= self.fh.tell()):
                self.fh.seek(0,0)
        
        self._log("Read %d SEED records (%d bytes)\n\n" % (record_count, byte_count), 'dbg')
        self.fh.close()

    def _process_file_legacy(self, file_name):
        byte_count = 0
        byte_total = 0
        byte_step  = 0
        byte_next  = 0
        record_length = 256

        circular = self.circular
        if (not os.path.exists(file_name)) or (not os.path.isfile(file_name)):
            self._log("Unable to locate file '%s'\n" % file_name, 'err')
            return

        if circular:
            if file_name[-4:] != '.buf':
                self._log("File '%s' does not appear to be a circular buffer.\n" % file_name, 'err')
                return
            if not os.path.isfile(file_name[:-4] + '.idx'):
                self._log("File '%s' does not have an accompanying .idx file.\n" % file_name, 'err')
                return

        file_stats = os.stat(file_name)

        if file_stats[stat.ST_SIZE] < 256:
            self._log("File '%s' is too small to contain SEED data.\n" % file_name, 'err')
            return

        byte_total = file_stats[stat.ST_SIZE]
        byte_step = float(byte_total) / 100.0

        fh = open(file_name, 'rb')
        record = fh.read(256)
        index = struct.unpack('>H', record[46:48])[0]
        if index >= len(record) - 48:
            self._log("File '%s' is not valid SEED. Index of first blockette is out of range.\n" % file_name, 'err')
            return
        blockette_type = struct.unpack('>H', record[index:index+2])[0]
        if blockette_type != 1000:
            self._log("File '%s' is not valid SEED. First blockette of a SEED record should always be type 1000.\n" % file_name, 'err')
            return

        record_length = 2 ** struct.unpack('>B', record[index+6:index+7])[0]
        if record_length < 256:
            self._log("File '%s' is not valid SEED. Recod length must be 256 bytes or greater.\n" % file_name, 'err')
            return

        if self.report_file_names:
            self._log("Processing file %s\n" % file_name)

        total_records = file_stats[stat.ST_SIZE] / record_length
        total_file_bytes = record_length * total_records
        st_name, ch_loc, ch_name, st_net = struct.unpack('>5s2s3s2s', record[8:20])

        num_records = total_records

        idx_last = 0
        idx_max  = 0
        if circular:
            index_file = file_name[:-4] + '.idx'
            ifh   = open(index_file, 'r')
            lines = ifh.readlines()
            ifh.close()
            if (type(lines) != list) or (len(lines) != 3):
                self._log("'%s' file does not contain three lines.\n" % index_file, 'err')
                return
            if not ((lines[0] == lines[1]) and (lines[0] == lines[2])):
                self._log("'%s' lines do not match.\n" % index_file, 'err')
                return
            try:
                idx_last,idx_max = tuple(map(int, lines[0].strip().split(' ', 1)))
            except ValueError:
                self._log("'%s' lines are invalid.\n" % index_file, 'err')
            if not idx_max:
                self._log("'%s' states circular buffer max size is 0.\n" % index_file, 'err')
                return
            if idx_last > idx_max:
                self._log("'%s' last index greater than max size.\n" % index_file, 'err')
                return
            if idx_last > total_records:
                self._log("'%s' last index greater than buffer file size.\n" % index_file, 'err')
                return
            # If the circular buffer isn't full, we can treat it like a flat file
            if idx_max > total_records:
                circular = False

        #if not self.succinct:
        #    self._log("===============================================================\n")
        #    self._log("\n")
        if (self.verbosity > 0) and (not self.succinct):
            self._log("RECORD SIZE --- %d bytes\n" % record_length)
            self._log("RECORD COUNT -- %d\n" % total_records)
            self._log("TOTAL SIZE ---- %d bytes\n\n" % file_stats[stat.ST_SIZE])

        seek_pos = 0
        if circular:
            seek_pos = idx_last * record_length
            fh.seek(seek_pos,0)
            record = fh.read(record_length)
            if len(record) != record_length:
                self._log("Circular buffer pre-processing failed (mis-calculated file size, whoops).\n", 'warn')
            if total_file_bytes <= fh.tell():
                fh.seek(0,0)
            timestamp = tuple(struct.unpack('>HHBBBBH', record[20:30]))
            record_count = 1
            while 1:
                if not self.reading: return

                # Give us a little cheat room
                if record_count >= (total_records + 2):
                    break
                record = fh.read(record_length)
                if len(record) != record_length:
                    self._log("Circular buffer pre-processing failed (mis-calculated file size, whoops).\n", 'warn')
                if total_file_bytes <= fh.tell():
                    fh.seek(0,0)
                old_timestamp = timestamp
                record_count += 1
                timestamp = tuple(struct.unpack('>HHBBBBH', record[20:30]))
                if CMP_SEED_TIMES(old_timestamp, timestamp) < 0:
                    index = fh.tell()
                    if index <= record_length:
                        seek_pos = (total_records - 1) * total_records
                    else:
                        seek_pos = index - record_length
                    break
            if (not self.succinct) and (self.verbosity > 0):
                self._log("Scanned %d records looking for first in circular buffer\n" % record_count)
        else:
            if num_records < total_records:
                seek_pos = (total_records - num_records) * record_length
        fh.seek(seek_pos, 0)

        record_count = 0
        while 1:
            if not self.reading: return

            if record_count >= num_records:
                if not self.succinct:
                    self._log("Done reading file.\n", 'dbg')
                break

            if circular:
                if fh.tell() >= (record_length * total_records):
                    fh.seek(0,0)

            record = fh.read(record_length)
            if len(record) != record_length:
                if not self.succinct:
                    self._log("Done reading file (mis-calculated file size, whoops).\n", 'warn')
                break
            record_count += 1

            byte_count += record_length
            if byte_count >= byte_next:
                self.gui.update_byte_count(byte_count, byte_total)
                byte_next += byte_step

            st_name, ch_loc, ch_name, st_net = struct.unpack('>5s2s3s2s', record[8:20])

            seq_num, _, _, st_name, ch_loc, ch_name, st_net, y, d, h, m, s, _, t, sample_count, rate_factor, rate_multiplier, activity_flags, _, _, _, time_correction, _, _ = struct.unpack('>6scc5s2s3s2sHHBBBBHHhhBBBBlHH', record[0:48]) 

            if rate_factor == 0:
                self._log("Found sample rate factor of zero.\n", 'dbg')
                rate = 0
            elif rate_multiplier == 0:
                self._log("Found sample rate multiplier of zero.\n", 'dbg')
                rate = 0
            else:
                if rate_factor > 0:
                    if rate_multiplier < 0:
                        rate = 1.0 / float(rate_factor) / float(rate_multiplier)
                    else:
                        rate = 1.0 / float(rate_factor) * float(rate_multiplier)
                else:
                    if rate_multiplier < 0:
                        rate = float(rate_factor) / float(rate_multiplier)
                    else:
                        rate = float(rate_factor) * float(rate_multiplier)
                #self._log("Record # %s (%s_%s %s-%s) %u,%u %02u:%02u:%02u.%04u (count[%d] factor[%d] multiplier[%d])" % (seq_num, st_net, st_name, ch_loc, ch_name, y, d, h, m, s, t, sample_count, rate_factor, rate_multiplier))
                rate *= 10000

            if y < 1 or d < 1:
                self._log("Found a bad date (%04u,%03u %02u:%02u:%02u.%04u).\n" % (y,d,h,m,s,t), 'warn')
                b_time = 0
            else:
                b_time = int(calendar.timegm(time.strptime("%04u,%03u,%02u:%02u:%02u" % (y,d,h,m,s), "%Y,%j,%H:%M:%S"))) * 10000 + t

            if (activity_flags & 0x02) == 0:
                b_time += time_correction
            e_time = b_time + rate * (sample_count - 1)

            # Send record to handler thread
            if self.header_info_only:
                self.record_queue.put(('READ',(file_name,seq_num,st_net,st_name,ch_loc,ch_name,b_time,e_time,None)))
            else:
                self.record_queue.put(('READ',(file_name,seq_num,st_net,st_name,ch_loc,ch_name,b_time,e_time,record)))

            if self.verbosity > 3:
                year,jday,hour,min,sec,_,tmsec = b_time
                position = fh.tell()
                self._log("Record %d [%d:%d] {%d:%d} " % (record_count,(position-record_length)/record_length,position/record_length,position-record_length,position))
                if self.verbosity > 4:
                    self._log("[%04u,%03u %02u:%02u:%02u.%04u]" % (year, jday, hour, min, sec, tmsec))
                self._log("\n")

            # Cycle back around if we have reached the end of the file
            if circular and (total_file_bytes <= fh.tell()):
                fh.seek(0,0)
        
        if not self.succinct:
            self._log("Number of %d-byte SEED records: %d\n\n" % (record_length, record_count), 'dbg')
        fh.close()
#/*}}}*/

# === AutoPackageThread Class /*{{{*/
class AutoPackageThread(Thread):
    def __init__(self, gui, write_queue, log_queue=None):
        Thread.__init__(self, 1024)
        self.gui = gui
        self.write_queue = write_queue
        self.log_queue = log_queue

    def _run(self, message, data):
        if message == 'READ':
            # [n] Network 
            # [s] Station
            # [l] Location
            # [c] Channel
            # [b] Begin timestamp
            # [e] End timestamp
            # [r] Record
            f,q,n,s,l,c,b,e,r = data
            key = '-'.join(map(str.strip,data[2:6]))
            if not self.gui.auto_package_channels.has_key(key):
                included = True
                if self.gui.regex_network and not self.gui.regex_network.search(n.strip()):
                    included = False
                if self.gui.regex_station and not self.gui.regex_station.search(s.strip()):
                    included = False
                if self.gui.regex_location and not self.gui.regex_location.search(l.strip()):
                    included = False
                if self.gui.regex_channel and not self.gui.regex_channel.search(c.strip()):
                    included = False
                self.gui.auto_package_channels[key] = included
                if not included:
                    return
            elif not self.gui.auto_package_channels[key]:
                return
            if (self.gui.package_end_time is not None) and (b > self.gui.package_end_time): 
                #self._log("RECORD # %s REJECTED DUE TO END TIME:" % q, 'dbg')
                #self._log("Package Start Time: %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(self.gui.package_start_time / 10000)), self.gui.package_start_time), 'dbg')
                #self._log("Package End Time:   %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(self.gui.package_end_time / 10000)), self.gui.package_end_time), 'dbg')
                #self._log("Record Start Time:  %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(b / 10000)), b), 'dbg')
                #self._log("Record End Time:    %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(e / 10000)), e), 'dbg')
                return
            if (self.gui.package_start_time is not None) and (e < self.gui.package_start_time): 
                #self._log("RECORD # %s REJECTED DUE TO START TIME:" % q, 'dbg')
                #self._log("Package Start Time: %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(self.gui.package_start_time / 10000)), self.gui.package_start_time), 'dbg')
                #self._log("Package End Time:   %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(self.gui.package_end_time / 10000)), self.gui.package_end_time), 'dbg')
                #self._log("Record Start Time:  %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(b / 10000)), b), 'dbg')
                #self._log("Record End Time:    %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(e / 10000)), e), 'dbg')
                return
            self.write_queue.put(('WRITE', data))
        else:
            self._log("Unrecognized message '%s' from queue" % message, 'warn')

    def _post(self):
        self.gui.notify_auto_write_complete()
# /*}}}*/

# === PackageThread Class /*{{{*/
class PackageThread(Thread):
    def __init__(self, gui, write_queue, log_queue=None):
        Thread.__init__(self, 1024)
        self.gui = gui
        self.write_queue = write_queue
        self.log_queue = log_queue

    def _run(self, message, data):
        if message == 'READ':
            # [n] Network 
            # [s] Station
            # [l] Location
            # [c] Channel
            # [b] Begin timestamp
            # [e] End timestamp
            # [r] Record
            f,q,n,s,l,c,b,e,r = data
            key = '-'.join(map(str.strip,data[2:6]))
            try:
                if not self.gui.package_channels[key]: return
            except KeyError: return
            if (self.gui.package_end_time is not None) and (b > self.gui.package_end_time): 
                #self._log("RECORD # %s REJECTED DUE TO END TIME:" % q, 'dbg')
                #self._log("Package Start Time: %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(self.gui.package_start_time / 10000)), self.gui.package_start_time), 'dbg')
                #self._log("Package End Time:   %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(self.gui.package_end_time / 10000)), self.gui.package_end_time), 'dbg')
                #self._log("Record Start Time:  %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(b / 10000)), b), 'dbg')
                #self._log("Record End Time:    %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(e / 10000)), e), 'dbg')
                return
            if (self.gui.package_start_time is not None) and (e < self.gui.package_start_time): 
                #self._log("RECORD # %s REJECTED DUE TO START TIME:" % q, 'dbg')
                #self._log("Package Start Time: %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(self.gui.package_start_time / 10000)), self.gui.package_start_time), 'dbg')
                #self._log("Package End Time:   %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(self.gui.package_end_time / 10000)), self.gui.package_end_time), 'dbg')
                #self._log("Record Start Time:  %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(b / 10000)), b), 'dbg')
                #self._log("Record End Time:    %s [%f]" % (time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime(e / 10000)), e), 'dbg')
                return
            self.write_queue.put(('WRITE', data))

    def _post(self):
        self.gui.notify_write_complete()
# /*}}}*/

# === ScanThread Class /*{{{*/
class ScanThread(Thread):
    def __init__(self, gui, log_queue=None):
        Thread.__init__(self, queue_max=1024)
        self.gui = gui
        self.log_queue = log_queue

    def _run(self, message, data):
        if message == 'READ':
            # [n] Network 
            # [s] Station
            # [l] Location
            # [c] Channel
            # [b] Begin timestamp
            # [e] End timestamp
            # [r] Record
            f,q,n,s,l,c,b,e,r = data
            key = '-'.join(map(str.strip,data[2:6]))
            if not self.gui.package_channels.has_key(key):
                self.gui.package_channels[key] = False
                self.gui.queue_channels.put((n,s,l,c))
                self.gui.notify_channel_added()
            if not self.gui.package_files.has_key(key):
                self.gui.package_files[key] = {}
            self.gui.package_files[key][f] = 0
            if (self.gui.scan_end_time is None) or (e > self.gui.scan_end_time):
                self.gui.scan_end_time = e
            if (self.gui.scan_start_time is None) or (b < self.gui.scan_start_time):
                self.gui.scan_start_time = b

    def _post(self):
        self.gui.notify_scan_complete()
        self._log("package_channels:\n%s" % str(self.gui.package_channels), 'dbg')
# /*}}}*/

# === ReadThread Class /*{{{*/
class ReadThread(Thread):
    def __init__(self, log_queue=None):
        Thread.__init__(self)
        self.daemon = True
        self.reader = None
        self.log_queue = log_queue

    def set_reader(self, reader):
        self.reader = reader

    def halt(self):
        self.reader.stop()

    def run(self):
        try:
            if not self.reader:
                raise ValueError("reader not supplied")
            elif not hasattr(self.reader, 'run') or not callable(self.reader.run):
                raise TypeError("supplied reader is has no run() method")
            self.reader.run()
        except KeyboardInterrupt:
            pass
        #except Exception, e:
        #    self._log("run() Exception: %s" % str(e), 'err')
#/*}}}*/

# === WriteThread Class /*{{{*/
class WriteThread(Thread):
    def __init__(self, gui, log_queue=None):
        Thread.__init__(self, queue_max=1024)
        self.gui = gui
        self.log_queue = log_queue
        self.file_handles = {}
        self.file_handle = None

        self.mode = ''
        self.merge_file = ''
        self.target_dir = ''

    def set_mode(self, mode):
        self.mode = mode

    def set_merge_file(self, merge_file):
        self.merge_file = merge_file

    def set_target_dir(self, target_dir):
        self.target_dir = target_dir

    def _run(self, message, data):
        try:
            if message == 'WRITE':
                if self.mode == 'SPLIT':
                    key = "%s_%s_%s_%s" % tuple(map(str.strip, data[2:6]))
                    if self.file_handles.has_key(key):
                        file_handle = self.file_handles[key]
                    else:
                        if not os.path.exists(self.target_dir):
                            raise ExDirDNE(self.target_dir)
                        file = self.target_dir + '/' + key + '.seed'
                        if os.path.exists(file):
                            raise ExFileExists(file)
                        self.file_handles[key] = open(file, 'w+b')
                        file_handle = self.file_handles[key]
                    record = data[8]
                    #self._log("SPLIT: Writing %d bytes for %s" % (len(record), key), 'dbg')
                    file_handle.write(record)
                elif self.mode == 'MERGE':
                    if not self.file_handle:
                        if os.path.exists(self.merge_file):
                            raise ExFileExists(self.merge_file)
                        self.file_handle = open(self.merge_file, 'w+b')
                    record = data[8]
                    #self._log("SPLIT: Writing %d bytes for %s" % (len(record), "%s_%s_%s_%s" % tuple(map(str.strip, data[2:6]))), 'dbg')
                    self.file_handle.write(record)
                else:
                    self._log("Unrecognized write mode '%s'" % self.mode, 'warn')
            else:
                self._log("Invalid message '%s'" % message, 'warn')
        except KeyboardInterrupt:
            pass
        except ExDirDNE, e:
            self.gui.context_dir_dne = str(e)
            self.gui.notify_dir_dne()
            self.running = False
        except ExFileExists, e:
            self.gui.context_file_exists = str(e)
            self.gui.notify_file_exists()
            self.running = False
        except Exception, e:
            self._log("_run() Exception: %s" % str(e), 'err')
#/*}}}*/
        
if __name__ == "__main__":
    try:
        app = SeedGui()
        gtk.main()
    except KeyboardInterrupt:
        if app:
            app.halt_all_threads()

