import click
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from sonic_py_common import multi_asic
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector

#
# 'config fabric ...'
#
@click.group(cls=clicommon.AbbreviationGroup)
def fabric():
    """FABRIC-related configuration tasks"""
    pass

#
# 'config fabric port ...'
#
@fabric.group(cls=clicommon.AbbreviationGroup)
def port():
    """FABRIC PORT configuration tasks"""
    pass

#
# 'config fabric port isolate <portid> [ -n <asic> ]'
#
@port.command()
@click.argument('portid', metavar='<portid>', required=True)
@multi_asic_util.multi_asic_click_option_namespace
def isolate(portid, namespace):
    """FABRIC PORT isolate <portid>"""

    ctx = click.get_current_context()

    if not portid.isdigit():
        ctx.fail("Invalid portid")

    n_asics = multi_asic.get_num_asics()
    if n_asics > 1 and namespace is None:
        ctx.fail('Must specify asic')

    # Connect to config database
    config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
    config_db.connect()

    # Connect to state database
    state_db = SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
    state_db.connect(state_db.STATE_DB, False)

    # check if the port is actually in use
    portName = f'PORT{portid}'
    portStateData = state_db.get_all(state_db.STATE_DB, "FABRIC_PORT_TABLE|" + portName)
    if "REMOTE_PORT" not in portStateData:
        ctx.fail(f"Port {portid} is not in use")

    # Make sure configuration data exists
    portName = f'Fabric{portid}'
    portConfigData = config_db.get_all(config_db.CONFIG_DB, "FABRIC_PORT|" + portName)
    if not bool(portConfigData):
        ctx.fail("Fabric monitor configuration data not present")

    # Update entry
    config_db.mod_entry("FABRIC_PORT", portName, {'isolateStatus': True})

#
# 'config fabric port unisolate <portid> [ -n <asic> ]'
#
@port.command()
@click.argument('portid', metavar='<portid>', required=True)
@multi_asic_util.multi_asic_click_option_namespace
def unisolate(portid, namespace):
    """FABRIC PORT unisolate <portid>"""

    ctx = click.get_current_context()

    if not portid.isdigit():
        ctx.fail("Invalid portid")

    n_asics = multi_asic.get_num_asics()
    if n_asics > 1 and namespace is None:
        ctx.fail('Must specify asic')

    # Connect to config database
    config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
    config_db.connect()

    # Connect to state database
    state_db = SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
    state_db.connect(state_db.STATE_DB, False)

    # check if the port is actually in use
    portName = f'PORT{portid}'
    portStateData = state_db.get_all(state_db.STATE_DB, "FABRIC_PORT_TABLE|" + portName)
    if "REMOTE_PORT" not in portStateData:
        ctx.fail(f"Port {portid} is not in use")

    # Make sure configuration data exists
    portName = f'Fabric{portid}'
    portConfigData = config_db.get_all(config_db.CONFIG_DB, "FABRIC_PORT|" + portName)
    if not bool(portConfigData):
        ctx.fail("Fabric monitor configuration data not present")

    # Update entry
    config_db.mod_entry("FABRIC_PORT", portName, {'isolateStatus': False})

#
# 'config fabric port monitor ...'
#
@port.group(cls=clicommon.AbbreviationGroup)
def monitor():
    """FABRIC PORT MONITOR configuration tasks"""
    pass

#
# 'config fabric port monitor error ...'
#
@monitor.group(cls=clicommon.AbbreviationGroup)
def error():
    """FABRIC PORT MONITOR ERROR configuration tasks"""
    pass

#
# 'config fabric port  monitor error threshold <crcCells> <rxCells>'
#
@error.command('threshold')
@click.argument('crcCells', metavar='<crcCells>', required=True, type=int)
@click.argument('rxcells', metavar='<rxCells>', required=True, type=int)
@multi_asic_util.multi_asic_click_option_namespace
def error_threshold(crccells, rxcells, namespace):
    """FABRIC PORT MONITOR ERROR THRESHOLD configuration tasks"""

    ctx = click.get_current_context()

    n_asics = multi_asic.get_num_asics()
    if n_asics > 1 and namespace is None:
        ctx.fail('Must specify asic')

    # Check the values
    if crccells < 1 or crccells > 1000:
        ctx.fail("crcCells must be in range 1...1000")
    if rxcells < 10000 or rxcells > 100000000:
        ctx.fail("rxCells must be in range 10000...100000000")

    # Connect to config database
    config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
    config_db.connect()

    # Connect to state database
    state_db = SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
    state_db.connect(state_db.STATE_DB, False)

    # Make sure configuration data exists
    monitorData = config_db.get_all(config_db.CONFIG_DB, "FABRIC_MONITOR|FABRIC_MONITOR_DATA")
    if not bool(monitorData):
        ctx.fail("Fabric monitor configuration data not present")

    # Update entry
    config_db.mod_entry("FABRIC_MONITOR", "FABRIC_MONITOR_DATA",
        {'monErrThreshCrcCells': crccells, 'monErrThreshRxCells': rxcells})

#
# 'config fabric port monitor poll ...'
#
@monitor.group(cls=clicommon.AbbreviationGroup)
def poll():
    """FABRIC PORT MONITOR POLL configuration tasks"""
    pass

#
# 'config fabric port monitor poll threshold ...'
#
@poll.group(cls=clicommon.AbbreviationGroup, name='threshold')
def poll_threshold():
    """FABRIC PORT MONITOR POLL THRESHOLD configuration tasks"""
    pass

#
# 'config fabric port monitor poll threshold isolation <pollCount>'
#
@poll_threshold.command()
@click.argument('pollcount', metavar='<pollCount>', required=True, type=int)
@multi_asic_util.multi_asic_click_option_namespace
def isolation(pollcount, namespace):
    """FABRIC PORT MONITOR POLL THRESHOLD configuration tasks"""

    ctx = click.get_current_context()

    n_asics = multi_asic.get_num_asics()
    if n_asics > 1 and namespace is None:
        ctx.fail('Must specify asic')

    if pollcount < 1 or pollcount > 10:
        ctx.fail("pollCount must be in range 1...10")

    # Connect to config database
    config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
    config_db.connect()

    # Connect to state database
    state_db = SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
    state_db.connect(state_db.STATE_DB, False)

    # Make sure configuration data exists
    monitorData = config_db.get_all(config_db.CONFIG_DB, "FABRIC_MONITOR|FABRIC_MONITOR_DATA")
    if not bool(monitorData):
        ctx.fail("Fabric monitor configuration data not present")

    # Update entry
    config_db.mod_entry("FABRIC_MONITOR", "FABRIC_MONITOR_DATA",
        {"monPollThreshIsolation": pollcount})


#
# 'config fabric port monitor poll threshold recovery <pollCount>'
#
@poll_threshold.command()
@click.argument('pollcount', metavar='<pollCount>', required=True, type=int)
@multi_asic_util.multi_asic_click_option_namespace
def recovery(pollcount, namespace):
    """FABRIC PORT MONITOR POLL THRESHOLD configuration tasks"""

    ctx = click.get_current_context()

    n_asics = multi_asic.get_num_asics()
    if n_asics > 1 and namespace is None:
        ctx.fail('Must specify asic')

    if pollcount < 1 or pollcount > 10:
        ctx.fail("pollCount must be in range 1...10")

    # Connect to config database
    config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
    config_db.connect()

    # Connect to state database
    state_db = SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
    state_db.connect(state_db.STATE_DB, False)

    # Make sure configuration data exists
    monitorData = config_db.get_all(config_db.CONFIG_DB, "FABRIC_MONITOR|FABRIC_MONITOR_DATA")
    if not bool(monitorData):
        ctx.fail("Fabric monitor configuration data not present")

    # Update entry
    config_db.mod_entry("FABRIC_MONITOR", "FABRIC_MONITOR_DATA",
        {"monPollThreshRecovery": pollcount})


