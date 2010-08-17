#!/usr/bin/env python
import asl

import pygtk
pygtk.require('2.0')
import gtk
import gobject

class Key:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Key")
        self.window.set_icon(asl.new_icon('keyboard'))

# ===== Widget Creation ===========================================
        self.hbox_main = gtk.HBox()
        self.vbox_label = gtk.VBox()
        self.vbox_display = gtk.VBox()

      # User Interaction Widgets
        self.label_state   = gtk.Label("State:")
        self.label_keyval  = gtk.Label("Key Value:")
        self.label_string  = gtk.Label("String:")
        self.label_keycode = gtk.Label("HW Key Code:")
        self.label_group   = gtk.Label("Keyboard Group:")

        self.label_state_v   = gtk.Label("")
        self.label_keyval_v  = gtk.Label("")
        self.label_string_v  = gtk.Label("")
        self.label_keycode_v = gtk.Label("")
        self.label_group_v   = gtk.Label("")


# ===== Layout Configuration ======================================
        self.window.add(self.hbox_main)
        #self.window.set_size_request(250,250)

        self.hbox_main.pack_start(self.vbox_label,     False, True,  0)
        self.hbox_main.pack_start(self.vbox_display,   False, True,  0)

        self.vbox_label.pack_start(self.label_state,   False, False, 2)
        self.vbox_label.pack_start(self.label_keyval,  False, False, 2)
        self.vbox_label.pack_start(self.label_string,  False, False, 2)
        self.vbox_label.pack_start(self.label_keycode, False, False, 2)
        self.vbox_label.pack_start(self.label_group,   False, False, 2)

        self.vbox_display.pack_start(self.label_state_v,   False, False, 2)
        self.vbox_display.pack_start(self.label_keyval_v,  False, False, 2)
        self.vbox_display.pack_start(self.label_string_v,  False, False, 2)
        self.vbox_display.pack_start(self.label_keycode_v, False, False, 2)
        self.vbox_display.pack_start(self.label_group_v,   False, False, 2)

# ===== Widget Configurations =====================================

# ===== Hidden Objects ============================================

# ===== Signal Bindings ===========================================

# ===== Event Bindings ============================================
        self.window.connect("destroy-event", self.callback_quit, None)
        self.window.connect("delete-event",  self.callback_quit, None)

# ===== Keyboard Shortcuts ========================================
        self.window.connect("key-press-event", self.callback_key_pressed)

        # Show widgets
        self.window.show_all()

        #for item in dir(self.entry_auth_code):
        #    print item

# ===== Callbacks =================================================
    def callback_key_pressed(self, widget, event, data=None):
        if event.state == gtk.gdk.MOD1_MASK:
            if event.keyval == ord('q'):
                self.close_application(widget, event, data)
                return True
        self.label_state_v.set_label(str(event.state))
        self.label_keyval_v.set_label(str(event.keyval))
        self.label_string_v.set_label(str(event.string))
        self.label_keycode_v.set_label(str(event.hardware_keycode))
        self.label_group_v.set_label(str(event.group))

    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, event, data)

# ===== Methods ===================================================
    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        return False

def main():
    app = Key()
    gtk.main()

if __name__ == "__main__":
    main()

