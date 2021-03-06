import logging
import os
import platform
from pprint import pprint
from subprocess import check_output
import sys

import click
from aiohttp import web

# My Junk
from lazyLib import lazyTools


__version__ = "1.0"

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(
    name="webserver",
    short_help="Serve up a nice directory index from a given point.",
    context_settings=CONTEXT_SETTINGS,
    cls=lazyTools.AliasedGroup,
    invoke_without_command=True,
)
@click.option(
    "-d",
    "--directory",
    help="Directory to serve from, defaults to current working directory.",
    default=os.getcwd(),
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        allow_dash=True,
    ),
)
@click.option(
    "-p",
    "--port",
    help="Port to bind to, defaults to 8080.",
    default=8000,
    type=click.IntRange(1, 65535),
)
@click.pass_context
def cli(ctx, directory, port):
    """
    Serve up a nice directory index from a given point.
    """
    logging.basicConfig(level=logging.INFO)

    if platform.system() != "Darwin":
        # Get our public IP addresses
        try:
            # Skip this if it fails
            ip_raw = str(check_output(["hostname", "-I"]))
            for ip in ip_raw.strip().split():
                click.echo("http://{ip}:{port}/".format(ip=ip, port=port))
        except:
            pass

    app = web.Application()
    app.router.add_static("/", directory, show_index=True)
    web.run_app(app, port=port, access_log_format=' => %a requested "%r" : Status: %s')
