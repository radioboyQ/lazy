# Standard Lib
import os
from os import walk
import logging
import json
from pprint import pprint
import sys

# 3rd Party Libs
import click
from tabulate import tabulate

# My Junk
from lazyLib import lazyTools
from lazyLib import nessus6Lib
from lazyLib import LazyCustomTypes

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(name='nessus', context_settings=CONTEXT_SETTINGS, invoke_without_command=False)
@click.option('-t', '--target', type=click.STRING, help='Server to upload Nessus file. This should be an IP address or hostanme.')
@click.option('-p', '--port', type=LazyCustomTypes.port, default='8834', help='Port number Nessus server can be accessed on.')
@click.option('-n', '--name', help='Name of a configuration section', default=False)
@click.pass_context
def cli(ctx, target, port, name):
    """
    Parent command to provide options for each child command.

    FUTURE:
        ID system to just use `--name str` to call all settings from a config file.
    :param target: URL or IP of Nessus server
    :type target: str
    :param port: Port number of Nessus server
    :type port: int
    """
    configOptions = lazyTools.TOMLConfigImport(ctx.parent.params['config_path'])

    # pprint(configOptions['nessus'], indent=4)

    if name in configOptions['nessus']:
        # Name given exists, grab hostname, port, access_key, secret_key and determine if VPN is required
        target = configOptions['nessus'][name]['Hostname']
        port = configOptions['nessus'][name]['Port']
        access_key = configOptions['nessus'][name]['access_key']
        secret_key = configOptions['nessus'][name]['secret_key']
        vpn_required = configOptions['nessus'][name]['VPN_Required']

        ctx.obj = {'target': target, 'port': port, 'access_key': access_key, 'secret_key': secret_key, 'vpn_required': vpn_required}

    else:
        if target is None:
            target = click.prompt('[?] What is the hostname or IP of the Nessus server', prompt_suffix='? ')
        if port is None:
            port = click.prompt('[?] What port is the Nessus server accessable on', prompt_suffix='? ', type=LazyCustomTypes.port)

        username = click.prompt('[?] What is your username for Nessus', prompt_suffix='? ')
        password = click.prompt('[?] What is your password for Nessus', prompt_suffix='? ', hide_input=True)

        ctx.obj = {'target': target, 'port': port, 'username': username, 'password': password}



@cli.command(name='upload', context_settings=CONTEXT_SETTINGS, short_help='Upload a folder or series of Nessus files to a server.')
@click.option('-l', '--local-nessus', required=True, type=click.Path(exists=False, file_okay=True, dir_okay=True, readable=True, resolve_path=True), help='Path to local Nessus file(s).')
@click.option('-r', '--remote-folder', type=click.INT, help='Destination folder ID on Nessus server.', required=True)
@click.option('--test', is_flag=True, default=False, help='Test authentication to Nessus server.')
@click.pass_context
def upload(ctx, local_nessus, remote_folder, test):
    """
    Upload lots of Nessus files to a folder in a Nessus Server.
    - Get user credentials - API or username and password
    - Determine if local_nessus is a directory or file
    -- Find all '.nessus' files in directory
    - Upload Nessus file to given folder
    """

    # If local-nessus is a file, skip OS walk and trying to find more Nessus files
    nessus_list = list()
    if os.path.isfile(local_nessus):
        if local_nessus.split('.')[-1:][0] == 'nessus':
            nessus_list.append(os.path.split(local_nessus))
    else:
        for (dirpath, dirnames, filenames) in walk(local_nessus):
            for fn in filenames:
                if fn.split('.')[-1:][0] == 'nessus':
                    nessus_list.append((dirpath, fn))
    # Make sure we actually found a Nessus file to upload
    if len(nessus_list) == 0:
        click.secho('[!] No Nessus files were specified.', fg='red')
        click.secho('[*] Exiting.', fg='green')
        sys.exit()

    if not ctx.obj['target'].startswith('https://'):
        ctx.obj['target'] = 'https://{}'.format(ctx.obj['target'])

    if ctx.obj['target'].endswith('/'):
        ctx.obj['target'] = ctx.obj['target'].replace('/', ':{}'.format(ctx.obj['port']))
    else:
        ctx.obj['target'] = '{}:{}'.format(ctx.obj['target'], ctx.obj['port'])

    # Check if we need to be on the VPN
    if ctx.obj['vpn_required'] == True:
        if lazyTools.ConnectedToVPN(ctx.parent.parent.params['config_path']):
            # Connected to VPN
            pass # print('Connected to VPN')
        else:
            # Not connected to VPN
            raise click.ClickException('Not connected to corporate VPN.')
    # Try to log in with API keys
    if ctx.obj['access_key'] and ctx.obj['secret_key']:
        with nessus6Lib(ctx.obj['target'], api_akey=ctx.obj['access_key'], api_skey=ctx.obj['secret_key']) as nessusAPI:
            if test == False:
                for full_path in nessus_list:
                    print(os.path.basename((os.path.join(full_path[0], full_path[1]))))
                    click.secho('[*] Attempting to upload {}'.format(full_path[1].rstrip()), fg='white')
                    nessusAPI.upload(os.path.join(full_path[0], full_path[1]))
                    click.secho('[*] Upload successful.', fg='green')

                    click.secho('[*] Attempting to import the scan into the correct folder.', fg='white')
                    nessusAPI.scan_import(full_path[1], remote_folder)
                    click.secho('[*] Import successful.', fg='green')
            else:
                click.secho('[*] This was a test. No files were uploaded.', fg='blue', bg='white')
            click.secho('[*] All done!', fg='green')
            nessusAPI._log_out()
    elif ctx.obj['username'] and ctx.obj['password']:
        with nessus6Lib(ctx.obj['target'], login=ctx.obj['username'], password=ctx.obj['password']) as nessusAPI:
            if test == False:
                for full_path in nessus_list:
                    click.secho('[*] Attempting to upload {}'.format(full_path[1].rstrip()), fg='white')
                    nessusAPI.upload(os.path.join(full_path[0], full_path[1]))
                    click.secho('[*] Upload successful.', fg='green')

                    click.secho('[*] Attempting to import the scan into the correct folder.', fg='white')
                    nessusAPI.scan_import(full_path[1], remote_folder)
                    click.secho('[*] Import successful.', fg='green')
            else:
                click.secho('[*] This was a test. No files were uploaded.', fg='blue', bg='white')
            click.secho('[*] All done!', fg='green')
            nessusAPI._log_out()


@cli.command(name='export', short_help='Export a scan or folder of scans from a Nessus server.')
@click.option('-i', '--id', required=True, type=click.INT, help='ID of the scan on the Nessus server.')
@click.option('-o', '--output-path', type=click.Path(exists=False, file_okay=True, dir_okay=True, resolve_path=True, writable=True), help='Location and/or name to save the scan', envvar='PWD')
@click.option('-t', '--target', type=click.STRING, help='Server to export Nessus file. This should be an IP address or hostanme.', default='dc2astns01.asmt.gps')
@click.option('-p', '--port', type=click.INT, default='8834')
@click.option('-eT', '--export-type', help='Define the exported file\'s type.', type=click.Choice(['nessus', 'db', 'pdf', 'html', 'csv']), default='nessus')
@click.option('--test', is_flag=True, default=False, help='Test authentication to Nessus server.')
@click.pass_context
def export(ctx, id, output_path, target, port, test, export_type):
    """
    Export Nessus scans from a file or folder on a remote server
    - Get user credentials - API or username and password
    - Determine if remote Nessus target is folder or a scan
    - If folder:
    -- Get scan IDs in folder
    -- Download scans one by one
    - elif scan
    -- Get scan
    """
    pass


