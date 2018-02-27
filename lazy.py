#!/Users/scottfraser/.virtualenvs/lazy/bin/python

# Standard Lib
import os
import logging
from pprint import pprint
import sys

# 3rd Party Libs
import click
import requests

# Lazy Lib
from lazyLib import lazyTools

# Check if we are connected to the VPN
# print(lazyTools.ConnectedToVPN(ctx.params['config']))

requests.packages.urllib3.disable_warnings()

# define our default configuration options

__version__ = '1.0'

# Version information
BANNER = """
Lazy App v%s
Sometimes writing code is easier than doing actual work.
Written by Scott Fraser
""" % __version__

plugin_folder = os.path.join(os.path.dirname(__file__), 'commands')

class MyCLI(click.MultiCommand):

    def list_commands(self, ctx):
        rv = []
        for filename in os.listdir(plugin_folder):
            if filename.endswith('.py'):
                rv.append(filename[:-3])
        rv.sort()
        return rv

    def get_command(self, ctx, name):
        matches = [x for x in self.list_commands(ctx) if x.startswith(name)]
        if not matches:
            return None
        elif len(matches) == 1:
            try:
                mod = __import__('commands.' + matches[0], None, None, ['cli'])
                return mod.cli
            except ImportError:
                return
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=False, cls=MyCLI)
@click.option('--config-path', help='Specify a configuration file to use.', type=click.Path(exists=True, dir_okay=False, resolve_path=True, allow_dash=True), default='/Users/scottfraser/PycharmProjects/lazy/lazy.conf')
@click.option('--debug', help='Enable debugging. -Work in progress-', is_flag=True, default=False)
@click.option('-v', '--verbose', help='Enable verbosity', is_flag=True, default=False)
@click.pass_context
def cli(ctx, config_path, debug, verbose):

    # Logging
    # Quiet down Requests logging
    logging.getLogger("requests").setLevel(logging.WARNING)
    # Quiet down urllib3 logging
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger(os.path.basename(__file__)[:-3])
    logger.setLevel(logging.DEBUG)
    # create console handler and set level
    ch = logging.StreamHandler()

    # If verbose but not debug
    if ctx.params['verbose'] == True and ctx.params['debug'] == False:
        ch.setLevel(logging.INFO)
        # create formatter
        formatter = logging.Formatter('%(levelname)s - %(message)s')
    elif ctx.params['debug']:
        ch.setLevel(logging.DEBUG)
        # Debug formatting
        formatter = logging.Formatter('%(levelname)s - %(message)s \t %(filename)s \t %(funcName)s')
    else:
        ch.setLevel(logging.WARNING)
        # create formatter
        formatter = logging.Formatter('%(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)



if __name__ == "__main__":
    cli()