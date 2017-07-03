import click

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



port = PortIntParamType()