#!/usr/bin/env python
import asl

import pygtk
pygtk.require('2.0')
import gtk
import gobject

class Q330_Code:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Q330 Authorization Code")
        self.window.set_icon(asl.new_icon('code'))

        self.code_postfix = "C"

# ===== Widget Creation ===========================================
        self.vbox_main       = gtk.VBox()

        self.hbox_station    = gtk.HBox()
        self.hbox_type       = gtk.HBox()
        self.hbox_auth_code  = gtk.HBox()
        self.hbox_control    = gtk.HBox()

      # User Interaction Widgets
        self.label_station   = gtk.Label("Station Code:")
        self.entry_station   = gtk.Entry(max=5)

        self.radiobutton_C   = gtk.RadioButton(group=None, label="C")
        self.radiobutton_1   = gtk.RadioButton(group=self.radiobutton_C, label="1")
        self.radiobutton_2   = gtk.RadioButton(group=self.radiobutton_C, label="2")
        self.radiobutton_3   = gtk.RadioButton(group=self.radiobutton_C, label="3")
        self.radiobutton_4   = gtk.RadioButton(group=self.radiobutton_C, label="4")
        self.radiobutton_G   = gtk.RadioButton(group=self.radiobutton_C, label="G")

        self.label_auth_code = gtk.Label("Auth. Code:")
        self.entry_auth_code = gtk.Entry(max=16)

        self.button_copy_all = gtk.Button(stock=None, use_underline=True)
        self.hbox_copy_all   = gtk.HBox()
        self.image_copy_all  = gtk.Image()
        self.image_copy_all.set_from_stock(gtk.STOCK_DND_MULTIPLE, gtk.ICON_SIZE_MENU)
        self.label_copy_all  = gtk.Label('Copy All')
        self.button_copy_all.add(self.hbox_copy_all)
        self.hbox_copy_all.pack_start(self.image_copy_all, padding=1)
        self.hbox_copy_all.pack_start(self.label_copy_all, padding=1)

        self.button_copy_selection = gtk.Button(stock=None, use_underline=True)
        self.hbox_copy_selection   = gtk.HBox()
        self.image_copy_selection  = gtk.Image()
        self.image_copy_selection.set_from_stock(gtk.STOCK_COPY, gtk.ICON_SIZE_MENU)
        self.label_copy_selection  = gtk.Label('Copy Selection')
        self.button_copy_selection.add(self.hbox_copy_selection)
        self.hbox_copy_selection.pack_start(self.image_copy_selection, padding=1)
        self.hbox_copy_selection.pack_start(self.label_copy_selection, padding=1)

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
        #self.window.set_size_request(250,250)

        self.vbox_main.pack_start(self.hbox_type,      False, True,  0)
        self.vbox_main.pack_start(self.hbox_station,   False, True,  0)
        self.vbox_main.pack_start(self.hbox_auth_code, False, True,  0)
        self.vbox_main.pack_start(self.hbox_control,   False, True,  0)

        self.hbox_station.pack_start(self.label_station, False,  False, 0)
        self.hbox_station.pack_end(self.entry_station, False, False, 0)

        self.hbox_type.pack_start(self.radiobutton_C, False, False, 5)
        self.hbox_type.pack_start(self.radiobutton_1, False, False, 5)
        self.hbox_type.pack_start(self.radiobutton_2, False, False, 5)
        self.hbox_type.pack_start(self.radiobutton_3, False, False, 5)
        self.hbox_type.pack_start(self.radiobutton_4, False, False, 5)
        self.hbox_type.pack_start(self.radiobutton_G, False, False, 5)

        self.hbox_auth_code.pack_start(self.label_auth_code, False, False, 0)
        self.hbox_auth_code.pack_end(self.entry_auth_code, False, False, 0)

        self.hbox_control.pack_start(self.button_copy_all, False, False, 0)
        self.hbox_control.pack_start(self.button_copy_selection, False, False, 0)
        self.hbox_control.pack_end(self.button_quit, False, False, 0)

# ===== Widget Configurations =====================================
        self.entry_station.set_text("")
        #self.entry_station.set_width_chars(7)
        self.entry_station.grab_focus()
        self.radiobutton_C.set_active(True)
        #self.entry_auth_code.set_justify(gtk.JUSTIFY_RIGHT)
        self.entry_auth_code.set_editable(False)
        self.entry_auth_code.set_text("0")
        self.button_copy_selection.set_sensitive(False)

# ===== Hidden Objects ============================================
        self.clipboard = gtk.Clipboard()

# ===== Signal Bindings ===========================================

# ===== Event Bindings ============================================
        self.window.connect("destroy-event", self.callback_quit, None)
        self.window.connect("delete-event",  self.callback_quit, None)

        self.entry_station.connect("changed", self.callback_generate, None)
        self.entry_station.connect("focus", self.callback_entry_station_focused, None)

        self.radiobutton_C.connect("toggled", self.callback_radio, None, "C")
        self.radiobutton_1.connect("toggled", self.callback_radio, None, "D1")
        self.radiobutton_2.connect("toggled", self.callback_radio, None, "D2")
        self.radiobutton_3.connect("toggled", self.callback_radio, None, "D3")
        self.radiobutton_4.connect("toggled", self.callback_radio, None, "D4")
        self.radiobutton_G.connect("toggled", self.callback_radio, None, "071920") # "GST" (guest)

        self.entry_auth_code.connect("focus", self.callback_entry_auth_code_focused, None)

        self.button_copy_all.connect("clicked", self.callback_copy_all, None)
        self.button_copy_selection.connect("clicked", self.callback_copy_selection, None)
        self.button_quit.connect("clicked", self.callback_quit, None)

# ===== Keyboard Shortcuts ========================================
        self.window.connect("key-press-event", self.callback_key_pressed)

        # Show widgets
        self.window.show_all()

        #for item in dir(self.entry_auth_code):
        #    print item

# ===== Callbacks =================================================
    def callback_key_pressed(self, widget, event, data=None):
        if event.state == gtk.gdk.MOD1_MASK:
            if event.keyval == ord('`'):
                self.radiobutton_C.set_active(True)
            elif event.keyval == ord('1'):
                self.radiobutton_1.set_active(True)
            elif event.keyval == ord('2'):
                self.radiobutton_2.set_active(True)
            elif event.keyval == ord('3'):
                self.radiobutton_3.set_active(True)
            elif event.keyval == ord('4'):
                self.radiobutton_4.set_active(True)
            elif event.keyval == ord('5'):
                self.radiobutton_G.set_active(True)
            elif event.keyval == ord('e'):
                self.entry_station.grab_focus()
            elif event.keyval == ord('c'):
                self.entry_auth_code.grab_focus()
            elif event.keyval == ord('a'):
                self.auth_code_to_clipboard()
            elif event.keyval == ord('s'):
                self.auth_code_to_clipboard(selection=True)
            elif event.keyval == ord('q'):
                self.close_application(widget, event, data)

    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, event, data)

    def callback_entry_station_focused(self, widget, event, data=None):
        self.entry_station.select_region(0, len(self.entry_station.get_text()))
        self.generate_code()
        
    def callback_entry_auth_code_focused(self, widget, event, data=None):
        self.generate_code()

    def callback_copy_selection(self, widget, event, data=None):
        self.auth_code_to_clipboard(selection=True)

    def callback_copy_all(self, widget, event, data=None):
        self.auth_code_to_clipboard()

    def callback_radio(self, widget, event, data=None):
        if type(data) == str:
            self.code_postfix = data
        else:
            self.code_postfix = ""
        self.callback_generate(widget, event, data=data)

    def callback_generate(self, widget, event, data=None):
        self.generate_code()

# ===== Methods ===================================================
    def auth_code_to_clipboard(self, selection=False):
        if selection:
            self.entry_auth_code.copy_clipboard()
        else:
            self.clipboard.set_text(self.entry_auth_code.get_text())

    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        return False

    def generate_code(self):
        if len(self.entry_station.get_text()) == 0:
            self.entry_auth_code.set_text("0")
            self.button_copy_selection.set_sensitive(False)
        else:
            teh_string = self.entry_station.get_text()
            code   = ""
            result = ""
            first  = True

            for index in range(0, len(teh_string)):
                val = ord(teh_string[index])
                if 47 < val < 58: 
                    code += str(val)
                elif 64 < val < 74:
                    if not first: code += "0"
                    code += str(val - 64)
                elif 73 < val < 91:
                    code += str(val - 64)
                elif 96 < val < 106:
                    if not first: code += "0"
                    code += str(val - 96)
                elif 105 < val < 123:
                    code += str(val - 96)
                else:
                    self.entry_auth_code.set_text("0")
                    self.button_copy_selection.set_sensitive(False)
                    return
                first = False
            code += self.code_postfix
            for count in range(0, 16 - len(code)):
                result += "0"
            result += code

            selection_start  = len(result) - len(code)
            selection_end    = len(result)
            selection_length = len(code)

            self.entry_auth_code.set_text(result)
            self.entry_auth_code.select_region(selection_start, selection_end)

            if selection_length:
                self.button_copy_selection.set_sensitive(True)
            else:
                self.button_copy_selection.set_sensitive(False)

def main():
    app = Q330_Code()
    gtk.main()

if __name__ == "__main__":
    main()

