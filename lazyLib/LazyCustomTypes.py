
# Third Party Libraries
import click

# My tools
from .lazyTools import *
from .lazyTools import *


class PortIntParamType(click.ParamType):
    name = 'port'

    def convert(self, value, param, ctx):
        try:
            if int(value) >= 0  or int(value) < 65536:
                return value
            else:
                raise ValueError
        except ValueError:
            self.fail('%s is not a valid port number' % value, param, ctx)

class IPAddressParamType(click.ParamType):
    name = 'ipaddr'

    def convert(self, value, param, ctx):
        try:
            ip_res = IPTools.checkIfIP(value)
            if ip_res is not None:
                return ip_res
        except IPToolsExceptions.NotValidIP:
            self.fail('{} is not a valid IP address or IP address range'.format(value))


port = PortIntParamType()
ipaddr = IPAddressParamType()
