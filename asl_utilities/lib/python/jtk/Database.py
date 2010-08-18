#!/usr/bin/env python
import hashlib
import base64
from pysqlite2 import dbapi2 as sqlite

class Database:
    def __init__(self):
        self.db  = None
        self.cur = None

    def __del__(self):
        self.close()

# ===== Public Methods ====================
    def select_database(self, file):
        self.close()
        self.db = sqlite.connect(file)
        self.cur = self.db.cursor()

    def close(self):
        if self.cur:
            self.cur.close()
            del self.cur
        if self.db:
            self.db.close()
            del self.db

    def select(self, query):
        self.cur.execute(query)
        return self.cur.fetchall()

    def insert(self, query):
        self.cur.execute(query)
        self.db.commit()

    def insert_many(self, query, list):
        self.cur.executemany(query, self._iterator())
        self.db.commit()
        
    def delete(self, query):
        self.cur.execute(query)
        self.db.commit()

    def interrupt(self):
        # sends an exception to any connected threads
        self.db.interrupt()

    def run_script(self, script):
        return self.cur.executescript(script)

# ===== Private Methods ===================
    def _iterator(self):
        if self.foreign_iterator:
            for items in self.foreign_iterator():
                yield items

    def _hash(self, text):
        sha_obj = hashlib.sha1()
        sha_obj.update(text)
        return base64.urlsafe_b64encode(sha_obj.digest())

