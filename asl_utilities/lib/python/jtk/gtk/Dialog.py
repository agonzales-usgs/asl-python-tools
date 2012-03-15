import pygtk
pygtk.require('2.0')
import gtk
import gobject

from GtkClass import GtkClass

class Dialog(gtk.Window, GtkClass):
    def __init__(self, title='Dialog', message='', modal=False, exit_callback=None, exit_data=None):
        gtk.Window.__init__(self)
        GtkClass.__init__(self)

        self.set_modal(modal)

        self.set_title(title)
        self.vbox_main = gtk.VBox()
        self.vbox = gtk.VBox()
        self.label = gtk.Label()
        self.hbox_buttons = gtk.HBox()

        self.add(self.vbox_main)
        self.vbox_main.pack_start(self.vbox, True, True, 2)
        self.vbox.pack_end(self.hbox_buttons, False, True, 2)
        self.vbox.pack_end(self.label, False, True, 2)

        self.set_message(message)

        self._focus_widget = None
        self._hidden_buttons = {}

        exit_data = (exit_callback,exit_data,self,True)
        self.connect("destroy-event", self.master_callback, exit_data)
        self.connect("delete-event",  self.master_callback, exit_data)

    def get_hidden_button(self, key):
        button = None
        if self._hidden_buttons.has_key(key):
            self._hidden_buttons[key]
        return button

    def set_message(self, message):
        if message == '':
            self.show_message = False
            self.label.set_label('')
        else:
            self.show_message = True
            self.label.set_label(message)

    def add_button_hidden(self, key, callback=None, data=None, hide=True, focus=False):
        self._add_button(key, callback, data, hide, focus, None, key)

    def add_button_left(self, label, callback=None, data=None, hide=True, focus=False):
        self._add_button(label, callback, data, hide, focus, True)

    def add_button_right(self, label, callback=None, data=None, hide=True, focus=False):
        self._add_button(label, callback, data, hide, focus, False)

    def _add_button(self, label, callback, data, hide, focus, left, key=None):
        button = gtk.Button(label)
        self._connect(button, 'clicked', self.master_callback, None, (callback,data,self,hide))
        if key:
            self._hidden_buttons[key] = button
        if left is not None:
            if left == True:
                self.hbox_buttons.pack_start(button, False, False, 2)
            else:
                self.hbox_buttons.pack_end(button, False, False, 2)
        if focus:
            self._focus_widget = button

    def run(self):
        self.show_all()
        if not self.show_message:
            self.label.hide()
        if self._focus_widget is not None:
            self._focus_widget.grab_focus()

    def master_callback(self, widget, event, data=None):
        callback,user_data,dialog,hide = data
        if hide:
            self.hide()
        if callback is None:
            self._disconnect_all()
            self.destroy()
        else:
            callback(dialog, event, user_data)

