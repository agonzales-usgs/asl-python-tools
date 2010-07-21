#!/usr/bin/env python
import asl

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

from jtk.Thread import Thread
from jtk.Logger import LogThread
from jtk.StatefulClass import StatefulClass

class FileWidget(gtk.ScrolledWindow):
    def __init__(self):
        gtk.ScrolledWindow.__init__(self)

# ===== GUI Build-up ========================================
        self.treestore_files    = gtk.TreeStore(gobject.TYPE_STRING)
        self.treestore_files    = self.treestore_right.filter_new()
        self.treeviewcol_files  = gtk.TreeViewColumn('Files')
        self.crtext_files       = gtk.CellRendererText()

        try:
            self.tooltips = gtk.Tooltips()
        except:
            self.tooltips = None

# ===== Widget Creation ============================================
        self.vbox_main          = gtk.VBox()
        self.hbox_display       = gtk.HBox()
        self.vbox_transfer      = gtk.VBox()

        self.treeview_files     = gtk.TreeView()
        self.iconview_files     = gtk.IconView()

        self.add(self.treeview_files)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)


class FileManager(StatefulClass):
    def __init__(self):
        StatefulClass.__init__(self)
        self.load_state()

# ===== GUI Build-up ========================================
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("File Manager")
        self.window.set_icon(asl.new_icon('aluminum_inactive'))

        

    def close_application(self, widget, event, data=None):
        self.save_state()
        gtk.main_quit()
        return False

        

