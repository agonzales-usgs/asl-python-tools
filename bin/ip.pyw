#!/usr/bin/env python
import asl

import pygtk
pygtk.require('2.0')
import gtk
import gobject

from jtk.gtk.utils import LEFT

class IPAddress:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("IP Address")
        self.window.set_icon(asl.new_icon('network'))

        self.ip_octets = []
        self.ip_seperators = []
        self.netmask_octets = []
        self.netmask_seperators = []

        self.generating = False

# ===== Widget Creation ===========================================
        self.table_main = gtk.Table()

        self.label_ip              = gtk.Label('IP:')
        self.hbox_ip               = gtk.HBox()
        for i in range(4):
            self.ip_octets.append(gtk.SpinButton())
        for i in range(3):
            self.ip_seperators.append(gtk.Label('.'))
        self.ip_seperators.append(gtk.Label('/'))
        self.ip_bits = gtk.SpinButton()

        self.label_netmask         = gtk.Label('Netmask:')
        self.hbox_netmask          = gtk.HBox()
        for i in range(4):
            self.netmask_octets.append(gtk.combo_box_new_text())
        for i in range(3):
            self.netmask_seperators.append(gtk.Label('.'))

        self.label_network         = gtk.Label('Network:')
        self.hbox_network          = gtk.HBox()
        self.label_network_disp    = gtk.Label('0.0.0.0')
                                   
        self.label_broadcast       = gtk.Label('Broadcast:')
        self.hbox_broadcast        = gtk.HBox()
        self.label_broadcast_disp  = gtk.Label('255.255.255.255')
                                   
        self.label_hosts           = gtk.Label('Host Range:')
        self.hbox_hosts            = gtk.HBox()
        self.label_hosts_disp      = gtk.Label('0.0.0.0 - 0.0.0.0 (1 Host)')

# ===== Layout Configuration ======================================
        self.window.add( self.table_main )
        #self.window.set_size_request(250,250)
        self.table_main.attach(LEFT(self.label_ip),              0, 1, 0, 1, gtk.FILL, 0, 1, 1)
        self.table_main.attach(self.hbox_ip,                     1, 2, 0, 1, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_main.attach(LEFT(self.label_netmask),         0, 1, 1, 2, gtk.FILL, 0, 1, 1)
        self.table_main.attach(self.hbox_netmask,                1, 2, 1, 2, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_main.attach(LEFT(self.label_network),         0, 1, 2, 3, gtk.FILL, 0, 1, 1)
        self.table_main.attach(self.hbox_network,                1, 2, 2, 3, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_main.attach(LEFT(self.label_broadcast),       0, 1, 3, 4, gtk.FILL, 0, 1, 1)
        self.table_main.attach(self.hbox_broadcast,              1, 2, 3, 4, gtk.FILL | gtk.EXPAND, 0, 1, 1)
        self.table_main.attach(LEFT(self.label_hosts),           0, 1, 4, 5, gtk.FILL, 0, 1, 1)
        self.table_main.attach(self.hbox_hosts,                  1, 2, 4, 5, gtk.FILL | gtk.EXPAND, 0, 1, 1)

        for i in range(4):
            self.hbox_ip.pack_start(self.ip_octets[i],     False, False, 2)
            self.hbox_ip.pack_start(self.ip_seperators[i], False, False, 2)
        self.hbox_ip.pack_start(self.ip_bits, False, False, 2)

        for i in range(3):
            self.hbox_netmask.pack_start(self.netmask_octets[i],     False, False, 2)
            self.hbox_netmask.pack_start(self.netmask_seperators[i], False, False, 2)
        self.hbox_netmask.pack_start(self.netmask_octets[3], False, False, 2)

        self.hbox_network.pack_start(self.label_network_disp,     False, False, 2)
        self.hbox_broadcast.pack_start(self.label_broadcast_disp, False, False, 2)
        self.hbox_hosts.pack_start(self.label_hosts_disp,         False, False, 2)

# ===== Widget Configurations =====================================

        for octet in self.ip_octets:
            octet.set_adjustment(gtk.Adjustment(0, 0, 255, 1, 1, 5))
            octet.set_update_policy(gtk.UPDATE_IF_VALID)
        self.ip_bits.set_adjustment(gtk.Adjustment(32, 0,  32, 1, 1, 5))
        self.ip_bits.set_update_policy(gtk.UPDATE_IF_VALID)

        for octet in self.netmask_octets:
            for v in ('0', '128', '192', '224', '240', '248', '252', '254', '255'):
                octet.append_text(v)
            octet.set_active(8)

# ===== Hidden Objects ============================================
        #self.clipboard = gtk.Clipboard()

# ===== Signal Bindings ===========================================

# ===== Event Bindings ============================================
        self.window.connect("destroy-event", self.callback_quit, None)
        self.window.connect("delete-event",  self.callback_quit, None)

        self.ip_octets[0].connect("changed", self.callback_generate, None, 'ip-octet-0')
        self.ip_octets[1].connect("changed", self.callback_generate, None, 'ip-octet-1')
        self.ip_octets[2].connect("changed", self.callback_generate, None, 'ip-octet-2')
        self.ip_octets[3].connect("changed", self.callback_generate, None, 'ip-octet-3')
        self.ip_bits.connect("changed", self.callback_generate, None, 'ip-bits')

        self.netmask_octets[0].connect("changed", self.callback_generate, None, 'netmask-octet-0')
        self.netmask_octets[1].connect("changed", self.callback_generate, None, 'netmask-octet-1')
        self.netmask_octets[2].connect("changed", self.callback_generate, None, 'netmask-octet-2')
        self.netmask_octets[3].connect("changed", self.callback_generate, None, 'netmask-octet-3')

        #self.button_quit.connect("clicked", self.callback_quit, None)

# ===== Keyboard Shortcuts ========================================
        self.window.connect("key-press-event", self.callback_key_pressed)

        # Show widgets
        self.window.show_all()

        #for item in dir(self.entry_auth_code):
        #    print item

# ===== Callbacks =================================================
    def callback_key_pressed(self, widget, event, data=None):
        if event.state == gtk.gdk.MOD1_MASK:
            if event.keyval == ord('q'):
                self.close_application(widget, event, data)

    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, event, data)

    def callback_generate(self, widget, event, data=None):
        self.generate_ip(data)

# ===== Methods ===================================================
    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        return False

    def generate_ip(self, source):
        if self.generating:
            return
        self.generating = True
        try:
            if source[0:9] == 'ip-octet-':
                octet = int(source[9])
                self.ip_octets[octet].update()

            if source[0:14] == 'netmask-octet-':
                octet = int(source[14])
                for i in range(4):
                    if i < octet:
                        self.netmask_octets[i].set_active(8)
                    elif i > octet:
                        self.netmask_octets[i].set_active(0)
                bits = 0
                for i in range(4):
                    index = self.netmask_octets[i].get_active() 
                    bits += index
                    if index < 8:
                        break
                self.ip_bits.set_value(bits)
            else:
                try:
                    bits = int(self.ip_bits.get_value())
                except:
                    bits = 0
                if bits < 0:
                    bits = 0
                elif bits > 32:
                    bits = 32

                tmp_bits = bits
                for i in range(4):
                    if tmp_bits >= 8:
                        index = 8
                        tmp_bits -= 8
                    elif tmp_bits == 0:
                        index = 0
                    else:
                        index = tmp_bits
                        tmp_bits = 0
                    self.netmask_octets[i].set_active(index)

            mask = (0xffffffff >> (32 - bits)) << (32 - bits)
            ip = 0
            for i in range(4):
                try:
                    byte = int(self.ip_octets[i].get_value())
                except:
                    byte = 0
                ip |= byte << ((3-i)*8)
            total_ips = (2 ** (32 - bits))
            network = ip & mask
            broadcast = network + total_ips - 1
            self.label_network_disp.set_text("%d.%d.%d.%d" % (split_ip(network)))
            self.label_broadcast_disp.set_text("%d.%d.%d.%d" % (split_ip(broadcast)))
            parts = []
            #parts.extend(split_ip(network))
            #parts.extend(split_ip(broadcast))
            parts.append(total_ips)
            if total_ips == 1:
                parts.append('')
            else:
                parts.append('s')
            self.label_hosts_disp.set_text("%d host%s" % tuple(parts))
        except Exception, e:
            print "Exception in generate_ip():", str(e)
        self.generating = False

def split_ip(ip):
    b0 = ip & 0xff
    b1 = (ip >> 8) & 0xff
    b2 = (ip >> 16) & 0xff
    b3 = (ip >> 24) & 0xff

    return (b3,b2,b1,b0)

def main():
    app = IPAddress()
    gtk.main()

if __name__ == "__main__":
    main()

