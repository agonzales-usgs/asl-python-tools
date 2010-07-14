import os

from Persistence import Persistence

class StatefulClass(object):
    def __init__(self, database):
        object.__init__(self)

        self.keep = Persistence()
        self.keep_dict = {}
        self.temp_dict = {}
        try:
            self.keep.select_database(database)
            self.keep.init()
            self.load_state()
        except:
            pass

    def store_value(self, key, value):
        try:
            self.keep_dict[key] = value
            return True
        except:
            return False

    def recall_value(self, key):
        try:
            return self.keep_dict[key]
        except:
            return None

    def save_value(self, key, value):
        try:
            self.keep.store(key, value)
            self.keep_dict[key] = value
            return True
        except:
            return False

    def load_value(self, key):
        try:
            value = self.keep.recall(key)
            self.keep_dict[key] = value
            return value
        except:
            return None

    def load_state(self):
        try:
            pairs = self.keep.get_all()
            for key,value in pairs:
                self.keep_dict[key] = value
            return True
        except:
            return False

    def save_state(self):
        try:
            self.keep.store_many(self.keep_iterator)
            return True
        except:
            return False

    def keep_iterator(self):
        for key,value in self.keep_dict.items():
            yield (key,value)

