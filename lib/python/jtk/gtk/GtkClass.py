class GtkClass(object):
    def __init__(self):
        object.__init__(self)
        self._connections = []

    def _connect(self, widget, *args):
        id = widget.connect(*args)
        self._connections.append((widget, id))

    def _disconnect_all(self):
        for widget,id in self._connections:
            widget.disconnect(id)
        self._connections = []

    def _disconnect(self, index):
        widget,id = self._connections.pop(index)
        widget.disconnect(id)

