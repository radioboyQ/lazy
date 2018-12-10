# Standard Library
import asyncio
from ipaddress import IPv4Address, IPv6Address, IPv4Network, IPv6Network, ip_address, ip_network
import os
from pathlib import Path
from pprint import pprint
import subprocess
import sys

# LazyLib Tools
from . import LazyCustomTypes


# 3rd Party Libs
import asyncssh
import click
from notifiers import get_notifier
import requests
import toml

__version__ = '2.0'

@click.pass_context
def notifications(ctx):
    config_options = TOMLConfigCTXImport(ctx)
    token = config_options['pushover']['token']
    user_token = config_options['pushover']['user']
    p = get_notifier('pushover')

    pprint(vars(ctx), indent=4)


    # pprint(config_options, indent=4)

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
    filename = Path(filename).expanduser()
    config = toml.load([str(filename)])

    return config

def TOMLConfigCTXImport(ctx):
    """Parse a TOML configuration file via the Click context"""

    return TOMLConfigImport(multi_getattr(ctx, ('parent.' * ctx._depth) + 'params')['config_path'])

def parentSetting(ctx, param):
    """Return the given top level setting"""

    return multi_getattr(ctx, ('parent.' * ctx._depth) + 'params')[param]

def multi_getattr(obj, attr, default=None):
    """
    Get a named attribute from an object; multi_getattr(x, 'a.b.c.d') is
    equivalent to x.a.b.c.d. When a default argument is given, it is
    returned when any attribute in the chain doesn't exist; without
    it, an exception is raised when a missing attribute is encountered.
    """
    attributes = attr.split(".")
    for i in attributes:
        try:
            obj = getattr(obj, i)
        except AttributeError:
            if default:
                return default
            else:
                raise
    return obj


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

def order_preserve_uniq_list(seq):
    # Order preserving
    seen = set()
    return [x for x in seq if x not in seen and not seen.add(x)]

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

    def __init__(self, username: str, host:str = None, port=22, password=None, known_hosts='/Users/scottfraser/.ssh/known_hosts'):
        self.host = host
        self.username = username
        self.port = port
        self.password = password
        self.known_hosts = known_hosts

    def progress_handler_upload(self, srcpath, dstpath, offset, size):
        self.print_progress(offset, size, prefix='Uploading: {}'.format(os.path.basename(os.path.normpath(srcpath.decode("utf-8") ))))

    def print_progress(self, iteration, total, prefix='Progress', suffix='% Complete', decimals=1, length=100, fill='█'):
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        filled_length = int(length * iteration // total)
        bar = fill * filled_length + '-' * (length - filled_length)
        print('\r{} |{}| {}{}'.format(prefix, bar, percent, suffix), end='\r')
        # Print New Line on Complete
        if iteration == total:
            print()

    def get_size(self, filepath):
        """
        Get the size in bytes of a given file
        """

        return os.path.getsize(filepath)

    async def upload_file(self, srcFilePath: str=None, destFilePath='.', progressBar: bool = True):
        """
        Upload a file to remote host
        """
        if self.password == None:
            async with asyncssh.connect(self.host, username=self.username, port=self.port, known_hosts=self.known_hosts) as conn:
                if progressBar:
                    await asyncssh.scp(srcFilePath, (conn, destFilePath), progress_handler=self.progress_handler_upload)
                else:
                    await asyncssh.scp(srcFilePath, (conn, destFilePath))
        else:
            async with asyncssh.connect(self.host, username=self.username, password=self.password, port=self.port, known_hosts=self.known_hosts) as conn:
                if progressBar:
                    await asyncssh.scp(srcFilePath, (conn, destFilePath), progress_handler=self.progress_handler_upload)
                else:
                    await asyncssh.scp(srcFilePath, (conn, destFilePath))

    async def run_client(self, command: str, host:str = None):
        """
        Single connection to run a single command
        """

        if host == None:
            if self.password == None:
                async with asyncssh.connect(self.host, username=self.username, port=self.port, known_hosts=self.known_hosts) as conn:
                    result = await conn.run(command)
                    responseDict = {self.host: {command: {'result_stdout': result.stdout, 'result_stderr': result.stderr, 'result_exit_status': result.exit_status}}}

            elif self.password:
                async with asyncssh.connect(self.host, username=self.username, password=self.password, port=self.port,  known_hosts=self.known_hosts) as conn:
                    result = await conn.run(command)
                    responseDict = {self.host: {command: {'result_stdout': result.stdout, 'result_stderr': result.stderr, 'result_exit_status': result.exit_status}}}
        elif host != None:
            if self.password == None:
                async with asyncssh.connect(self.host, username=self.username, port=self.port, known_hosts=self.known_hosts) as conn:
                    result = await conn.run(command)
                    responseDict = {self.host: {command: {'result_stdout': result.stdout, 'result_stderr': result.stderr, 'result_exit_status': result.exit_status}}}

            elif self.password:
                async with asyncssh.connect(self.host, username=self.username, password=self.password, port=self.port,  known_hosts=self.known_hosts) as conn:
                    result = await conn.run(command)
                    responseDict = {self.host: {command: {'result_stdout': result.stdout, 'result_stderr': result.stderr, 'result_exit_status': result.exit_status}}}

        return responseDict

    async def run_multiple_clients(self, hosts: list, command: str):
        """
        Run the same command against multiple hosts
        """

        tasks = (self.run_client(command, host) for host in hosts)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return results

    async def single_client_multiple_commands(self, commands: list):
        """
        Run a list of commands against a single host
        """

        tasks = (self.run_client(command) for command in commands)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return self.combine_multi_results(results)

    def combine_multi_results(self, results: list):
        """
        Combine list with task responses into one big dictionary
        """
        resultsDict = dict()

        for response in results:
            for hostname in response:
                # print(response[hostname])
                if hostname in resultsDict:
                    for command in response[hostname]:
                        if command in resultsDict[hostname]:
                            raise ('Duplicate command! {}'.format(command))
                        else:
                            resultsDict[hostname][command] = response[hostname][command]
                else:
                    resultsDict.update({hostname: response[hostname]})

        return resultsDict

    @staticmethod
    async def local_port_forward(ssh_target: str, ssh_port: int, ssh_username: str, local_host: str, local_port: int,
                                 id_file: str, remote_port: int, remote_host: str, debug: bool, start_event,
                                 exit_event):
        """
        Function to spin up a local listener
        :param ssh_target: IP address to connect to
        :param listen_host: The hostname or address on the local host to listen on
        :param local_port: The port to forward from. This is the first number in -L 8080:<remote_host>:80
        :param remote_port:  The port to forward to. This is the last number in `-L 8080:<remote_host>:80`
        :param remote_host: Target host. Can be localhost or something else the target can reach.
        """
        if debug:
            click.echo(
                '[*] Attempting to connect to {} on port {} as user {} with SSH ID file {}'.format(ssh_target, ssh_port,
                                                                                                   ssh_username,
                                                                                                   id_file))

        async with asyncssh.connect(host=ssh_target, username=ssh_username, port=ssh_port, known_hosts=None,
                                    client_keys=[id_file]) as conn:
            # print(remote_port)
            # print(type(remote_port))
            # raise click.Abort()
            listener = await conn.forward_local_port('', local_port, remote_host, remote_port)
            # click.echo('Listening on port {}'.format(listener.get_port()))
            start_event.set()
            await exit_event.wait()
            if debug:
                click.echo('[!] Tasks done. Closing tunnel.')
            listener.close()

    async def local_port_fwd(self, remote_host, remote_port):
        """
        Create a connection to the middle host for the remote host with a port forward
        """
        async with asyncssh.connect(host=self.host, username=self.username, port=self.port, known_hosts=None, client_keys=[id_file]) as conn:
            pass

class AsyncIOSSHAddingDuplicateCommandToResults(Exception):
    """Adding a duplicate command to the command list"""


def timeIt(startTime, stopTime):
    """
    Get the delta between two times and humanize them
    """

    return stopTime - startTime



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