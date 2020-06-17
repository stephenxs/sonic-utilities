#!/usr/bin/env python

import traceback
import sys
import argparse
import syslog
import re
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
        self.CURRENT_VERSION = 'version_1_0_5'

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
        """
        mellanox_default_parameter = {
            "version_1_0_2": {
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
                                 "egress_lossy_pool": {"size": "12042240", "type": "egress", "mode": "dynamic" } }
            },
            "version_1_0_3": {
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

                # spc3 configurations are for old configuration only
                "spc3_t0_pool": {"ingress_lossless_pool": { "size": "56623104", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "56623104", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "60817392", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "56623104", "type": "egress", "mode": "dynamic" } },
                "spc3_t1_pool": {"ingress_lossless_pool": { "size": "36011952", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "36011952", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "60817392", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "36011952", "type": "egress", "mode": "dynamic" } },

                "profiles": {"ingress_lossless_profile": {"dynamic_th": "0", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                             "ingress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|ingress_lossy_pool]", "size": "0"},
                             "egress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossless_pool]", "size": "0"},
                             "egress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "4096"},
                             "q_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "0"}}
            },
            "version_1_0_4": {
                "buffer_pool_list" : ['ingress_lossless_pool', 'egress_lossless_pool', 'egress_lossy_pool'],
                "spc1_t0_pool": {"ingress_lossless_pool": { "size": "10706880", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "14024599", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "10706880", "type": "egress", "mode": "dynamic" } },
                "spc1_t1_pool": {"ingress_lossless_pool": { "size": "5570496", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "14024599", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "5570496", "type": "egress", "mode": "dynamic" } },

                "spc2_3800_t0_pool": {"ingress_lossless_pool": { "size": "28196784", "type": "ingress", "mode": "dynamic" },
                                      "egress_lossless_pool": { "size": "34340832", "type": "egress", "mode": "dynamic" },
                                      "egress_lossy_pool": {"size": "28196784", "type": "egress", "mode": "dynamic" } },
                "spc2_3800_t1_pool": {"ingress_lossless_pool": { "size": "17891280", "type": "ingress", "mode": "dynamic" },
                                      "egress_lossless_pool": { "size": "34340832", "type": "egress", "mode": "dynamic" },
                                      "egress_lossy_pool": {"size": "17891280", "type": "egress", "mode": "dynamic" } },

                "profiles": {"ingress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                             "ingress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                             "egress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossless_pool]", "size": "0"},
                             "egress_lossy_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "9216"},
                             "q_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "0"}}
            },
            "version_1_0_5": {
                "buffer_pool_list" : ['ingress_lossless_pool', 'egress_lossless_pool', 'ingress_lossy_pool', 'egress_lossy_pool'],
                "spc1_pool": {"ingress_lossless_pool": {"type": "ingress", "mode": "dynamic" },
                              "ingress_lossy_pool": { "type": "ingress", "mode": "dynamic" },
                              "egress_lossless_pool": { "size": "14024599", "type": "egress", "mode": "dynamic" },
                              "egress_lossy_pool": {"type": "egress", "mode": "dynamic" }},
                "spc2_pool": {"ingress_lossless_pool": {"type": "ingress", "mode": "dynamic" },
                              "ingress_lossy_pool": {"type": "ingress", "mode": "dynamic" },
                              "egress_lossless_pool": { "size": "34340822", "type": "egress", "mode": "dynamic" },
                              "egress_lossy_pool": {"type": "egress", "mode": "dynamic" } },
                "spc2_3800_pool": {"ingress_lossless_pool": { "type": "ingress", "mode": "dynamic" },
                                   "ingress_lossy_pool": { "type": "ingress", "mode": "dynamic" },
                                   "egress_lossless_pool": { "size": "34340832", "type": "egress", "mode": "dynamic" },
                                   "egress_lossy_pool": { "type": "egress", "mode": "dynamic" } },
                "spc3_pool": {"ingress_lossless_pool": {"type": "ingress", "mode": "dynamic" },
                              "ingress_lossy_pool": {"type": "ingress", "mode": "dynamic" },
                              "egress_lossless_pool": { "size": "60817392", "type": "egress", "mode": "dynamic" },
                              "egress_lossy_pool": {"type": "egress", "mode": "dynamic" } },

                "profiles": {"ingress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                             "ingress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|ingress_lossy_pool]", "size": "0"},
                             "egress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossless_pool]", "size": "0"},
                             "egress_lossy_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "9216"},
                             "q_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "0"}}
            }
        }

        if (db_version == "version_1_0_5"):
            keysmap = {"spc1_t0_pool": "spc1_pool", "spc1_t1_pool": "spc1_pool",
                       "spc2_t0_pool": "spc2_pool", "spc2_t1_pool": "spc2_pool",
                       "spc2_3800_t0_pool": "spc2_3800_pool", "spc2_3800_t1_pool": "spc2_3800_pool",
                       "spc3_t0_pool": "spc3_pool", "spc3_t1_pool": "spc3_pool"}
            if table in keysmap.keys():
                table = keysmap[table]

        if table in mellanox_default_parameter[db_version].keys():
            return mellanox_default_parameter[db_version][table]
        else:
            return None

    def mlnx_migrate_buffer_pool_size(self, old_version, new_version):
        """
        On Mellanox platform the buffer pool size changed since 
        version with new SDK 4.3.3052, SONiC to SONiC update 
        from version with old SDK will be broken without migration.
        This migration is specifically for Mellanox platform.
        """
        buffer_pool_conf = {}
        device_data = self.configDB.get_table('DEVICE_METADATA')
        if 'localhost' in device_data.keys():
            hwsku = device_data['localhost']['hwsku']
            platform = device_data['localhost']['platform']
        else:
            log_error("Trying to get DEVICE_METADATA from DB but doesn't exist, skip migration")
            return False

        # SKUs that have single ingress buffer pool
        single_ingress_pool_skus = ['Mellanox-SN2700-C28D8', 'Mellanox-SN2700-D48C8', 'Mellanox-SN3800-D112C8']
        if not hwsku in single_ingress_pool_skus:
            if new_version == "version_1_0_4":
                return True
            if old_version == "version_1_0_4":
                old_version = "version_1_0_3"

        # Buffer pools defined in old version
        old_buffer_pools = self.mlnx_default_buffer_parameters(old_version, "buffer_pool_list")

        # Old default buffer pool values on Mellanox platform
        spc1_t0_old_default_config = self.mlnx_default_buffer_parameters(old_version, "spc1_t0_pool")
        spc1_t1_old_default_config = self.mlnx_default_buffer_parameters(old_version, "spc1_t1_pool")
        spc2_t0_old_default_config = self.mlnx_default_buffer_parameters(old_version, "spc2_t0_pool")
        spc2_t1_old_default_config = self.mlnx_default_buffer_parameters(old_version, "spc2_t1_pool")

        # New default buffer pool configuration on Mellanox platform
        spc1_t0_new_default_config = self.mlnx_default_buffer_parameters(new_version, "spc1_t0_pool")
        spc1_t1_new_default_config = self.mlnx_default_buffer_parameters(new_version, "spc1_t1_pool")

        spc2_t0_new_default_config = self.mlnx_default_buffer_parameters(new_version, "spc2_t0_pool")
        spc2_t1_new_default_config = self.mlnx_default_buffer_parameters(new_version, "spc2_t1_pool")

        # 3800 platform has gearbox installed so the buffer pool size is different with other Spectrum2 platform
        spc2_3800_t0_new_default_config = self.mlnx_default_buffer_parameters(new_version, "spc2_3800_t0_pool")
        spc2_3800_t1_new_default_config = self.mlnx_default_buffer_parameters(new_version, "spc2_3800_t1_pool")
 
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

        # To check if the buffer pool size is equal to old default values
        new_buffer_pool_conf = None
        if config_of_default_pools_in_db == spc1_t0_old_default_config:
            new_buffer_pool_conf = spc1_t0_new_default_config
        elif config_of_default_pools_in_db == spc1_t1_old_default_config:
            new_buffer_pool_conf = spc1_t1_new_default_config
        elif config_of_default_pools_in_db == spc2_t0_old_default_config:
            if platform == 'x86_64-mlnx_msn3800-r0':
                new_buffer_pool_conf = spc2_3800_t0_new_default_config
            else:
                new_buffer_pool_conf = spc2_t0_new_default_config
        elif config_of_default_pools_in_db == spc2_t1_old_default_config:
            if platform == 'x86_64-mlnx_msn3800-r0':
                new_buffer_pool_conf = spc2_3800_t1_new_default_config
            else:
                new_buffer_pool_conf = spc2_t1_new_default_config
        else:
            spc2_3800_t0_old_default_config = self.mlnx_default_buffer_parameters(old_version, "spc2_3800_t0_pool")
            spc2_3800_t1_old_default_config = self.mlnx_default_buffer_parameters(old_version, "spc2_3800_t1_pool")
            spc3_t0_old_default_config = self.mlnx_default_buffer_parameters(old_version, "spc3_t0_pool")
            spc3_t1_old_default_config = self.mlnx_default_buffer_parameters(old_version, "spc3_t1_pool")
            spc3_t0_new_default_config = self.mlnx_default_buffer_parameters(new_version, "spc3_t0_pool")
            spc3_t1_new_default_config = self.mlnx_default_buffer_parameters(new_version, "spc3_t1_pool")
            if config_of_default_pools_in_db == spc2_3800_t0_old_default_config:
                new_buffer_pool_conf = spc2_3800_t0_new_default_config
            elif config_of_default_pools_in_db == spc2_3800_t1_old_default_config:
                new_buffer_pool_conf = spc2_3800_t1_new_default_config
            elif config_of_default_pools_in_db == spc3_t0_old_default_config:
                new_buffer_pool_conf = spc3_t0_new_default_config
            elif config_of_default_pools_in_db == spc3_t1_old_default_config:
                new_buffer_pool_conf = spc3_t1_new_default_config
            else:
                # It's not using default buffer pool configuration, no migration needed.
                log_info("buffer pool size is not old default value, no need to migrate")
                return True

        # Migrate old buffer conf to latest.
        for pool in old_buffer_pools:
            if pool in new_buffer_pool_conf.keys():
                self.configDB.set_entry('BUFFER_POOL', pool, new_buffer_pool_conf[pool])
            else:
                self.configDB.set_entry('BUFFER_POOL', pool, None)
            log_info("Successfully migrate mlnx buffer pool size to the latest.")
        return True

    def mlnx_migrate_buffer_profile(self, single_pool):
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
        single_ingress_pool_skus = ['Mellanox-SN2700-C28D8', 'Mellanox-SN2700-D48C8', 'Mellanox-SN3800-D112C8']

        if single_pool and not hwsku in single_ingress_pool_skus:
            return True

        # old buffer profile configurations
        buffer_profile_old_configure = self.mlnx_default_buffer_parameters("version_1_0_3", "profiles")
        # old port ingress buffer list configurations
        buffer_port_ingress_profile_list_old = "[BUFFER_PROFILE|ingress_lossless_profile],[BUFFER_PROFILE|ingress_lossy_profile]"

        # new buffer profile configurations
        if single_pool:
            buffer_profile_new_configure = self.mlnx_default_buffer_parameters("version_1_0_4", "profiles")
        else:
            buffer_profile_new_configure = self.mlnx_default_buffer_parameters("version_1_0_5", "profiles")
        # new port ingress buffer list configurations
        buffer_port_ingress_profile_list_new = "[BUFFER_PROFILE|ingress_lossless_profile]"

        buffer_profile_conf = self.configDB.get_table('BUFFER_PROFILE')
        for name, profile in buffer_profile_old_configure.iteritems():
            if name in buffer_profile_conf.keys() and profile == buffer_profile_old_configure[name]:
                continue
            # return if any default profile isn't in cofiguration
            return True

        for name, profile in buffer_profile_new_configure.iteritems():
            self.configDB.set_entry('BUFFER_PROFILE', name, profile)            

        if single_pool:
            buffer_port_ingress_profile_list_conf = self.configDB.get_table('BUFFER_PORT_INGRESS_PROFILE_LIST')
            for profile_list, profiles in buffer_port_ingress_profile_list_conf.iteritems():
                if profiles['profile_list'] == buffer_port_ingress_profile_list_old:
                    continue
                # return if any port's profile list isn't default
                return True

            for name in buffer_port_ingress_profile_list_conf.keys():
                self.configDB.set_entry('BUFFER_PORT_INGRESS_PROFILE_LIST', name,
                                        {'profile_list': buffer_port_ingress_profile_list_new})

        return True

    def mlnx_migrate_buffer_dynamic_calculation(self):
        """
        """
        # Migrate BUFFER_PROFILEs, removing dynamically generated profiles
        dynamic_profile = self.configDB.get_table('BUFFER_PROFILE')
        profile_pattern = 'pg_lossless_([0-9]*000)_([0-9]*m)_profile'
        speed_list = ['1000', '10000', '25000', '40000', '50000', '100000', '200000', '400000']
        cable_len_list = ['5m', '40m', '300m']
        for name, info in dynamic_profile.iteritems():
            m = re.search(profile_pattern, name)
            if not m:
                continue
            speed = m.group(1)
            cable_length = m.group(2)
            if speed in speed_list and cable_length in cable_len_list:
                self.configDB.set_entry('BUFFER_PROFILE', name, None)

        # Migrate BUFFER_PGs, removing the explicit designated profiles
        buffer_pgs = self.configDB.get_table('BUFFER_PG')
        ports = self.configDB.get_table('PORT')
        all_cable_lengths = self.configDB.get_table('CABLE_LENGTH')
        cable_lengths = all_cable_lengths[all_cable_lengths.keys()[0]]
        for name, profile in buffer_pgs.iteritems():
            port, pg = name
            if pg != '3-4':
                continue
            try:
                m = re.search(profile_pattern, profile['profile'][1:-1].split('|')[1])
            except:
                continue
            if not m:
                continue
            speed = m.group(1)
            cable_length = m.group(2)
            try:
                if speed == ports[port]["speed"] and cable_length == cable_lengths[port]:
                    self.configDB.set_entry('BUFFER_PG', name, {'NULL': 'NULL'})
            except:
                continue

        # Insert other tables required for dynamic buffer calculation
        self.configDB.set_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE', {"default_dynamic_th": "0"})
        self.configDB.set_entry('LOSSLESS_TRAFFIC_PATTERN', 'AZURE', {
                                'mtu': '1500', 'small_packet_percentage': '100'})

        return True

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
            if self.mlnx_migrate_buffer_pool_size('version_1_0_3', 'version_1_0_4') \
               and self.mlnx_migrate_buffer_profile(True):
                self.set_version('version_1_0_4')
        else:
            self.set_version('version_1_0_4')

        return 'version_1_0_4'

    def version_1_0_4(self):
        """
        Version 1_0_4
        """
        log_info('Handling version_1_0_4')

        version_info = sonic_device_util.get_sonic_version_info()
        if version_info['asic_type'] == "mellanox":
            if self.mlnx_migrate_buffer_pool_size('version_1_0_4', 'version_1_0_5') \
               and self.mlnx_migrate_buffer_profile(False) \
               and self.mlnx_migrate_buffer_dynamic_calculation():
                self.set_version('version_1_0_5')
        else:
            self.set_version('version_1_0_5')

        return 'version_1_0_5'

    def version_1_0_5(self):
        """
        Current latest version. Nothing to do here.
        """
        log_info('Handling version_1_0_5')

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
