# Standard Library
import ipaddress
from pprint import pprint

# Third Party Libraries
import click

# My libraries
from lazyLib import lazyTools
from lazyLib import LazyCustomTypes


__version__ = '0.2'

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(name='ipaddrs', short_help='Useful IP address tools.', context_settings=CONTEXT_SETTINGS, invoke_without_command=False)
@click.pass_context
def cli(ctx):
    """
    Group for holding IP address tools
    """
    pass

@cli.command(name='subtract', help='Subtract a smaller subnet from a bigger one.')
@click.option('-p', '--parent-network', type=LazyCustomTypes.ipaddr, help='This set of networks are to be subtracted from.', multiple=True, required=True)
@click.option('-c', '--child-network', type=LazyCustomTypes.ipaddr, help='Other networks to subtract from the parent network', multiple=True, required=True)
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

    # for c_addr in child_network_list:
    #     print(c_addr)


    for i in master_list:
        click.secho(i)
