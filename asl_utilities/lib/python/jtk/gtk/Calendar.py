import datetime
import re
import string
import threading
import time

import pygtk
pygtk.require('2.0')
import gtk
import gobject

class Calendar(object):
    def __init__(self, master=None, docked=False):
        object.__init__(self)
        self.master = master
        self.lock_update_time = threading.Lock()
        self.hidden = False
        self.docked = docked
        self.calendar = None

        self.completion_callback = None
        self.completion_data = None
        self.cancel_callback = None
        self.cancel_data = None
        self.time_high = True
        self.pushing = False

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

        self.granularity = "day"
        self.granules = {  'day'    : 4 ,
                           'hour'   : 3 ,
                           'minute' : 2 ,
                           'second' : 1 } 

        times = time.gmtime()
        self.timestamp = { 'year'   : times[0] ,
                           'month'  : times[1] ,
                           'day'    : times[2] ,
                           'hour'   : times[3] ,
                           'minute' : times[4] ,
                           'second' : times[5] }
        self.running = False


    def create_window(self, title=None, icon=None):
        if self.running:
            return
        self.running = True
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        if title is not None:
            self.window.set_title(title)
        if icon is not None:
            try:
                self.window.set_icon(icon)
            except:
                self.window.set_icon(asl.new_icon(icon))

# ===== GUI Container Widgets =====
        self.vbox_date_time = gtk.VBox()
        self.hbox_date      = gtk.HBox()
        self.hbox_jdate     = gtk.HBox()
        self.hbox_time      = gtk.HBox()
        self.hbox_control   = gtk.HBox()
        self.vbox_year      = gtk.VBox()
        self.vbox_month     = gtk.VBox()
        self.vbox_day       = gtk.VBox()
        self.vbox_jyear     = gtk.VBox()
        self.vbox_jday      = gtk.VBox()
        self.vbox_today     = gtk.VBox()
        self.vbox_hour      = gtk.VBox()
        self.vbox_minute    = gtk.VBox()
        self.vbox_second    = gtk.VBox()

# ===== Widget Creation =====
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

        self.label_year = gtk.Label("Year:")
        self.spinbutton_year = gtk.SpinButton(adjustment=self.adjustment_year,  climb_rate=1, digits=0)
        self.label_month = gtk.Label("Month:")
        self.spinbutton_month = gtk.SpinButton(adjustment=self.adjustment_month, climb_rate=1, digits=0)
        self.label_day = gtk.Label("Day:")
        self.spinbutton_day = gtk.SpinButton(adjustment=self.adjustment_day,   climb_rate=1, digits=0)
        self.label_jyear = gtk.Label("Year:")
        self.spinbutton_jyear = gtk.SpinButton(adjustment=self.adjustment_jyear, climb_rate=1, digits=0)
        self.label_jday = gtk.Label("J-Day:")
        self.spinbutton_jday = gtk.SpinButton(adjustment=self.adjustment_jday,  climb_rate=1, digits=0)
        self.label_today_spacing = gtk.Label("")
        self.button_today = gtk.Button(label="Today")

        self.label_hour         = gtk.Label("Hour")
        self.label_minute       = gtk.Label("Minute")
        self.label_second       = gtk.Label("Second")
        self.spinbutton_hour    = gtk.SpinButton()
        self.spinbutton_minute  = gtk.SpinButton()
        self.spinbutton_second  = gtk.SpinButton()
        self.button_ok          = gtk.Button(label="OK")
        self.button_cancel      = gtk.Button(label="Cancel")
        self.calendar           = gtk.Calendar()

      # Hidden Buttons
        self.button_hide   = gtk.Button()
        self.button_show   = gtk.Button()

# ===== Layout Configuration =====
      # Primary Containers
        self.window.add(self.vbox_date_time)

        self.vbox_date_time.pack_start(self.calendar,       True, True, 0)
        self.vbox_date_time.pack_start(self.hbox_date,      False, True, 0)
        self.vbox_date_time.pack_start(self.hbox_jdate,     False, True, 0)
        self.vbox_date_time.pack_start(self.hbox_time,      False, True, 0)
        self.vbox_date_time.pack_start(self.hbox_control,   False, True, 0)

      # Day Controls
        self.hbox_date.pack_start(self.vbox_year,   True, True, 0)
        self.hbox_date.pack_start(self.vbox_month,  True, True, 0)
        self.hbox_date.pack_start(self.vbox_day,    True, True, 0)
        self.hbox_jdate.pack_start(self.vbox_jyear, True, True, 0)
        self.hbox_jdate.pack_start(self.vbox_jday,  True, True, 0)
        self.hbox_jdate.pack_start(self.vbox_today,  True, True, 0)

        self.vbox_year.pack_start(self.label_year, False, False, 0)
        self.vbox_year.pack_start(self.spinbutton_year, False, False, 0)
        self.vbox_month.pack_start(self.label_month, False, False, 0)
        self.vbox_month.pack_start(self.spinbutton_month, False, False, 0)
        self.vbox_day.pack_start(self.label_day, False, False, 0)
        self.vbox_day.pack_start(self.spinbutton_day, False, False, 0)
        self.vbox_jyear.pack_start(self.label_jyear, False, False, 0)
        self.vbox_jyear.pack_start(self.spinbutton_jyear, False, False, 0)
        self.vbox_jday.pack_start(self.label_jday, False, False, 0)
        self.vbox_jday.pack_start(self.spinbutton_jday, False, False, 0)
        self.vbox_today.pack_start(self.label_today_spacing, False, False, 0)
        self.vbox_today.pack_start(self.button_today, False, False, 0)

      # Time Controls
        self.hbox_time.pack_start(self.vbox_hour, True, True, 0)
        self.hbox_time.pack_start(self.vbox_minute, True, True, 0)
        self.hbox_time.pack_start(self.vbox_second, True, True, 0)

        self.vbox_hour.pack_start(self.label_hour, False, True, 0)
        self.vbox_hour.pack_start(self.spinbutton_hour, False, True, 0)
        self.vbox_minute.pack_start(self.label_minute, False, True, 0)
        self.vbox_minute.pack_start(self.spinbutton_minute, False, True, 0)
        self.vbox_second.pack_start(self.label_second, False, True, 0)
        self.vbox_second.pack_start(self.spinbutton_second, False, True, 0)

      # Buttons
        self.hbox_control.pack_start(self.button_ok, False, False, 0)
        self.hbox_control.pack_end(self.button_cancel, False, False, 0)

# ===== Widget Configurations =====================================
        # Time selection
        self.label_year.set_justify(  gtk.JUSTIFY_LEFT )
        self.label_month.set_justify( gtk.JUSTIFY_LEFT )
        self.label_day.set_justify(   gtk.JUSTIFY_LEFT )
        self.label_jyear.set_justify( gtk.JUSTIFY_LEFT )
        self.label_jday.set_justify(  gtk.JUSTIFY_LEFT )

        self.spinbutton_jday.grab_focus()

        self.spinbutton_hour.set_range(   0, 23 )
        self.spinbutton_minute.set_range( 0, 59 )
        self.spinbutton_second.set_range( 0, 59 )

        self.spinbutton_hour.set_increments(   1, 5 )
        self.spinbutton_minute.set_increments( 1, 5 )
        self.spinbutton_second.set_increments( 1, 5 )

# ===== Signal Bindings ===========================================

# ===== Event Bindings =====
        self.window.connect(        "destroy_event", self.callback_complete, None )
        self.window.connect(        "delete_event",  self.callback_complete, None )
        self.button_today.connect(  "clicked", self.callback_today,    None)
        self.button_ok.connect(     "clicked", self.callback_complete, None, "KILL")
        self.button_cancel.connect( "clicked", self.callback_cancel,   None, "KILL")

        self.calendar.connect( "day-selected",  self.callback_update_time, None )
        self.calendar.connect( "day-selected-double-click", self.callback_update_time, None )
        self.calendar.connect( "month-changed", self.callback_update_time, None )
        self.calendar.connect( "next-month",    self.callback_update_time, None )
        self.calendar.connect( "prev-month",    self.callback_update_time, None )
        self.calendar.connect( "next-year",     self.callback_update_time, None )
        self.calendar.connect( "prev-year",     self.callback_update_time, None )

        self.spinbutton_hour.connect(   "value-changed", self.callback_update_time, None )
        self.spinbutton_minute.connect( "value-changed", self.callback_update_time, None )
        self.spinbutton_second.connect( "value-changed", self.callback_update_time, None )

        #self.window.connect("key-press-event", self.callback_key_pressed)

        self.push_time()

        # Show our contents
        self.window.show_all()

    def set_granularity(self, granule):
        if self.granules.has_key(granule):
            self.granularity = granule

    def get_granularity(self):
        return self.granularity

    def get_granule(self, granule):
        if self.granules.has_key(granule):
            return self.granules[granule]
        return 0

    def current_granule(self):
        if self.granules.has_key(self.granularity):
            return self.granules[self.granularity]
        return 0

    def set_default_high(self, high=True):
        self.time_high = high

    def get_default_high(self):
        return self.time_high
        
    def delete_window(self, data=None):
        if not self.running:
            return
        if data == 'KILL':
            self.window.hide()
            del self.window
        self.window = None
        self.running = False

# ===== Utility Methods =====
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

# ===== Callback Methods =====
    def callback_update_time(self, widget, event, data=None):
        if not self.lock_update_time.acquire(0):
            return
        if not self.calendar or self.pushing:
            return
        (year, month, day) = self.calendar.get_date()
        self.timestamp['year']   = year
        self.timestamp['month']  = month + 1
        self.timestamp['day']    = day
        if self.current_granule() <= self.get_granule('hour'):
            self.timestamp['hour'] = int(self.spinbutton_hour.get_value())
        elif self.time_high:
            self.timestamp['hour'] = 23
        else:
            self.timestamp['hour'] = 0

        if self.current_granule() <= self.get_granule('minute'):
            self.timestamp['minute'] = int(self.spinbutton_minute.get_value())
        elif self.time_high:
            self.timestamp['minute'] = 59
        else:
            self.timestamp['minute'] = 0

        if self.current_granule() <= self.get_granule('second'):
            self.timestamp['second'] = int(self.spinbutton_second.get_value())
        elif self.time_high:
            self.timestamp['second'] = 59
        else:
            self.timestamp['second'] = 0

    def callback_today(self, widget=None, event=None, data=None):
        times = time.gmtime()
        self.timestamp = { 'year'   : times[0] ,
                           'month'  : times[1] ,
                           'day'    : times[2] ,
                           'hour'   : times[3] ,
                           'minute' : times[4] ,
                           'second' : times[5] }
        self.push_time()

    def callback_complete(self, widget=None, event=None, data=None):
        if callable(self.completion_callback):
            if self.completion_data is None:
                self.completion_callback()
            else:
                self.completion_callback(self.completion_data)
        self.delete_window(data)

    def set_callback_complete(self, callback, data=None):
        self.completion_callback = callback
        self.completion_data = data

    def callback_cancel(self, widget=None, event=None, data=None):
        if callable(self.cancel_callback):
            if self.cancel_data is None:
                self.cancel_callback()
            else:
                self.cancel_callback(self.cancel_data)
        self.delete_window(data)

    def set_callback_cancel(self, callback, data=None):
        self.cancel_callback = callback
        self.cancel_data = data

    def set_callback(self, callback, data=None):
        self.set_callback_complete(callback, data)

    def push_time(self):
        if not self.calendar:
            return
        self.pushing = True
        self.calendar.select_month(self.timestamp['month'] - 1, self.timestamp['year'])
        self.calendar.select_day(self.timestamp['day'])
        if self.current_granule() <= self.get_granule('hour'):
            self.spinbutton_hour.set_value(self.timestamp['hour'])
        if self.current_granule() <= self.get_granule('minute'):
            self.spinbutton_minute.set_value(self.timestamp['minute'])
        if self.current_granule() <= self.get_granule('second'):
            self.spinbutton_second.set_value(self.timestamp['second'])
        self.pushing = False

    def prompt(self):
        self.create_window()

    def get_date(self):
        date_str = "%(year)04d/%(month)02d/%(day)02d %(hour)02d:%(minute)02d:%(second)02d" % self.timestamp
        date = time.strptime(date_str,"%Y/%m/%d %H:%M:%S")
        return date

    def set_date(self, date):
        self.timestamp['year']   = date[0]
        self.timestamp['month']  = date[1]
        self.timestamp['day']    = date[2]
        if self.current_granule() <= self.get_granule('hour'):
            self.timestamp['hour']   = date[3]
        elif self.time_high:
            self.timestamp['hour'] = 23
        else:
            self.timestamp['hour'] = 0

        if self.current_granule() <= self.get_granule('minute'):
            self.timestamp['minute'] = date[4]
        elif self.time_high:
            self.timestamp['minute'] = 59
        else:
            self.timestamp['minute'] = 0

        if self.current_granule() <= self.get_granule('second'):
            self.timestamp['second'] = date[5]
        elif self.time_high:
            self.timestamp['second'] = 59
        else:
            self.timestamp['second'] = 0
        self.push_time()

