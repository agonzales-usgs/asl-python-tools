#!/usr/bin/env python
import asl

import hashlib
import os
import sys

import pygtk
pygtk.require('2.0')
import gtk
import gobject

from jtk.gtk.utils import LEFT
from jtk.gtk.utils import RIGHT
from jtk.file.utils import dir_from_file_path
from jtk.gtk.utils import select_file

def get_hash_engine(key):
    engine = None
    if key == 'MD5':
        engine = hashlib.md5()
    elif key == 'SHA-1':
        engine = hashlib.sha1()
    elif key == 'SHA-224':
        engine = hashlib.sha224()
    elif key == 'SHA-256':
        engine = hashlib.sha256()
    elif key == 'SHA-384':
        engine = hashlib.sha384()
    elif key == 'SHA-512':
        engine = hashlib.sha512()
    return engine

def hashsum(filename, key):
    engine = get_hash_engine(key)
    digest = ''
    if engine is not None:
        with open(filename,'rb') as f:
            for chunk in iter(lambda: f.read(engine.block_size), ''):
                engine.update(chunk)
        digest = engine.hexdigest()
    return digest

class HashGui:
    def __init__(self):
        if os.environ.has_key('HOME'):
            self.home_directory = os.environ['HOME']
        elif os.environ.has_key('USERPROFILE'):
            self.home_directory = os.environ['USERPROFILE']

# ===== Main Window ================================================
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Hash-Sum")
        self.window.set_icon(asl.new_icon('hash'))

# ===== Widget Creation ============================================
        self.vbox_main    = gtk.VBox()
        self.table_hash   = gtk.Table()
        self.hbox_control = gtk.HBox()

        self.label_file  = gtk.Label('File:')
        self.entry_file  = gtk.Entry()
        self.button_file = gtk.Button()
        self.image_file  = gtk.Image()
        self.image_file.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        self.button_file.add(self.image_file)

        self.label_hash = gtk.Label('Hash:')
        self.combobox_hash = gtk.combo_box_new_text()

        self.label_digest = gtk.Label('Digest:')
        self.entry_digest = gtk.Entry()

      # Control Buttons
        self.button_generate = gtk.Button(stock=None, use_underline=True)
        self.hbox_generate   = gtk.HBox()
        self.image_generate  = gtk.Image()
        self.image_generate.set_from_stock(gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU)
        self.label_generate  = gtk.Label('Generate')
        self.button_generate.add(self.hbox_generate)
        self.hbox_generate.pack_start(self.image_generate, padding=1)
        self.hbox_generate.pack_start(self.label_generate, padding=1)

        self.button_copy = gtk.Button(stock=None, use_underline=True)
        self.hbox_copy   = gtk.HBox()
        self.image_copy  = gtk.Image()
        self.image_copy.set_from_stock(gtk.STOCK_DND_MULTIPLE, gtk.ICON_SIZE_MENU)
        self.label_copy  = gtk.Label('Copy Hash')
        self.button_copy.add(self.hbox_copy)
        self.hbox_copy.pack_start(self.image_copy, padding=1)
        self.hbox_copy.pack_start(self.label_copy, padding=1)

        self.label_copy_info = gtk.Label('')

        self.button_quit = gtk.Button(stock=None, use_underline=True)
        self.hbox_quit   = gtk.HBox()
        self.image_quit  = gtk.Image()
        self.image_quit.set_from_stock(gtk.STOCK_QUIT, gtk.ICON_SIZE_MENU)
        self.label_quit  = gtk.Label('Quit')
        self.button_quit.add(self.hbox_quit)
        self.hbox_quit.pack_start(self.image_quit, padding=1)
        self.hbox_quit.pack_start(self.label_quit, padding=1)

        self.window.add( self.vbox_main )
        self.vbox_main.pack_start(self.table_hash,     False, True,  0)
        self.vbox_main.pack_start(self.hbox_control,   False, True,  0)

        self.table_hash.attach(LEFT(self.label_hash),    0, 1, 0, 1, gtk.FILL, 0, 1, 1)
        self.table_hash.attach(LEFT(self.combobox_hash), 1, 2, 0, 1, gtk.FILL, 0, 1, 1)
        self.table_hash.attach(LEFT(self.label_file),    0, 1, 1, 2, gtk.FILL, 0, 1, 1)
        self.table_hash.attach(self.entry_file,          1, 4, 1, 2, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_hash.attach(self.button_file,         4, 5, 1, 2, 0, 0, 1, 1)
        self.table_hash.attach(LEFT(self.label_digest),  0, 1, 2, 3, gtk.FILL, 0, 1, 1)
        self.table_hash.attach(self.entry_digest,        1, 4, 2, 3, gtk.FILL | gtk.EXPAND, 0, 1, 1)

        self.hbox_control.pack_start(self.button_generate, False, False, 0)
        self.hbox_control.pack_start(self.button_copy, False, False, 0)
        self.hbox_control.pack_start(self.label_copy_info, False, False, 0)
        self.hbox_control.pack_end(self.button_quit, False, False, 0)

# ===== Hidden Objects ============================================
        self.clipboard = gtk.Clipboard()

# ===== Widget Configurations ======================================
        for h in ('MD5', 'SHA-1', 'SHA-224', 'SHA-256', 'SHA-384', 'SHA-512'):
            self.combobox_hash.append_text(h)
        self.combobox_hash.set_active(0)
        self.entry_digest.set_editable(False)
        self.entry_digest.set_width_chars(64)

# ===== Event Bindings =============================================
        self.combobox_hash.connect("changed", self.callback_hash_changed, None)
        self.button_file.connect("clicked", self.callback_select_file, None)
        self.button_generate.connect("clicked", self.callback_generate, None)
        self.button_copy.connect("clicked", self.callback_copy, None)
        self.button_quit.connect("clicked", self.callback_quit, None)

      # Show widgets
        self.window.show_all()


# ===== Callbacks ==================================================
    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, event, data)

    def callback_select_file(self, widget, event, data=None):
        current_dir = self.entry_file.get_text()
        if not os.path.isdir(current_dir):
            current_dir = dir_from_file_path(current_dir)
        if os.path.isdir(current_dir):
            self.entry_file.set_text(select_file(current_dir))
        else:
            self.entry_file.set_text(select_file())
        if self.entry_file.get_text() == '':
            self.entry_file.set_text(self.home_directory)
        self.update_interface()

    def callback_hash_changed(self, widget, event, data=None):
        self.update_interface()

    def callback_copy(self, widget, event, data=None):
        self.clipboard.set_text(self.entry_digest.get_text())

    def callback_generate(self, widget, event, data=None):
        self.update_interface()
        filename = os.path.abspath(self.entry_file.get_text())
        digest = ''
        if os.path.isfile(filename):
            try:
                digest = hashsum(filename, self.combobox_hash.get_active_text())
            except:
                pass
        self.entry_digest.set_text(digest)


# ===== Methods ====================================================
    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        return False

    def update_interface(self):
        self.entry_digest.set_text('')
        self.label_copy_info.set_text('')


def main():
    app = HashGui()
    gtk.main()

if __name__ == "__main__":
    main()

