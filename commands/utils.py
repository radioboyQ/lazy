import os
from pprint import pprint
import sys

import click

# My Junk
from lazyLib import lazyTools

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
                if not returnValue[0]:
                    click.secho(returnValue)
                    click.secho('[!] {}'.format(returnValue[1]), fg='red')
                elif returnValue[0]:
                    click.secho('[*] Share unmounted successfully.', fg='white')
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

