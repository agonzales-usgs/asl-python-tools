#!/usr/bin/python
import asl

import calendar
import datetime
import os
import Queue
import re
import string
import sys
import time
import threading

import pygtk
pygtk.require('2.0')
import gtk
import gobject

# === Dates Class /*{{{*/
class Dates:
    def __init__(self, docked=True):
        self.lock_update_time = threading.Lock()
        self.hidden = False
        self.docked = docked

        self.month_map = [
            [31, 31], # January
            [28, 29], # February
            [31, 31], # March
            [30, 30], # April
            [31, 31], # May
            [30, 30], # June
            [31, 31], # July
            [31, 31], # August
            [30, 30], # September
            [31, 31], # October
            [30, 30], # November
            [31, 31]  # December
        ]

        self.create_window()

    def create_window(self):
# ===== Widget Creation ===========================================
      # Layout Control Widgets
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Know Thy Season")
        self.window.set_icon(asl.new_icon('clock'))

        self.vbox_main    = gtk.VBox()

        self.vbox_top     = gtk.VBox()
        self.vbox_bottom  = gtk.VBox()

        self.hbox_station = gtk.HBox()
        self.table_times  = gtk.Table(rows=4, columns=3)

      # User Interaction Widgets
        # Time-Zone selection
        self.combobox_timezone = gtk.ComboBox()

        # Time period selection
        self.calendar    = gtk.Calendar()
        self.label_year  = gtk.Label( "Year:" )
        self.label_month = gtk.Label( "Month:" )
        self.label_day   = gtk.Label( "Day:" )
        self.label_jyear = gtk.Label( "Year:" )
        self.label_jday  = gtk.Label( "J-Day:" )

        self.adjustment_year  = gtk.Adjustment(value=1, lower=datetime.MINYEAR, upper=datetime.MAXYEAR, step_incr=1, page_incr=5)
        self.adjustment_month = gtk.Adjustment(value=1, lower=1, upper=12,   step_incr=1, page_incr=5)
        self.adjustment_day   = gtk.Adjustment(value=1, lower=1, upper=31,   step_incr=1, page_incr=5)
        self.adjustment_jyear = gtk.Adjustment(value=1, lower=datetime.MINYEAR, upper=datetime.MAXYEAR, step_incr=1, page_incr=5)
        self.adjustment_jday  = gtk.Adjustment(value=1, lower=1, upper=366,  step_incr=1, page_incr=5)
        self.button_today = gtk.Button(stock=None)
        self.hbox_today   = gtk.HBox()
        self.image_today  = gtk.Image()
        self.image_today.set_from_stock(gtk.STOCK_OK, gtk.ICON_SIZE_MENU)
        self.label_today  = gtk.Label('Today')
        self.button_today.add(self.hbox_today)
        self.hbox_today.pack_start(self.image_today, padding=1)
        self.hbox_today.pack_start(self.label_today, padding=1)

        self.spinbutton_year  = gtk.SpinButton(adjustment=self.adjustment_year,  climb_rate=1, digits=0)
        self.spinbutton_month = gtk.SpinButton(adjustment=self.adjustment_month, climb_rate=1, digits=0)
        self.spinbutton_day   = gtk.SpinButton(adjustment=self.adjustment_day,   climb_rate=1, digits=0)
        self.spinbutton_jyear = gtk.SpinButton(adjustment=self.adjustment_jyear, climb_rate=1, digits=0)
        self.spinbutton_jday  = gtk.SpinButton(adjustment=self.adjustment_jday,  climb_rate=1, digits=0)

      # Hidden Buttons
        self.button_hide   = gtk.Button()
        self.button_show   = gtk.Button()

# ===== Layout Configuration ======================================
      # Primary Containers
        self.window.add(self.vbox_main)
        #self.window.set_size_request(250,250)

        self.vbox_main.pack_start( self.vbox_top, expand=True, fill=True )
        self.vbox_main.pack_end( self.table_times, expand=False, fill=True )

      # UI Widget Attachments
        self.vbox_top.pack_start(self.calendar, expand=True, fill=True)

        self.table_times.attach( self.label_year,  0, 1, 0, 1, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )
        self.table_times.attach( self.label_month, 1, 2, 0, 1, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )
        self.table_times.attach( self.label_day,   2, 3, 0, 1, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )
        self.table_times.attach( self.label_jyear, 0, 1, 2, 3, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )
        self.table_times.attach( self.label_jday,  1, 2, 2, 3, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )

        self.table_times.attach( self.spinbutton_year,  0, 1, 1, 2, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )
        self.table_times.attach( self.spinbutton_month, 1, 2, 1, 2, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )
        self.table_times.attach( self.spinbutton_day,   2, 3, 1, 2, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )
        self.table_times.attach( self.spinbutton_jyear, 0, 1, 3, 4, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )
        self.table_times.attach( self.spinbutton_jday,  1, 2, 3, 4, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )
        self.table_times.attach( self.button_today,     2, 3, 3, 4, xoptions=0, yoptions=0, xpadding=1, ypadding=1 )

# ===== Widget Configurations =====================================
        # Time selection
        self.label_year.set_justify(  gtk.JUSTIFY_LEFT )
        self.label_month.set_justify( gtk.JUSTIFY_LEFT )
        self.label_day.set_justify(   gtk.JUSTIFY_LEFT )
        self.label_jyear.set_justify( gtk.JUSTIFY_LEFT )
        self.label_jday.set_justify(  gtk.JUSTIFY_LEFT )

        self.spinbutton_jday.grab_focus()

# ===== Signal Bindings ===========================================

# ===== Event Bindings ============================================
        self.window.connect( "destroy-event", self.callback_close, None )
        self.window.connect( "delete-event",  self.callback_close, None )

        self.calendar.connect( "day-selected",  self.callback_update_time, 'calendar')
        self.calendar.connect( "month-changed", self.callback_update_time, 'calendar')
        self.calendar.connect( "next-month",    self.callback_update_time, 'calendar')
        self.calendar.connect( "next-year",     self.callback_update_time, 'calendar')
        self.calendar.connect( "prev-month",    self.callback_update_time, 'calendar')
        self.calendar.connect( "prev-year",     self.callback_update_time, 'calendar')
        self.spinbutton_year.connect(  "value-changed", self.callback_update_time, 'year'  )
        self.spinbutton_month.connect( "value-changed", self.callback_update_time, 'month' )
        self.spinbutton_day.connect(   "value-changed", self.callback_update_time, 'day'   )
        self.spinbutton_jyear.connect( "value-changed", self.callback_update_time, 'jyear' )
        self.spinbutton_jday.connect(  "value-changed", self.callback_update_time, 'jday'  )
        self.button_today.connect(     "clicked", self.callback_update_time, 'today' )

        self.button_hide.connect("clicked", self.callback_hide, None)
        self.button_show.connect("clicked", self.callback_show, None)

# ===== Keyboard Shortcuts ========================================
        self.window.connect("key-press-event", self.callback_key_pressed)

        # Show widgets
        self.window.show_all()

        # Synchronize the widget contents
        self.button_today.clicked()
        

# ===== Utility Methods ===========================================
    def get_active_text(self, combobox):
        model = combobox.get_model()
        active = combobox.get_active()
        if active < 0:
            return None
        return model[active][0]

    def month_days(self, year, month):
        idx = 0
        if (month < 1) or (month > 12):
            raise ValueError("invalid month")
        if (year < 1) or (year > 9999):
            raise ValueError("invalid year")
        if calendar.isleap(year):
            idx = 1
        return int(self.month_map[month-1][idx])

    def year_days(self, year):
        if calendar.isleap(year):
            return int(366)
        return int(365)

    def julian_to_mday(self, year, jday):
        idx   = 0
        days  = 0
        month = 0

        if calendar.isleap(year):
            idx = 1
        elif jday > 365:
            jday = 365
        for i in range(0, 12):
            if (days + self.month_map[i][idx]) >= jday:
                break
            days += self.month_map[i][idx]
            month += 1
        
        month += 1
        day = jday - days

        return (int(year),int(month),int(day))
        
        
# ===== Callback Methods =============================================
    def callback_close(self, widget, event, data=None):
        if self.docked:
            self.create_window()
            self.hide()
        else:
            gtk.main_quit()

    def callback_key_pressed(self, widget, event, data=None):
        if event.state == gtk.gdk.MOD1_MASK:
            if event.keyval == ord('q'):
                self.callback_close(widget, event, data)

    def callback_hide(self, widget, event, data=None):
        self.window.hide()

    def callback_show(self, widget, event, data=None):
        self.window.show()

    def toggle(self):
        if self.hidden:
            self.show()
        else:
            self.hide()

    def hide(self):
        self.button_hide.clicked()
        self.hidden = True

    def show(self):
        self.button_show.clicked()
        self.hidden = False

    def today(self):
        self.button_today.clicked()

    def position(self, x, y):
        self.window.set_position(gtk.WIN_POS_MOUSE)

    def set_from_time(self):
        y,m,d,_,_,_,_,j,_ = self.the_date.timetuple()
        year  = int(y)
        month = int(m)
        day   = int(d)
        jday  = int(j)
        self.adjustment_day  = gtk.Adjustment(value=year, lower=1, upper=self.month_days(year, month), step_incr=1, page_incr=5)
        self.adjustment_jday = gtk.Adjustment(value=year, lower=1, upper=self.year_days(year),         step_incr=1, page_incr=5)

        # updated spinbox adjustments
        self.spinbutton_day.set_adjustment(self.adjustment_day)
        self.spinbutton_jday.set_adjustment(self.adjustment_jday)

        # update date values
        self.spinbutton_year.set_value(year)
        self.spinbutton_month.set_value(month)
        self.spinbutton_day.set_value(day)

        # update julian values
        self.spinbutton_jyear.set_value(year)
        self.spinbutton_jday.set_value(jday)

        # update calendar
        self.calendar.select_month(month-1, year)
        self.calendar.select_day(day)

    def callback_update_time(self, evt, source):
        if not self.lock_update_time.acquire(0):
            return
        year  = None
        month = None
        day   = None
        if source == 'calendar':
            (y,m,d) = self.calendar.get_date()
            year  = int(y)
            month = int(m+1)
            day   = int(d)
        elif source in ('year', 'month', 'day'):
            year  = int(self.spinbutton_year.get_value())
            month = int(self.spinbutton_month.get_value())
            day   = int(self.spinbutton_day.get_value())
        elif source in ('jyear', 'jday'):
            (y,m,d) = self.julian_to_mday( self.spinbutton_jyear.get_value(),
                                           self.spinbutton_jday.get_value() )
            year  = int(y)
            month = int(m)
            day   = int(d)
        elif source in ('today'):
            y,m,d,_,_,_,_,_,_ = datetime.datetime(1,1,1).today().timetuple()
            year  = int(y)
            month = int(m)
            day   = int(d)

        try:
            self.the_date = datetime.datetime(year, month, day)
        except ValueError:
            day = self.month_days(year, month)
            self.the_date = datetime.datetime(year, month, day)
        self.set_from_time()

        try: self.lock_update_time.release()
        except: pass
#/*}}}*/

# === DateIcon Class /*{{{*/
class DateIcon:
    def __init__(self):
        docked = True
        try:
            self.status_icon = gtk.StatusIcon()
            self.status_icon.set_from_pixbuf(asl.new_icon('clock'))
            self.status_icon.set_visible(True)
            self.status_icon.connect( "popup-menu", self.callback_menu, None )
            self.status_icon.connect( "activate", self.callback_activate, None )

            self.menu = gtk.Menu()
            self.menu.set_title("Dates")

            self.image_today = gtk.Image()
            self.image_today.set_from_pixbuf(asl.new_icon('arrow_down'))

            self.image_quit = gtk.Image()
            self.image_quit.set_from_pixbuf(asl.new_icon('stop'))

            self.menuitem_today = gtk.ImageMenuItem("Today", "Today")
            self.menuitem_quit  = gtk.ImageMenuItem("Quit", "Quit")

            self.menuitem_today.set_image(self.image_today)
            self.menuitem_quit.set_image(self.image_quit)

            #self.menuitem_today = 

            self.menuitem_today.connect("activate", self.callback_today, None)
            self.menuitem_quit.connect( "activate", self.callback_quit,  None)

            self.menu.append(self.menuitem_today)
            self.menu.append(self.menuitem_quit)

            self.menu.show()
            self.menuitem_today.show()
            self.menuitem_quit.show()
        except:
            docked = False

        self.dates = Dates(docked)
        if docked:
            self.dates.hide()

# ===== Callback Methods =============================================
    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, None, data)

    def callback_today(self, widget, event, data=None):
        self.dates.today()

    def callback_menu(self, widget, button, activate_time, data=None):
        self.menu.popup( None, None, None, button, activate_time, data )

    def callback_activate(self, widget, event, data=None):
        self.dates.toggle()

# ===== Methods ======================================================
    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        return False
#/*}}}*/

if __name__ == "__main__":
    try:
        app = DateIcon()
        gtk.main()
    except KeyboardInterrupt:
        pass

