import os
from pprint import pprint
from pathlib import Path
import subprocess
import sys
import zipfile

import arrow
import boto3
import click
import click_spinner

# My Junk
from lazyLib import lazyTools

__version__ = '1.0'

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(name='utils', short_help='A collection of tools which are useful but don\'t fit anywhere else.', context_settings=CONTEXT_SETTINGS, cls=lazyTools.AliasedGroup)
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
    configOptions = lazyTools.TOMLConfigCTXImport(ctx)

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
    with click_spinner.spinner(beep=False):
        with zipfile.ZipFile(backup_full, 'w') as zipf:
            for root, dirs, files in os.walk(archive_data):
                for file in files:
                    zipf.write(os.path.join(root, file))

    # Let's use Amazon S3
    s3 = boto3.client('s3')

    bucket_name = 'local-wiki'

    click.echo('[*] Uploading {} to bucket {} now.'.format(backup_full, bucket_name))
    with click_spinner.spinner(beep=False):
        with open(backup_full, 'rb') as f:
            s3.upload_fileobj(f, bucket_name, backup_filename)
    click.echo('[!] Done! \n')

@cli.command('backup', help='Backup various files and folders I care about.', context_settings=CONTEXT_SETTINGS)
@click.option('-s', '--server', help='Server profile to use', type=click.STRING, default='remote_apt_mirror')
@click.pass_context
def backup(ctx, server):
    """
    Backup local files to Synology when on the home network
    """
    ssh_config = lazyTools.TOMLConfigCTXImport(ctx)['backup']

    try:
        server_config = ssh_config[server]
    except KeyError:
        raise click.ClickException('Invalid server configuration. Check the config file and try again.')

    # Connect to NYC server with tunnel
    vps = lazyTools.SSHTools(server_config['ssh_middle_user'], server_config['ssh_middle_host'])

    vps.local_port_forward()


@cli.command('udev-rename', help='Rename a network device using a generated string.')
@click.option('-m', '--mac-addr', help='MAC address of device to be renamed')
@click.option('-n', '--name', help='Name of the new device')
@click.option('-w', '--write', help='Append string to udev file. This requires "sudo" privileges. *Not working!* ', is_flag=True, default=True)
@click.option('-p', '--udev-path', help='Udev configuration file path. Default: /etc/udev/rules.d/60-persistent-net.rules', default="/etc/udev/rules.d/60-persistent-net.rules", type=click.Path(exists=True, dir_okay=False, writable=False, resolve_path=True, allow_dash=True))
@click.pass_context
def udev_rename(ctx, mac_addr, name, write, udev_path):
    """
    Generate a string for the udev conf to rename a network card
    """
    # These are just here to get around some syntax requirements and fill in the strings when using f-strings
    address = "{address}"
    dev_id = "{dev_id}"
    attr_type = "{type}"
    
    udev_str = f'SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*",ATTR{address}=="{mac_addr}",ATTR{dev_id}=="0x0", ATTR{attr_type}=="1",KERNEL=="*", NAME="{name}"\n'
    
    # Append the string to udev config
    # if write:
        # if os.geteuid() != 0:
            # click.echo("[*] Appending string to udev file. You may be prompted for your password")
            # python_sudo_cmd_str = f"from pathlib import Path; Path('{udev_path}').open('a').write('{udev_str}')"
            # print(python_sudo_cmd_str)
            # print("sudo", ["sudo"] + ["python3"] + ["-c"] + [python_sudo_cmd_str])
            # subprocess.Popen(["sudo", "bash", "-c", f"echo {udev_str} >> {udev_path}"], shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    click.secho("[*] Run this command:", bold=True)
    click.echo("echo 'SUBSYSTEM==\"net\", ACTION==\"add\", DRIVERS==\"?*\",ATTR{address}==\"a0:ce:c8:31:6e:cb\",ATTR{dev_id}==\"0x0\", ATTR{type}==\"1\",KERNEL==\"*\", NAME=\"usb-hub-silver\"' | sudo tee -a /etc/udev/rules.d/60-persistent-net.rules")


@cli.command('maps', help='Open Google Maps with a specific user ID.', context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--id', help='User ID to open as.', default=1, type=click.INT)
@click.pass_context
def maps(ctx, id):
    """
    Open Google Maps with the specified user ID
    """
    click.launch('https://www.google.com/maps/?authuser={}'.format(id))
