import base64

from Persistence import Persistence
from blowfish import Blowfish

class Keys(Persistence):
    def __init__(self):
        Persistence.__init__(self)

    # Overrides Persitence::select_database
    def select_database(self, name):
        Persistence.select_database(self, name)
        self.init()

    # Overrides Persitence::store_iterator
    def store_iterator(self, foreign_iterator, encryption_key=None):
        for (id, key) in foreign_iterator():
            yield (id, self.key_pre(key, encryption_key))

    def key_pre(self, key, encryption_key):
        return self.key_prepare(key, encryption_key, True)

    def key_post(self, key, encryption_key):
        return self.key_prepare(key, encryption_key, False)

    def key_prepare(self, key, encryption_key, store=True):
        key_crypt = key
        if encryption_key is not None:
            try:
                engine = Blowfish(encryption_key)
                engine.initCTR()
                key_crypt = engine.encryptCTR(key)
            except:
                pass
        try:
            if store:
                key_ready = base64.standard_b64encode(key_crypt)
            else:
                key_ready = base64.standard_b64decode(key_crypt)
        except:
            key_ready = key_crypt
        return key_ready

    def add_key(self, id, key, encryption_key=None):
        try:
            self.insert(id, self.key_pre(key, encryption_key))
            return True
        except Persistence.sqlite.IntegrityError:
            return False

    def add_keys(self, foreign_iterator, encryption_key=None):
        try:
            self.insert_many(foreign_iterator)
            return True
        except Persistence.sqlite.IntegrityError:
            return False

    def get_key(self, id, encryption_key=None):
        try:
            return self.key_post(self.recall(id), encryption_key)
        except IndexError:
            return None

    def get_keys(self, limit=-1, idx=0, encryption_key=None):
        try:
            results = []
            for id,key in self.get_many(limit, idx):
                results.append((id,self.key_post(key, encryption_key)))
            return results
        except:
            return None

    def get_ids(self, limit=-1, idx=0):
        return Persistence.get_keys(self, limit, idx)

    def remove_key(self, id):
        self.delete(id)

    def remove_keys(self, foreign_iterator):
        self.delete_many(foreign_iterator)

