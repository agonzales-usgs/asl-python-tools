import string
import threading
import urllib2

from jtk.Thread import Thread

MAX_QUEUED_VALUES = 8192

class GetRespException(Exception):
    pass

class CancelException(Exception):
    pass

class ResponsesThread(Thread):
    def __init__(self, status_queue, resp_list):
        Thread.__init__(self, MAX_QUEUED_VALUES)
        self.status_queue = status_queue
        self.resp_list = resp_list

    def run(self):
        try:
            index = 0
            for responses in self.resp_list:
                index += 1
                responses.set_status_queue(self.status_queue)
                responses.run()
        except GetRespException, e:
            self.status_queue.put(("ERROR: %s" % str(e), (-1, -1, False)))
        self.status_queue.put(("DONE", (-1, -1, True)))

class Responses(Thread): 
    def __init__(self, network, station, location, channel, status_queue=None):
        Thread.__init__(self, MAX_QUEUED_VALUES)
        self.network = network
        self.station = station
        self.location = location
        self.channel = channel

        self.resp_server = "ftp://aslftp.cr.usgs.gov"
        self.resp_file = "RESP.%s.%s.%s.%s" % (network, station, location, channel)
        self.resp_url  = "%s/pub/responses/%s" % (self.resp_server, self.resp_file)
        self.resp_data = None
        self.resp_data_ready = False
        self.resp_map  = {}
        self.resp_map_ready = False

        self.set_status_queue(status_queue)

    def get_channel_key(self):
        return "%s-%s-%s-%s" % (self.network, self.station, self.location, self.channel)

    def set_status_queue(self, queue):
        self.status_queue = queue

    def check_halted(self):
        if not self.running:
            raise CancelException()

    def update_status(self, state, count=-1, total=-1, done=False): 
        if self.status_queue is not None:
            self.status_queue.put((state, (count, total, done)))

  # prevent actual thread from running
  # (we want all the functionality)
    def start(self):
        self.run()

    def run(self):
        self.running = True
        try:
            self.get_resp()
            self.parse_resp()
        except CancelException, e:
            print "Cancelled"
            pass

    def get_resp(self):
        self.check_halted()

        if self.resp_data_ready:
            return

        print "Full path to RESP file:", self.resp_url
        print "Connecting...",
        self.update_status("connecting to %s" % self.resp_server)
        try:
            resp_handle = urllib2.urlopen(self.resp_url)
        except urllib2.URLError, e:
            raise GetRespException("Could not open response file URL: %s" % self.resp_url)
        print "Connected."

        print "Downloading..."
        self.check_halted()
        self.update_status("downloading %s" % self.resp_url)
        try:
            self.resp_data = resp_handle.readlines()
        except urllib2.URLError, e:
            raise GetRespException("Error downloading response file")
        print "Complete."

        self.resp_data_ready = True
        self.check_halted()

    def parse_resp(self):
        if self.resp_map_ready:
            return

        if self.resp_data_ready and self.resp_data is not None:
            line_count = len(self.resp_data)
            processed_lines = 0
            last_percent = 0
            for line in self.resp_data:
                self.check_halted()

                processed_lines += 1
                processed_percent = int(float(processed_lines) / float(line_count) * 100.0)
        
                if processed_percent > last_percent:
                    self.update_status("parsing %s" % self.resp_file, processed_lines, line_count)
                    last_percent = processed_percent

                line = line.strip()
                if line[0] == '#':
                    continue
                if line[0] != 'B':
                    continue
                key,data = line.split(None,1)
                blk_id,rest = key[1:].split('F', 1)
                field_ids = map(int, rest.split('-', 1))
                blockette = int(blk_id)
                if not self.resp_map.has_key(blockette):
                    self.resp_map[blockette] = {}

              # populate multi-field (child) items
                if len(field_ids) > 1:
                    parts = map(string.strip, data.split())
                    index = parts[0]
                    fields = parts[1:]
                    field_low,field_high = map(int, field_ids)
                    parent_id = field_low - 1 
                    pocket = self.resp_map[blockette][parent_id]['children']
                    idx = 0
                    for field_id in range(field_low, field_high+1):
                        if not pocket.has_key(field_id):
                            pocket[field_id] = {'value':[]}
                        pocket[field_id]['value'].append(fields[idx])
                        idx += 1

              # populate normal and count (parent) items
                else:
                    field_id = int(field_ids[0])
                    description,value = map(string.strip, data.split(':', 1))
                    self.resp_map[blockette][field_id] = {
                        'children'    : {},
                        'description' : description,
                        'value'       : value,
                    }

        self.resp_map_ready = True
        self.check_halted()
