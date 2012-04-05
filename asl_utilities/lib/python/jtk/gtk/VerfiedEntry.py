import time

import pygtk
pygtk.require('2.0')
import gtk
import gobject

VERIFY_TYPE_NONE = 0
VERIFY_TYPE_POPULATED = 1
VERIFY_TYPE_INT = 2
VERIFY_TYPE_FLOAT = 3
VERIFY_TYPE_DATE = 4

class VerifiedEntry(gtk.Entry):
    def __init__(self, max=0, verify_type=VERIFY_TYPE_NONE, hint_text=None):
        gtk.Entry.__init__(self, max)
        self._valid = True
        self._verify_method = self._verify_none
        self._change_callback = None
        self._change_args = []
        if hint_text == "":
            hint_text = None
        self._hint_text = hint_text

        self.connect("changed", self.callback_changed, None)
        self.connect("focus-in-event", self.callback_focus_in, None)
        self.connect("focus-out-event", self.callback_focus_out, None)
        self._verify()

# = Callbacks
    def callback_changed(self, widget, event, data=None):
        self._verify()
        if callable(self._change_callback):
            args = self._change_args
            self._change_callback(*args)

    def callback_focus_in(self, widget, event, data=None):
        self._hide_hint_text(widget)

    def callback_focus_out(self, widget, event, data=None):
        self._show_hint_text(widget)

# = Verifiers
    def _show_hint_text(self, widget):
        if not len(widget.get_text()):
            widget.set_text(widget._hint_text)
            widget.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('#888888'))

    def _hide_hint_text(self, widget):
        if widget.get_text() == widget._hint_text:
            widget.set_text('')
        widget.modify_text(gtk.STATE_NORMAL, gtk.gdk.Color())

    def _verify_none(self):
        return self.get_text()

    def _verify_populated(self):
        value = self.get_text()
        if value in ("", self._hint_text):
            raise ValueError()
        return value

    def _verify_int(self):
        return int(self.get_text())

    def _verify_float(self):
        return float(self.get_text())

    def _verify_date(self):
        #TODO Populate
        pass

    def _verify(self):
        try:
            self._verify_method()
            self.modify_base(gtk.STATE_NORMAL, gtk.gdk.Color(45000, 65000, 45000)) #Green
            self._valid = True
        except ValueError:
            self.modify_base(gtk.STATE_NORMAL, gtk.gdk.Color(65000, 45000, 45000)) #Red
            self._valid = False

# = Public Methods
    def get_verified_text(self):
        try:
            value = self._verify_method()
        except ValueError:
            value = ""
        if hasattr(self, _hint_text):
            if value == self._hint_text:
                value = ""
        return value

    def set_changed_callback(self, callback, *args):
        self._change_callback = callback
        self._change_args = args

    def verify(self):
        self._verify()
        return self._valid

