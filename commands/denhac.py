import asyncio
import logging
from pathlib import Path
from time import sleep

import asyncssh
import click
import pendulum
import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Lazy Lib
from lazyLib import lazyTools

from lazyLib.UVC_SyncLib import UVC_API_Sync

__version__ = '1.0'

def datetime_check(ctx, param, value):
    """
    Function to check the datetime input
    """
    if value is None:
        if param.name is 'start_time':
            raise click.BadParameter('You must provide a start time.')
        elif param.name is 'end_time':
            raise click.BadParameter('You must provide an end time.')
        else:
            raise click.BadParameter(f'I\' being called for {param.name} which is wrong. WTF MATE.')
    try:
        dt = pendulum.from_format(value, 'DD-MM-YYYY:HH:mm:ss', tz='UTC')

        # Convert the datetime object to JavaScript Epoch time
        return dt.int_timestamp * 1000
    except:
        if param.name is 'start_time':
            raise click.BadParameter('Start datetime is not in the correct format.')
        elif param.name is 'end_time':
            raise click.BadParameter('End datetime is not in the correct format.')
        else:
            raise click.BadParameter(f'I\' being called for {param.name} which is wrong. WTF MATE.')

async def run_client(host, uname, command):
    # print('Hostname: {}'.format(host))
    # print('Username: {}'.format(uname))
    # print('Command: {}'.format(command))

    async with asyncssh.connect(host, username=uname) as conn:
        return await conn.run(command)


async def run_multiple_clients(hosts: list, username: str, sh_command: str):
    """
    Library that can connect to multiple hosts at once and run the same command.

    Src: https://asyncssh.readthedocs.io/en/latest/#running-multiple-clients
    """

    # print('Hosts: {}'.format(hosts))

    failed_task = list()
    non_zero_exit = list()
    success_task = list()

    tasks = (run_client(host, username, sh_command) for host in hosts)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results, 0):
        if isinstance(result, Exception):
            failed_task.append('Host {} failed with error: {}\n'.format(hosts[i], str(result)))
        elif result.exit_status != 0:
            non_zero_exit.append('Host {} exited with a non 0 error. Error code: {}\n'.format(hosts[i], result.exit_status))
            non_zero_exit.append(result.stderr)
        else:
            success_task.append('Host {}\'s task succeeded. \n'.format(hosts[i]))
            success_task.append(result.stdout)

    return failed_task, non_zero_exit, success_task


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group('denhac', help='Commands to help with denhac server administration.', cls=lazyTools.AliasedGroup)
@click.pass_context
def cli(ctx):
    """
    Base command for denhac helpers
    """


@cli.command('restart-odoo', help='Restarts denhac\'s webserver, Odoo.')
@click.option('-s', '--server', help='Remote server to connect to.', default='denhac.org')
@click.option('-c', '--cmd', help='Command to run on the remote hosts. Defaults to restarting Odoo.', type=click.STRING, default='sudo systemctl restart odoo')
@click.option('-u', '--username', help='Username to login with.', type=click.STRING, default='radioboy')
@click.pass_context
def restart_odoo(ctx, server, cmd, username):
    """
    Sub command to log into the webserver and restart Odoo.
    """

    hosts = [server]

    loop = asyncio.get_event_loop()
    failed_task, non_zero_exit, success_task = loop.run_until_complete(run_multiple_clients(hosts, username, cmd))

    if len(failed_task) != 0:
        for i in failed_task:
            print(i)

    if len(non_zero_exit) != 0:
        for i in non_zero_exit:
            print(i)

    if len(success_task) != 0:
        for i in success_task:
            print(i)

    click.echo(75 * '-')

@click.command(name='download-videos', help='Download videos for cameras for a specific timeframe.', context_settings=CONTEXT_SETTINGS)
@click.option('-s', '--start-time', callback=datetime_check, help='Specify a start time in DD:MM:YYYY-HH:mm')
@click.option('-e', '--end-time', callback=datetime_check, help='Specify a start time in DD:MM:YYYY-HH:mm')
@click.option('-u', '--username', help='Unifi Video username', required=True, default='choochoo', type=click.STRING)
@click.option('-d', '--hostname', help='Domain name, hostname or IP address for the Video controller. E.g. 127.0.0.1', type=click.STRING, required=True)
@click.option('-p', '--port', help='Port number for the Video controller. Defaults to 7443', default=7443, type=click.IntRange(1, 65535))
@click.option('-o', '--output-dir', help='Directory to save the videos to.', type=click.Path(exists=False, file_okay=False, writable=True, resolve_path=True, allow_dash=True))
@click.option('-p', '--password', help='UVC User\'s password.', prompt=True, hide_input=True)
@click.argument('camera-names', nargs=-1)
@click.pass_context
def main(ctx, start_time, end_time, username, hostname, port, output_dir, password, camera_names):
    # Create base logger
    logger = logging.getLogger("UVC-DVR-Downloader")

    console_log_level = 30

    # Base logger
    logger.setLevel(logging.DEBUG)

    # Create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(console_log_level)

    # Create log format
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')

    # Set the format
    ch.setFormatter(formatter)

    # Add console handler to main logger
    logger.addHandler(ch)

    """
    - Log into UVC
    - Get Camera information
    - Search for block of videos
    - Download videos
    """

    client = UVC_API_Sync(hostname, port, username, password, logger, sleep_time=0)

    raw_resp = client.login()

    raw_resp = client.camera_info()

    camera_id_list = client.camera_name(camera_names)

    client.clip_search(epoch_start=start_time, epoch_end=end_time, camera_id_list=camera_id_list)

    client.download_footage(Path(output_dir))

    sleep(.2)

    raw_resp = client.logout()