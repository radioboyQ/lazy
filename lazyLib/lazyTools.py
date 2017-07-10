# Standard Library
from ipaddress import IPv4Address, IPv6Address, IPv4Network, IPv6Network, ip_address, ip_network
import os
import subprocess
import sys


# 3rd Party Libs
from lxml import etree
import requests
import toml

__version__ = '1.1'

def nmap_parser(nmap_filepath):
    """
    Generate a list of dictionaries with `IP`, `PortNumber`, `Protocol`, `Application`, `Version`
    :param nmap_filepath: Filepath as string
    :type nmap_filepath: str
    :return: List of dictionaries
    :rtype: list
    """
    headers = ['Host', 'Port', 'Protocol', 'Application', 'Version']

    finalData = list()

    # Check if the file given is an XML file
    if os.path.isfile(nmap_filepath) and nmap_filepath.endswith('xml'):

        tree = etree.parse(nmap_filepath)

        root = tree.getroot()

        for h in root.xpath('./host'):
            for hostAttrib in h:
                if hostAttrib.tag == 'address':
                    addr = hostAttrib.attrib['addr']
                elif hostAttrib.tag == 'ports':
                    for ports in hostAttrib:
                        if ports.tag == 'port':
                            protocol = ports.attrib['protocol']
                            portNumber = ports.attrib['portid']
                            for service in ports:
                                if service.tag == 'service':
                                    application = service.attrib['name']
                                    try:
                                        version = service.attrib['product']
                                    except KeyError:
                                        version = ""
                    data = {'Host': addr, 'Port': portNumber, 'Protocol': protocol, 'Application': application,
                            'Version': version}
                    finalData.append(data)
    else:
        raise FileNotFoundError('File must end in \'xml\'')

def TOMLConfigImport(filename):
    """Parse a TOML configuration file"""
    with open(filename) as f:
        config = toml.load(f)

    return config

def getPublicIP(url='https://icanhazip.com'):
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
        print('[*] VPN addresses not found under VPN in list called \'vpn_addresses\'')
        sys.exit(1)

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
    """Class with IP address toosl"""

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





class IPToolsExceptions(Exception):
    class NotValidIP(Exception):
        """Exception raised when given string is not a valid IP network or address"""
    class NoValidIPs(Exception):
        """Exception raised when no IP address are present"""

class GetHTTPException(Exception):
    """Exception raised when status code other than 200 returned from website when attempting to get public IP"""
class NotConnectedToVPN(Exception):
    """Exception raised when public IP is not inside list of valid VPN IPs"""