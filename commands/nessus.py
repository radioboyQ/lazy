# Standard Lib
import os
from os import walk
import logging
import json
from pprint import pprint
import sys

# 3rd Party Libs
import click
from lxml import etree
# from tabulate import tabulate

# My Junk
from nessrest.nessrest import ness6rest
from lazyLib import lazyTools
from lazyLib import LazyCustomTypes

__version__ = '1.0'

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(name='nessus', context_settings=CONTEXT_SETTINGS, invoke_without_command=False, short_help='Tools that are useful for interacting with a Nessus scanner.', cls=lazyTools.AliasedGroup)
@click.pass_context
def cli(ctx):
    """
    Parent Nessus command to provide options for each child command.
    """


@cli.command(name='upload', context_settings=CONTEXT_SETTINGS, short_help='Upload a folder or series of Nessus files to a server.')
@click.option('-l', '--local-nessus', required=True, type=click.Path(exists=False, file_okay=True, dir_okay=True, readable=True, resolve_path=True), help='Path to local Nessus file(s).')
@click.option('-r', '--remote-folder', type=click.INT, help='Destination folder ID on Nessus server.', required=True)
@click.option('--test', is_flag=True, default=False, help='Test authentication to Nessus server.')
@click.option('-t', '--target', type=click.STRING, help='Server to upload Nessus file. This should be an IP address or hostanme.')
@click.option('-p', '--port', type=LazyCustomTypes.port, default='8834', help='Port number Nessus server can be accessed on.')
@click.option('-n', '--name', help='Name of a configuration section', default='dc2astns02')
@click.pass_context
def upload(ctx, local_nessus, remote_folder, test, target, port, name):
    """
    Upload lots of Nessus files to a folder in a Nessus Server.
    - Get user credentials - API or username and password
    - Determine if local_nessus is a directory or file
    -- Find all '.nessus' files in directory
    - Upload Nessus file to given folder
    """

    # Check server information
    ctx, target, port, name = lazyTools.checkNessusServerConfig(ctx, target, port, name)


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

        nessusAPI = ness6rest.Scanner(url=ctx.obj['target'], api_akey=ctx.obj['access_key'], api_skey=ctx.obj['secret_key'], insecure=True)
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
    elif ctx.obj['username'] and ctx.obj['password']:
            nessusAPI = ness6rest.Scanner(ctx.obj['target'], login=ctx.obj['username'], password=ctx.obj['password'], insecure=True)
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


@cli.command(name='download', short_help='Export a scan or folder of scans from a Nessus server.')
@click.option('-i', '--id', required=True, type=click.INT, help='ID of the scan or folder on the Nessus server.')
@click.option('-o', '--output-path', type=click.Path(exists=False, file_okay=True, dir_okay=True, resolve_path=True, writable=True), help='Location and/or name to save the scan', envvar='PWD')
@click.option('-eT', '--export-type', help='Define the exported file\'s type.', type=click.Choice(['nessus', 'pdf', 'html', 'csv']), default='nessus')
@click.option('--test', is_flag=True, default=False, help='Test authentication to Nessus server.')
@click.option('-t', '--target', type=click.STRING, help='Server to upload Nessus file. This should be an IP address or hostanme.')
@click.option('-p', '--port', type=LazyCustomTypes.port, default='8834', help='Port number Nessus server can be accessed on.')
@click.option('-n', '--name', help='Name of a configuration section', default='dc2astns02')
@click.pass_context
def export(ctx, id, output_path, test, export_type, target, port, name):
    """
    Download Nessus scans from a file or folder on a remote server
    - Get user credentials - API or username and password
    - Determine if remote Nessus target is folder or a scan
    - If folder:
    -- Get scan IDs in folder
    -- Download scans one by one
    - elif scan
    -- Get scan
    """

    # Check server information
    ctx, target, port, name = lazyTools.checkNessusServerConfig(ctx, target, port, name)

    # Check if we need to be on the VPN
    if ctx.obj['vpn_required'] == True:
        if lazyTools.ConnectedToVPN(ctx.parent.parent.params['config_path']):
            # Connected to VPN
            pass  # print('Connected to VPN')
        else:
            # Not connected to VPN
            raise click.ClickException('Not connected to corporate VPN.')

    if ctx.obj['access_key'] and ctx.obj['secret_key']:
        folderIDDict = dict()
        scanIDDict = dict()

        nessusAPI = ness6rest.Scanner(url=ctx.obj['target'], api_akey=ctx.obj['access_key'], api_skey=ctx.obj['secret_key'], debug=False)

        scanFolderDict = nessusAPI.scan_list()

        click.secho('[*] Downloaded scan and folder data. Checking if provided ID is valid.')

        # Get list of folder IDs
        for folder in scanFolderDict['folders']:
            folderIDDict.update({folder['id']: folder['name']})

        # Get list of scan IDs
        for scans in scanFolderDict['scans']:
            scanIDDict.update({scans['id']:scans['name']})

        # Check if ID is in scans list
        if id in scanIDDict:
            nessusAPI.scan_id = id
            click.secho('[*] Downloading scan: {}'.format(scanIDDict[id]))
            scanString = nessusAPI.download_scan(export_format=export_type)

            click.secho('[*] Downloaded scan: {}'.format(scanIDDict[id]))
            with open('{}.{}'.format(os.path.join(output_path, scanIDDict[id]), export_type), 'wb') as f:
                f.write(scanString)
            click.secho('[*] Saved {}.{} to disk.'.format(scanIDDict[id], export_type))
        elif id in folderIDDict:
            click.secho('[*] Downloading from folder {}'.format(folderIDDict[id]))
            for scans in scanFolderDict['scans']:
                if scans['folder_id'] == id:
                    click.secho('[+] Downloading scan: {}'.format(scans['name']))
                    nessusAPI.scan_id = scans['id']
                    scanString = nessusAPI.download_scan(export_format=export_type)

                    # click.secho('[*] Downloaded scan: {}'.format(scans['name']))
                    with open('{}.{}'.format(os.path.join(output_path, scans['name']), export_type), 'wb') as f:
                        f.write(scanString)
                    click.secho('[*] Saved {}.{} to disk.'.format(scans['name'], export_type))
        else:
            raise click.BadParameter('{} is not a valid scan or folder number'.format(id))

@cli.command(name='sslippycup', short_help='Display all the hosts and ports with a valid SSL/TLS cert.')
@click.argument('nessus_files', nargs=-1, type=click.Path(exists=True, file_okay=True, dir_okay=True, resolve_path=True,readable=True))
@click.option('-p', '--plugin-id', help='Plugin ID to export hostname and ports for. Default plugin: \'SSL Certificate Information\' : 10863', type=click.STRING, default='10863')
@click.pass_context
def sslippycup(ctx, nessus_files, plugin_id):
    """
    Display all the hosts and their ports associated to the given Nessus plugin ID.
    """

    outlist = list()

    nessus_list = list()


    for entry in nessus_files:
        if os.path.isfile(entry):
            if entry.split('.')[-1:][0] == 'nessus':
                nessus_list.append(os.path.split(entry))
        elif os.path.isdir(entry):
            for (dirpath, dirnames, filenames) in walk(entry):
                for fn in filenames:
                    if fn.split('.')[-1:][0] == 'nessus':
                        nessus_list.append((dirpath, fn))

    # Make sure we actually found a Nessus file to play with
    if len(nessus_list) == 0:
        click.secho('[!] No Nessus files were specified.', fg='red')
        click.secho('[*] Exiting.', fg='green')
        sys.exit()

    for file in nessus_list:
        nessus_file_path = os.path.join(file[0], file[1])
        if os.path.isfile(nessus_file_path):
            try:
                tree = etree.parse(nessus_file_path)

                root = tree.getroot()

                for i in root.xpath('./Report/ReportHost/ReportItem'):
                    if i.attrib['pluginID'] == plugin_id:
                        for h in i.xpath('..'):
                            hostname = h.attrib['name']

                        port = i.attrib['port']

                        final_str = '{}:{}'.format(hostname, port)

                        if final_str not in outlist:
                            outlist.append(final_str)
            except:
                click.echo('An error occured, are you sure that you\'ve got a Nessus file?')
                click.echo(sys.exc_info()[0])
                sys.exit(1)

    for host_port in outlist:
        click.echo(host_port)