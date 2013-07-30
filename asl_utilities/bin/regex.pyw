#!/usr/bin/env python
import asl

import os
import re
import sre_constants
import sys

import pygtk
pygtk.require('2.0')
import gtk
import gobject

from jtk.gtk.utils import LEFT
from jtk.gtk.utils import RIGHT
from jtk.file.utils import dir_from_file_path
from jtk.gtk.utils import select_file
from jtk import hashsum

COLOR_NEUTRAL = gtk.gdk.Color(65535, 65535, 65535)
COLOR_VALID   = gtk.gdk.Color(15000, 65000, 15000)
COLOR_INVALID = gtk.gdk.Color(65000, 15000, 15000)

class RegexGui:
    def __init__(self):
        if os.environ.has_key('HOME'):
            self.home_directory = os.environ['HOME']
        elif os.environ.has_key('USERPROFILE'):
            self.home_directory = os.environ['USERPROFILE']

# ===== Main Window ================================================
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Regex Tester")
        self.window.set_icon(asl.new_icon('python'))

# ===== Widget Creation ============================================
        self.vbox_main    = gtk.VBox()
        self.table_hash   = gtk.Table()
        self.hbox_control = gtk.HBox()

        self.test_string_label = gtk.Label('Test String:')
        self.test_string_entry = gtk.Entry()

        self.regex_label = gtk.Label('Regex:')
        self.regex_entry = gtk.Entry()

        self.result_label = gtk.Label('Result:')
        self.result_entry = gtk.Entry()

      # Control Buttons
        self.copy_button = gtk.Button(stock=None, use_underline=True)
        self.hbox_copy   = gtk.HBox()
        self.image_copy  = gtk.Image()
        self.image_copy.set_from_stock(gtk.STOCK_DND_MULTIPLE, gtk.ICON_SIZE_MENU)
        self.label_copy  = gtk.Label('Copy Regex')
        self.copy_button.add(self.hbox_copy)
        self.hbox_copy.pack_start(self.image_copy, padding=1)
        self.hbox_copy.pack_start(self.label_copy, padding=1)

        self.label_copy_info = gtk.Label('')

        self.quit_button = gtk.Button(stock=None, use_underline=True)
        self.hbox_quit   = gtk.HBox()
        self.image_quit  = gtk.Image()
        self.image_quit.set_from_stock(gtk.STOCK_QUIT, gtk.ICON_SIZE_MENU)
        self.label_quit  = gtk.Label('Quit')
        self.quit_button.add(self.hbox_quit)
        self.hbox_quit.pack_start(self.image_quit, padding=1)
        self.hbox_quit.pack_start(self.label_quit, padding=1)

        self.window.add( self.vbox_main )
        self.vbox_main.pack_start(self.table_hash,     False, True,  0)
        self.vbox_main.pack_start(self.hbox_control,   False, True,  0)

        self.table_hash.attach(LEFT(self.test_string_label),  0, 1, 2, 3, gtk.FILL, 0, 1, 1)
        self.table_hash.attach(self.test_string_entry,        1, 4, 2, 3, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_hash.attach(LEFT(self.regex_label),        0, 1, 3, 4, gtk.FILL, 0, 1, 1)
        self.table_hash.attach(self.regex_entry,              1, 4, 3, 4, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_hash.attach(LEFT(self.result_label),       0, 1, 4, 5, gtk.FILL, 0, 1, 1)
        self.table_hash.attach(self.result_entry,             1, 4, 4, 5, gtk.FILL | gtk.EXPAND, 0, 1, 1)

        self.hbox_control.pack_start(self.copy_button, False, False, 0)
        self.hbox_control.pack_start(self.label_copy_info, False, False, 0)
        self.hbox_control.pack_end(self.quit_button, False, False, 0)

# ===== Hidden Objects ============================================
        self.clipboard = gtk.Clipboard()

# ===== Widget Configurations ======================================
        self.test_string_entry.set_editable(True)
        self.test_string_entry.set_width_chars(64)
        self.regex_entry.set_editable(True)
        self.regex_entry.set_width_chars(64)

# ===== Event Bindings =============================================
        self.copy_button.connect("clicked", self.callback_copy, None)
        self.quit_button.connect("clicked", self.callback_quit, None)
        self.test_string_entry.connect("changed", self.callback_update, None)
        self.regex_entry.connect("changed", self.callback_update, None)

      # Show widgets
        self.window.show_all()

        self.update_interface()


# ===== Callbacks ==================================================
    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, event, data)

    def callback_copy(self, widget, event, data=None):
        self.clipboard.set_text(self.regex_entry.get_text())

    def callback_update(self, widget, event, data=None):
        self.update_interface()


# ===== Methods ====================================================
    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        return False

    def update_interface(self):
        regex_string = self.regex_entry.get_text()
        test_string = self.test_string_entry.get_text()

        compile_failed = False
        try:
            compiled = re.compile(regex_string)
        except sre_constants.error, e:
            compile_failed = True

        if compile_failed:
            self.regex_entry.modify_base(gtk.STATE_NORMAL, COLOR_INVALID)
            self.result_entry.set_text('')
            self.result_entry.modify_base(gtk.STATE_NORMAL, COLOR_NEUTRAL)
        else:
            self.regex_entry.modify_base(gtk.STATE_NORMAL, COLOR_VALID)

            match = compiled.match(test_string)
            self.result_entry.set_text(str(match))

            if match is None:
                self.result_entry.modify_base(gtk.STATE_NORMAL, COLOR_INVALID)
            else:
                self.result_entry.modify_base(gtk.STATE_NORMAL, COLOR_VALID)

def main():
    app = RegexGui()
    gtk.main()

if __name__ == "__main__":
    main()

