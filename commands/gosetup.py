# Standard Libraries
import csv
import os
from pprint import pprint

# Third party Libraries
import aiohttp
import async_timeout
import asyncio
import asyncssh
import click
import asyncGoPhishClient
from gophish import Gophish
from gophish.models import *
import requests
from tabulate import tabulate

# My Junk
from lazyLib import lazyTools

__version__ = '0.1'

requests.packages.urllib3.disable_warnings()

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(name='gosetup', help='A collection of tools to setup a GoPhish phishing campaign.', context_settings=CONTEXT_SETTINGS, cls=lazyTools.AliasedGroup)
@click.pass_context
def cli(ctx):
    """
    A collection of tools for GoPhish campaign setups.
    """
    pass

@cli.command('email-import', help='Import a list of emails into a GoPhish server.', context_settings=CONTEXT_SETTINGS)
@click.argument('user-csv', type=click.Path(exists=True, file_okay=True, dir_okay=True, readable=True, resolve_path=True, allow_dash=False))
@click.option('-g', '--group-size', help='Define the email group size on import.', default='0', type=click.INT)
@click.option('-n', '--group-name', help='Set the base name of each group. i.e. GPS_Group becomes  GPS_Group_1', type=click.STRING, default='Phishing_Campaign')
# @click.option('-d', '--dry-run', help='Show group names and group members, but don\'t push updates to the GoPhish server.', type=click.BOOL, default=False)
@click.option('-s', '--section-name', help='Name of the config section to use.', type=click.STRING, required=True)
@click.pass_context
def email_import(ctx, user_csv, group_size, group_name, section_name):
    """
    Import a list of emails into the GoPhish instance
    """
    usersChunked = dict()

    config_options = lazyTools.TOMLConfigCTXImport(ctx)

    debug = lazyTools.parentSetting(ctx, 'debug')
    verbose = lazyTools.parentSetting(ctx, 'verbose')

    if section_name.lower() in config_options['gophish']:

        # Debug print statement to check if the section name was properly found
        if debug:
            click.secho('[*] Section name found in config file.', fg='green')

        # Check if we need to be on the VPN
        if config_options['gophish'][section_name.lower()]['VPN_Required']:
            # Skip VPN check if debug is True
            if debug:
                click.secho('[*] Skipping VPN check ')
            else:
                if lazyTools.ConnectedToVPN(ctx.parent.parent.params['config_path']):
                    # Connected to VPN
                    if debug:
                        click.secho('[*] Connected to VPN', fg='green')
                else:
                    raise click.Abort('The VPN does not appear to be connected. Try again after connecting to the VPN. ')

        # Connect to GoPhish server
        if debug:
            click.echo('[*] Using hostname: https://{hostname}:{port}'.format(hostname=config_options['gophish'][section_name.lower()]['Hostname'], port=config_options['gophish'][section_name.lower()]['Port']))
            if config_options['gophish'][section_name.lower()]['Verify_SSL']:
                click.echo('[*] SSL connections will be verified.')
            else:
                click.secho('[*] SSL connections will not be verified.', bold=True)

        api = Gophish(config_options['gophish'][section_name.lower()]['api_key'], host='https://{hostname}:{port}'.format(hostname=config_options['gophish'][section_name.lower()]['Hostname'], port=config_options['gophish'][section_name.lower()]['Port']), verify=config_options['gophish'][section_name.lower()]['Verify_SSL'])

        # Try to get list of existing groups
        try:
            groups = api.groups.get()
        except requests.exceptions.ConnectionError as e:
            click.secho('Connection to the GoPhish server failed because {e}. Check the host and try again.'.format(e=e), fg='red')
            raise click.Abort()

        # Check if something went wrong. Error parsing on the part of GoPhish library needs some love.
        if isinstance(groups, Error):
            click.secho('[!] {message}. Remediate the issue and try again.'.format(message=groups.message), fg='red', bold=True)
            raise click.Abort()

        # groups isn't an Error object, so we *should* be good to go.
        if debug:
            click.secho('A list of groups was successfully acquired.', fg='green')

            # List all users in existing groups
            for group in groups:
                # print(group.targets)
                for user in group.targets:
                    pass # print(vars(user))
                # printUsersInGroup(group)


        # Read the CSV file with the users in it.
        with open(user_csv, 'r', encoding='utf-8') as user_csv_file:
            # dialect = csv.Sniffer().sniff(user_csv_file.read(1024))
            # print(vars(dialect))
            userReader = csv.DictReader(user_csv_file, delimiter=',')
            rowList = list()
            for row in userReader:
                rowList.append(row)

        # click.echo(tabulate(rowList, headers='keys', tablefmt="grid"))

        # Divide the list of users into groups by group name
        # Template: <First>_<Second>_<Number
        # i.e. Phishing_Campaign_Remote_4

        group_name = group_name.replace(' ', '_')
        group_name = group_name + '_{}'

        if group_size == 0:
            # Do not divide list of group_size is 0
            usersChunked = {group_name.format(1): rowList}

        else:
            chunks = [rowList[x:x + group_size] for x in range(0, len(rowList), group_size)]

            for count, userListChunk in enumerate(chunks, start=1):
                usersChunked.update({group_name.format(count): userListChunk})

        # For each group in usersChunked, upload
        with click.progressbar(usersChunked, length=len(usersChunked), label='Groups Added', show_eta=False, show_pos=True) as bar:
            for chunkName in bar:
                targetList = list()
                for user in usersChunked[chunkName]:
                    targetList.append(User(first_name=user['First Name'], last_name=user['Last Name'], email=user['Email'], position=user['Position']))
                group = Group(name=chunkName, targets=targetList)

                group = api.groups.post(group)

                if isinstance(group, Error):
                    click.secho('[!] {message}. Remediate the issue and try again.'.format(message=group.message), fg='red', bold=True)
                    raise click.Abort()

                if debug:
                    click.echo('Group {} was successfully added.'.format(group.name))

    else:
        raise click.BadParameter('The section name \'{}\' doesn\'t appear to exist. Check the config file and try again.'.format(ctx.params['section_name']))

@cli.command('delete-groups', help='Delete groups that start with a given string.', context_settings=CONTEXT_SETTINGS)
@click.argument('group-prefix')
@click.option('-s', '--section-name', help='Name of the config section to use.', type=click.STRING, required=True)
@click.pass_context
def delete_groups(ctx, group_prefix, section_name):
    """
    Delete groups that start with a given string.
    """
    config_options = lazyTools.TOMLConfigCTXImport(ctx)

    debug = lazyTools.parentSetting(ctx, 'debug')
    verbose = lazyTools.parentSetting(ctx, 'verbose')

    group_found = False
    group_counter = 0

    if section_name.lower() in config_options['gophish']:

        # Debug print statement to check if the section name was properly found
        if debug:
            click.secho('[*] Section name found in config file.', fg='green')

        # Check if we need to be on the VPN
        if config_options['gophish'][section_name.lower()]['VPN_Required']:
            # Skip VPN check if debug is True
            if debug:
                click.secho('[*] Skipping VPN check ')
            else:
                if lazyTools.ConnectedToVPN(lazyTools.parentSetting(ctx, 'config_path')):
                    # Connected to VPN
                    if debug:
                        click.secho('[*] Connected to VPN', fg='green')
                else:
                    raise click.Abort(
                        'The VPN does not appear to be connected. Try again after connecting to the VPN. ')

        # Connect to GoPhish server
        if debug:
            click.echo('[*] Using hostname: https://{hostname}:{port}'.format(
                hostname=config_options['gophish'][section_name.lower()]['Hostname'],
                port=config_options['gophish'][section_name.lower()]['Port']))
            if config_options['gophish'][section_name.lower()]['Verify_SSL']:
                click.echo('[*] SSL connections will be verified.')
            else:
                click.secho('[*] SSL connections will not be verified.', bold=True)

        api = Gophish(config_options['gophish'][section_name.lower()]['api_key'],
                      host='https://{hostname}:{port}'.format(
                          hostname=config_options['gophish'][section_name.lower()]['Hostname'],
                          port=config_options['gophish'][section_name.lower()]['Port']),
                      verify=config_options['gophish'][section_name.lower()]['Verify_SSL'])

        groups = api.groups.get()

        with click.progressbar(groups, length=len(groups), label='Groups Removed', show_eta=False, show_pos=True) as bar:
            for group in bar:
                groupName = group.name
                group_prefix = group_prefix.replace(' ','_')
                if group.name.startswith(group_prefix):
                    group_found = True
                    group_counter += 1
                    if debug:
                        click.echo('Found group: {}'.format(groupName))

                    deleteResponse = api.groups.delete(group.id)
                    # The response is just a bunch of None and not helpful.

                    if isinstance(deleteResponse, Error):
                        click.secho('[!] {message}. Remediate the issue and try again.'.format(message=deleteResponse.message),
                                    fg='red', bold=True)
                        raise click.Abort()
        if group_found == False:
            click.secho('[!] No groups were found that start with {} .'.format(group_prefix), bold=True)
        else:
            click.secho('[*] {count} groups were found and they were deleted.'.format(count=group_counter), bold=True, fg='green')
    else:
        raise click.BadParameter('The section name \'{}\' doesn\'t appear to exist. Check the config file and try again.'.format(ctx.params['section_name']))

@cli.command('temp',  context_settings=CONTEXT_SETTINGS)
@click.option('-s', '--section-name', help='Name of the config section to use.', type=click.STRING, required=True)
@click.pass_context
def temp(ctx, section_name):
    """
    AsyncIOSSH Port Forward Test
    """
    config_options = lazyTools.TOMLConfigCTXImport(ctx)

    # pprint(config_options, indent=4)

    debug = lazyTools.parentSetting(ctx, 'debug')
    verbose = lazyTools.parentSetting(ctx, 'verbose')

    host = config_options['gophish'][section_name.lower()]['Hostname']
    ssh_username = config_options['gophish'][section_name.lower()]['ssh_username']
    ssh_port = config_options['gophish'][section_name.lower()]['ssh_port']
    ssh_listen_interface = config_options['gophish'][section_name.lower()]['ssh_listen_interface']
    ssh_listen_port = config_options['gophish'][section_name.lower()]['ssh_listen_port']
    gophish_port = config_options['gophish'][section_name.lower()]['gophish_port']
    gophish_interface = config_options['gophish'][section_name.lower()]['gophish_interface']
    api_key = config_options['gophish'][section_name.lower()]['api_key']
    authorized_keys_file = config_options['gophish'][section_name.lower()]['authorized_keys_file']
    id_file = config_options['gophish'][section_name.lower()]['id_file']
    verify = config_options['gophish'][section_name.lower()]['Verify_SSL']


    if section_name.lower() in config_options['gophish']:

        # Debug print statement to check if the section name was properly found
        if debug:
            click.secho('[*] Section name found in config file.', fg='green')

        # Check if we need to be on the VPN
        if config_options['gophish'][section_name.lower()]['VPN_Required']:
            if debug:
                click.echo('[*] Skipping VPN check.')
            else:
                if lazyTools.ConnectedToVPN(lazyTools.parentSetting(ctx, 'config_path')):
                    # Connected to VPN
                    if debug:
                        click.secho('[*] Connected to VPN', fg='green')
                else:
                    raise click.Abort('The VPN does not appear to be connected. Try again after connecting to the VPN. ')

        # Create GoPhish instance
        # go_connect = golib.golib(api_key, gophish_interface, gophish_port, verify=verify)

        try:
            start_event = asyncio.Event()
            exit_event = asyncio.Event()
            # Schedule all setup tasks
            tasks = asyncio.gather(lazyTools.SSHTools.local_port_forward(host, ssh_port, ssh_username, ssh_listen_interface, ssh_listen_port, id_file, gophish_port, gophish_interface, debug, start_event, exit_event), asyncGoPhishClient.Gophish(config_options['gophish'][section_name.lower()]['api_key'], host='https://{hostname}:{port}'.format( hostname=config_options['gophish'][section_name.lower()]['Hostname'], port=config_options['gophish'][section_name.lower()]['Port']), verify=config_options['gophish'][section_name.lower()]['Verify_SSL']))
            # tasks = asyncio.gather(asyncGoPhishClient.Gophish(config_options['gophish'][section_name.lower()]['api_key'], host='https://{hostname}:{port}'.format( hostname=config_options['gophish'][section_name.lower()]['Hostname'], port=config_options['gophish'][section_name.lower()]['Port']), verify=config_options['gophish'][section_name.lower()]['Verify_SSL']))

            # Set up event loop
            event_loop = asyncio.get_event_loop()

            # Start event loop
            event_loop.run_until_complete(tasks)


        except (OSError, asyncssh.Error) as exc:
            click.secho('SSH connection failed: {}'.format(str(exc)), fg='red')
            click.Abort()
        except KeyboardInterrupt:
            click.secho('[!] Keyboard interrupt caught, exiting!', bold=True)
            shutdown(event_loop)
            click.Abort()

    else:
        raise click.BadParameter('The section name \'{}\' doesn\'t appear to exist. Check the config file and try again.'.format(ctx.params['section_name']))

def shutdown(loop):
    for task in asyncio.Task.all_tasks():
        # pprint(task.all_tasks(loop=loop), indent=4)
        # print(help(task))
        click.echo('[*] Canceling task.')
        task.cancel()

def listUsersInDict(group) -> list:
    """
    List users in GoPhish Groups
    :return: List of dictionaries representing rows
    """
    headers = ['ID', 'First Name', 'Last Name', 'Email', 'Position']
    rows = list()
    for user in group.targets:
        rows.append({'ID': user.id, 'First Name': user.first_name, 'Last Name': user.last_name, 'Email': user.email, 'Position': user.position})

    return rows

def printUsersInGroup(group) -> None:
    """
    Print a table of all the users in a specifc group
    """
    click.echo(tabulate(listUsersInDict(group), headers='keys', tablefmt="grid"))


