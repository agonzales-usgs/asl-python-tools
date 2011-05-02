from Database import Database

import base64
import hashlib
import threading
try:
    import sqlite3 as sqlite
except ImportError, e:
    from pysqlite2 import dbapi2 as sqlite

class StationDatabase(Database):
    def __init__(self):
        Database.__init__(self)


  # INSERT Operations
    def add_station(self, network, station):
        query = """INSERT OR REPLACE INTO Station(id,network,name) VALUES(?,?,?)"""
        self.cur.execute(query, (create_station_hash(network, station), network, station))
        self.db.commit()

    def add_stations(self, foreign_iterator):
        query = """INSERT OR REPLACE INTO Station(id,network,name) VALUES(?,?,?)"""
        self.cur.executemany(query, self._iterate_stations(foreign_iterator))
        self.db.commit()

    def add_channel(self, location, channel, sample_rate):
        query = """INSERT OR REPLACE INTO Station(id,location,name,sample_rate) VALUES(?,?,?,?)"""
        self.cur.execute(query, (create_station_hash(network, station), network, station))
        self.db.commit()

    def add_channels(self, foreign_iterator):
        query = """INSERT OR REPLACE INTO Channel(id,location,name,sample_rate) VALUES(?,?,?,?)"""
        self.cur.executemany(query, self._iterate_channels(foreign_iterator))
        self.db.commit()

    def add_station_channel(self, station_id, channel_id, source):
        query = """
            INSERT OR IGNORE INTO StationChannel(station_id,channel_id,source)
            VALUES (
                (SELECT (Station.id) from Station where Station.id = ?),
                (SELECT (Channel.id) from Channel where Channel.id = ?),
                ?
            )
        """
        self.cur.execute(query, (source, station_id, channel_id))
        self.db.commit()

    def add_station_channels(self, foreign_iterator):
        query = """
            INSERT OR IGNORE INTO StationChannel(station_id,channel_id,source)
            VALUES (
                (SELECT (Station.id) from Station where Station.id = ?),
                (SELECT (Channel.id) from Channel where Channel.id = ?),
                ?
            )
        """
        self.cur.executemany(query, self._iterate_station_channels(foreign_iterator))
        self.db.commit()

    def add_subset(self, id, description):
        query = """
            INSERT OR REPLACE INTO Subset(id, description) VALUES (?,?)
        """
        self.cur.execute(query, ())
        self.db.commit()

    def add_subsets(self, foreign_iterator): 
        query = """
            INSERT OR REPLACE INTO Subset(id, description) VALUES (?,?)
        """
        self.cur.executemany(query, self._iterate_subsets(foreign_iterator))
        self.db.commit()

    def add_station_subset(self, station_id, subset_id):
        query = """
            INSERT OR IGNORE INTO StationSubset(station_id,subset_id)
            VALUES (
                (SELECT (Station.id) from Station where Station.id = ?),
                (SELECT (Subset.id) from Subset where Subset.id = ?)
            )
        """
        self.cur.execute(query, (station_id, subset_id))
        self.db.commit()
        
    def add_station_subsets(self, foreign_iterator):
        query = """
            INSERT OR FAIL INTO StationSubset(station_id,subset_id)
            VALUES (
                (SELECT (Station.id) from Station where Station.id = ?),
                (SELECT (Subset.id) from Subset where Subset.id = ?)
            )
        """
        self.cur.executemany(query, self._iterate_station_subsets(foreign_iterator))
        self.db.commit()


  # SELECT Operations
    def get_stations(self, station=None, network=None):
        query = "SELECT * FROM Station"

        reqs = []
        if network is not None :
            reqs.append(("Station.network = ?", network))
        if station is not None :
            reqs.append(("Station.name = ?", station))

        return self._get(query, reqs)

    def get_stations_by_subset(self, subset_id, exclude=False):
        query = """
            SELECT Station.id,
                   Station.network,
                   Station.name
            FROM Station
            WHERE Station.id """ +T(exclude, "NOT IN", "IN")+ """ (
                SELECT DISTINCT Station.id
                FROM Station
                INNER JOIN StationSubset
                    ON Station.id = StationSubset.station_id
                WHERE StationSubset.subset_id = ?
            )
        """
        print query
        self.cur.execute(query, (subset_id,))
        return self.cur.fetchall()


    def get_channels(self, network=None, station=None, location=None, channel=None):
        query = """
            SELECT (Station.network,
                    Station.name,
                    Channel.location,
                    Channel.name,
                    Channel.sample_rate)
            FROM Station 
            INNER JOIN StationChannel
                ON Station.id = StationChannel.station_id
            INNER JOIN Channel
                ON StationChannel.channel_id = Channel.id
        """

        reqs = []
        if network is not None :
            reqs.append(("Station.network = ?", network))
        if station is not None :
            reqs.append(("Station.name = ?", station))
        if location is not None :
            reqs.append(("Channel.location = ?", location))
        if channel is not None :
            reqs.append(("Channel.name = ?", channel))

        return self._get(query, reqs)

    def get_subsets(self):
        query = "SELECT * FROM Subset"
        reqs = []
        return self._get(query, reqs)


    def init(self):
        result = self.cur.executescript("""
CREATE TABLE IF NOT EXISTS Channel (
    id TEXT NOT NULL,
    location TEXT,
    name TEXT NOT NULL,
    sample_rate REAL,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS Station (
    id TEXT NOT NULL,
    network TEXT,
    name TEXT NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS StationChannel (
    station_id TEXT NOT NULL REFERENCES Station (id) ON DELETE CASCADE,
    channel_id TEXT NOT NULL REFERENCES Channel (id) ON DELETE CASCADE,
    source TEXT
);

CREATE TABLE IF NOT EXISTS Subset (
    id TEXT NOT NULL,
    description TEXT,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS StationSubset (
    station_id TEXT NOT NULL REFERENCES Station (id) ON DELETE CASCADE,
    subset_id TEXT NOT NULL REFERENCES Subset (id) ON DELETE CASCADE
);
        """)


  # Support Methods
    def _get(self, base_query, reqs):
        query = base_query
        if len(reqs):
            args = []
            first = False
            for (string,value) in reqs:
                joiner = " AND "
                if first:
                    first = False
                    joiner = " WHERE "
                query += joiner + string
                args.append(value)
            print query
            self.cur.execute(query, tuple(args))
        else:
            self.cur.execute(query)
        return self.cur.fetchall()

    def _iterate_stations(self, foreign_iterator):
        for (network,station) in foreign_iterator:
            id = create_station_hash(network,station)
            yield (id,network,station)

    def _iterate_channels(self, foreign_iterator):
        for (location,channel,sample_rate) in foreign_iterator:
            id = create_channel_hash(location,channel,sample_rate)
            yield (id,location,channel,sample_rate)

    def _iterate_station_channels(self, foreign_iterator):
        for (station_id,channel_id,source) in foreign_iterator:
            yield (source,station_id,channel_id)

    def _iterate_subsets(self, foreign_iterator):
        for (id,description) in foreign_iterator:
            yield (id,description)

    def _iterate_station_subsets(self, foreign_iterator):
        for (station_id,subset_id) in foreign_iterator:
            yield (station_id,subset_id)


def create_station_hash(network, name):
    return create_hash((network, name))

def create_channel_hash(location, name, sample_rate):
    return create_hash((location, name, "%0.6f" % sample_rate))

def create_hash(parts):
    return base64.urlsafe_b64encode(hashlib.sha1(''.join(list(map(lambda p: p.strip(), parts)))).digest())

def T(case, true_value, false_value):
    if case:
        return true_value
    return false_value

