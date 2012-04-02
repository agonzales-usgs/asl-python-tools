import Queue

import pygtk
pygtk.require('2.0')
import gtk
import gobject

from Dialog import Dialog
from .. import Counter
from .. import Thread

class ProgressThread(Thread.Thread):
    def __init__(self, dialog, pulse_interval=0.25):
        Thread.Thread.__init__(self, 1024, timeout=pulse_interval, timeout_message='PULSE')
        self.dialog = dialog

    def _run(self, status, data):
        count = -1
        total = -1
        done = False
        if data is not None:
            count,total,done = data
        self.dialog.update_progress(status, count, total)

    def _post(self):
        self.dialog.work_done()


class ProgressDialog(Dialog):
    def __init__(self, title, parent, callback, callback_data=None):
        Dialog.__init__(self, title, modal=True, exit_callback=self.callback_exit, exit_data=callback_data)
        self.queue = Queue.Queue(1024)
        self.mode = "PULSE"
        self.status_counter = Counter.Counter()
        self._callback = callback

        self.progress_bar = gtk.ProgressBar()

        self.hbox_buttons.pack_start(self.progress_bar, True, True, 2)
        self.add_button_right("Cancel", self.callback_cancel)
        
        self.add_button_hidden("update", self.callback_update_progress, hide=False)
        self.add_button_hidden("done", self.callback_done)

        self.status_bar = gtk.Statusbar()
        self.vbox_main.pack_end(self.status_bar, False, True, 2)

        self.result = "UNKNOWN"

    def work_done(self):
        gobject.idle_add(gobject.GObject.emit, self._hidden_buttons['done'], 'clicked')

    def update_progress(self, message, count, total):
        self.queue.put_nowait((message, count, total))
        gobject.idle_add(gobject.GObject.emit, self._hidden_buttons['update'], 'clicked')

    def callback(self):
        self._callback(self)

    def callback_exit(self, widget, event, data=None):
        self.result = "EXITED"
        self.callback()

    def callback_update_progress(self, widget, event, data=None):
        self.update_progress_bar()

    def callback_cancel(self, widget, event, data=None):
        if self.result == "CANCELLED":
            return
        self.result = "CANCELLED"
        self.callback()

    def callback_done(self, widget, event, data=None):
        self.result = "COMPLETED"
        self.callback()

    def update_progress_bar(self):
        while not self.queue.empty():
            status,count,total = self.queue.get_nowait()
            if status == "DONE":
                self.hide_calibs_progress()
                self._calibs_thread_active = False
                break
            elif status == "PULSE":
                if self.mode == "PULSE":
                    self.progress_bar.pulse()
            else:
                self.mode = "PULSE"
                fraction = 0.0
                percent = 0.0
                show_percent = False

                progress = ""
                if count > -1:
                    if (total > 0) and (count <= total):
                        fraction = float(count) / float(total)
                        percent = fraction * 100.0
                        progress = "%d/%d (%0.1f%%)" % (count, total, percent)
                        show_percent = True
                    else:
                        progress = "%d" % count
                else:
                    progress = ""

                self.status_bar.pop(self.status_counter.value())
                self.status_bar.push(self.status_counter.inc(), status)
                self.progress_bar.set_text(progress)
                if show_percent:
                    self.progress_bar.set_fraction(fraction)
                    self.mode = "FRACTION"
                else:
                    self.progress_bar.set_pulse_step(0.5)
                    self.mode = "PULSE"

