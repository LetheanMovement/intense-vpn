#!/usr/bin/python

import os
import sys
# Add lib directory to search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../lib')))

import ed25519
import getopt
import log
import logging
import logging.config
import config
import argparse
import configargparse
import util
import pprint
import time
import services
import sdp
import sdps
import random
import string
import requests
import json
import socket
import re
import atexit

def parseUri(cfg, uri):
    # authid:mgmtid@providerid:serviceid
    p = re.search("(.*):(.*)@(.*):(.*)", uri)
    if (p):
        cfg.authId = p.group(1)
        cfg.uniqueId = p.group(2)
        cfg.providerid = p.group(3)
        cfg.serviceId = p.group(4)
    else:
        # authid@providerid:serviceid
        p = re.search("(.*)@(.*):(.*)", uri)
        if (p):
            cfg.authId = p.group(1)
            cfg.uniqueId = "_random_"
            cfg.providerid = p.group(2)
            cfg.serviceId = p.group(3)
        else:
            # providerid:serviceid
            p = re.search("(.*):(.*)", uri)
            if (p):
                cfg.authId = "_random_"
                cfg.uniqueId = "_random_"
                cfg.providerid = p.group(1)
                cfg.serviceId = p.group(2)
            else:
                log.L.error("Bad URI %s" % (uri))
                return(None)
    if (cfg.authId[:2] != cfg.serviceId):
        print(cfg.authId)
        log.L.error("Authid must start with serviceid!")
        return(None)
    return(cfg)

def generateAuthId(sid):
    return (sid+''.join(random.choice('ABCDEF0123456789') for _ in range(14)))

def generateMgmtId():
    return (''.join(random.choice('ABCDEF0123456789') for _ in range(16)))

def loadService(pid, sid):
    if (not sid or not pid):
        log.L.error("You must specify serviceid and providerid!")
        return(None)
    else:
        if sdps.SDPS.getSDP(pid):
            s = sdps.SDPS.getSDP(pid)
            services.SERVICES.loadClient(s)
            services.SERVICES.mgmt.disable()
            services.SERVICES.http.disable()
            if services.SERVICES.get(sid):
                return(True)
            else:
                log.L.error("Service id %s does not exists!" % (sid))
                return(None)
        else:
            log.L.error("Provider id %s does not exists!" % (pid))
            return(None)
    
# Starting here
def main(argv):
    
    config.CONFIG = config.Config("dummy")
    p = configargparse.getArgumentParser(ignore_unknown_config_file_keys=True, fromfile_prefix_chars='@')
    util.commonArgs(p)
    p.add_argument('--authid', dest='authId', metavar='AUTHID', required=None, default=None, help='Authentication ID. Use "random" to generate.')
    p.add_argument('--uniqueid', dest='uniqueId', metavar='UNIQUEID', required=None, default=None, help='Unique ID of proxy. Use "random" to generate.')
    p.add_argument('--stunnel-port', dest='stunnelPort', metavar='PORT', required=None, default=8187, help='Use this stunnel local port for connections over proxy.')
    p.add_argument('--https-proxy-host', dest='httpsProxyHost', metavar='HOST', required=None, default=None, help='Use this https proxy host.')
    p.add_argument('--https-proxy-port', dest='httpsProxyPort', metavar='PORT', required=None, default=3128, help='Use this https proxy port.')
    p.add_argument('--proxy-port', dest='proxyPort', metavar='PORT', required=None, default=8186, help='Use this port as local bind port for proxy.')
    p.add_argument('--proxy-bind', dest='proxyBind', metavar='IP', required=None, default="127.0.0.1", help='Use this host as local bind for proxy.')
    p.add_argument('--connect-timeout', dest='connectTimeout', metavar='S', required=None, default=30, help='Timeout for connect to service.')
    p.add_argument('--payment-timeout', dest='paymentTimeout', metavar='S', required=None, default=1200, help='Timeout for payment to service.')
    p.add_argument('--exit-on-no-payment', dest='exitNoPayment', metavar='Bool', required=None, default=None, help='Exit after payment is gone.')
    
    p.add('cmd', metavar='Command', choices=["connect","list"], help='Exit after payment is gone.')
        
    (cfg, args) = p.parse_known_args()
    util.parseCommonArgs(p, cfg)
    config.Config.CAP = cfg

    config.CONFIG = config.Config("dummy")
    cmd = cfg.cmd
    cfg.O = None
    cfg.L = None
    
    if (cmd == "list"):
        cfg.L = True
    elif (cmd == "connect"):
        cfg.O = True
        if len(args)==0:
            log.L.error("Expecting argument to connect!")
            sys.exit(1)
        uri = args[0]
        p = re.search("(.*)/(.*)", uri)
        if (p):
            log.L.error("Complex URI not supported yet :(")
            sys.exit(1)
        cfg = parseUri(cfg, uri)
        if not cfg:
            sys.exit(1)
            
    if cfg.authId == "_random_":
        cfg.authId = generateAuthId(cfg.serviceId)
    if cfg.uniqueId == "_random_":
        cfg.uniqueId = generateMgmtId()
    
    config.Config.CAP = cfg

    # Initialise services
    services.SERVICES = services.Services()
    log.A.audit(log.A.START, log.A.SERVICE, "lthnvpnc")
    sdps.SDPS = sdps.SDPList()
    sdps.SDPS.parse()
    
    if (cfg.O):
        if (loadService(cfg.providerid, cfg.serviceId)):
            services.SERVICES.syslog.run()
            services.SERVICES.show()
            sid = services.SERVICES.get(cfg.serviceId)
            sid.cfg["uniqueid"] = cfg.uniqueId
            sid.cfg["paymentid"] = cfg.authId
            sdp = sdps.SDPS.getSDP(cfg.providerid)
            atexit.register(sid.stop)
            sid.run()
            sid.connect(sdp)   
                      
    elif (cfg.L):
        print("ProviderId:ServiceId,serviceType,ProviderName,ServiceName")
        for pid in sdps.SDPS.list():
            sdp = sdps.SDPS.getSDP(pid)
            for srv in sdp["services"]:
                sid = srv["id"]
                print("%s:%s,%s,%s,%s" % (pid, sid, srv["type"], sdp["provider"]["name"], srv["name"]))
    else:
        log.L.error("You must specify command (list|connect|show)")
        sys.exit(1)
            
if __name__ == "__main__":
    main(sys.argv[1:])
    
