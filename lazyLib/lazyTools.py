# Standard Library
from ipaddress import IPv4Address, IPv6Address, IPv4Network, IPv6Network, ip_address, ip_network
import os
import subprocess
import sys

# LazyLib Tools
from . import LazyCustomTypes


# 3rd Party Libs
import asyncssh
import click
import requests
import toml

__version__ = '1.5'

def file_exist(path_in):
    """
    Check if path exists
    :param path_in: Does this file exist
    :return: True for exist; False for does not exist
    :rtype: bool
    """
    return os.path.isfile(path_in)

def dir_exists(path_in):
    """
    Check if directory exists
    :param path_in: Does this file exist
    :return: True for exist; False for does not exist
    :rtype: bool
    """
    return os.path.isdir(path_in)

def TOMLConfigImport(filename):
    """Parse a TOML configuration file"""
    with open(filename) as f:
        config = toml.load(f)

    return config

def getPublicIP(url='https://ipv4.icanhazip.com'):
    resp = requests.get(url)
    if resp.status_code != 200:
        err_str = "{} returned status code {}".format(url, resp.status_code)
        raise GetHTTPException(err_str) from None
    else:
        return resp.text.rstrip()

def ConnectedToVPN(config_file: str) -> bool:
    try:
        # Parse Configuration File
        vpn_list = TOMLConfigImport(config_file)['VPN']['vpn_addresses']
    except KeyError:
        raise VPNAddressListNotFound('[*] VPN addresses not found under VPN in list called \'vpn_addresses\'')

    try:
        return IPTools.ipInList(getPublicIP(), vpn_list)
    except GetHTTPException as e:
        print(e)
        sys.exit(1)

def mount_changer(share_location):
    """
    # Mount drive if not mounted, unmount if mounted
    :return: True for successful unmount and False for a failure. Also return error message in tuple
    """
    cmd_rtn = subprocess.run("diskutil unmount {}".format(share_location), shell=True, check=False,
                             stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    if cmd_rtn.returncode == 0:
        return [True, 'Share unmounted successfully']
    elif cmd_rtn.returncode != 0:
        # If it failed somehow, return error msg
        err_str = '{}'.format(cmd_rtn.stderr.decode("utf-8"))
        return [False, err_str]


class IPTools():
    """Class with IP address tools"""

    @staticmethod
    def ipInList(unknown_ip, ip_list):
        """Check if unknown_ip is in ip_list"""
        ip_obj_list = list()

        # Convert unknown IP str to IP object
        unknown_ip = IPTools.checkIfIP(unknown_ip)

        # print("{}: {}".format(unknown_ip, type(unknown_ip)))

        # Convert ip_list list to IP objects in a list
        for ip in ip_list:
            ip_obj_list.append(IPTools.checkIfIP(ip))

        for src_ip in ip_obj_list:
            # return src_ip.hosts()
            if unknown_ip in src_ip.hosts():
                ip_on_list = True
            else:
                ip_on_list = False

            if ip_on_list:
                return True
        return False

    @staticmethod
    def checkIfIP(ip: str):
        """
        Checks if the provided string is a valid IPv4 or IPv6 address

        This function either returns a ipaddress object
        :param ip: IP address in string format
        :type ip: str
        :return: Returns an ipaddress object
        :rtype: ipaddress
        """
        try:
            return ip_address(ip)
        except ValueError:
            try:
                return ip_network(ip, strict=False)
            except ValueError:
                raise IPToolsExceptions.NotValidIP("'{}' is not a valid IP network or address".format(ip)) from None

    @staticmethod
    def countNetworkRange(ip):
        """
        Count how many IPs are in a given network
        :param ip: IP Network object
        :return: Int of number of IPs in network
        :rtype: int
        """
        try:
            count = 1
            for count, addr in enumerate(ip.hosts()):
                pass
            return count
        except AttributeError:
            return 1

    @staticmethod
    def networkToList(ip_addr):
        """
        Convert ipaddress.ip_network types to a list of valid addresses
        :param ip_addr: ipaddress.IPv4Network or ipaddress.IPv6Network to be converted
        :return: List of IP addresses
        :rtype: list
        """
        network_list = list()
        if isinstance(ip_addr, IPv4Network) or isinstance(ip_addr, IPv6Network):
            for ip in ip_addr:
                network_list.append(ip)
            return network_list
        else:
            network_list.append(ip_addr)
        return network_list


def checkNessusServerConfig(ctx, target, port, name):
    """
    Check that the provided configuration checks out

    ### THIS FUNCTION REQUESTS INFORMATION FROM THE USER ###
    """
    configOptions = TOMLConfigImport(ctx.parent.parent.params['config_path'])
    if name in configOptions['nessus']:
        # Name given exists, grab hostname, port, access_key, secret_key and determine if VPN is required
        target = configOptions['nessus'][name]['Hostname']
        port = configOptions['nessus'][name]['Port']
        access_key = configOptions['nessus'][name]['access_key']
        secret_key = configOptions['nessus'][name]['secret_key']
        vpn_required = configOptions['nessus'][name]['VPN_Required']

        ctx.obj = {'target': target, 'port': port, 'access_key': access_key, 'secret_key': secret_key,
                   'vpn_required': vpn_required}

    else:
        if target is None:
            target = click.prompt('[?] What is the hostname or IP of the Nessus server', prompt_suffix='? ')
        if port is None:
            port = click.prompt('[?] What port is the Nessus server accessable on', prompt_suffix='? ',
                                type=LazyCustomTypes.port)

        username = click.prompt('[?] What is your username for Nessus', prompt_suffix='? ')
        password = click.prompt('[?] What is your password for Nessus', prompt_suffix='? ', hide_input=True)

        ctx.obj = {'target': target, 'port': port, 'username': username, 'password': password}

    if not ctx.obj['target'].startswith('https://'):
        ctx.obj['target'] = 'https://{}'.format(ctx.obj['target'])

    if ctx.obj['target'].endswith('/'):
        ctx.obj['target'] = ctx.obj['target'].replace('/', ':{}'.format(ctx.obj['port']))
    else:
        ctx.obj['target'] = '{}:{}'.format(ctx.obj['target'], ctx.obj['port'])

    # Set the VPN_Required flag to false
    ctx.obj['vpn_required'] = False

    return ctx, target, port, name


class AliasedGroup(click.Group):

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx) if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))

class SSHTools(object):

    @staticmethod
    async def upload_file(rhost, rport, username, password, local_file, remote_file=None, preserve=False, recurse=False, block_size=16384, progress_handler=None, error_handler=None):
        async with asyncssh.connect(rhost, port=rport, username=username, password=password, known_hosts=None) as conn:
            conn.run('ls')
            # if remote_file == None:
            #     # Name the file the same as the src
            #     await asyncssh.scp((conn, local_file), '.', preserve=preserve, recurse=recurse, block_size=block_size, progress_handler=progress_handler, error_handler=error_handler)
            # else:
            #     await asyncssh.scp((conn, local_file), remote_file, preserve=preserve, recurse=recurse, block_size=block_size, progress_handler=progress_handler, error_handler=error_handler)



class IPToolsExceptions(Exception):
    class NotValidIP(Exception):
        """Exception raised when given string is not a valid IP network or address"""
    class NoValidIPs(Exception):
        """Exception raised when no IP address are present"""
class VPNAddressListNotFound(Exception):
    """Raised when list of addresses is not found in the config file."""
class GetHTTPException(Exception):
    """Exception raised when status code other than 200 returned from website when attempting to get public IP"""
class NotConnectedToVPN(Exception):
    """Exception raised when public IP is not inside list of valid VPN IPs"""