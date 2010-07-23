#!/usr/bin/env python
import pygtk
pygtk.require('2.0')
import gtk
import gobject
gobject.threads_init()

import urllib
import re
import os
import sys

sizes = [
    '21x21',
    '25x25',
    '29x29',
    '33x33',
    '57x57',
    '177x177',
]

quality = [
    'L',
    'M',
    'Q',
    'H',
]

class QR:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("QR Code Generator")

        self.vbox_main = gtk.VBox()
        self.hbox_feature = gtk.HBox()
        self.hbox_control = gtk.HBox()

        self.combobox_size = gtk.combo_box_new_text()
        self.combobox_quality = gtk.combo_box_new_text()
        self.textview = gtk.TextView()
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.add(self.textview)
        self.image = gtk.Image()
        self.button_generate = gtk.Button(label="Generate")
        self.button_close = gtk.Button(label="Close")

        self.window.add(self.vbox_main)
        self.vbox_main.pack_start(self.hbox_feature, False, True, 0)
        self.hbox_feature.pack_start(self.combobox_size, False, False, 3)
        self.hbox_feature.pack_start(self.combobox_quality, False, False, 3)
        self.vbox_main.pack_start(self.scrolledwindow, True, True, 1)
        self.vbox_main.pack_start(self.image, False, True, 1)
        self.vbox_main.pack_start(self.hbox_control, False, True, 0)
        self.hbox_control.pack_start(self.button_generate, False, False, 1)
        self.hbox_control.pack_end(self.button_close, False, False, 1)

        self.window.connect("destroy-event", self.callback_quit, None)
        self.window.connect("delete-event",  self.callback_quit, None)
        self.button_generate.connect("clicked", self.callback_generate, None)
        self.button_close.connect("clicked", self.callback_quit, None)
        self.window.connect("key-press-event", self.callback_key_pressed)

        for q in quality:
            self.combobox_quality.append_text(q)
        self.combobox_quality.set_active(len(quality)-1)

        for s in sizes:
            self.combobox_size.append_text(s)
        self.combobox_size.set_active(len(sizes)-1)

        self.textview.grab_focus()

        self.window.set_size_request(350,450)

        self.window.show_all()

    def callback_key_pressed(self, widget, event, data=None):
        if event.state == gtk.gdk.MOD1_MASK: #gtk.gdk.ALT_MASK 
            if event.keyval == ord('q'):
                self.button_close.clicked()
            elif event.keyval == ord('g'):
                self.button_generate.clicked()

    def callback_generate(self, widget, event, data=None):
        start = self.textview.get_buffer().get_start_iter()
        end = self.textview.get_buffer().get_end_iter()
        text = self.textview.get_buffer().get_text(start, end)
        size = self.combobox_size.get_active_text()
        quality = self.combobox_quality.get_active_text()
        self.generate_code(text, size, quality)

    def callback_quit(self, widget, event, data=None):
        gtk.main_quit()

    def generate_code(self, text, size, quality):
        request = {
            'cht' : 'qr',
            'chs' : size,
            'chl' : text,
            'chd' : quality,
        }
        data = urllib.urlencode(request)
        handle = urllib.urlopen('http://chart.apis.google.com/chart', data)
        info = handle.read()
        loader = gtk.gdk.PixbufLoader()
        loader.write(info)
        loader.close()
        pixbuf = loader.get_pixbuf()
        self.image.set_from_pixbuf(pixbuf)

def main():
    qr = QR()
    gtk.main()

if __name__ == '__main__':
    main()

