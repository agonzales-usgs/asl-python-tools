#!/usr/bin/env python
import pygtk
pygtk.require('2.0')
import gtk
import gobject

import os
import re
import struct
import sys

class Q330_Code:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Event Finder")

# ===== Widget Creation ===========================================
        self.vbox_main    = gtk.VBox()

        self.hbox_file    = gtk.HBox()
        self.hbox_display = gtk.HBox()
        self.hbox_control = gtk.HBox()

      # User Interaction Widgets
        self.label_file  = gtk.Label("Log File:")
        self.entry_file  = gtk.Entry()
        self.button_file = gtk.Button(stock=None, use_underline=True)
        self.b_hbox_file   = gtk.HBox()
        self.b_image_file  = gtk.Image()
        self.b_image_file.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        self.b_label_file  = gtk.Label('Select File')
        self.button_file.add(self.b_hbox_file)
        self.b_hbox_file.pack_start(self.b_image_file, padding=1)
        self.b_hbox_file.pack_start(self.b_label_file, padding=1)

        self.textbuffer_display = gtk.TextBuffer()
        self.textview_display   = gtk.TextView(buffer=self.textbuffer_display)
        self.scrolledwindow_display = gtk.ScrolledWindow()
        self.scrolledwindow_display.add(self.textview_display)

        self.button_find = gtk.Button(stock=None, use_underline=True)
        self.hbox_find   = gtk.HBox()
        self.image_find  = gtk.Image()
        self.image_find.set_from_stock(gtk.STOCK_ZOOM_IN, gtk.ICON_SIZE_MENU)
        self.label_find  = gtk.Label('Find Events')
        self.button_find.add(self.hbox_find)
        self.hbox_find.pack_start(self.image_find, padding=1)
        self.hbox_find.pack_start(self.label_find, padding=1)

        self.button_copy = gtk.Button(stock=None, use_underline=True)
        self.hbox_copy   = gtk.HBox()
        self.image_copy  = gtk.Image()
        self.image_copy.set_from_stock(gtk.STOCK_COPY, gtk.ICON_SIZE_MENU)
        self.label_copy  = gtk.Label('Copy')
        self.button_copy.add(self.hbox_copy)
        self.hbox_copy.pack_start(self.image_copy, padding=1)
        self.hbox_copy.pack_start(self.label_copy, padding=1)

        self.button_quit = gtk.Button(stock=None, use_underline=True)
        self.hbox_quit   = gtk.HBox()
        self.image_quit  = gtk.Image()
        self.image_quit.set_from_stock(gtk.STOCK_QUIT, gtk.ICON_SIZE_MENU)
        self.label_quit  = gtk.Label('Quit')
        self.button_quit.add(self.hbox_quit)
        self.hbox_quit.pack_start(self.image_quit, padding=1)
        self.hbox_quit.pack_start(self.label_quit, padding=1)



# ===== Layout Configuration ======================================
        self.window.add( self.vbox_main )
        self.window.set_size_request(550, 300)

        self.vbox_main.pack_start(self.hbox_file,    False, True,  0)
        self.vbox_main.pack_start(self.hbox_display, True, True,  0)
        self.vbox_main.pack_start(self.hbox_control, False, True,  0)

        self.hbox_file.pack_start(self.label_file,  False, False, 0)
        self.hbox_file.pack_start(self.entry_file,  True, True, 0)
        self.hbox_file.pack_start(self.button_file, False, False, 0)

        self.hbox_display.pack_start(self.scrolledwindow_display, True, True, 0)

        self.hbox_control.pack_start(self.button_find, False, False, 0)
        self.hbox_control.pack_start(self.button_copy, False, False, 0)
        self.hbox_control.pack_end(self.button_quit, False, False, 0)

# ===== Widget Configurations =====================================
        self.entry_file.set_text("")
        self.entry_file.grab_focus()
        self.textbuffer_display.set_text("")
        self.textview_display.set_editable(False)
        self.button_find.set_sensitive(False)
        self.button_copy.set_sensitive(False)

# ===== Hidden Objects ============================================
        self.clipboard = gtk.Clipboard()

# ===== Signal Bindings ===========================================

# ===== Event Bindings ============================================
        self.window.connect("destroy-event", self.callback_quit, None)
        self.window.connect("delete-event",  self.callback_quit, None)

        self.entry_file.connect("changed", self.callback_update_buttons, None)

        self.button_file.connect("clicked", self.callback_file, None)
        self.button_find.connect("clicked", self.callback_find, None)
        self.button_copy.connect("clicked", self.callback_copy, None)
        self.button_quit.connect("clicked", self.callback_quit, None)

# ===== Keyboard Shortcuts ========================================
        self.window.connect("key-press-event", self.callback_key_pressed)

        # Show widgets
        self.window.show_all()

# ===== Callbacks =================================================
    def callback_key_pressed(self, widget, event, data=None):
        if event.state == gtk.gdk.MOD1_MASK:
            if event.keyval == ord('q'):
                self.close_application(widget, event, data)
            elif event.keyval == ord('c'):
                if not (self.button_copy.state & gtk.STATE_INSENSITIVE):
                    self.text_to_clipboard()
            elif event.keyval == ord('f'):
                if not (self.button_find.state & gtk.STATE_INSENSITIVE):
                    self.callback_find(widget, event, data)

    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, event, data)

    def callback_find(self, widget, event, data=None):
        self.process_log()
        self.callback_update_buttons(widget, event, data)
        
    def callback_file(self, widget, event, data=None):
        self.select_file()
        self.callback_update_buttons(widget, event, data)

    def callback_update_buttons(self, widget, event, data=None):
        if len(self.entry_file.get_text()):
            self.button_find.set_sensitive(True)
        else:
            self.button_find.set_sensitive(False)
        s,e = self.textbuffer_display.get_bounds()
        if len(self.textbuffer_display.get_text(s,e)):
            self.button_copy.set_sensitive(True)
        else:
            self.button_copy.set_sensitive(False)

    def callback_copy(self, widget, event, data=None):
        self.text_to_clipboard()

# ===== Methods ===================================================
    def text_to_clipboard(self, selection=False):
        if selection:
            self.textbuffer_display.copy_clipboard()
        else:
            s,e = self.textbuffer_display.get_bounds()
            self.clipboard.set_text(self.textbuffer_display.get_text(s,e))

    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        return False

    def select_file(self):
        file_chooser = gtk.FileChooserDialog("Select Log File", None,
                                             gtk.FILE_CHOOSER_ACTION_OPEN,
                                             (gtk.STOCK_CANCEL,
                                              gtk.RESPONSE_CANCEL,
                                              gtk.STOCK_OPEN,
                                              gtk.RESPONSE_OK))
        file_chooser.set_default_response(gtk.RESPONSE_OK)
        result = file_chooser.run()
        if result == gtk.RESPONSE_OK:
            self.entry_file.set_text(file_chooser.get_filename())
        file_chooser.destroy()

    def process_log(self):
        self.textbuffer_display.set_text("")
        file_name = self.entry_file.get_text()
        records_read = 0
        if not os.path.exists(file_name):
            msgd = gtk.MessageDialog(type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK)
            msgd.set_markup("<span size='x-large' weight='bold'>Unable to locate file '%s'</span>" % file_name)
            msgd.set_default_response(gtk.RESPONSE_OK)
            result = msgd.run()
            msgd.hide()
            return
        fh = open(file_name, 'rb')
        regex = re.compile('([{]122[}].+?\r\n)', re.M)
        buffer = ""
        record = fh.read(512)
        blockette_index = struct.unpack('>H', record[46:48])[0]
        blockette_type = struct.unpack('>H', record[blockette_index:blockette_index+2])[0]
        if blockette_type != 1000:
            msgd = gtk.MessageDialog(type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK)
            msgd.set_markup("<span size='x-large' weight='bold'>File is not valid SEED. First blockette should always be type 1000.</span>")
            msgd.set_default_response(gtk.RESPONSE_OK)
            result = msgd.run()
            msgd.hide()
            return
        record_length = 2 ** struct.unpack('>B', record[blockette_index+6:blockette_index+7])[0]
        if record_length < 256:
            msgd = gtk.MessageDialog(type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK)
            msgd.set_markup("<span size='x-large' weight='bold'>File is not valid SEED. Record length must be 256 bytes or greater.</span>")
            msgd.set_default_response(gtk.RESPONSE_OK)
            result = msgd.run()
            msgd.hide()
            return
        fh.seek(0,0)
        while 1:
            record = fh.read(record_length)
            records_read += 1
            if len(record) != record_length:
                break
            next_blockette = struct.unpack('>H', record[46:48])[0]
            while next_blockette != 0:
                blockette_index = next_blockette
                blockette_type = struct.unpack('>H', record[blockette_index:blockette_index+2])[0]
                next_blockette = struct.unpack('>H', record[blockette_index+2:blockette_index+4])[0]
                if blockette_type != 1000:
                    continue
                data_index = blockette_index + 8
                data = record[data_index:]

                matches = regex.findall(data)
                if matches:
                    for match in matches:
                        buffer += match
        
        if len(buffer):
            self.textbuffer_display.set_text(buffer)
        fh.close()

if __name__ == "__main__":
    app = Q330_Code()
    gtk.main()

