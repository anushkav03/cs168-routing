"""
Your awesome Distance Vector router for CS 168

Based on skeleton code by:
  MurphyMc, zhangwen0411, lab352
"""

import sim.api as api
from cs168.dv import (
    RoutePacket,
    Table,
    TableEntry,
    DVRouterBase,
    Ports,
    FOREVER,
    INFINITY,
)


class DVRouter(DVRouterBase):

    # A route should time out after this interval
    ROUTE_TTL = 15

    # -----------------------------------------------
    # At most one of these should ever be on at once
    SPLIT_HORIZON = False
    POISON_REVERSE = False
    # -----------------------------------------------

    # Determines if you send poison for expired routes
    POISON_EXPIRED = False

    # Determines if you send updates when a link comes up
    SEND_ON_LINK_UP = False

    # Determines if you send poison when a link goes down
    POISON_ON_LINK_DOWN = False

    def __init__(self):
        """
        Called when the instance is initialized.
        DO NOT remove any existing code from this method.
        However, feel free to add to it for memory purposes in the final stage!
        """
        assert not (
            self.SPLIT_HORIZON and self.POISON_REVERSE
        ), "Split horizon and poison reverse can't both be on"

        self.start_timer()  # Starts signaling the timer at correct rate.

        # Contains all current ports and their latencies.
        # See the write-up for documentation.
        self.ports = Ports()

        # This is the table that contains all current routes
        self.table = Table()
        self.table.owner = self

        ##### Begin Stage 10A #####
        self.history = {} # {Port: {Host: latest TableEntry()}, - - - }       

        ##### End Stage 10A #####

    def add_static_route(self, host, port):
        """
        Adds a static route to this router's table.

        Called automatically by the framework whenever a host is connected
        to this router.

        :param host: the host.
        :param port: the port that the host is attached to.
        :returns: nothing.
        """
        # `port` should have been added to `peer_tables` by `handle_link_up`
        # when the link came up.
        assert port in self.ports.get_all_ports(), "Link should be up, but is not."

        ##### Begin Stage 1 #####
        t = self.table # fwding table
        latency = self.ports.get_latency(port)
        t[host] = TableEntry(dst=host, port=port, latency=latency, expire_time=FOREVER)
        ##### End Stage 1 #####

    def handle_data_packet(self, packet, in_port):
        """
        Called when a data packet arrives at this router.

        You may want to forward the packet, drop the packet, etc. here.

        :param packet: the packet that arrived.
        :param in_port: the port from which the packet arrived.
        :return: nothing.
        """
        
        ##### Begin Stage 2 #####
        destination = packet.dst
        if destination in self.table:
            table_entry = self.table[destination]

            dest_port = table_entry.port
            overall_latency = table_entry.latency

            if overall_latency >= INFINITY:
                return # drop pkts
            else:
                self.send(packet=packet, port=dest_port) # send packet


        ##### End Stage 2 #####

    def send_routes(self, force=False, single_port=None):
        """
        Send route advertisements for all routes in the table.

        :param force: if True, advertises ALL routes in the table;
                      otherwise, advertises only those routes that have
                      changed since the last advertisement.
               single_port: if not None, sends updates only to that port; to
                            be used in conjunction with handle_link_up.
        :return: nothing.
        """
        
        ##### Begin Stages 3, 6, 7, 8, 10 #####

        ## 10A helpers ##
        def isNewRoute(port, host, entry_latency):
            if port not in self.history or host not in self.history[port]: # this port is not in history altho idk how that would happen
                return True
            port_hosts = self.history[port] # returns a dict {Host: Entry_latency, Host: Entry_latency - - -}
            return port_hosts[host] != entry_latency # current latency differs from last sent latency

        def updateHistory(port, host, entry_latency):
            if port not in self.history:
                self.history[port] = {}
            self.history[port][host] = entry_latency

        ## Stage 3: Send periodic adverts ##
        t = self.table

        if single_port is None:
            ports = self.ports.get_all_ports()
        else:
            ports = [single_port]
        
        for p in ports:
            for host, entry in t.items():
                if p == entry.port:
                    # Split Horizon: Don't advertise back
                    if self.SPLIT_HORIZON:
                        continue

                    # Reverse Poison: Explicitly advertise poison back
                    elif self.POISON_REVERSE:
                        if force or isNewRoute(p, host, INFINITY):
                            self.send_route(p, host, INFINITY)
                            updateHistory(p, host, INFINITY)

                    # If both flags are false, advertise back to neighbour
                    else:
                        adv_latency = min(INFINITY, entry.latency)
                        if force or isNewRoute(p, host, adv_latency):
                            self.send_route(p, host, adv_latency)
                            updateHistory(p, host, adv_latency)
                        else:
                            continue

                elif p != entry.port:
                    adv_latency = min(INFINITY, entry.latency)
                    if force or isNewRoute(p, host, adv_latency):
                        self.send_route(p, host, adv_latency)
                        updateHistory(p, host, adv_latency)
                    else:
                        continue

        ##### End Stages 3, 6, 7, 8, 10 #####

    def expire_routes(self):
        """
        Clears out expired routes from table.
        accordingly.
        """
        
        ##### Begin Stages 5, 9 #####
        expired_routes = []
        t = self.table

        for host, entry in t.items():
            if api.current_time() >= entry.expire_time: # if curr time is beyond expire time for the entry
                expired_routes.append(host)     
       
        for host in expired_routes:
            if self.POISON_EXPIRED:
                port = t[host].port
                t[host] = TableEntry(dst=host, port=port, latency=INFINITY, expire_time=(api.current_time()+self.ROUTE_TTL))
            else:
                t.pop(host) # delete entry

        ##### End Stages 5, 9 #####

    def handle_route_advertisement(self, route_dst, route_latency, port):
        """
        Called when the router receives a route advertisement from a neighbor.

        :param route_dst: the destination of the advertised route.
        :param route_latency: latency from the neighbor to the destination.
        :param port: the port that the advertisement arrived on.
        :return: nothing.
        """
        
        ##### Begin Stages 4, 10 #####
        update = False

        link_latency = self.ports.get_latency(port)
        overall_latency = route_latency + link_latency
        t = self.table
        
        # if route not in table yet 
        if (not (route_dst in self.table)): 
            update = True

        # or ad is from next-hop
        elif port == t[route_dst].port:
            update = True 

        # or better latency than current
        elif overall_latency < t[route_dst].latency:
            update = True
        
        if update:
            t[route_dst] = TableEntry(dst=route_dst, port=port, latency=overall_latency, expire_time=api.current_time()+self.ROUTE_TTL)
            self.send_routes(force=False) ## Stage 10A

        ##### End Stages 4, 10 #####

    def handle_link_up(self, port, latency):
        """
        Called by the framework when a link attached to this router goes up.

        :param port: the port that the link is attached to.
        :param latency: the link latency.
        :returns: nothing.
        """
        self.ports.add_port(port, latency)

        ##### Begin Stage 10B #####
        if self.SEND_ON_LINK_UP:
            self.send_routes(single_port=port)

        ##### End Stage 10B #####

    def handle_link_down(self, port):
        """
        Called by the framework when a link attached to this router goes down.

        :param port: the port number used by the link.
        :returns: nothing.
        """
        self.ports.remove_port(port)

        ##### Begin Stage 10B #####
        t = self.table
        remove = []

        if self.POISON_ON_LINK_DOWN:
            for host, entry in t.items():
                if entry.port == port:
                    t[host] = TableEntry(dst=host, port=port, latency=INFINITY, expire_time=(api.current_time()+self.ROUTE_TTL))
                    self.send_routes(force=False)
        elif not self.POISON_ON_LINK_DOWN:
            for host, entry in t.items():
                if entry.port == port:
                    remove.append(host)

        for host in remove:
            t.pop(host)

        ##### End Stage 10B #####

    # Feel free to add any helper methods!
