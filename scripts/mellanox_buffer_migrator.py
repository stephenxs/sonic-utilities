from sonic_py_common import logger

SYSLOG_IDENTIFIER = 'mellanox_buffer_migrator'

# Global logger instance
log = logger.Logger(SYSLOG_IDENTIFIER)

class MellanoxBufferMigrator():
    def __init__(self, configDB):
        self.configDB = configDB

        self.platform = None
        self.sku = None

        device_data = self.configDB.get_entry('DEVICE_METADATA', 'localhost')
        if device_data:
            self.platform = device_data.get('platform')
            self.sku = device_data.get('hwsku')
        if not self.platform or not self.sku:
            log.log_error("Trying to get DEVICE_METADATA from DB but doesn't exist, skip migration")

        self.pending_update_items = list()
        self.default_speed_list = ['1000', '10000', '25000', '40000', '50000', '100000', '200000', '400000']
        self.default_cable_len_list = ['5m', '40m', '300m']
        self.is_buffer_config_default = True

    mellanox_default_parameter = {
        "version_1_0_2": {
            # Buffer pool migration control info
            "pool_configuration_list": ["spc1_t0_pool", "spc1_t1_pool", "spc2_t0_pool", "spc2_t1_pool", "spc1_t0_pool_shp", "spc1_t1_pool_shp"],

            # Buffer pool configuration info
            "buffer_pool_list" : ['ingress_lossless_pool', 'egress_lossless_pool', 'ingress_lossy_pool', 'egress_lossy_pool'],
            # default buffer pools
            "buffer_pools": {
                "spc1_t0_pool": {"ingress_lossless_pool": { "size": "4194304", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "7340032", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "16777152", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "7340032", "type": "egress", "mode": "dynamic" } },
                "spc1_t1_pool": {"ingress_lossless_pool": { "size": "2097152", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "5242880", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "16777152", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "5242880", "type": "egress", "mode": "dynamic" } },
                "spc2_t0_pool": {"doublepool": { "size": "8224768" }, "egress_lossless_pool": { "size": "35966016"}},
                "spc2_t1_pool": {"doublepool": { "size": "12042240" }, "egress_lossless_pool": { "size": "35966016"}},

                # buffer pools with shared headroom pool supported
                "spc1_t0_pool_shp": {"doublepool": { "size": "3988992" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_t1_pool_shp": {"doublepool": { "size": "4554240" }, "egress_lossless_pool": { "size": "13945824"}}
            }
        },
        "version_1_0_3": {
            # On Mellanox platform the buffer pool size changed since
            # version with new SDK 4.3.3052, SONiC to SONiC update
            # from version with old SDK will be broken without migration.
            #
            "pool_configuration_list": ["spc1_t0_pool", "spc1_t1_pool", "spc2_t0_pool", "spc2_t1_pool"],
            "pool_mapped_from_old_version": {
                "spc1_t0_pool_shp": "spc1_t0_pool",
                "spc1_t1_pool_shp": "spc1_t1_pool"
            },

            # Buffer pool configuration info
            "buffer_pool_list" : ['ingress_lossless_pool', 'egress_lossless_pool', 'ingress_lossy_pool', 'egress_lossy_pool'],
            "buffer_pools": {
                "spc1_t0_pool": {"doublepool": { "size": "5029836" }, "egress_lossless_pool": { "size": "14024599"}},
                "spc1_t1_pool": {"doublepool": { "size": "2097100" }, "egress_lossless_pool": { "size": "14024599"}},
                "spc2_t0_pool": {"doublepool": { "size": "14983147" }, "egress_lossless_pool": { "size": "34340822"}},
                "spc2_t1_pool": {"doublepool": { "size": "9158635" }, "egress_lossless_pool": { "size": "34340822"}}
            },

            "headrooms": {
                # Lossless headroom info
                "spc1_headroom": {
                    "default": {"pg_lossless_10000_5m_profile": {"size": "34816", "xon": "18432"},
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
                                "pg_lossless_100000_300m_profile": {"size": "184320", "xon": "18432"}}
                },
                "spc2_headroom": {
                    "default": {"pg_lossless_1000_5m_profile": {"size": "35840", "xon": "18432"},
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
                                "pg_lossless_200000_300m_profile": {"size": "376832", "xon": "18432"}}
                }
            },

            # Buffer profile info
            "buffer_profiles": {
                "default": {"ingress_lossless_profile": {"dynamic_th": "0", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                            "ingress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|ingress_lossy_pool]", "size": "0"},
                            "egress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossless_pool]", "size": "0"},
                            "egress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "4096"},
                            "q_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "0"}}
            }
        },
        "version_1_0_4": {
            # version 1.0.4 is introduced for updating the buffer settings
            "pool_configuration_list": ["spc1_t0_pool", "spc1_t1_pool",
                                        "spc1_2700_t0_pool", "spc1_2700_t1_pool", "spc1_2700-d48c8_t0_pool", "spc1_2700-d48c8_t1_pool",
                                        "spc2_t0_pool", "spc2_t1_pool", "spc2_3800_t0_pool", "spc2_3800_t1_pool",
                                        "spc3_t0_pool", "spc3_t1_pool"],
            # Buffer pool info for normal mode
            "buffer_pool_list" : ['ingress_lossless_pool', 'ingress_lossy_pool', 'egress_lossless_pool', 'egress_lossy_pool'],
            "buffer_pools": {
                "spc1_t0_pool": {"doublepool": { "size": "4580864" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_t1_pool": {"doublepool": { "size": "3302912" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc2_t0_pool": {"doublepool": { "size": "14542848" }, "egress_lossless_pool": { "size": "34287552"}},
                "spc2_t1_pool": {"doublepool": { "size": "11622400" }, "egress_lossless_pool": { "size": "34287552"}},

                # The following pools are used only for migrating from 1.0.4 to newer version
                "spc1_2700_t0_pool": {"singlepool": {"size": "9489408"}, "egress_lossless_pool": {"size": "13945824"}},
                "spc1_2700_t1_pool": {"singlepool": {"size": "7719936"}, "egress_lossless_pool": {"size": "13945824"}},
                "spc1_2700-d48c8_t0_pool": {"singlepool": {"size": "6687744"}, "egress_lossless_pool": {"size": "13945824"}},
                "spc1_2700-d48c8_t1_pool": {"singlepool": {"size": "8506368"}, "egress_lossless_pool": {"size": "13945824"}},

                # Buffer pool info for normal mode
                "spc2_3800_t0_pool": {"doublepool": { "size": "13924352" }, "egress_lossless_pool": { "size": "34287552" }},
                "spc2_3800_t1_pool": {"doublepool": { "size": "12457984" }, "egress_lossless_pool": { "size": "34287552" }},

                # 3800 derived SKUs

                # SPC3 is used only when migrating from 1.0.4 to newer version
                "spc3_t0_pool": {"doublepool": { "size": "26451968" }, "egress_lossless_pool": { "size": "60817392" }},
                "spc3_t1_pool": {"doublepool": { "size": "20627456" }, "egress_lossless_pool": { "size": "60817392" }}
            },

            "headrooms": {
                # Lossless headroom info
                "spc1_headroom":{
                    "default": {"pg_lossless_10000_5m_profile": {"size": "49152", "xon":"19456"},
                                "pg_lossless_25000_5m_profile": {"size": "49152", "xon":"19456"},
                                "pg_lossless_40000_5m_profile": {"size": "49152", "xon":"19456"},
                                "pg_lossless_50000_5m_profile": {"size": "49152", "xon":"19456"},
                                "pg_lossless_100000_5m_profile": {"size": "50176", "xon":"19456"},
                                "pg_lossless_10000_40m_profile": {"size": "49152", "xon":"19456"},
                                "pg_lossless_25000_40m_profile": {"size": "51200", "xon":"19456"},
                                "pg_lossless_40000_40m_profile": {"size": "52224", "xon":"19456"},
                                "pg_lossless_50000_40m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_100000_40m_profile": {"size": "58368", "xon":"19456"},
                                "pg_lossless_10000_300m_profile": {"size": "56320", "xon":"19456"},
                                "pg_lossless_25000_300m_profile": {"size": "67584", "xon":"19456"},
                                "pg_lossless_40000_300m_profile": {"size": "78848", "xon":"19456"},
                                "pg_lossless_50000_300m_profile": {"size": "86016", "xon":"19456"},
                                "pg_lossless_100000_300m_profile": {"size": "123904", "xon":"19456"}},
                    # lossless headroom info for MSFT SKUs.
                    "msft": {"pg_lossless_10000_5m_profile": {"size": "41984", "xon":"19456"},
                             "pg_lossless_25000_5m_profile": {"size": "41984", "xon":"19456"},
                             "pg_lossless_40000_5m_profile": {"size": "41984", "xon":"19456"},
                             "pg_lossless_50000_5m_profile": {"size": "41984", "xon":"19456"},
                             "pg_lossless_100000_5m_profile": {"size": "43008", "xon":"19456"},
                             "pg_lossless_10000_40m_profile": {"size": "41984", "xon":"19456"},
                             "pg_lossless_25000_40m_profile": {"size": "44032", "xon":"19456"},
                             "pg_lossless_40000_40m_profile": {"size": "45056", "xon":"19456"},
                             "pg_lossless_50000_40m_profile": {"size": "45056", "xon":"19456"},
                             "pg_lossless_100000_40m_profile": {"size": "49152", "xon":"19456"},
                             "pg_lossless_10000_300m_profile": {"size": "47104", "xon":"19456"},
                             "pg_lossless_25000_300m_profile": {"size": "56320", "xon":"19456"},
                             "pg_lossless_40000_300m_profile": {"size": "64512", "xon":"19456"},
                             "pg_lossless_50000_300m_profile": {"size": "69632", "xon":"19456"},
                             "pg_lossless_100000_300m_profile": {"size": "98304", "xon":"19456"}}
                },
                "spc2_headroom": {
                    "default": {"pg_lossless_10000_5m_profile": {"size": "52224", "xon":"19456"},
                                "pg_lossless_25000_5m_profile": {"size": "52224", "xon":"19456"},
                                "pg_lossless_40000_5m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_50000_5m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_100000_5m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_200000_5m_profile": {"size": "55296", "xon":"19456"},
                                "pg_lossless_10000_40m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_25000_40m_profile": {"size": "55296", "xon":"19456"},
                                "pg_lossless_40000_40m_profile": {"size": "57344", "xon":"19456"},
                                "pg_lossless_50000_40m_profile": {"size": "58368", "xon":"19456"},
                                "pg_lossless_100000_40m_profile": {"size": "63488", "xon":"19456"},
                                "pg_lossless_200000_40m_profile": {"size": "74752", "xon":"19456"},
                                "pg_lossless_10000_300m_profile": {"size": "60416", "xon":"19456"},
                                "pg_lossless_25000_300m_profile": {"size": "73728", "xon":"19456"},
                                "pg_lossless_40000_300m_profile": {"size": "86016", "xon":"19456"},
                                "pg_lossless_50000_300m_profile": {"size": "95232", "xon":"19456"},
                                "pg_lossless_100000_300m_profile": {"size": "137216", "xon":"19456"},
                                "pg_lossless_200000_300m_profile": {"size": "223232", "xon":"19456"}}
                },
                "spc3_headroom": {
                    "default": {"pg_lossless_10000_5m_profile": {"size": "52224", "xon":"19456"},
                                "pg_lossless_25000_5m_profile": {"size": "52224", "xon":"19456"},
                                "pg_lossless_40000_5m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_50000_5m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_100000_5m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_200000_5m_profile": {"size": "55296", "xon":"19456"},
                                "pg_lossless_400000_5m_profile": {"size": "86016", "xon":"37888"},
                                "pg_lossless_10000_40m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_25000_40m_profile": {"size": "55296", "xon":"19456"},
                                "pg_lossless_40000_40m_profile": {"size": "57344", "xon":"19456"},
                                "pg_lossless_50000_40m_profile": {"size": "58368", "xon":"19456"},
                                "pg_lossless_100000_40m_profile": {"size": "63488", "xon":"19456"},
                                "pg_lossless_200000_40m_profile": {"size": "74752", "xon":"19456"},
                                "pg_lossless_400000_40m_profile": {"size": "124928", "xon":"37888"},
                                "pg_lossless_10000_300m_profile": {"size": "60416", "xon":"19456"},
                                "pg_lossless_25000_300m_profile": {"size": "73728", "xon":"19456"},
                                "pg_lossless_40000_300m_profile": {"size": "86016", "xon":"19456"},
                                "pg_lossless_50000_300m_profile": {"size": "95232", "xon":"19456"},
                                "pg_lossless_100000_300m_profile": {"size": "137216", "xon":"19456"},
                                "pg_lossless_200000_300m_profile": {"size": "223232", "xon":"19456"},
                                "pg_lossless_400000_300m_profile": {"size": "420864", "xon":"37888"}}
                }
            },

            # Buffer profile info
            "buffer_profiles": {
                "default": {"ingress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                               "ingress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|ingress_lossy_pool]", "size": "0"},
                               "egress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossless_pool]", "size": "0"},
                               "egress_lossy_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "9216"},
                               "q_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "0"}},
                "singlepool": {"ingress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                               "ingress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                               "egress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossless_pool]", "size": "0"},
                               "egress_lossy_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "9216"},
                               "q_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "0"}}
            }
        },
        "version_1_0_5": {
            # version 1.0.4 is introduced for updating the buffer settings
            "pool_configuration_list": ["spc1_t0_pool", "spc1_t1_pool", "spc2_t0_pool", "spc2_t1_pool", "spc2_3800_t0_pool", "spc2_3800_t1_pool"],
            "pool_convert_map": {
                "spc1_t0_pool_sku_map": {"Mellanox-SN2700-C28D8": "spc1_2700_t0_pool_shp",
                                         "Mellanox-SN2700-D48C8": "spc1_2700-d48c8_t0_pool_shp",
                                         "Mellanox-SN2700": "spc1_2700_t0_pool_shp"},
                "spc1_t1_pool_sku_map": {"Mellanox-SN2700-C28D8": "spc1_2700_t1_pool_shp",
                                         "Mellanox-SN2700-D48C8": "spc1_2700-d48c8_t1_pool_shp",
                                         "Mellanox-SN2700": "spc1_2700_t1_pool_shp"},
                "spc2_3800_t0_pool_sku_map": {"Mellanox-SN3800-C64": "spc2_3800-c64_t0_pool_shp",
                                              "Mellanox-SN3800-D112C8": "spc2_3800-d112c8_t0_pool_shp",
                                              "Mellanox-SN3800-D24C52": "spc2_3800-d24c52_t0_pool_shp",
                                              "Mellanox-SN3800-D28C50": "spc2_3800-d28c50_t0_pool_shp"},
                "spc2_3800_t1_pool_sku_map": {"Mellanox-SN3800-C64": "spc2_3800-c64_t1_pool_shp",
                                              "Mellanox-SN3800-D112C8": "spc2_3800-d112c8_t1_pool_shp",
                                              "Mellanox-SN3800-D24C52": "spc2_3800-d24c52_t1_pool_shp",
                                              "Mellanox-SN3800-D28C50": "spc2_3800-d28c50_t1_pool_shp"}
            },
            "pool_mapped_from_old_version": {
                # MSFT SKUs and generic SKUs may have different pool seetings
                "spc1_t0_pool": ("sku", "spc1_t0_pool_sku_map"),
                "spc1_t1_pool": ("sku", "spc1_t1_pool_sku_map"),
                "spc1_2700_t0_pool": "spc1_2700_t0_single_pool_shp",
                "spc1_2700_t1_pool": "spc1_2700_t1_single_pool_shp",
                "spc1_2700-d48c8_t0_pool": "spc1_2700-d48c8_t0_single_pool_shp",
                "spc1_2700-d48c8_t1_pool": "spc1_2700-d48c8_t1_single_pool_shp"
            },

            # Buffer pool info for normal mode
            "buffer_pool_list" : ['ingress_lossless_pool', 'ingress_lossy_pool', 'egress_lossless_pool', 'egress_lossy_pool'],

            "buffer_pools": {
                "spc1_t0_pool": {"doublepool": { "size": "4580864" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_t1_pool": {"doublepool": { "size": "3302912" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc2_t0_pool": {"doublepool": { "size": "14542848" }, "egress_lossless_pool": { "size": "34287552"}},
                "spc2_t1_pool": {"doublepool": { "size": "11622400" }, "egress_lossless_pool": { "size": "34287552"}},

                "spc1_2700_t0_pool_shp": {"doublepool": { "size": "5088768", "xoff": "688128" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_2700_t1_pool_shp": {"doublepool": { "size": "4646400", "xoff": "1572864" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_2700-d48c8_t0_pool_shp": {"doublepool": { "size": "3859968", "xoff": "1032192" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_2700-d48c8_t1_pool_shp": {"doublepool": { "size": "4843008", "xoff": "1179648" }, "egress_lossless_pool": { "size": "13945824"}},

                # Buffer pool for single pool
                "spc1_2700_t0_single_pool_shp": {"singlepool": { "size": "10177536", "xoff": "688128" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_2700_t1_single_pool_shp": {"singlepool": { "size": "9292800", "xoff": "1572864" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_2700-d48c8_t0_single_pool_shp": {"singlepool": { "size": "7719936", "xoff": "1032192" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_2700-d48c8_t1_single_pool_shp": {"singlepool": { "size": "9686016", "xoff": "1179648" }, "egress_lossless_pool": { "size": "13945824"}},

                # The following pools are used for upgrading from 1.0.5 to the newer version
                "spc2_3800-c64_t0_pool_shp": {"singlepool": {"size": "25866240", "xoff": "2523136"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-c64_t1_pool_shp": {"singlepool": {"size": "23900160", "xoff": "4489216"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-d112c8_t0_pool_shp": {"singlepool": {"size": "20017152", "xoff": "3440640"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-d112c8_t1_pool_shp": {"singlepool": {"size": "19124224", "xoff": "4333568"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-d24c52_t0_pool_shp": {"singlepool": {"size": "24576000", "xoff": "2756608"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-d24c52_t1_pool_shp": {"singlepool": {"size": "22597632", "xoff": "4734976"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-d28c50_t0_pool_shp": {"singlepool": {"size": "24360960", "xoff": "2795520"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-d28c50_t1_pool_shp": {"singlepool": {"size": "22380544", "xoff": "4775936"}, "egress_lossless_pool": {"size": "34287552"}},

                "spc2_3800_t0_pool": {"doublepool": { "size": "13924352" }, "egress_lossless_pool": { "size": "34287552"}},
                "spc2_3800_t1_pool": {"doublepool": { "size": "12457984" }, "egress_lossless_pool": { "size": "34287552"}},
                "spc3_t0_pool": {"doublepool": { "size": "26451968" }, "egress_lossless_pool": { "size": "60817392"}},
                "spc3_t1_pool": {"doublepool": { "size": "20627456" }, "egress_lossless_pool": { "size": "60817392"}}
            },

            "headrooms": {
                "mapping": {
                    "msft": "shp",
                    "default": ("skumap", {"Mellanox-SN2700": "shp", "Mellanox-SN2700-C28D8": "shp", "Mellanox-SN2700-D48C8": "shp"})
                },
                "spc1_headroom": {
                    "default": ("version_1_0_4", "spc1_headroom"),
                    "shp": {"pg_lossless_10000_5m_profile": {"xoff": "22528", "xon":"19456"},
                            "pg_lossless_25000_5m_profile": {"xoff": "22528", "xon":"19456"},
                            "pg_lossless_40000_5m_profile": {"xoff": "22528", "xon":"19456"},
                            "pg_lossless_50000_5m_profile": {"xoff": "22528", "xon":"19456"},
                            "pg_lossless_100000_5m_profile": {"xoff": "23552", "xon":"19456"},
                            "pg_lossless_10000_40m_profile": {"xoff": "22528", "xon":"19456"},
                            "pg_lossless_25000_40m_profile": {"xoff": "24576", "xon":"19456"},
                            "pg_lossless_40000_40m_profile": {"xoff": "25600", "xon":"19456"},
                            "pg_lossless_50000_40m_profile": {"xoff": "25600", "xon":"19456"},
                            "pg_lossless_100000_40m_profile": {"xoff": "29696", "xon":"19456"},
                            "pg_lossless_10000_300m_profile": {"xoff": "27648", "xon":"19456"},
                            "pg_lossless_25000_300m_profile": {"xoff": "36864", "xon":"19456"},
                            "pg_lossless_40000_300m_profile": {"xoff": "45056", "xon":"19456"},
                            "pg_lossless_50000_300m_profile": {"xoff": "50176", "xon":"19456"},
                            "pg_lossless_100000_300m_profile": {"xoff": "78848", "xon":"19456"}}
                },
                "spc2_3800_headroom": {
                    "default": {"pg_lossless_10000_5m_profile": {"size": "54272", "xon":"19456"},
                                "pg_lossless_25000_5m_profile": {"size": "58368", "xon":"19456"},
                                "pg_lossless_40000_5m_profile": {"size": "61440", "xon":"19456"},
                                "pg_lossless_50000_5m_profile": {"size": "64512", "xon":"19456"},
                                "pg_lossless_100000_5m_profile": {"size": "75776", "xon":"19456"},
                                "pg_lossless_10000_40m_profile": {"size": "55296", "xon":"19456"},
                                "pg_lossless_25000_40m_profile": {"size": "60416", "xon":"19456"},
                                "pg_lossless_40000_40m_profile": {"size": "65536", "xon":"19456"},
                                "pg_lossless_50000_40m_profile": {"size": "69632", "xon":"19456"},
                                "pg_lossless_100000_40m_profile": {"size": "86016", "xon":"19456"},
                                "pg_lossless_10000_300m_profile": {"size": "63488", "xon":"19456"},
                                "pg_lossless_25000_300m_profile": {"size": "78848", "xon":"19456"},
                                "pg_lossless_40000_300m_profile": {"size": "95232", "xon":"19456"},
                                "pg_lossless_50000_300m_profile": {"size": "106496", "xon":"19456"},
                                "pg_lossless_100000_300m_profile": {"size": "159744", "xon":"19456"}},
                    "shp": {"pg_lossless_10000_5m_profile": {"xoff": "25600", "xon":"19456"},
                            "pg_lossless_25000_5m_profile": {"xoff": "28672", "xon":"19456"},
                            "pg_lossless_40000_5m_profile": {"xoff": "30720", "xon":"19456"},
                            "pg_lossless_50000_5m_profile": {"xoff": "32768", "xon":"19456"},
                            "pg_lossless_100000_5m_profile": {"xoff": "40960", "xon":"19456"},
                            "pg_lossless_10000_40m_profile": {"xoff": "26624", "xon":"19456"},
                            "pg_lossless_25000_40m_profile": {"xoff": "30720", "xon":"19456"},
                            "pg_lossless_40000_40m_profile": {"xoff": "33792", "xon":"19456"},
                            "pg_lossless_50000_40m_profile": {"xoff": "36864", "xon":"19456"},
                            "pg_lossless_100000_40m_profile": {"xoff": "48128", "xon":"19456"},
                            "pg_lossless_10000_300m_profile": {"xoff": "31744", "xon":"19456"},
                            "pg_lossless_25000_300m_profile": {"xoff": "44032", "xon":"19456"},
                            "pg_lossless_40000_300m_profile": {"xoff": "55296", "xon":"19456"},
                            "pg_lossless_50000_300m_profile": {"xoff": "63488", "xon":"19456"},
                            "pg_lossless_100000_300m_profile": {"xoff": "102400", "xon":"19456"}}
                }
            }
        },
        "version_2_0_0": {
            # version 2.0.0 is introduced for dynamic buffer calculation
            #
            "pool_configuration_list": ["spc1_pool", "spc2_pool", "spc3_pool"],
            "pool_mapped_from_old_version": {
                "spc1_t0_pool": "spc1_pool",
                "spc1_t1_pool": "spc1_pool",
                "spc2_t0_pool": "spc2_pool",
                "spc2_t1_pool": "spc2_pool",
                "spc2_3800_t0_pool": "spc2_pool",
                "spc2_3800_t1_pool": "spc2_pool",
                "spc3_t0_pool": "spc3_pool",
                "spc3_t1_pool": "spc3_pool"
            },

            # Buffer pool info for normal mode
            "buffer_pool_list" : ['ingress_lossless_pool', 'ingress_lossy_pool', 'egress_lossless_pool', 'egress_lossy_pool'],
            "buffer_pools": {
                "spc1_pool": {"ingress_lossless_pool": { "type": "ingress", "mode": "dynamic" },
                              "ingress_lossy_pool": { "type": "ingress", "mode": "dynamic" },
                              "egress_lossless_pool": { "size": "13945824", "type": "egress", "mode": "dynamic" },
                              "egress_lossy_pool": {"type": "egress", "mode": "dynamic" } },
                "spc2_pool": {"ingress_lossless_pool": { "type": "ingress", "mode": "dynamic" },
                              "ingress_lossy_pool": { "type": "ingress", "mode": "dynamic" },
                              "egress_lossless_pool": { "size": "34287552", "type": "egress", "mode": "dynamic" },
                              "egress_lossy_pool": { "type": "egress", "mode": "dynamic" } },
                "spc3_pool": {"ingress_lossless_pool": { "type": "ingress", "mode": "dynamic" },
                              "ingress_lossy_pool": { "type": "ingress", "mode": "dynamic" },
                              "egress_lossless_pool": { "size": "60817392", "type": "egress", "mode": "dynamic" },
                              "egress_lossy_pool": {"type": "egress", "mode": "dynamic" } }
            }
        }
    }

    def mlnx_default_buffer_parameters(self, db_version, table):
        """
        We extract buffer configurations to a common function
        so that it can be reused among different migration
        The logic of buffer parameters migrating:
        1. Compare the current buffer configuration with the default settings
        2. If there is a match, migrate the old value to the new one
        3. Insert the new setting into database
        Each settings defined below (except that for version_1_0_2) will be used twice:
        1. It is referenced as new setting when database is migrated to that version
        2. It is referenced as old setting when database is migrated from that version
        """

        return self.mellanox_default_parameter[db_version].get(table)

    def mlnx_migrate_map_old_pool_to_new(self, pool_mapping, pool_convert_map, old_config_name):
        new_config_name = None
        if pool_mapping:
            new_config_map = pool_mapping.get(old_config_name)
            if type(new_config_map) is tuple:
                method, mapname = new_config_map
                if method == "sku":
                    skumap = pool_convert_map.get(mapname)
                    new_config_name = skumap.get(self.sku)
                else:
                    log.log_info("Unsupported mapping method {} found. Stop db_migrator".format(method))
                    return False
            else:
                new_config_name = new_config_map
        return new_config_name

    def mlnx_migrate_extend_condensed_pool(self, pool_config, config_name = None):
        condensedpool = pool_config.get("doublepool")
        doublepool = False
        if not condensedpool:
            condensedpool = pool_config.get("singlepool")
            if condensedpool:
                pool_config.pop("singlepool")
            else:
                log.log_info("Got old default pool configuration {} {}".format(config_name, pool_config))
        else:
            pool_config.pop("doublepool")
            doublepool = True

        if condensedpool:
            xoff = condensedpool.get('xoff')
            if xoff:
                condensedpool.pop('xoff')
            log.log_info("condensed pool {}".format(condensedpool))
            condensedpool['type'] = 'egress'
            condensedpool['mode'] = 'dynamic'
            pool_config['egress_lossy_pool'] = {}
            pool_config['egress_lossy_pool'].update(condensedpool)

            pool_config['egress_lossless_pool']['type'] = 'egress'
            pool_config['egress_lossless_pool']['mode'] = 'dynamic'

            condensedpool['type'] = 'ingress'
            pool_config['ingress_lossless_pool'] = {}
            pool_config['ingress_lossless_pool'].update(condensedpool)

            if doublepool:
                pool_config['ingress_lossy_pool'] = {}
                pool_config['ingress_lossy_pool'].update(condensedpool)

            if xoff:
                pool_config['ingress_lossless_pool']['xoff'] = xoff

            log.log_info("Initialize condensed buffer pool: {}".format(pool_config))

    def mlnx_migrate_get_headroom_profiles(self, headroom_profile_set):
        if type(headroom_profile_set) is tuple:
            version, key = headroom_profile_set
            result = self.mlnx_default_buffer_parameters(version, "headrooms")[key]["default"]
        elif type(headroom_profile_set) is dict:
            result = headroom_profile_set

        return result

    def mlnx_migrate_extend_headroom_profile(self, headroom_profile):
        headroom_profile['dynamic_th'] = '0'
        if not 'xoff' in headroom_profile.keys():
            headroom_profile['xoff'] = str(int(headroom_profile['size']) - int(headroom_profile['xon']))
        elif not 'size' in headroom_profile.keys():
            headroom_profile['size'] = headroom_profile['xon']
        headroom_profile['pool'] = '[BUFFER_POOL|ingress_lossless_pool]'

        return headroom_profile

    def mlnx_migrate_buffer_pool_size(self, old_version, new_version):
        """
        To migrate buffer pool configuration
        """
        self.is_buffer_config_default = False
        buffer_pool_conf_in_db = {}

        # Buffer pools defined in old version
        default_buffer_pool_list_old = self.mlnx_default_buffer_parameters(old_version, "buffer_pool_list")

        # Try to get related info from DB
        configdb_buffer_pools = self.configDB.get_table('BUFFER_POOL')

        # Get current buffer pool configuration, only migrate configuration which
        # with default values, if it's not default, leave it as is.
        configdb_buffer_pool_names = configdb_buffer_pools.keys()

        # Buffer pool numbers is different from default, we don't need to migrate it
        if len(configdb_buffer_pool_names) > len(default_buffer_pool_list_old):
            log.log_notice("Pools in CONFIG_DB ({}) don't match default ({}), skip buffer pool migration".format(configdb_buffer_pool_names, default_buffer_pool_list_old))
            return True

        # If some buffer pool is not default ones, don't need migrate
        for buffer_pool in default_buffer_pool_list_old:
            if buffer_pool not in configdb_buffer_pool_names and buffer_pool != 'ingress_lossy_pool':
                log.log_notice("Default pool {} isn't in CONFIG_DB, skip buffer pool migration".format(buffer_pool))
                return True

        default_pool_conf_list_old = self.mlnx_default_buffer_parameters(old_version, "pool_configuration_list")
        if not default_pool_conf_list_old:
            log.log_error("Trying to get pool configuration list or migration control failed, skip migration")
            return False

        new_config_name = None
        pool_mapping = self.mlnx_default_buffer_parameters(new_version, "pool_mapped_from_old_version")
        pool_convert_map = self.mlnx_default_buffer_parameters(new_version, "pool_convert_map")
        log.log_info("got old configuration {}".format(configdb_buffer_pools))
        default_buffer_pools_old = self.mlnx_default_buffer_parameters(old_version, "buffer_pools")
        for old_config_name in default_pool_conf_list_old:
            old_config = default_buffer_pools_old[old_config_name]
            self.mlnx_migrate_extend_condensed_pool(old_config, old_config_name)

            log.log_info("Checking old pool configuration {} {}".format(old_config_name, old_config))
            if configdb_buffer_pools == old_config:
                new_config_name = self.mlnx_migrate_map_old_pool_to_new(pool_mapping, pool_convert_map, old_config_name)
                if not new_config_name:
                    new_config_name = old_config_name
                log.log_info("Old buffer pool configuration {} will be migrate to new one {}".format(old_config_name, new_config_name))
                break

        if not new_config_name:
            log.log_notice("The configuration doesn't match any default configuration, migration for pool isn't required")
            return True

        default_buffer_pools_new = self.mlnx_default_buffer_parameters(new_version, "buffer_pools")
        new_buffer_pool_conf = default_buffer_pools_new.get(new_config_name)
        if not new_buffer_pool_conf:
            log.log_error("Can't find the buffer pool configuration for {} in {}".format(new_config_name, new_version))
            return False

        self.mlnx_migrate_extend_condensed_pool(new_buffer_pool_conf, new_config_name)

        # Migrate old buffer conf to latest.
        for pool in configdb_buffer_pools:
            self.pending_update_items.append(('BUFFER_POOL', pool, None))
        for pool in new_buffer_pool_conf:
            self.pending_update_items.append(('BUFFER_POOL', pool, new_buffer_pool_conf.get(pool)))

        self.is_buffer_config_default = True

        return True

    def mlnx_get_buffer_profile_key(self):
        spc1_platforms = ["x86_64-mlnx_msn2010-r0", "x86_64-mlnx_msn2100-r0", "x86_64-mlnx_msn2410-r0", "x86_64-mlnx_msn2700-r0", "x86_64-mlnx_msn2740-r0"]
        spc2_platforms = ["x86_64-mlnx_msn3700-r0", "x86_64-mlnx_msn3700c-r0"]
        spc2_platform_with_gearbox = ['x86_64-mlnx_msn3800-r0']
        spc3_platforms = ["x86_64-mlnx_msn4600c-r0", "x86_64-mlnx_msn4700-r0"]

        if self.platform in spc2_platform_with_gearbox:
            return "spc2_3800_headroom"
        elif self.platform in spc3_platforms:
            return "spc3_headroom"
        elif self.platform in spc2_platforms:
            return "spc2_headroom"
        elif self.platform in spc1_platforms:
            return "spc1_headroom"

        return None

    def mlnx_migrate_buffer_profile(self, old_version, new_version):
        """
        This is to migrate BUFFER_PROFILE configuration
        """
        if not self.is_buffer_config_default:
            return True
        else:
            self.is_buffer_config_default = False

        spc1_platforms = ["x86_64-mlnx_msn2010-r0", "x86_64-mlnx_msn2100-r0", "x86_64-mlnx_msn2410-r0", "x86_64-mlnx_msn2700-r0", "x86_64-mlnx_msn2740-r0"]
        spc2_platforms = ["x86_64-mlnx_msn3700-r0", "x86_64-mlnx_msn3700c-r0"]

        # get profile
        default_buffer_profiles_old = self.mlnx_default_buffer_parameters(old_version, "buffer_profiles")
        default_buffer_profiles_new = self.mlnx_default_buffer_parameters(new_version, "buffer_profiles")

        configdb_buffer_profiles = self.configDB.get_table('BUFFER_PROFILE')

        # we need to transform lossless pg profiles to new settings
        # to achieve that, we just need to remove this kind of profiles, buffermgrd will generate them automatically
        default_headroom_sets_old = self.mlnx_default_buffer_parameters(old_version, "headrooms")
        default_headroom_sets_new = self.mlnx_default_buffer_parameters(new_version, "headrooms")
        default_headrooms_old = None
        default_headrooms_new = None
        if default_headroom_sets_old and default_headroom_sets_new:
            if self.platform == 'x86_64-mlnx_msn3800-r0':
                default_headrooms_old = default_headroom_sets_old.get("spc2_3800_headroom")
                default_headrooms_new = default_headroom_sets_new.get("spc2_3800_headroom")
            elif self.platform in spc2_platforms:
                default_headrooms_old = default_headroom_sets_old.get("spc2_headroom")
                default_headrooms_new = default_headroom_sets_new.get("spc2_headroom")
            elif self.platform in spc1_platforms:
                default_headrooms_old = default_headroom_sets_old.get("spc1_headroom")
                default_headrooms_new = default_headroom_sets_new.get("spc1_headroom")

        if default_headrooms_old and default_headrooms_new:
            # match the old lossless profiles?
            for headroom_set_name, lossless_profiles in default_headrooms_old.iteritems():
                if headroom_set_name == "mapping":
                    continue
                lossless_profiles = self.mlnx_migrate_get_headroom_profiles(lossless_profiles)
                matched = True
                for name, profile in configdb_buffer_profiles.iteritems():
                    if name in lossless_profiles.keys():
                        default_profile = self.mlnx_migrate_extend_headroom_profile(lossless_profiles.get(name))
                        if profile != default_profile:
                            log.log_info("Skip headroom profile set {} due to {} mismatched: {} vs {}".format(
                                headroom_set_name, name, default_profile, profile))
                            matched = False
                            break
                if matched:
                    mapping = default_headroom_sets_new.get("mapping")
                    if not mapping:
                        new_headroom_set_name = headroom_set_name
                        log.log_info("Migrate profile set {} ".format(headroom_set_name))
                    else:
                        new_headroom_set_name = mapping.get(headroom_set_name)
                        if type(new_headroom_set_name) is tuple:
                            log.log_info("Use headroom profiles map {}".format(mapping))
                            maptype, mapping = new_headroom_set_name
                            if maptype == "skumap":
                                new_headroom_set_name = mapping.get(self.sku)
                        if not new_headroom_set_name:
                            new_headroom_set_name = headroom_set_name
                    log.log_info("{} has been mapped to {} according to sku".format(headroom_set_name, new_headroom_set_name))
                    break

            if not matched:
                log.log_notice("Headroom profiles don't match any of the default value, skip migrating")
                return True

            default_headrooms_new = default_headrooms_new.get(new_headroom_set_name)
            if type(default_headrooms_new) is dict:
                for name, profile in configdb_buffer_profiles.iteritems():
                    if name in default_headrooms_new.keys():
                        default_profile = self.mlnx_migrate_extend_headroom_profile(default_headrooms_new.get(name))
                        self.pending_update_items.append(('BUFFER_PROFILE', name, default_profile))
                        log.log_info("Profile {} has been migrated to {}".format(name, default_profile))

        self.is_buffer_config_default = True

        if not default_buffer_profiles_new:
            # Not providing new profile configure in new version means they do need to be changed
            log.log_notice("No buffer profile in {}, don't need to migrate non-lossless profiles".format(new_version))
            return True

        profile_matched = True
        for _, profiles in default_buffer_profiles_old.iteritems():
            for name, profile in profiles.iteritems():
                if name in configdb_buffer_profiles.keys() and profile == configdb_buffer_profiles[name]:
                    continue
                # return if any default profile isn't in cofiguration
                profile_matched = False
                break

        if not profile_matched:
            log.log_notice("Profiles doesn't match default value".format(name))
            return True

        for name, profile in default_buffer_profiles_new["default"].iteritems():
            log.log_info("Successfully migrate profile {}".format(name))
            self.pending_update_items.append(('BUFFER_PROFILE', name, profile))
        return True

    def mlnx_append_item_on_pending_configuration_list(self, item):
        self.pending_update_items.append(item)

    def mlnx_abandon_pending_buffer_configuration(self):
        """
        We found the buffer configuration on the device doesn't match the default one, so no migration performed
        Clear pending update item list in this case
        """
        self.pending_update_items = []
        self.is_buffer_config_default = False

    def mlnx_flush_new_buffer_configuration(self):
        """
        Flush all the pending items to config database
        """
        if not self.is_buffer_config_default:
            log.log_notice("No item pending to be updated")
            metadata = self.configDB.get_entry('DEVICE_METADATA', 'localhost')
            metadata['buffer_model'] = 'traditional'
            self.configDB.set_entry('DEVICE_METADATA', 'localhost', metadata)
            log.log_notice("Set buffer_model as traditional")
            return True

        for item in self.pending_update_items:
            table, key, value = item
            self.configDB.set_entry(table, key, value)
            if value:
                log.log_notice("Successfully migrate {} {} to {}".format(table, key, value))
            else:
                log.log_notice("Successfully remove {} {} which is no longer used".format(table, key))

        return True

    def mlnx_get_default_lossless_profile(self, db_version):
        platform_key = self.mlnx_get_buffer_profile_key()
        if not platform_key:
            return None

        headrooms = self.mlnx_default_buffer_parameters(db_version, 'headrooms').get(platform_key)
        default_profiles = headrooms.get('default')
        return self.mlnx_migrate_get_headroom_profiles(default_profiles)
