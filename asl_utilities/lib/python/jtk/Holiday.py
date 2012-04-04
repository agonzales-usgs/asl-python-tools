import datetime

WEEK_FIRST  = 1
WEEK_SECOND = 2
WEEK_THIRD  = 3
WEEK_FOURTH = 4
WEEK_LAST   = 5

MONDAY      = 0
TUESDAY     = 1
WEDNESDAY   = 2
THURSDAY    = 3
FRIDAY      = 4
SATURDAY    = 5
SUNDAY      = 6

JANUARY     = 1
FEBRUARY    = 2
MARCH       = 3
APRIL       = 4
MAY         = 5
JUNE        = 6
JULY        = 7
AUGUST      = 8
SEPTEMBER   = 9
OCTOBER     = 10
NOVEMBER    = 11
DECEMBER    = 12

class Holiday:
    def __init__(self, month, floating=False, *args):
        self.floating = floating
        if floating:
            self._method = self._calculate_floating
            self._init_floating(month, *args)
        else:
            self._method = self._calculate_fixed
            self._init_fixed(month, *args)

    def _init_floating(self, month, week_day, month_week):
        self._args = [month, week_day, month_week]

    def _init_fixed(self, month, day):
        self._args = [month, day]
    
    def _calculate_floating(self, year, month, week_day, month_week):
        date = datetime.date(year, month, 1)
        print "date:", date
        first_week_day = date.weekday()
        print "first week day:", first_week_day
        if first_week_day > week_day:
            day = 1 + (7 - first_week_day) + week_day
        else:
            day = 1 + week_day - first_week_day

        try:
            month_day = day + ((month_week - 1) * 7)
            date = datetime.date(year, month, month_day)
        except ValueError:
            month_day = day + ((month_week - 2) * 7)
            date = datetime.date(year, month, month_day)
        return date

    def _calculate_fixed(self, year, month, day):
        date = datetime.date(year, month, day)
        if date.weekday() == SUNDAY:
            date += datetime.timedelta(days=1)
        if date.weekday() == SATURDAY:
            date -= datetime.timedelta(days=1)
        return date

    def get_date(self, year):
        args = [year]
        args.extend(self._args)
        return self._method(*args)

