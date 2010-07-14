from pysqlite2 import dbapi2 as sqlite

class Persistence(object):
    def __init__(self):
        object.__init__(self)
        
        self.db  = None
        self.cur = None
        self.foreign_iterator = None

    def _hash(self, text):
        sha_obj = hashlib.sha1()
        sha_obj.update( text )
        return base64.urlsafe_b64encode( sha_obj.digest() )

    def select_database(self, file):
        self.db = None
        self.db = sqlite.connect(file)
        self.cur = self.db.cursor()

    def store(self, key, value):
        self.cur.execute("INSERT OR REPLACE INTO Data(key, value) VALUES (?,?)", (key, value))
        self.db.commit()

    def store_many(self, foreign_iterator):
        self.foreign_iterator = foreign_iterator
        self.cur.executemany("INSERT OR REPLACE INTO Data(key, value) VALUES (?,?)", self.iterator_pairs())
        self.db.commit()

    def iterator_pairs(self):
        for (key, value) in self.foreign_iterator():
            yield (key, value)

    def recall(self, key):
        self.cur.execute("SELECT value FROM Data WHERE key=?", (key,))
        return self.cur.fetchall()[0]

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

