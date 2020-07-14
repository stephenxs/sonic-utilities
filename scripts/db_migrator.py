#!/usr/bin/env python

import traceback
import sys
import argparse
import syslog
from swsssdk import ConfigDBConnector, SonicDBConfig
import sonic_device_util


SYSLOG_IDENTIFIER = 'db_migrator'


def log_info(msg):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_INFO, msg)
    syslog.closelog()


def log_error(msg):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_ERR, msg)
    syslog.closelog()


class DBMigrator():
    def __init__(self, namespace, socket=None):
        """
        Version string format:
           version_<major>_<minor>_<build>
              major: starting from 1, sequentially incrementing in master
                     branch.
              minor: in github branches, minor version stays in 0. This minor
                     version creates space for private branches derived from
                     github public branches. These private branches shall use
                     none-zero values.
              build: sequentially increase within a minor version domain.
        """
        self.CURRENT_VERSION = 'version_1_0_4'

        self.TABLE_NAME      = 'VERSIONS'
        self.TABLE_KEY       = 'DATABASE'
        self.TABLE_FIELD     = 'VERSION'

        db_kwargs = {}
        if socket:
            db_kwargs['unix_socket_path'] = socket

        if namespace is None:
            self.configDB = ConfigDBConnector(**db_kwargs)
        else:
            self.configDB = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace, **db_kwargs)
        self.configDB.db_connect('CONFIG_DB')

    def migrate_pfc_wd_table(self):
        '''
        Migrate all data entries from table PFC_WD_TABLE to PFC_WD
        '''
        data = self.configDB.get_table('PFC_WD_TABLE')
        for key in data.keys():
            self.configDB.set_entry('PFC_WD', key, data[key])
        self.configDB.delete_table('PFC_WD_TABLE')

    def is_ip_prefix_in_key(self, key):
        '''
        Function to check if IP address is present in the key. If it
        is present, then the key would be a tuple or else, it shall be
        be string
        '''
        return (isinstance(key, tuple))

    def migrate_interface_table(self):
        '''
        Migrate all data from existing INTERFACE table with IP Prefix
        to have an additional ONE entry without IP Prefix. For. e.g, for an entry
        "Vlan1000|192.168.0.1/21": {}", this function shall add an entry without
        IP prefix as ""Vlan1000": {}". This is for VRF compatibility.
        '''
        if_db = []
        if_tables = {
                     'INTERFACE',
                     'PORTCHANNEL_INTERFACE',
                     'VLAN_INTERFACE',
                     'LOOPBACK_INTERFACE'
                    }
        for table in if_tables:
            data = self.configDB.get_table(table)
            for key in data.keys():
                if not self.is_ip_prefix_in_key(key):
                    if_db.append(key)
                    continue

        for table in if_tables:
            data = self.configDB.get_table(table)
            for key in data.keys():
                if not self.is_ip_prefix_in_key(key) or key[0] in if_db:
                    continue
                log_info('Migrating interface table for ' + key[0])
                self.configDB.set_entry(table, key[0], data[key])
                if_db.append(key[0])

    def mlnx_default_buffer_parameters(self, db_version, table):
        """
        We extract buffer configurations to a common function
        so that it can be reused among different migration
        This 
        The logic of buffer parameters migrating:
        1. Compare the current buffer configuration with the default settings
        2. If there is a match, map the old setting to a new one acording to the map "pool_mapped_from_old_version"
        3. Insert the new setting into database
        Each settings defined below (except that for version_1_0_2) will be used twice:
        1. It is referenced as new setting when database is migrated to that version
        2. It is referenced as old setting when database is migrated from that version
        """
        mellanox_default_parameter = {
            "version_1_0_2": {
                # Buffer pool configuration info
                "buffer_pool_list" : ['ingress_lossless_pool', 'egress_lossless_pool', 'ingress_lossy_pool', 'egress_lossy_pool'],
                "spc1_t0_pool": {"ingress_lossless_pool": { "size": "4194304", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "7340032", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "16777152", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "7340032", "type": "egress", "mode": "dynamic" } },
                "spc1_t1_pool": {"ingress_lossless_pool": { "size": "2097152", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "5242880", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "16777152", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "5242880", "type": "egress", "mode": "dynamic" } },
                "spc2_t0_pool": {"ingress_lossless_pool": { "size": "8224768", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "8224768", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "35966016", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "8224768", "type": "egress", "mode": "dynamic" } },
                "spc2_t1_pool": {"ingress_lossless_pool": { "size": "12042240", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "12042240", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "35966016", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "12042240", "type": "egress", "mode": "dynamic" } },

                # Buffer pool migration control info
                "pool_configuration_list": ["spc1_t0_pool", "spc1_t1_pool", "spc2_t0_pool", "spc2_t1_pool"]
            },
            "version_1_0_3": {
                # On Mellanox platform the buffer pool size changed since
                # version with new SDK 4.3.3052, SONiC to SONiC update
                # from version with old SDK will be broken without migration.
                #
                # Buffer pool migration control info
                # v1.0.2                   hwsku/platform                     configuration set in v1.0.3
                # spc1_t0_pool                                                spc1_t0_pool
                #
                # spc1_t1_pool                                                spc1_t1_pool
                #
                # spc2_t0_pool--platform---x86_64-mlnx_msn3800-r0-------------spc2_3800_t0_pool
                #                   |
                #                   +------other spc2 platforms---------------spc2_t0_pool
                #
                # spc2_t1_pool--platform---platform: x86_64-mlnx_msn3800-r0---spc2_3800_t1_pool
                #                   |
                #                   +------other spc2 platforms---------------spc2_t1_pool
                #
                "pool_configuration_list": ["spc1_t0_pool", "spc1_t1_pool", "spc2_t0_pool", "spc2_t1_pool", "spc2_3800_t0_pool", "spc2_3800_t1_pool"],
                "pool_mapped_from_old_version": {
                    "spc2_t0_pool": ("platform", {"x86_64-mlnx_msn3800-r0": "spc2_3800_t0_pool"}),
                    "spc2_t1_pool": ("platform", {"x86_64-mlnx_msn3800-r0": "spc2_3800_t1_pool"})
                    },

                # Buffer pool configuration info
                "buffer_pool_list" : ['ingress_lossless_pool', 'egress_lossless_pool', 'ingress_lossy_pool', 'egress_lossy_pool'],
                "spc1_t0_pool": {"ingress_lossless_pool": { "size": "5029836", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "5029836", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "14024599", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "5029836", "type": "egress", "mode": "dynamic" } },
                "spc1_t1_pool": {"ingress_lossless_pool": { "size": "2097100", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "2097100", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "14024599", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "2097100", "type": "egress", "mode": "dynamic" } },

                "spc2_t0_pool": {"ingress_lossless_pool": { "size": "14983147", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "14983147", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "34340822", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "14983147", "type": "egress", "mode": "dynamic" } },
                "spc2_t1_pool": {"ingress_lossless_pool": { "size": "9158635", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "9158635", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "34340822", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "9158635", "type": "egress", "mode": "dynamic" } },

                # 3800 platform has gearbox installed so the buffer pool size is different with other Spectrum2 platform
                "spc2_3800_t0_pool": {"ingress_lossless_pool": { "size": "28196784", "type": "ingress", "mode": "dynamic" },
                                      "ingress_lossy_pool": { "size": "28196784", "type": "ingress", "mode": "dynamic" },
                                      "egress_lossless_pool": { "size": "34340832", "type": "egress", "mode": "dynamic" },
                                      "egress_lossy_pool": {"size": "28196784", "type": "egress", "mode": "dynamic" } },
                "spc2_3800_t1_pool": {"ingress_lossless_pool": { "size": "17891280", "type": "ingress", "mode": "dynamic" },
                                      "ingress_lossy_pool": { "size": "17891280", "type": "ingress", "mode": "dynamic" },
                                      "egress_lossless_pool": { "size": "34340832", "type": "egress", "mode": "dynamic" },
                                      "egress_lossy_pool": {"size": "17891280", "type": "egress", "mode": "dynamic" } },

                # Lossless headroom info
                "spc1_headroom": {"pg_lossless_10000_5m_profile": {"size": "34816", "xon": "18432"},
                                  "pg_lossless_25000_5m_profile": {"size": "34816", "xon": "18432"},
                                  "pg_lossless_40000_5m_profile": {"size": "34816", "xon": "18432"},
                                  "pg_lossless_50000_5m_profile": {"size": "34816", "xon": "18432"},
                                  "pg_lossless_100000_5m_profile": {"size": "36864", "xon": "18432"},
                                  "pg_lossless_10000_40m_profile": {"size": "36864", "xon": "18432"},
                                  "pg_lossless_25000_40m_profile": {"size": "39936", "xon": "18432"},
                                  "pg_lossless_40000_40m_profile": {"size": "41984", "xon": "18432"},
                                  "pg_lossless_50000_40m_profile": {"size": "41984", "xon": "18432"},
                                  "pg_lossless_100000_40m_profile": {"size": "54272", "xon": "18432"},
                                  "pg_lossless_10000_300m_profile": {"size": "49152", "xon": "18432"},
                                  "pg_lossless_25000_300m_profile": {"size": "71680", "xon": "18432"},
                                  "pg_lossless_40000_300m_profile": {"size": "94208", "xon": "18432"},
                                  "pg_lossless_50000_300m_profile": {"size": "94208", "xon": "18432"},
                                  "pg_lossless_100000_300m_profile": {"size": "184320", "xon": "18432"}},
                "spc2_headroom": {"pg_lossless_1000_5m_profile": {"size": "35840", "xon": "18432"},
                                  "pg_lossless_10000_5m_profile": {"size": "36864", "xon": "18432"},
                                  "pg_lossless_25000_5m_profile": {"size": "36864", "xon": "18432"},
                                  "pg_lossless_40000_5m_profile": {"size": "36864", "xon": "18432"},
                                  "pg_lossless_50000_5m_profile": {"size": "37888", "xon": "18432"},
                                  "pg_lossless_100000_5m_profile": {"size": "38912", "xon": "18432"},
                                  "pg_lossless_200000_5m_profile": {"size": "41984", "xon": "18432"},
                                  "pg_lossless_1000_40m_profile": {"size": "36864", "xon": "18432"},
                                  "pg_lossless_10000_40m_profile": {"size": "38912", "xon": "18432"},
                                  "pg_lossless_25000_40m_profile": {"size": "41984", "xon": "18432"},
                                  "pg_lossless_40000_40m_profile": {"size": "45056", "xon": "18432"},
                                  "pg_lossless_50000_40m_profile": {"size": "47104", "xon": "18432"},
                                  "pg_lossless_100000_40m_profile": {"size": "59392", "xon": "18432"},
                                  "pg_lossless_200000_40m_profile": {"size": "81920", "xon": "18432"},
                                  "pg_lossless_1000_300m_profile": {"size": "37888", "xon": "18432"},
                                  "pg_lossless_10000_300m_profile": {"size": "53248", "xon": "18432"},
                                  "pg_lossless_25000_300m_profile": {"size": "78848", "xon": "18432"},
                                  "pg_lossless_40000_300m_profile": {"size": "104448", "xon": "18432"},
                                  "pg_lossless_50000_300m_profile": {"size": "121856", "xon": "18432"},
                                  "pg_lossless_100000_300m_profile": {"size": "206848", "xon": "18432"},
                                  "pg_lossless_200000_300m_profile": {"size": "376832", "xon": "18432"}},
                "spc2_3800_headroom": {"pg_lossless_1000_5m_profile": {"size": "32768", "xon": "18432"},
                                       "pg_lossless_10000_5m_profile": {"size": "34816", "xon": "18432"},
                                       "pg_lossless_25000_5m_profile": {"size": "38912", "xon": "18432"},
                                       "pg_lossless_40000_5m_profile": {"size": "41984", "xon": "18432"},
                                       "pg_lossless_50000_5m_profile": {"size": "44032", "xon": "18432"},
                                       "pg_lossless_100000_5m_profile": {"size": "55296", "xon": "18432"},
                                       "pg_lossless_200000_5m_profile": {"size": "77824", "xon": "18432"},
                                       "pg_lossless_1000_40m_profile": {"size": "33792", "xon": "18432"},
                                       "pg_lossless_10000_40m_profile": {"size": "36864", "xon": "18432"},
                                       "pg_lossless_25000_40m_profile": {"size": "43008", "xon": "18432"},
                                       "pg_lossless_40000_40m_profile": {"size": "49152", "xon": "18432"},
                                       "pg_lossless_50000_40m_profile": {"size": "53248", "xon": "18432"},
                                       "pg_lossless_100000_40m_profile": {"size": "72704", "xon": "18432"},
                                       "pg_lossless_200000_40m_profile": {"size": "112640", "xon": "18432"},
                                       "pg_lossless_1000_300m_profile": {"size": "34816", "xon": "18432"},
                                       "pg_lossless_10000_300m_profile": {"size": "50176", "xon": "18432"},
                                       "pg_lossless_25000_300m_profile": {"size": "75776", "xon": "18432"},
                                       "pg_lossless_40000_300m_profile": {"size": "101376", "xon": "18432"},
                                       "pg_lossless_50000_300m_profile": {"size": "117760", "xon": "18432"},
                                       "pg_lossless_100000_300m_profile": {"size": "202752", "xon": "18432"},
                                       "pg_lossless_200000_300m_profile": {"size": "373760", "xon": "18432"}},

                # Buffer profile info
                "buffer_profiles": {"ingress_lossless_profile": {"dynamic_th": "0", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                                    "ingress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|ingress_lossy_pool]", "size": "0"},
                                    "egress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossless_pool]", "size": "0"},
                                    "egress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "4096"},
                                    "q_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "0"}}
            },
            "version_1_0_4": {
                # version 1.0.4 is introduced for:
                # 1. Supporting single ingress buffer pool for MSFT SKUs
                # 2. Updating the buffer settings
                #
                # Buffer pool migration control info
                # v1.0.3              hwsku/platform                     v1.0.4
                # spc1_t0_pool----hwsku------Mellanox-SN2700-C28D8-------spc1_t0_pool_single_pool
                #                   |
                #                   +--------Mellanox-SN2700-D48C8-------spc1_t0_pool_single_pool
                #                   |
                #                   +--------all other spc1 hwskus-------spc1_t0_pool
                #
                # spc1_t1_pool----hwsku------Mellanox-SN2700-C28D8-------spc1_t1_pool_single_pool
                #                   |
                #                   +--------Mellanox-SN2700-D48C8-------spc1_t1_pool_single_pool
                #                   |
                #                   +--------all other spc1 hwskus-------spc1_t1_pool
                #
                # spc2_3800_t0_pool--hwsku---Mellanox-SN3800-D112C8------spc2_3800_t0_pool_single_pool
                #                      |
                #                      +-----Mellanox-SN3800-C64---------spc2_3800_t0_pool_single_pool
                #                      |
                #                      +-----Mellanox-SN3800-D24C52------spc2_3800_t0_pool_single_pool
                #                      |
                #                      +-----Mellanox-SN3800-D28C50------spc2_3800_t0_pool_single_pool
                #                      |
                #                      +-----other 3800 hwskus-----------spc2_3800_t0_pool
                #
                # spc2_3800_t1_pool--hwsku---Mellanox-SN3800-D112C8------spc2_3800_t1_pool_single_pool
                #                      |
                #                      +-----Mellanox-SN3800-C64---------spc2_3800_t1_pool_single_pool
                #                      |
                #                      +-----Mellanox-SN3800-D24C52------spc2_3800_t1_pool_single_pool
                #                      |
                #                      +-----Mellanox-SN3800-D28C50------spc2_3800_t1_pool_single_pool
                #                      |
                #                      +-----other 3800 hwskus-----------spc2_3800_t1_pool
                #
                "pool_configuration_list": ["spc1_t0_pool", "spc1_t1_pool", "spc2_t0_pool", "spc2_t1_pool", "spc2_3800_t0_pool", "spc2_3800_t1_pool",
                               "spc1_t0_pool_single_pool", "spc1_t1_pool_single_pool", "spc2_3800_t0_pool_single_pool", "spc2_3800_t1_pool_single_pool"],
                "pool_mapped_from_old_version": {
                    "spc1_t0_pool": ("sku",
                                     {"Mellanox-SN2700-C28D8": "spc1_t0_pool_single_pool",
                                      "Mellanox-SN2700-D48C8": "spc1_t0_pool_single_pool"}),
                    "spc1_t1_pool": ("sku",
                                     {"Mellanox-SN2700-C28D8": "spc1_t1_pool_single_pool",
                                      "Mellanox-SN2700-D48C8": "spc1_t1_pool_single_pool"}),
                    "spc2_3800_t0_pool": ("sku",
                                          {"Mellanox-SN3800-D112C8": "spc2_3800_t0_pool_single_pool",
                                           "Mellanox-SN3800-C64": "spc2_3800_t0_pool_single_pool",
                                           "Mellanox-SN3800-D24C52": "spc2_3800_t0_pool_single_pool",
                                           "Mellanox-SN3800-D28C50": "spc2_3800_t0_pool_single_pool"}),
                    "spc2_3800_t1_pool": ("sku",
                                          {"Mellanox-SN3800-D112C8": "spc2_3800_t1_pool_single_pool",
                                           "Mellanox-SN3800-C64": "spc2_3800_t1_pool_single_pool",
                                           "Mellanox-SN3800-D24C52": "spc2_3800_t1_pool_single_pool",
                                           "Mellanox-SN3800-D28C50": "spc2_3800_t1_pool_single_pool"})
                    },

                # Buffer pool info for single pool mode
                "buffer_pool_list_single_pool" : ['ingress_lossless_pool', 'egress_lossless_pool', 'egress_lossy_pool'],
                "spc1_t0_pool_single_pool": {"ingress_lossless_pool": { "size": "10608640", "type": "ingress", "mode": "dynamic" },
                                             "egress_lossless_pool": { "size": "14024640", "type": "egress", "mode": "dynamic" },
                                             "egress_lossy_pool": {"size": "10608640", "type": "egress", "mode": "dynamic" } },
                "spc1_t1_pool_single_pool": {"ingress_lossless_pool": { "size": "7553024", "type": "ingress", "mode": "dynamic" },
                                             "egress_lossless_pool": { "size": "14024640", "type": "egress", "mode": "dynamic" },
                                             "egress_lossy_pool": {"size": "7553024", "type": "egress", "mode": "dynamic" } },

                "spc2_3800_t0_pool_single_pool": {"ingress_lossless_pool": { "size": "27598848", "type": "ingress", "mode": "dynamic" },
                                                  "egress_lossless_pool": { "size": "34340832", "type": "egress", "mode": "dynamic" },
                                                  "egress_lossy_pool": {"size": "27598848", "type": "egress", "mode": "dynamic" } },
                "spc2_3800_t1_pool_single_pool": {"ingress_lossless_pool": { "size": "20627456", "type": "ingress", "mode": "dynamic" },
                                                  "egress_lossless_pool": { "size": "34340832", "type": "egress", "mode": "dynamic" },
                                                  "egress_lossy_pool": {"size": "20627456", "type": "egress", "mode": "dynamic" } },

                "buffer_profiles_single_pool": {"ingress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                                                "ingress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                                                "egress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossless_pool]", "size": "0"},
                                                "egress_lossy_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "9216"},
                                                "q_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "0"}},

                # Buffer pool info for normal mode
                "buffer_pool_list" : ['ingress_lossless_pool', 'ingress_lossy_pool', 'egress_lossless_pool', 'egress_lossy_pool'],
                "spc1_t0_pool": {"ingress_lossless_pool": { "size": "5304320", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "5304320", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "14024640", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "5304320", "type": "egress", "mode": "dynamic" } },
                "spc1_t1_pool": {"ingress_lossless_pool": { "size": "2736128", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "2736128", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "14024640", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "2736128", "type": "egress", "mode": "dynamic" } },

                "spc2_t0_pool": {"ingress_lossless_pool": { "size": "15241216", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "15241216", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "34340832", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "15241216", "type": "egress", "mode": "dynamic" } },
                "spc2_t1_pool": {"ingress_lossless_pool": { "size": "9388032", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "9388032", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "14024640", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "9388032", "type": "egress", "mode": "dynamic" } },

                "spc2_3800_t0_pool": {"ingress_lossless_pool": { "size": "13799424", "type": "ingress", "mode": "dynamic" },
                                      "ingress_lossy_pool": { "size": "13799424", "type": "ingress", "mode": "dynamic" },
                                      "egress_lossless_pool": { "size": "34340832", "type": "egress", "mode": "dynamic" },
                                      "egress_lossy_pool": {"size": "13799424", "type": "egress", "mode": "dynamic" } },
                "spc2_3800_t1_pool": {"ingress_lossless_pool": { "size": "7946240", "type": "ingress", "mode": "dynamic" },
                                      "ingress_lossy_pool": { "size": "7946240", "type": "ingress", "mode": "dynamic" },
                                      "egress_lossless_pool": { "size": "34340832", "type": "egress", "mode": "dynamic" },
                                      "egress_lossy_pool": {"size": "7946240", "type": "egress", "mode": "dynamic" } },

                # Buffer profile info
                "buffer_profiles": {"ingress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                                    "ingress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|ingress_lossy_pool]", "size": "0"},
                                    "egress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossless_pool]", "size": "0"},
                                    "egress_lossy_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "9216"},
                                    "q_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "0"}}
            }
        }

        if table in mellanox_default_parameter[db_version].keys():
            return mellanox_default_parameter[db_version][table]
        else:
            return None

    def mlnx_migrate_buffer_pool_size(self, old_version, new_version):
        """
        v1.0.3:
        On Mellanox platform the buffer pool size changed since
        version with new SDK 4.3.3052, SONiC to SONiC update
        from version with old SDK will be broken without migration.
        This migration is specifically for Mellanox platform.
        v1.0.4:
        Single ingress buffer is supported, which also affects the
        buffer pool settings on some SKUs
        """
        buffer_pool_conf = {}
        device_data = self.configDB.get_table('DEVICE_METADATA')
        if 'localhost' in device_data.keys():
            hwsku = device_data['localhost']['hwsku']
            platform = device_data['localhost']['platform']
        else:
            log_error("Trying to get DEVICE_METADATA from DB but doesn't exist, skip migration")
            return False

        # Buffer pools defined in old version
        single_ingress_pool_skus = [
            'Mellanox-SN2700-C28D8', 'Mellanox-SN2700-D48C8',
            'Mellanox-SN3800-D112C8', 'Mellanox-SN3800-C64', 'Mellanox-SN3800-D24C52', 'Mellanox-SN3800-D28C50'
        ]
        old_buffer_pools = None
        if hwsku in single_ingress_pool_skus:
            old_buffer_pools = self.mlnx_default_buffer_parameters(old_version, "buffer_pool_list_single_pool")
        if not old_buffer_pools:
            # Two cases that old_buffer_pools is None
            # 1. It's not the single ingress pool SKU
            # 2. The old_version is 1.0.2/1.0.3 in which the single buffer hasn't been introduced
            old_buffer_pools = self.mlnx_default_buffer_parameters(old_version, "buffer_pool_list")
 
        # Try to get related info from DB
        buffer_pool_conf = self.configDB.get_table('BUFFER_POOL')

        # Get current buffer pool configuration, only migrate configuration which 
        # with default values, if it's not default, leave it as is.
        config_of_default_pools_in_db = {}
        pools_in_db = buffer_pool_conf.keys()

        # Buffer pool numbers is different with default, don't need migrate
        if len(pools_in_db) != len(old_buffer_pools):
            return True

        # If some buffer pool is not default ones, don't need migrate
        for buffer_pool in old_buffer_pools:
            if buffer_pool not in pools_in_db:
                return True
            config_of_default_pools_in_db[buffer_pool] = buffer_pool_conf[buffer_pool]

        old_pool_configuration_list = self.mlnx_default_buffer_parameters(old_version, "pool_configuration_list")
        pool_migration_control = self.mlnx_default_buffer_parameters(new_version, "pool_mapped_from_old_version")
        if not old_pool_configuration_list or not pool_migration_control:
            log_error("Trying to get pool configuration list or migration control failed, skip migration")
            return False
        new_config_name = None
        for old_pool_name in old_pool_configuration_list:
            old_config = self.mlnx_default_buffer_parameters(old_version, old_pool_name)
            log_info("Checking old pool configuration {}".format(old_pool_name))
            if config_of_default_pools_in_db == old_config:
                if old_pool_name in pool_migration_control.keys():
                    method, mapping = pool_migration_control[old_pool_name]
                    if method == "platform":
                        new_config_name = mapping.find(platform)
                    elif method == "sku":
                        new_config_name = mapping.get(hwsku)
                    else:
                        log_info("Can't find new pool configuration for {}".format(old_pool_name))
                        return False
                    if not new_config_name:
                        new_config_name = old_pool_name
                    log_info("Old buffer pool configuration {} will be migrate to {} according to {}".format(old_pool_name, new_config_name, method))
                else:
                    log_info("Old buffer pool configuration {} will be migrate to new one".format(old_pool_name))
                    new_config_name = old_pool_name
                break

        if not new_config_name:
            log_info("The configuration doesn't match any default configuration, migration for pool isn't required")
            return True

        new_buffer_pool_conf = self.mlnx_default_buffer_parameters(new_version, new_config_name)
        if not new_buffer_pool_conf:
            log_error("Can't find the buffer pool configuration for {}".format(new_config_name))
            return False

        # Migrate old buffer conf to latest.
        for pool in old_buffer_pools:
            if pool in new_buffer_pool_conf.keys():
                self.configDB.set_entry('BUFFER_POOL', pool, new_buffer_pool_conf[pool])
            else:
                self.configDB.set_entry('BUFFER_POOL', pool, None)
            log_info("Successfully migrate mlnx buffer pool size to the latest.")

        return True

    def mlnx_migrate_buffer_profile(self, old_version, new_version):
        """
        This is to migrate BUFFER_PROFILE and BUFFER_PORT_INGRESS_PROFILE_LIST tables
        to single ingress pool mode for Mellanox SKU.
        """
        device_data = self.configDB.get_table('DEVICE_METADATA')
        if 'localhost' in device_data.keys():
            hwsku = device_data['localhost']['hwsku']
            platform = device_data['localhost']['platform']
        else:
            log_error("Trying to get DEVICE_METADATA from DB but doesn't exist, skip migration")
            return False

        # SKUs that have single ingress buffer pool
        single_ingress_pool_skus = ['Mellanox-SN2700-C28D8', 'Mellanox-SN2700-D48C8', 'Mellanox-SN3800-D112C8', 'Mellanox-SN3800-C64', 'Mellanox-SN3800-D24C52', 'Mellanox-SN3800-D28C50']
        spc1_skus = ['Mellanox-SN2700-C28D8', 'Mellanox-SN2700-D48C8']

        need_migrate_buffer_profile_list = False

        # get profile 
        if hwsku in single_ingress_pool_skus:
            buffer_profile_old_configure = self.mlnx_default_buffer_parameters(old_version, "buffer_profiles_single_pool")
            if not buffer_profile_old_configure:
                # there is no single pool info in the old version
                buffer_profile_old_configure = self.mlnx_default_buffer_parameters(old_version, "buffer_profiles")
                need_migrate_buffer_profile_list = True
                buffer_port_ingress_profile_list_old = "[BUFFER_PROFILE|ingress_lossless_profile],[BUFFER_PROFILE|ingress_lossy_profile]"
                buffer_port_ingress_profile_list_new = "[BUFFER_PROFILE|ingress_lossless_profile]"
            buffer_profile_new_configure = self.mlnx_default_buffer_parameters(new_version, "buffer_profiles_single_pool")
        else:
            buffer_profile_old_configure = self.mlnx_default_buffer_parameters(old_version, "buffer_profiles")
            buffer_profile_new_configure = self.mlnx_default_buffer_parameters(new_version, "buffer_profiles")

        buffer_profile_conf = self.configDB.get_table('BUFFER_PROFILE')

        # we need to transform lossless pg profiles to new settings
        # to achieve that, we just need to remove this kind of profiles, buffermgrd will generate them automatically
        if platform == 'x86_64-mlnx_msn3800-r0':
            default_lossless_profiles = self.mlnx_default_buffer_parameters(old_version, "spc2_3800_headroom")
        elif platform in ["x86_64-mlnx_msn3700-r0", "x86_64-mlnx_msn3700c-r0"]:
            default_lossless_profiles = self.mlnx_default_buffer_parameters(old_version, "spc2_headroom")
        else:
            default_lossless_profiles = self.mlnx_default_buffer_parameters(old_version, "spc1_headroom")
        for name, profile in buffer_profile_conf.iteritems():
            if name in default_lossless_profiles.keys():
                default_profile = default_lossless_profiles[name]
                default_profile['dynamic_th'] = '0'
                default_profile['xoff'] = str(int(default_profile['size']) - int(default_profile['xon']))
                default_profile['pool'] = '[BUFFER_POOL|ingress_lossless_pool]'
                if profile == default_profile:
                    self.configDB.set_entry('BUFFER_PROFILE', name, None)

        for name, profile in buffer_profile_old_configure.iteritems():
            if name in buffer_profile_conf.keys() and profile == buffer_profile_old_configure[name]:
                continue
            # return if any default profile isn't in cofiguration
            return True

        if need_migrate_buffer_profile_list:
            buffer_port_ingress_profile_list_conf = self.configDB.get_table('BUFFER_PORT_INGRESS_PROFILE_LIST')
            for profile_list, profiles in buffer_port_ingress_profile_list_conf.iteritems():
                if profiles['profile_list'] == buffer_port_ingress_profile_list_old:
                    continue
                # return if any port's profile list isn't default
                return True

            for name in buffer_port_ingress_profile_list_conf.keys():
                self.configDB.set_entry('BUFFER_PORT_INGRESS_PROFILE_LIST', name,
                                        {'profile_list': buffer_port_ingress_profile_list_new})

        for name, profile in buffer_profile_new_configure.iteritems():
            self.configDB.set_entry('BUFFER_PROFILE', name, profile)            

    def version_unknown(self):
        """
        version_unknown tracks all SONiC versions that doesn't have a version
        string defined in config_DB.
        Nothing can be assumped when migrating from this version to the next
        version.
        Any migration operation needs to test if the DB is in expected format
        before migrating date to the next version.
        """

        log_info('Handling version_unknown')

        # NOTE: Uncomment next 3 lines of code when the migration code is in
        #       place. Note that returning specific string is intentional,
        #       here we only intended to migrade to DB version 1.0.1.
        #       If new DB version is added in the future, the incremental
        #       upgrade will take care of the subsequent migrations.
        self.migrate_pfc_wd_table()
        self.migrate_interface_table()
        self.set_version('version_1_0_2')
        return 'version_1_0_2'

    def version_1_0_1(self):
        """
        Version 1_0_1.
        """
        log_info('Handling version_1_0_1')

        self.migrate_interface_table()
        self.set_version('version_1_0_2')
        return 'version_1_0_2'

    def version_1_0_2(self):
        """
        Version 1_0_2.
        """
        log_info('Handling version_1_0_2')
        # Check ASIC type, if Mellanox platform then need DB migration
        version_info = sonic_device_util.get_sonic_version_info()
        if version_info['asic_type'] == "mellanox":
            if self.mlnx_migrate_buffer_pool_size('version_1_0_2', 'version_1_0_3'):
                self.set_version('version_1_0_3')
        else:
            self.set_version('version_1_0_3')
        return 'version_1_0_3'

    def version_1_0_3(self):
        """
        Version 1_0_3.
        """
        log_info('Handling version_1_0_3')

        # Check ASIC type, if Mellanox platform then need DB migration
        version_info = sonic_device_util.get_sonic_version_info()
        if version_info['asic_type'] == "mellanox":
            if self.mlnx_migrate_buffer_pool_size('version_1_0_3', 'version_1_0_4') and self.mlnx_migrate_buffer_profile('version_1_0_3', 'version_1_0_4'):
                self.set_version('version_1_0_4')
        else:
            self.set_version('version_1_0_4')

        return 'version_1_0_4'

    def version_1_0_4(self):
        """
        Current latest version. Nothing to do here.
        """
        log_info('Handling version_1_0_4')

    def get_version(self):
        version = self.configDB.get_entry(self.TABLE_NAME, self.TABLE_KEY)
        if version and version[self.TABLE_FIELD]:
            return version[self.TABLE_FIELD]

        return 'version_unknown'


    def set_version(self, version=None):
        if not version:
            version = self.CURRENT_VERSION
        log_info('Setting version to ' + version)
        entry = { self.TABLE_FIELD : version }
        self.configDB.set_entry(self.TABLE_NAME, self.TABLE_KEY, entry)


    def migrate(self):
        version = self.get_version()
        log_info('Upgrading from version ' + version)
        while version:
            next_version = getattr(self, version)()
            if next_version == version:
                raise Exception('Version migrate from %s stuck in same version' % version)
            version = next_version


def main():
    try:
        parser = argparse.ArgumentParser()

        parser.add_argument('-o',
                            dest='operation',
                            metavar='operation (migrate, set_version, get_version)',
                            type = str,
                            required = False,
                            choices=['migrate', 'set_version', 'get_version'],
                            help = 'operation to perform [default: get_version]',
                            default='get_version')
        parser.add_argument('-s',
                        dest='socket',
                        metavar='unix socket',
                        type = str,
                        required = False,
                        help = 'the unix socket that the desired database listens on',
                        default = None )
        parser.add_argument('-n',
                        dest='namespace',
                        metavar='asic namespace',
                        type = str,
                        required = False,
                        help = 'The asic namespace whose DB instance we need to connect',
                        default = None )
        args = parser.parse_args()
        operation = args.operation
        socket_path = args.socket
        namespace = args.namespace

        if args.namespace is not None:
            SonicDBConfig.load_sonic_global_db_config(namespace=args.namespace)

        if socket_path:
            dbmgtr = DBMigrator(namespace, socket=socket_path)
        else:
            dbmgtr = DBMigrator(namespace)

        result = getattr(dbmgtr, operation)()
        if result:
            print(str(result))

    except Exception as e:
        log_error('Caught exception: ' + str(e))
        traceback.print_exc()
        print(str(e))
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
