import os

try:
    from Persistence import Persistence
    KEEP=True
except:
    KEEP=False

class PersistenceStub(object):
    def __init__(self): object.__init__(self)
    def select_database(db): return
    def init(): return
    def store(k,v): return
    def recall(k): return None
    def get_all(): return []
    def store_many(i): return

class StatefulClass(object):
    def __init__(self, database):
        object.__init__(self)

        if KEEP:
            self.keep = Persistence()
        else:
            self.keep = PersistenceStub()
        self.keep_dict = {}
        self.temp_dict = {}
        try:
            self.keep.select_database(database)
            self.keep.init()
            self.load_state()
        except:
            pass

    def store_temp_value(self, key, value):
        try:
            self.temp_dict[key] = value
            return True
        except:
            return False

    def recall_temp_value(self, key, default=None):
        try:
            return self.temp_dict[key]
        except:
            return default

    def clear_temp_value(self):
        try:
            del self.temp_dict[key]
            return True
        except:
            return False

    def store_value(self, key, value):
        try:
            self.keep_dict[key] = value
            return True
        except:
            return False

    def recall_value(self, key, default=None):
        try:
            return self.keep_dict[key]
        except:
            return default

    def clear_value(self):
        try:
            del self.keep_dict[key]
            return True
        except:
            return False

    def save_value(self, key, value):
        try:
            self.keep.store(key, value)
            self.keep_dict[key] = value
            return True
        except:
            return False

    def load_value(self, key, default=None):
        try:
            value = self.keep.recall(key)
            self.keep_dict[key] = value
            return value
        except:
            return default

    def delete_value(self, key):
        try:
            self.keep.delete(key)
            return True
        except:
            return False

    def load_state(self):
        try:
            pairs = self.keep.get_all()
            for key,value in pairs:
                if (type(value) in (tuple, list)) and (len(value) == 1):
                    value = value[0]
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

    def destroy_state(self):
        try:
            self.keep.delete_all()
            return True
        except:
            return False

    def keep_iterator(self):
        for key,value in self.keep_dict.items():
            yield (key,value)

  # === Methods to add mapping functionality ===
    def __getitem__(self, key):
        return self.recall_value(key)

    def __setitem__(self, key, value):
        self.store_value(key, value)

    def __delitem__(self, key):
        self.clear_value(key)

    def has_key(self, key):
        return self.keep_dict.has_key(key)

    def keys(self):
        return self.keep_dict.keys()

    def values(self):
        return self.keep_dict.values()

    def items(self):
        return self.keep_dict.items()

