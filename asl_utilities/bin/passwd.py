#!/usr/bin/env python

# ASL Utilities, Modules, and Data
import asl

# Custom Modules
from jtk import pexpect
from jtk import pxssh
from jtk.file import utils

# General Modules
import getpass
import optparse
import os
import socket
import sys
from xml.dom import minidom

PASSWD_CONFIG = ""
if os.environ.has_key("PASSWD_UPDATE_CONFIG_FILE"):
    PASSWD_CONFIG = os.environ["PASSWD_UPDATE_CONFIG_FILE"]
if not utils.test_file(PASSWD_CONFIG, 'r') and os.environ.has_key("HOME"):
    PASSWD_CONFIG = "%s/.ssh/passwd_update.xml" % os.environ["HOME"]
if not utils.test_file(PASSWD_CONFIG, 'r'):
    PASSWD_CONFIG = "passwd_update.xml"
if not utils.test_file(PASSWD_CONFIG, 'r'):
    PASSWD_CONFIG = ""

class Main:
    def __init__(self):
        option_list = []
        option_list.append(optparse.make_option("-c", "--config-file", dest="config_file", action="store", help="station file contents are encrypted"))
        option_list.append(optparse.make_option("-s", "--select", dest="selection", action="store", help="comma seperated list of hosts to update"))
        option_list.append(optparse.make_option("-x", "--exclude", dest="exclusion", action="store", help="comma seperated list of hosts to exclude from update"))
        self.parser = optparse.OptionParser(option_list=option_list)
        self.parser.set_usage("""Usage: %prog [options] - update passwords on multiple systems simultaneously""")

        self.passwords = None
        self.hosts = {}

    def usage(self, message=''):
        if message != '':
            print "E:", message
        self.parser.print_help()
        sys.exit(1)

    def error(self, message):
        print "E:", message
        sys.exit(1)

    def parse_config(self):
        dom = minidom.parse(self.config_file)
        hosts = dom.getElementsByTagName("host")
        if len(hosts) < 1:
            self.error("No hosts found in configuration.")
        for host in hosts:
            try: assert dom.documentElement.tagName == "passwd"
            except AssertionError: self.error("Malformed XML in Configuration File")

            try: id = host.attributes["id"].firstChild.data
            except Exception, e: self.error("Malformed XML in Configuration File")
            print "id:", id

            addresses = host.getElementsByTagName("address")
            if not addresses or len(addresses) != 1:
                self.error("Malformed XML in Configuration File")

            ports = host.getElementsByTagName("port")
            if ports and len(ports) > 1:
                self.error("Malformed XML in Configuration File")

            users = host.getElementsByTagName("user")
            if not users or len(users) != 1:
                self.error("Malformed XML in Configuration File")

            modes = host.getElementsByTagName("mode")
            if modes:
                if len(modes) != 1:
                    self.error("Malformed XML in Configuration File")

            hostname = addresses[0].firstChild.data.strip()
            try: address = socket.gethostbyname(hostname)
            except socket.gaierror: self.error("Invalid address for host '%s'" % id)
            print "address: %s (%s)" % (address, hostname)

            if not ports:
                port = 22
            else:
                try: port = int(ports[0].firstChild.data.strip())
                except ValueError: self.error("Invalid port for host '%s'" % id)
            print "port:", port

            user = users[0].firstChild.data.strip()
            print "user:", user
            if len(user) < 1:
                self.error("Invalid value for user.")

            mode = "default"
            if len(modes) > 0:
                mode = modes[0].firstChild.data.strip().lower()
                print "mode:", mode
                if mode.lower() != "explicit":
                    mode = "default"


            if self.hosts.has_key(id):
                self.error("Found duplicate ID in config file.")
            self.hosts[id] = {'address' : address,
                              'port'    : port,
                              'user'    : user,
                              'mode'    : mode}

            print

    def get_passwords(self):
        current = getpass.getpass("Current Passord: ")

        first = True
        passA = 'A'
        passB = 'B'
        while passA != passB:
            if not first:
                print "New passwords do not match, please try again."
            else:
                first = False
            passA = getpass.getpass("New Password: ")
            passB = getpass.getpass("Confirm New Password: ")

        self.passwords = (current, passA, passB)

    def set_password(self, host_id):
        reader = pxssh.pxssh()
        host = self.hosts[host_id]
        try:
            reader.login(host['address'], host['user'], password=self.passwords[0], port=host['port'])
        except Exception, e:
            print "Failed to ssh to station '%s'" % host_id
            return

        if host['mode'] == "explicit":
            reader.sendline('passwd %(user)s' % host)
        else:
            reader.sendline('passwd')

        for password in self.passwords:
            try:
                reader.expect("assword:", timeout=3)
            except Exception, e:
                print "Error while trying to set new password:", str(e)
                break
            reader.sendline(password)

        try:
            reader.prompt(timeout=3)
            print "Result:", reader.before
        except Exception, e:
            print "Password update failed."

        reader.close()

    def start(self):
        options, args = self.parser.parse_args()

        arg_selection = None
        arg_exclusion = None
        if options.selection:
            arg_selection = map(lambda i: i.lower(), options.selection.split(','))
        if options.exclusion:
            arg_exclusion = map(lambda i: i.lower(), options.exclusion.split(','))

        if (arg_exclusion is not None) and (arg_selection  is not None):
            self.usage("Can not use both -s and -x options.")

        self.config_file = PASSWD_CONFIG
        if options.config_file:
            self.config_file = options.config_file
        if not os.path.exists(self.config_file):
            self.error("Config file '%s' not found." % self.config_file)
        if not os.access(self.config_file, os.W_OK):
            self.error("Config file '%s' permission denied." % self.config_file)

        print "Parsing config file '%s'..." % self.config_file
        self.parse_config()

        if arg_exclusion:
            print "Filtering hosts..."
            for host in self.hosts.keys():
                if host.lower() in arg_exclusion:
                    del self.hosts[host]

        if arg_selection:
            print "Filtering hosts..."
            for host in self.hosts.keys():
                if host.lower() not in arg_selection:
                    del self.hosts[host]

        self.get_passwords()

        for host in self.hosts.keys():
            print "Setting password for host '%s'..." % host
            self.set_password(host)

        print "All resets complete."


if __name__ == '__main__':
    try:
        Main().start()
    except KeyboardInterrupt:
        print

