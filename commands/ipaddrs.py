# Standard Library
from collections import namedtuple
from functools import partial
from ipaddress import (
    IPv4Address,
    IPv6Address,
    IPv4Network,
    IPv6Network,
    ip_address,
    ip_network,
)
from multiprocessing import Pool
from pprint import pprint
from tabulate import tabulate

# Third Party Libraries
import click
import dataset

# My libraries
from lazyLib import lazyTools
from lazyLib import LazyCustomTypes


__version__ = "0.2"

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(
    name="ipaddrs",
    short_help="Useful IP address tools.",
    context_settings=CONTEXT_SETTINGS,
    invoke_without_command=False,
    cls=lazyTools.AliasedGroup,
)
@click.pass_context
def cli(ctx):
    """
    Group for holding IP address tools
    """
    pass


@cli.command(name="subtract", help="Subtract a smaller subnet from a bigger one.")
@click.option(
    "-p",
    "--parent-network",
    type=LazyCustomTypes.ipaddr,
    help="This set of networks are to be subtracted from.",
    multiple=True,
    required=True,
)
@click.option(
    "-c",
    "--child-network",
    type=LazyCustomTypes.ipaddr,
    help="Other networks to subtract from the parent network",
    multiple=True,
    required=True,
)
@click.pass_context
def subtract_IPs(ctx, parent_network, child_network):
    """
    Command to subtract two IP ranges from each other
    """
    # TODO: Output types. Various ways of exporting data, pretty for users, raw data for piping into another application, etc.
    master_list = list()
    parent_network_list = list()
    child_network_list = list()

    for p_net in parent_network:
        for single_ip in lazyTools.IPTools.networkToList(p_net):
            if single_ip in parent_network_list:
                pass
            else:
                # Only add the IPs that aren't already in the list to the list
                # De-doup the  IP list
                parent_network_list.append(single_ip)

    for p_net in child_network:
        for single_ip in lazyTools.IPTools.networkToList(p_net):
            if single_ip in child_network_list:
                pass
            else:
                # Only add the IPs that aren't already in the list to the list
                # De-doup the IP list
                child_network_list.append(single_ip)

    for i in master_list:
        click.secho(i)


@cli.command(name="add", help="Add multiple networks and hosts together.")
@click.argument(
    "filename",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
)
@click.pass_context
def add_IPs(ctx, filename):
    """
    Add all IP Addresses listed in the given file
    """

    IP_List = list()
    count = 1

    with open(filename, "r") as f:
        for l in f:
            IP_List.append(l.strip())

    for ip in IP_List:
        ip_obj = lazyTools.IPTools.checkIfIP(ip)

        if isinstance(ip_obj, IPv4Network) or isinstance(ip_obj, IPv6Network):
            count += lazyTools.IPTools.countNetworkRange(ip_obj)
        else:
            count += 1

    click.echo("[*] There are {} addresses in this file.".format(count))


@cli.command(name="host-in-scope-file", help="Check if a given host IP address is in scope.")
@click.option(
    "--host",
    type=LazyCustomTypes.ipaddr,
    help="Host to check against scope file",
    multiple=True,
)
@click.option(
    "--unknown-file",
    help="File with IP addresses which need to be checked if they're in scope.",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
)
@click.argument(
    "scope-filename",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
)
@click.pass_context
def host_in_scope_file(ctx, host, scope_filename, unknown_file):
    """
    Check if host is in filename
    """
    IP_List = list()
    unknown_IP_List = list()

    if unknown_file is not None:
        with open(unknown_file, "r") as f:
            for l in f:
                unknown_IP_List.append(l.strip())

    with open(scope_filename, "r") as f:
        for l in f:
            IP_List.append(l.strip())

    if host is not None:
        for h in host:
            if lazyTools.IPTools.ipInList(h, IP_List):
                # IP is in scope
                click.secho(
                    "[*] The address {} is in the scoping file. ".format(h), bold=True
                )
            else:
                # IP is not in scope
                click.secho(
                    "[!] The address {} is *not* in scope. ".format(h), bold=True
                )

    if unknown_file is not None:
        for ip in unknown_IP_List:
            if lazyTools.IPTools.ipInList(ip, IP_List):
                # IP is in scope
                click.secho(
                    "[*] The address {} is in the scoping file. ".format(ip), bold=True
                )
            else:
                # IP is not in scope
                click.secho(
                    "[!] The address {} is *not* in scope. ".format(ip), bold=True
                )


@cli.command(name="host-in-scope", help="Check if a given host IP address is in scope.")
@click.option(
    "-h",
    "--host",
    type=LazyCustomTypes.ipaddr,
    help="Host to check against scope IPs. Multiples OK",
    multiple=True, required=True
)
@click.argument(
    "scope-addresses",
    type=click.STRING,
    nargs=-1,
)
@click.option("-w", "--workers", default=4, required=False, type=click.INT, help="Number of helper processes to stand up", show_default=True)
@click.pass_context
def host_in_scope(ctx, host, scope_addresses, workers):
    """
    Check if host is in IP addresses
    """
    scope_addresses_list = list()
    unknown_IP_List = list()

    # Create dictionary for our output
    ScopeOutputDict = {'In_Scope': False, "Found_In": None, "Host": None}


    # Make sure the unknown host is an IP address or network
    for h in host:
        scope = lazyTools.IPTools.checkIfIP(h)
        unknown_IP_List.append(scope)

    # Ensure the scope addresses are an IP or network address
    for s in scope_addresses:
        scope = lazyTools.IPTools.checkIfIP(s)
        scope_addresses_list.append(scope)

    # Create an object we can pass to map later
    func = partial(process_pool_ip_in_scope, scope_addresses_list, ScopeOutputDict)

    # Use process pool to determine if unknown IP is in the scope
    with Pool(workers) as p:
        # We have to use a dict so it's only "one" argument
        results = p.map(func, unknown_IP_List)

    print(tabulate(results, headers="keys", tablefmt="grid"))

def process_pool_ip_in_scope(scope_addresses_list, ScopeOutputDict, unknown_IP_addr):
    """
    Run this function in a process pool to get faster processing times
    """

    for addr in scope_addresses_list:
        # If Scope address is a network
        if isinstance(addr, IPv4Network) or isinstance(addr, IPv6Network):
            ScopeOutputDict.update(In_Scope=False, Found_In=None, Host=unknown_IP_addr)
            if unknown_IP_addr in addr.hosts():
                ScopeOutputDict.update(In_Scope=True, Found_In=addr, Host=unknown_IP_addr)

        # If scope address is a single host
        elif isinstance(addr, IPv4Address) or isinstance(addr, IPv6Address):
            # elif scope is a single address
            if unknown_IP_addr == addr:
                ScopeOutputDict.update(In_Scope=True, Found_In=addr, Host=unknown_IP_addr)

    return ScopeOutputDict


@cli.command(name="uniq-list", help="Print a list of uniq IP addresses from list ")
@click.argument(
    "filename",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
)
@click.pass_context
def uniq_list(ctx, filename):
    """
    Create a list of uniq IP addresses
    """

    IP_List = list()
    FinalIP_List = list()
    count = 1

    with open(filename, "r") as f:
        for l in f:
            IP_List.append(l.strip())

    for ip in IP_List:
        ip_obj = lazyTools.IPTools.checkIfIP(ip)

        if isinstance(ip_obj, IPv4Network) or isinstance(ip_obj, IPv6Network):
            for ip_addr in ip_obj.hosts():
                if str(ip_addr) not in FinalIP_List:
                    FinalIP_List.append(str(ip_addr))
                else:
                    # Duplicate address
                    pass
        else:
            # IP must be a single address
            if str(ip) not in FinalIP_List:
                FinalIP_List.append(str(ip))
            else:
                # Duplicate address
                pass

    # pprint(FinalIP_List, indent=4)

    for ip in FinalIP_List:
        print(ip)


# @cli.command(name='uniq-list', help='Print a list of uniq IP addresses from list ')
# @click.argument('filename', type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True))
# @click.pass_context
# def uniq_list(ctx, filename):
#     """
#     Create a list of uniq IP addresses
#     """
#
#     IP_List = list()
#     FinalIP_List = list()
#     count = 1
#
#     with open(filename, 'r') as f:
#         for l in f:
#             IP_List.append(l.strip())
#
#     # Open DB Connection
#     db = dataset.connect('sqlite:///:memory:')
#     table = db['ip_addresses']
#
#
#     for ip in IP_List:
#         ip_obj = lazyTools.IPTools.checkIfIP(ip)
#         if isinstance(ip_obj, IPv4Network) or isinstance(ip_obj, IPv6Network):
#             for ip_addr in ip_obj.hosts():
#                 response = table.find_one(f'{ip_addr}')
#                 print(response)
#         else:
#             table.insert(dict(ipaddr=f'{ip_obj}'))
