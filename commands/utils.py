import os
from pprint import pprint
import sys
import zipfile

import arrow
import boto3
import click
import click_spinner
from lifxlan import LifxLAN, WARM_WHITE, PINK

# My Junk
from lazyLib import lazyTools

__version__ = '1.0'

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(name='utils', short_help='A collection of tools which are useful but don\'t fit anywhere else.', context_settings=CONTEXT_SETTINGS)
@click.pass_context
def cli(ctx):
    """
    A collection of tools which are useful but don\'t fit anywhere else.
    """
    pass

@cli.command('share', help='Mount or unmount a shared drive.', context_settings=CONTEXT_SETTINGS)
@click.option('-s', '--share-name', help='Name of the share from the config file.', default='QNAP', type=click.STRING)
@click.option('--status', help='Show the current status of the mounted drive.', is_flag=True, default=False)
@click.pass_context
def share(ctx, share_name, status):
    """
    Mount or unmount a shared drive with configurations from the global config file
    """
    configOptions = lazyTools.TOMLConfigImport(ctx.parent.parent.params['config_path'])

    if share_name.lower() in configOptions['share']:
        if configOptions['share'][share_name.lower()]['VPN_Required']:
            if lazyTools.ConnectedToVPN(ctx.parent.parent.params['config_path']):
                # Connected to VPN
                click.secho('[*] Connected to VPN', fg='green')
            else:
                # Not connected to VPN
                raise click.ClickException('Not connected to corporate VPN.')
        else:
            pass #print('VPN not required')

        share_status = os.path.ismount(configOptions['share'][share_name.lower()]['mount_point'])

        if status:
            if share_status:
                click.secho('[*] The shared drive is already mounted.', fg='green')
                sys.exit()
            else:
                click.secho('[*] The shared drive is not mounted.', fg='white')
        else:
            # Mount drive if not mounted, unmount if mounted
            if share_status:
                click.secho('[!] The shared drive is already mounted. Attempting to unmount it.', fg='white')
                returnValue = lazyTools.mount_changer(configOptions['share'][share_name.lower()]['mount_point'])
                if returnValue[0] == True:
                    click.secho('[*] Share unmounted successfully.', fg='white')
                else:
                    # Share didn't unmount
                    click.secho('[!] {}'.format(returnValue[1].strip()), fg='red')
                    if returnValue[1].startswith('Unmount failed for'):
                        # Advise the user to check for active sessions on the remote share
                        click.secho('[*] Check for files that are open on the remote share. This also includes command prompts pointed to the remote file system.', fg='red')
            else:
                click.secho('[*] Share not mounted', fg='white')
                username = configOptions['share'][share_name.lower()]['username']
                password = configOptions['share'][share_name.lower()]['password']
                filled_path = configOptions['share'][share_name.lower()]['path'].format(uname=username, pword=password)

                # Mount the shared drive
                click.secho('[*] Mounting the share.', fg='white')
                click.launch(filled_path)




    else:
        raise click.BadParameter('The share name \'{}\' doesn\'t appear to exist. Check the config file and try again.'.format(ctx.params['share_name']))

@cli.command('wiki-backup', help='Backup the local Doku Wiki to an Amazon S3 bucket.', context_settings=CONTEXT_SETTINGS)
@click.pass_context
def backup(ctx):
    # Archive location
    backup_path = '/Users/scottfraser/Sites/Backups/'
    backup_filename = 'personalWiki_{date}.zip'.format(date=arrow.utcnow().to('local').format('YYYY-MM-DD'))
    backup_full = os.path.join(backup_path, backup_filename)

    # Data to archive
    archive_data = '/Library/WebServer/Documents/dokuwiki/'

    click.echo('[*] Compressing data from {} into {}'.format(archive_data, backup_full))
    with click_spinner.spinner(beep=True):
        with zipfile.ZipFile(backup_full, 'w') as zipf:
            for root, dirs, files in os.walk(archive_data):
                for file in files:
                    zipf.write(os.path.join(root, file))

    # Let's use Amazon S3
    s3 = boto3.client('s3')

    bucket_name = 'local-wiki'

    click.echo('[*] Uploading {} to bucket {} now.'.format(backup_full, bucket_name))
    with click_spinner.spinner(beep=True):
        with open(backup_full, 'rb') as f:
            s3.upload_fileobj(f, bucket_name, backup_filename)
    click.echo('[!] Done! \n')

@cli.group('lights', help='Base command for the controlling the lights.', context_settings=CONTEXT_SETTINGS)
@click.pass_context
def lights(ctx):
    """
    Base command for controlling the lights
    """

@lights.command('out', help='Turns off all Lifx bulbs on the local network.')
@click.pass_context
def lights_out(ctx):
    """
    Turns off all Lifx bulbs on the local network.
    """

    num_lights = None

    lifx = LifxLAN(num_lights, verbose=False)

    # get devices
    devices = lifx.get_lights()
    labels = []
    for device in devices:
        # pprint(vars(device))
        labels.append({'label': device.get_label(), 'ip_addr': device.get_ip_addr()})

    if ctx.parent.parent.params['verbose'] == True:
        click.echo("Found Bulbs:")
        for label in labels:
            print('[-] Label: {}\n[->] IP Address: {}'.format(label['label'], label['ip_addr']))

    lifx.set_power_all_lights("off", rapid=True)

@lights.command('normal', help='Sets the bulbs to a normal color.')
@click.pass_context
def normal(ctx):
    """
    Set all the lights to normal
    """

    num_lights = None

    lifx = LifxLAN(num_lights, verbose=False)

    # get devices
    devices = lifx.get_lights()

    for device in devices:
        # Set color
        device.set_color(WARM_WHITE, rapid=True)

@lights.command('pink', help='Sets the bulbs to pink.')
@click.pass_context
def normal(ctx):
    """
    Set all the lights to pink
    """

    num_lights = None

    lifx = LifxLAN(num_lights, verbose=False)

    # get devices
    devices = lifx.get_lights()

    for device in devices:
        # Set color
        device.set_color(PINK, rapid=True)
