#!/usr/bin/env python
import asl

from jtk import StationDatabase

channel_file = "allchan.txt"
device_file = "instrument.txt"
database = "stations.db"

sensor_map = {
'36000I'      : 'KS36000',
'54000'       : 'KS54000',
'CMG3-T'      : 'CMG3-T',
'CMG3-T-B'    : 'CMG3-TB',
'FBA23'       : 'FBA23',
'FBAES-T'     : 'ES-T',
'PARO_MB'     : 'Paro-MBaro',
'RMYOUNG_WDI' : 'Wind-Direction',
'RMYOUNG_WSI' : 'Wind-Speed',
'S13'         : 'GS-13',
'SETRA-270'   : 'Setra-270',
'STS-2-HG'    : 'STS-2-HG',
'STS-2-SG'    : 'STS-2-SG',
'STS-2.5'     : 'STS-2.5',
'STS1HVBB'    : 'STS-1-H',
'STS1VBBE300' : ('STS-1-V-E300', 'STS-1-H-E300'),
'STS1VVBB'    : 'STS-1-V',
'STS2VBB'     : 'STS-2-SG',
'TR240'       : 'TR-240',
'VAISALA'     : 'Vaisala',
}

subsets = {
"AFRICA"    : "Africa",
"ALL"       : "All Stations",
"ANSS"      : "ANSS (Advanced National Seismic System)",
"ANTARCTIC" : "Antarctica",
"ASIA"      : "Asia",
"ATLANTIC"  : "Atlantic",
"AUSTRALIA" : "Australia",
"CAMERICA"  : "Central America",
"CARIBBEAN" : "Caribbean",
"CDSN"      : "CDSN (China Digital Seismograph Network)",
"CHINA"     : "People's Republic of China",
"CU"        : "CU (Caribbean/USGS)",
"EUROPE"    : "Europe",
"GCI"       : "CTBTO GCI Link Hosted",
"CTBTO"     : "CTBTO Shared Data",
"GSRAS"     : "GSRAS (Geophysical Survey Russian Academy of Sciences)",
"IC"        : "IC (IRIS/China)",
"IU"        : "IU (IRIS/USGS)",
"MPINT"     : "MP Intergral",
"NAMERICA"  : "North America",
"PACIFIC"   : "Pacific",
"PTWC"      : "PTWC (Pacific Tsunami Warning Center)",
"RUSSIA"    : "Russia",
"SAMERICA"  : "South America",
"USA"       : "United States of America",
}

stations = {
    'CU_ANWB' : ['ALL', 'CU', 'CARIBBEAN', 'MPINT'],
    'CU_BBGH' : ['ALL', 'CU', 'CARIBBEAN', 'MPINT'], 
    'CU_BCIP' : ['ALL', 'CU', 'CARIBBEAN', 'MPINT', 'CAMERICA'], 
    'CU_GRGR' : ['ALL', 'CU', 'CARIBBEAN', 'MPINT'], 
    'CU_GRTK' : ['ALL', 'CU', 'CARIBBEAN', 'MPINT'], 
    'CU_GTBY' : ['ALL', 'CU', 'CARIBBEAN', 'MPINT'], 
    'CU_MTDJ' : ['ALL', 'CU', 'CARIBBEAN', 'MPINT'], 
    'CU_SDDR' : ['ALL', 'CU', 'CARIBBEAN', 'MPINT'], 
    'CU_TGUH' : ['ALL', 'CU', 'CARIBBEAN', 'MPINT', 'CAMERICA'],
    'IC_BJT'  : ['ALL', 'IC', 'CDSN', 'CHINA', 'ASIA', 'CTBTO'],
    'IC_ENH'  : ['ALL', 'IC', 'CDSN', 'CHINA', 'ASIA'],
    'IC_HIA'  : ['ALL', 'IC', 'CDSN', 'CHINA', 'ASIA'],
    'IC_KMI'  : ['ALL', 'IC', 'CDSN', 'CHINA', 'ASIA', 'CTBTO'],
    'IC_LSA'  : ['ALL', 'IC', 'CDSN', 'CHINA', 'ASIA'],
    'IC_MDJ'  : ['ALL', 'IC', 'CDSN', 'CHINA', 'ASIA'],
    'IC_QIZ'  : ['ALL', 'IC', 'CDSN', 'CHINA', 'ASIA'],
    'IC_SSE'  : ['ALL', 'IC', 'CDSN', 'CHINA', 'ASIA', 'CTBTO'],
    'IC_WMQ'  : ['ALL', 'IC', 'CDSN', 'CHINA', 'ASIA'],
    'IC_XAN'  : ['ALL', 'IC', 'CDSN', 'CHINA', 'ASIA', 'CTBTO'],
    'IU_ADK'  : ['ALL', 'IU', 'USA'], 
    'IU_AFI'  : ['ALL', 'IU', 'PTWC', 'PACIFIC', 'CTBTO'],
    'IU_ANMO' : ['ALL', 'IU', 'USA', 'NAMERICA', 'CTBTO'],
    'IU_ANTO' : ['ALL', 'IU', 'EUROPE'],
    'IU_BBSR' : ['ALL', 'IU', 'ATLANTIC'],
    'IU_BILL' : ['ALL', 'IU', 'GSRAS', 'RUSSIA', 'ASIA', 'CTBTO'],
    'IU_CASY' : ['ALL', 'IU', 'ANTARCTIC'],
    'IU_CCM'  : ['ALL', 'IU', 'ANSS', 'USA', 'NAMERICA'],
    'IU_CHTO' : ['ALL', 'IU', 'ASIA'],
    'IU_COLA' : ['ALL', 'IU', 'USA', 'NAMERICA'],
    'IU_COR'  : ['ALL', 'IU', 'ANSS', 'USA', 'NAMERICA'],
    'IU_CTAO' : ['ALL', 'IU', 'CTBTO', 'AUSTRALIA'],
    'IU_DAV'  : ['ALL', 'IU', 'CTBTO', 'GCI'],
    'IU_DWPF' : ['ALL', 'IU', 'ANSS', 'USA', 'NAMERICA'],
    'IU_FUNA' : ['ALL', 'IU', 'PTWC', 'PACIFIC'],
    'IU_FURI' : ['ALL', 'IU', 'CTBTO', 'AFRICA'],
    'IU_GRFO' : ['ALL', 'IU', 'EUROPE'],
    'IU_GNI'  : ['ALL', 'IU', 'CTBTO', 'GCI', 'ASIA'],
    'IU_GUMO' : ['ALL', 'IU', 'PACIFIC', 'CTBTO'],
    'IU_HKT'  : ['ALL', 'IU', 'ANSS', 'USA', 'NAMERICA'],
    'IU_HNR'  : ['ALL', 'IU', 'CTBTO', 'GCI'],
    'IU_HRV'  : ['ALL', 'IU', 'USA', 'NAMERICA'],
    'IU_INCN' : ['ALL', 'IU', 'ASIA'],
    'IU_JOHN' : ['ALL', 'IU', 'PTWC', 'PACIFIC'],
    'IU_KBL'  : ['ALL', 'IU', 'ASIA'],
    'IU_KBS'  : ['ALL', 'IU'],
    'IU_KEV'  : ['ALL', 'IU', 'EUROPE'],
    'IU_KIEV' : ['ALL', 'IU', 'EUROPE'],
    'IU_KIP'  : ['ALL', 'IU', 'PTWC', 'USA', 'PACIFIC'],
    'IU_KMBO' : ['ALL', 'IU', 'CTBTO', 'GCI', 'AFRICA'],
    'IU_KNTN' : ['ALL', 'IU', 'PTWC', 'PACIFIC'],
    'IU_KONO' : ['ALL', 'IU', 'EUROPE'],
    'IU_KOWA' : ['ALL', 'IU', 'AFRICA', 'CTBTO'],
    'IU_LCO'  : ['ALL', 'IU', 'SAMERICA'],
    'IU_LSZ'  : ['ALL', 'IU', 'CTBTO', 'GCI', 'AFRICA'],
    'IU_LVC'  : ['ALL', 'IU', 'CTBTO', 'GCI', 'SAMERICA'],
    'IU_MA2'  : ['ALL', 'IU', 'GSRAS', 'RUSSIA', 'ASIA', 'CTBTO'],
    'IU_MACI' : ['ALL', 'IU', 'AFRICA'],
    'IU_MAJO' : ['ALL', 'IU', 'ASIA'],
    'IU_MAKZ' : ['ALL', 'IU', 'ASIA'],
    'IU_MBWA' : ['ALL', 'IU', 'AUSTRALIA'],
    'IU_MIDW' : ['ALL', 'IU', 'PTWC', 'PACIFIC'],
    'IU_MSKU' : ['ALL', 'IU', 'CTBTO', 'GCI', 'AFRICA'],
    'IU_NWAO' : ['ALL', 'IU', 'CTBTO', 'AUSTRALIA'],
    'IU_OTAV' : ['ALL', 'IU', 'SAMERICA', 'MPINT'],
    'IU_PAB'  : ['ALL', 'IU', 'EUROPE'],
    'IU_PAYG' : ['ALL', 'IU', 'PACIFIC', 'MPINT'],
    'IU_PET'  : ['ALL', 'IU', 'GSRAS', 'RUSSIA', 'ASIA'],
    'IU_PMG'  : ['ALL', 'IU', 'PTWC', 'CTBTO'],
    'IU_PMSA' : ['ALL', 'IU', 'ANTARCTIC', 'CTBTO'],
    'IU_POHA' : ['ALL', 'IU', 'PTWC', 'USA', 'PACIFIC'],
    'IU_PTCN' : ['ALL', 'IU', 'PACIFIC'],
    'IU_PTGA' : ['ALL', 'IU', 'CTBTO', 'GCI', 'SAMERICA'],
    'IU_QSPA' : ['ALL', 'IU', 'ANTARCTIC', 'CTBTO'],
    'IU_RAO'  : ['ALL', 'IU', 'CTBTO', 'GCI', 'PACIFIC'],
    'IU_RAR'  : ['ALL', 'IU', 'CTBTO', 'GCI', 'PACIFIC'],
    'IU_RCBR' : ['ALL', 'IU', 'CTBTO', 'GCI', 'SAMERICA'],
    'IU_RSSD' : ['ALL', 'IU', 'ANSS', 'USA', 'NAMERICA'],
    'IU_SAML' : ['ALL', 'IU', 'SAMERICA', 'MPINT'],
    'IU_SBA'  : ['ALL', 'IU', 'ANTARCTIC'],
    'IU_SDV'  : ['ALL', 'IU', 'CTBTO', 'GCI', 'SAMERICA'],
    'IU_SFJD' : ['ALL', 'IU', 'CTBTO', 'GCI'],
    'IU_SJG'  : ['ALL', 'IU', 'CARIBBEAN', 'CTBTO'],
    'IU_SLBS' : ['ALL', 'IU', 'CAMERICA', 'MPINT'],
    'IU_SNZO' : ['ALL', 'IU'],
    'IU_SSPA' : ['ALL', 'IU', 'ANSS', 'USA', 'NAMERICA'],
    'IU_TARA' : ['ALL', 'IU', 'PTWC', 'PACIFIC'],
    'IU_TATO' : ['ALL', 'IU', 'ASIA'],
    'IU_TEIG' : ['ALL', 'IU', 'CTBTO', 'GCI', 'CAMERICA'],
    'IU_TIXI' : ['ALL', 'IU', 'GSRAS', 'RUSSIA', 'ASIA', 'CTBTO'],
    'IU_TRIS' : ['ALL', 'IU', 'CTBTO', 'GCI', 'ATLANTIC'],
    'IU_TRQA' : ['ALL', 'IU', 'SAMERICA', 'MPINT'],
    'IU_TSUM' : ['ALL', 'IU', 'CTBTO', 'GCI', 'AFRICA'],
    'IU_TUC'  : ['ALL', 'IU', 'USA', 'NAMERICA'],
    'IU_ULN'  : ['ALL', 'IU', 'ASIA'],
    'IU_WAKE' : ['ALL', 'IU', 'PTWC', 'PACIFIC'],
    'IU_WCI'  : ['ALL', 'IU', 'ANSS', 'USA', 'NAMERICA'],
    'IU_WVT'  : ['ALL', 'IU', 'ANSS', 'USA', 'NAMERICA'],
    'IU_XMAS' : ['ALL', 'IU', 'PTWC', 'PACIFIC'],
    'IU_YAK'  : ['ALL', 'IU', 'GSRAS', 'RUSSIA', 'ASIA', 'CTBTO'],
    'IU_YSS'  : ['ALL', 'IU', 'GSRAS', 'RUSSIA', 'ASIA', 'CTBTO']
}

def parse_channel_file(file):
    channel_list = []
    station_channel_pairs = []
    rh = open(file, 'r')
    for line in rh:
        if len(line.strip()) == 0:
            continue
        parts = map(lambda l: l.strip(), line.split())
        if len(parts) == 2:
            s,c = parts
            n = ""
            l = ""
        if len(parts) == 3:
            s,n,c = parts
            l = ""
        else:
            s,n,c,l = parts
        description = ""
        channel_list.append((l,c,description))
        st_id = StationDatabase.create_station_key(n,s)
        ch_id = StationDatabase.create_channel_key(l,c)
        station_channel_pairs.append((st_id, ch_id, "", ""))

    return (channel_list,station_channel_pairs)
    

def update_channels():
    channel_list,station_channel_pairs = parse_channel_file(channel_file)

    db = StationDatabase.StationDatabase()
    db.select_database(database)

    db.execute("DELETE FROM stationchannel")
    db.execute("DELETE FROM channel")
    db.add_channels(channel_list)
    db.add_station_channels(station_channel_pairs)

def generate_database():
    subset_list  = []
    station_list = []
    station_subset_pairs = []

    for (k,v) in subsets.items():
        subset_list.append((k,v))

    for (k,v) in stations.items():
        net,name = k.strip().split('_')
        id = StationDatabase.create_station_key(net, name)
        station_list.append((net,name))
        for s in v:
            if s not in (subsets.keys()):
                print s, "not recognized"
            station_subset_pairs.append((id,s))

    channel_list, station_channel_pairs = parse_channel_file(channel_file)

    db = StationDatabase.StationDatabase()
    db.select_database(database)
    db.init()
    db.add_subsets(subset_list)
    db.add_stations(station_list)
    db.add_station_subsets(station_subset_pairs)
    db.add_channels(channel_list)
    db.add_station_channels(station_channel_pairs)

def parse_device_file(file):
    chan_dev_list = []
    rh = open(file, 'r')
    for line in rh:
        if len(line.strip()) == 0:
            continue
        parts = map(lambda l: l.strip(), line.split())
        if len(parts) == 4:
            s,n,c,i = parts
            l = ""
        else:
            s,n,l,c,i = parts
        if sensor_map.has_key(i):
            name = sensor_map[i]
            if type(name) == tuple:
                if len(name) == 1:
                    i = name[0]
                elif c[-1].upper() == 'Z':
                    i = name[0]
                elif len(name) == 2:
                    i = name[1]
                elif c[-1].upper() in ('N','1'):
                    i = name[1]
                else:
                    i = name[2]
            else:
                i = name
        st_id = StationDatabase.create_station_key(n,s)
        ch_id = StationDatabase.create_channel_key(l,c)
        chan_dev_list.append((st_id,ch_id,i,""))

    return chan_dev_list


def update_devices():
    chan_dev_list = parse_device_file(device_file)
    db = StationDatabase.StationDatabase()
    db.select_database(database)
    db.add_station_channels(chan_dev_list)

#update_channels()
update_devices()


