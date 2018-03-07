import csv
from pprint import pprint
import json

# Third party Libraries
import click
from gophish import Gophish
from gophish.models import *
import requests
import pendulum
from pytz import timezone
from tabulate import tabulate

# My Junk
from lazyLib import lazyTools

__version__ = '0.1'

requests.packages.urllib3.disable_warnings()

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(name='gocampign', help='A collection of tools to send a GoPhish phishing campaign.', context_settings=CONTEXT_SETTINGS, cls=lazyTools.AliasedGroup)
@click.pass_context
def cli(ctx):
    """
    A collection of tools for GoPhish campaigns.
    """
    pass

@cli.command('schedule-campaign', help='Schedule campaigns with corresponding groups and a timing offset.', context_settings=CONTEXT_SETTINGS)
# @click.argument('campign-prefix', type=click.STRING)
@click.option('-s', '--section-name', help='Name of the config section to use.', type=click.STRING, required=True)
@click.option('-r', '--send-rate', help='The delta to schedule each group after prior one. Time is in minutes', type=click.INT)
@click.option('-c', '--campaign-name', help='Set the base name of each campaign. i.e. GPS_Campaign becomes  GPS_Campaign_1', type=click.STRING, default='Phishing_Campaign')
@click.option('-g', '--group-name', help='Set the base name of each group. i.e. GPS_Group becomes  GPS_Group_1', type=click.STRING, default='Phishing_Campaign')
@click.pass_context
def schedule_campaign(ctx, group_name, campaign_name, section_name, send_rate):
    """
    Create Campaigns for sending each group with a time delay.
    """
    config_options = lazyTools.TOMLConfigCTXImport(ctx)

    debug = ctx.parent.parent.params['debug']

    group_found = False
    group_counter = 0
    campaignNameList = list()
    utc = pendulum.timezone('UTC')
    est = pendulum.timezone('EST')

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
                    click.secho('The VPN does not appear to be connected. Try again after connecting to the VPN. ')
                    raise click.Abort()

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
                click.secho('[*] A list of groups was successfully acquired.', fg='green')

            # BEGIN CAMPAIGN SETUP SECTION
            # Format Campaign Name
            campaign_name = campaign_name.replace(' ', '_')

            # Get list of active campaigns
            campaigns = api.campaigns.get()

            # Make a list to ensure that we don't make a campaign with the same name
            for campaign in campaigns:
                campaignNameList.append(campaign.name)

            # start_date = pendulum.now('UTC')

            start_date = pendulum.from_format('2018-03-07 15', '%Y-%m-%d %H')

            start_date = utc.convert(start_date)

            # BEGIN GROUP SETUP SECTION
            group_name = group_name.replace(' ', '_')

            with click.progressbar(groups, length=len(groups), label='Campaigns Added', show_eta=False) as bar:
                for group in bar:
                    if group.name.startswith(group_name):
                        group_found = True
                        group_counter += 1
                        if debug:
                            click.secho('\n[*] {} matches and will be included in campaign setup.'.format(group.name))

                        final_campaign_name = "{}_{}".format(campaign_name, group_counter)

                        launch_date = datetime.strptime(start_date.add(minutes=send_rate*group_counter).format('%b %d %Y %I:%M%p'), '%b %d %Y %I:%M%p')

                        # launch_date = launch_date.replace(tzinfo=timezone('UTC'))

                        # Commented because progress bar
                        # if debug:
                        #     click.echo('[*] Start time will be {} EST.'.format(est.convert(launch_date)))
                        launch_date = launch_date.strftime("%Y-%m-%dT%H:%M:%S+00:00")


                        # Add a campaign and append each group to it pending campaign doesn't exist
                        headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
                        url = 'https://localhost:3333/api/campaigns/?api_key=fbe27eec3692aad93bd4d57cd25c327e4306f85592ba9ab27a9303a2ca77870c'

                        # ToDo: Add a way to dynamically specify templates, URL, landing page, SMTP sending profile and start date for launch
                        data = json.dumps({"name": final_campaign_name, "template": {"name": "Stein Mart Landing"}, "url": "https://steinmart.org", "page": {"name": "Stein Mart Office 365 Landing page"}, "smtp": {"name": "Sendgrid Spoof"}, "launch_date": launch_date, "groups":[{"name": group.name}]})
                        r = requests.post(url, data=data, headers=headers, verify=False)
                        # ToDo: Add error parsing
                        if debug:
                             click.echo(r.text)

            if group_found == False:
                click.secho('[!] No groups were found that start with {} .'.format(group_name), bold=True, show_pos=True)
                raise click.Abort()

            click.echo('[!] Done adding campaigns!')
            # for campaign in campaigns:
            #     pprint(vars(campaign))

    else:
        raise click.BadParameter('The section name \'{}\' doesn\'t appear to exist. Check the config file and try again.'.format(ctx.params['section_name']))


@cli.command('delete-campaign', help='Remove campaigns with a given prefix.', context_settings=CONTEXT_SETTINGS)
@click.argument('campaign-prefix', type=click.STRING)
@click.option('-s', '--section-name', help='Name of the config section to use.', type=click.STRING, required=True)
@click.pass_context
def delete_campaign(ctx, campaign_prefix, section_name):
    """
    Remove campaigns that start with a given prefix.
    """
    config_options = lazyTools.TOMLConfigCTXImport(ctx)

    debug = ctx.parent.parent.params['debug']
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
                if lazyTools.ConnectedToVPN(ctx.parent.parent.params['config_path']):
                    # Connected to VPN
                    if debug:
                        click.secho('[*] Connected to VPN', fg='green')
                else:
                    click.secho('The VPN does not appear to be connected. Try again after connecting to the VPN. ')
                    raise click.Abort()

            # Connect to GoPhish server
            if debug:
                click.echo('[*] Using hostname: https://{hostname}:{port}'.format(hostname=config_options['gophish'][section_name.lower()]['Hostname'], port=config_options['gophish'][section_name.lower()]['Port']))
                if config_options['gophish'][section_name.lower()]['Verify_SSL']:
                    click.echo('[*] SSL connections will be verified.')
                else:
                    click.secho('[*] SSL connections will not be verified.', bold=True)

            api = Gophish(config_options['gophish'][section_name.lower()]['api_key'], host='https://{hostname}:{port}'.format(hostname=config_options['gophish'][section_name.lower()]['Hostname'], port=config_options['gophish'][section_name.lower()]['Port']), verify=config_options['gophish'][section_name.lower()]['Verify_SSL'])

            # BEGIN CAMPAIGN SETUP SECTION
            # Format Campaign Name
            campaign_prefix = campaign_prefix.replace(' ', '_')

            # Get list of active campaigns
            campaigns = api.campaigns.get()

            if len(campaigns) == 0:
                click.secho('[!] No campaigns match the campaign-prefix {}.'.format(campaign_prefix))
                raise click.Abort()

            with click.progressbar(campaigns, length=len(campaigns), label='Campaigns Removed', show_eta=False, show_pos=True) as bar:
                for c in bar:
                    if c.name.startswith(campaign_prefix):
                        if debug:
                            click.echo('[*] Deleting campaign {}'.format(c.name))
                        # pprint(vars(c), indent=4)
                        response = api.campaigns.delete(campaign_id=c.id)


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
    print(tabulate(listUsersInDict(group), headers='keys', tablefmt="grid"))