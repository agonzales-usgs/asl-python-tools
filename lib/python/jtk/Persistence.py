from pysqlite2 import dbapi2 as sqlite

class Persistence(object):
    def __init__(self):
        object.__init__(self)
        
        self.file_name = ''
        self.db  = None
        self.cur = None

    def _hash(self, text):
        sha_obj = hashlib.sha1()
        sha_obj.update( text )
        return base64.urlsafe_b64encode( sha_obj.digest() )

    def select_database(self, file):
        self.db = None
        self.db = sqlite.connect(file)
        self.cur = self.db.cursor()
        self.file_name = file

    def get_database_file_name(self):
        return self.file_name

    def delete(self, key):
        self.cur.execute("DELETE FROM Data WHERE key=?", (key,))
        self.db.commit()

    def delete_many(self, foreign_iterator):
        self.cur.executemany("DELETE FROM Data WHERE key=?", self.delete_iterator(foreign_iterator))
        self.db.commit()

    def insert(self, key, value):
        self.cur.execute("INSERT INTO Data(key, value) VALUES (?,?)", (key, value))
        self.db.commit()

    def insert_many(self, foreign_iterator):
        self.cur.executemany("INSERT INTO Data(key, value) VALUES (?,?)", self.store_iterator(foreign_iterator))
        self.db.commit()

    def store(self, key, value):
        self.cur.execute("INSERT OR REPLACE INTO Data(key, value) VALUES (?,?)", (key, value))
        self.db.commit()

    def store_many(self, foreign_iterator):
        self.cur.executemany("INSERT OR REPLACE INTO Data(key, value) VALUES (?,?)", self.store_iterator(foreign_iterator))
        self.db.commit()

    def delete_iterator(self, foreign_iterator):
        for key in foreign_iterator():
            yield key

    def store_iterator(self, foreign_iterator):
        for (key, value) in foreign_iterator():
            yield (key, value)

    def recall(self, key):
        self.cur.execute("SELECT value FROM Data WHERE key=?", (key,))
        return self.cur.fetchall()[0]

    def get_keys(self, limit=-1, idex=0):
        if limit > 0:
            self.cur.execute("SELECT key FROM Data LIMIT ? OFFSET ?", (limit, idx))
        else:
            self.cur.execute("SELECT key FROM Data OFFSET ?", (idx,))
        return self.cur.fetchall()

    def get_many(self, limit=-1, idx=0):
        if limit > 0:
            self.cur.execute("SELECT key,value FROM Data LIMIT ? OFFSET ?", (limit, idx))
        else:
            self.cur.execute("SELECT key,value FROM Data OFFSET ?", (idx,))
        return self.cur.fetchall()

    def get_all(self):
        self.cur.execute("SELECT key,value FROM Data")
        return self.cur.fetchall()

    def init(self):
        result = self.cur.executescript("""
            CREATE TABLE IF NOT EXISTS Data (
                key TEXT,
                value TEXT,
                PRIMARY KEY (key)
            );
            """)

