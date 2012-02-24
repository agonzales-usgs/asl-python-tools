from Database import Database

import base64
import hashlib
import threading
try:
    import sqlite3 as sqlite
except ImportError, e:
    from pysqlite2 import dbapi2 as sqlite

class StationDatabase2(Database):
    def __init__(self):
        Database.__init__(self)

    def execute(self, query):
        self.cur.execute(query)
        self.db.commit()

  # INSERT Operations
    def add_station(self, network, station, description=None, latitude=None, longitude=None):
        query = """INSERT OR REPLACE INTO Stations(network,station,description,latitude,longitude) VALUES(?,?,?,?,?)"""
        self.cur.execute(query, (network, station, description, latitude, longitude))
        self.db.commit()

    def add_stations(self, foreign_iterator):
        query = """INSERT OR REPLACE INTO Stations(network,station,description,latitude,longitude) VALUES(?,?,?,?,?)"""
        self.cur.executemany(query, self._iterate_stations(foreign_iterator))
        self.db.commit()

    def add_sensor(self, station_id, location, type, serial_number):
        query = """INSERT OR REPLACE INTO Sensors(station_id,location,type,serial_number) VALUES(?,?,?,?)"""
        self.cur.execute(query, (network, station, description))
        self.db.commit()

    def add_sensor(self, foreign_iterator):
        query = """INSERT OR REPLACE INTO Sensors(station_id,location,type,serial_number) VALUES(?,?,?,?)"""
        self.cur.executemany(query, self._iterate_sesnors(foreign_iterator))
        self.db.commit()

    def add_channel(self, location, channel, description):
        query = """INSERT OR REPLACE INTO Channel(sensor_id,channel,description) VALUES(?,?,?,?)"""
        self.cur.execute(query, (network, station, description))
        self.db.commit()

    def add_channels(self, foreign_iterator):
        query = """INSERT OR REPLACE INTO Channel(station_id,location,name,description) VALUES(?,?,?,?)"""
        self.cur.executemany(query, self._iterate_channels(foreign_iterator))
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
            INSERT OR REPLACE INTO StationSubset(station_id,subset_id)
            VALUES (
                (SELECT (Station.id) from Station where Station.id = ?),
                (SELECT (Subset.id) from Subset where Subset.id = ?)
            )
        """
        self.cur.execute(query, (station_id, subset_id))
        self.db.commit()
        
    def add_station_subsets(self, foreign_iterator):
        query = """
            INSERT OR REPLACE INTO StationSubset(station_id,subset_id)
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

        return self._get(query, reqs, "Station.name")

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
            ORDER BY Station.name
        """
        self.cur.execute(query, (subset_id,))
        return self.cur.fetchall()


    def get_channels(self, network=None, station=None, location=None, channel=None):
        query = """
            SELECT Station.network,
                   Station.name,
                   Channel.location,
                   Channel.name,
                   Channel.description
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

        return self._get(query, reqs, "Channel.location,Channel.name")

    def get_subsets(self):
        query = "SELECT * FROM Subset"
        reqs = []
        return self._get(query, reqs, "Subset.description")

    def get_subsets_by_station(self, station, network=None):
        query = """
            SELECT * 
            FROM Subset 
            INNER JOIN StationSubset
                ON Subset.id = StationSubset.subset_id
            INNER JOIN Station
                ON StationSubset.station_id = Station.id
            """
        reqs = []
        reqs.append(("Station.name = ?", station))
        if network is not None:
            reqs.append(("Station.network = ?", station))

        return self._get(query, reqs, "Subset.description")


  # Support Methods
    def _get(self, base_query, reqs, order=""):
        query = base_query
        order_by = ""
        if len(order) > 0:
            order_by = " ORDER BY %s" % order
        if len(reqs):
            args = []
            first = True
            for (string,value) in reqs:
                joiner = " AND "
                if first:
                    first = False
                    joiner = " WHERE "
                query += joiner + string
                args.append(value)
            self.cur.execute(query + order_by, tuple(args))
        else:
            self.cur.execute(query + order_by)
        return self.cur.fetchall()

    def _iterate_stations(self, foreign_iterator):
        for (network,station) in foreign_iterator:
            id = create_station_key(network,station)
            yield (id,network,station)

    def _iterate_channels(self, foreign_iterator):
        for (location,channel,description) in foreign_iterator:
            id = create_channel_key(location,channel)
            yield (id,location,channel,description)

    def _iterate_subsets(self, foreign_iterator):
        for (id,description) in foreign_iterator:
            yield (id,description)

    def _iterate_station_subsets(self, foreign_iterator):
        for (station_id,subset_id) in foreign_iterator:
            yield (station_id,subset_id)


    def init(self):
        result = self.cur.executescript("""
CREATE TABLE IF NOT EXISTS Stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    network TEXT,
    station TEXT NOT NULL,
    description TEXT,
    latitude REAL,
    longitude REAL,
    UNIQUE (network, station)
);

CREATE TABLE IF NOT EXISTS DPs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL REFERENCES Stations (id) ON DELECTE CASCADE,
    ethernet_ip TEXT DEFAULT 192.168.0.2,
    external_ip TEXT NOT NULL,
    ssh_port INTEGER DEFAULT 22,
    telemetry_port INTEGER DEFAULT 39136,
    request_port INTEGER DEFAULT 4003,
    serial_number TEXT NOT NULL,
    UNIQUE (station_id)
);

CREATE TABLE IF NOT EXISTS Q330s (
    tag_id INTEGER PRIMARY KEY,
    station_id INTEGER NOT NULL REFERENCES Stations (id) ON DELETE CASCADE,
    device_id INTEGER,
    type TEXT DEFAULT 'Q330',
    ethernet_ip TEXT NOT NULL,
    external_ip TEXT NOT NULL,
    base_port INTEGER DEFAULT 5330,
    serial_number TEXT NOT NULL,
    auth_code TEXT NOT NULL,
    UNIQUE (station_id, device_id),
    UNIQUE (serial_number)
);

CREATE TABLE IF NOT EXISTS Sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    digitizer_id INTEGER NOT NULL,
    interface TEXT NOT NULL,
    sample_rate REAL,
    UNIQUE (interface, sample_rate)
);

CREATE TABLE IF NOT EXISTS Sensors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES Sources (id) ON DELETE CASCADE,
    location TEXT NOT NULL,
    type TEXT NOT NULL,
    serial_number TEXT NOT NULL,
    UNIQUE (station_id, location)
);

CREATE TABLE IF NOT EXISTS Channel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL REFERENCES Sensors (id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    description TEXT,
    source source_id INTEGER NOT NULL REFERNCES Sources (id)
    UNIQUE (sensor_id, channel)
);

CREATE TABLE IF NOT EXISTS Subset (
    id TEXT NOT NULL,
    description TEXT,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS StationSubset (
    station_id INTEGER NOT NULL REFERENCES Stations (id) ON DELETE CASCADE,
    subset_id TEXT NOT NULL REFERENCES Subset (id) ON DELETE CASCADE,
    PRIMARY KEY (station_id,subset_id)
);
""")

def create_key(parts):
    return ''.join(list(map(lambda p: p.strip(), parts)))

def create_hash(parts):
    return base64.urlsafe_b64encode(hashlib.sha1(''.join(list(map(lambda p: p.strip(), parts)))).digest())

def T(case, true_value, false_value):
    if case:
        return true_value
    return false_value

