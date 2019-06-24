import asyncio
import collections
import concurrent.futures
from datetime import datetime, timedelta
import itertools
from pathlib import Path
from pprint import pprint
import sys
import time
import threading

import asyncssh
import click
from gophish import Gophish
from gophish.models import *
import pendulum
import pytz
from tabulate import tabulate

# Create logger
from loguru import logger
# Remove base logger from loguru
logger.remove(0)

# Disable warning about insecure requests
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

async def run_client(ctx):
    """
    Actual SSH client running in a AsyncIO event loop
    """

    logger.debug(f"Server: {ctx.parent.params['server']}")
    logger.debug(f"Port: {ctx.parent.params['ssh_port']}")
    logger.debug(f"Username: {ctx.parent.params['ssh_username']}")
    logger.debug(f"SSH Key Files: {ctx.obj['ssh_key_files']}")
    logger.debug(f"GoPhish Server: {ctx.parent.params['gophish_server']}")
    logger.debug(f"GoPhish Port: {ctx.parent.params['gophish_port']}")

    async with asyncssh.connect(host=ctx.parent.params['server'], port=ctx.parent.params['ssh_port'],
                                username=ctx.parent.params['ssh_username'], client_keys=ctx.obj['ssh_key_files'],
                                known_hosts=None) as conn:
        logger.debug(f"SSH connected to the server successfully")

        # See if 'port' is set in the params
        try:
            ssh_port = ctx.params['port']
        except:
            ssh_port = 0


        listener = await conn.forward_local_port('', ssh_port, ctx.parent.params['gophish_server'],
                                                 ctx.parent.params['gophish_port'])
        logger.debug(f"Tunnel is started and running")

        ctx.obj.update({'listener_port': listener.get_port()})
        # click.secho(f"Tunnel is listening on port {listener.get_port()}", bold=True)
        # await asyncio.sleep(1.0)
        ctx.obj['tunnel_active'].set()
        while not ctx.obj['tasks_done'].is_set():
            logger.debug(f'Waiting for tasks to finish.')
            await asyncio.sleep(1.0)
            # await listener.wait_closed()
        logger.debug('Tasks are done')
        listener.close()

def get_ssh_client_keys(ctx):
    """
    From the source directory, add to a list the path of any SSH keys that are found and return the list
    """
    ssh_key_files = list()
    # ctx, api_key, server, gophish_port, ssh_port, ssh_key, ssh_username, verify, campaign_name, url, dry_run):

    # Find all the SSH keys
    ssh_key_path = Path(ctx.params['ssh_key'])
    if ssh_key_path.is_dir():
        # The path given is a directory
        # Only parse the files that end in .nessus
        ssh_key_files_start_id = sorted(ssh_key_path.glob('**/id_*'))
        for key in ssh_key_files_start_id:
            if len(key.suffixes) is 0 and key.is_dir() is False:
                logger.debug(f"Found key: {key}")
                ssh_key_files.append(str(key))
    elif ssh_key_path.is_file():
        # The path given is a ssh key file
        # Validate the file starts with id_ and does not end with *.pub
        if len(ssh_key_path.suffixes) is 0 and ssh_key_path.is_dir() is False:
            logger.debug(f"Found key: {ssh_key_path}")
            ssh_key_files.append(str(ssh_key_path))
        else:
            logger.error(f"Looks like this key is not a private key {ssh_key_path}")
    else:
        logger.error(f"This is not a file or a directory: {ssh_key_path}")
    return ssh_key_files

async def async_sleep_shim(time):
    """
    A wrapper around the asyncio.sleep() function

    If I can figure out a way to do something similar to `asyncio.run(await asyncio.sleep(time))` that would be better
    But this works for now
    """

    await asyncio.sleep(time)


class Spinner(object):
    """
    Create a loading bar spinner
    Based off of: https://github.com/click-contrib/click-spinner
    """

    spinner_cycle = itertools.cycle(['-', '/', '|', '\\'])

    def __init__(self, title=None, beep=False, disable=False, force=False, suffix=': '):
        # logger.info("Class Init")
        self.disable = disable
        if title is not None:
            self.title = title.rstrip()
        else:
            self.title = title
        self.beep = beep
        self.force = force
        self.stop_running = None
        self.spin_thread = None
        self.term_width = click.get_terminal_size()[0]
        self.suffix = suffix

    def start(self):
        # logger.info("Start Function")
        if self.disable:
            return
        if sys.stdout.isatty() or self.force:
            self.stop_running = threading.Event()
            self.spin_thread = threading.Thread(target=self.init_spin)
            self.spin_thread.start()

    def stop(self):
        # logger.info("\nStop Function")
        if self.title is not None:
            sys.stdout.write('\r')
            sys.stdout.write(' ' * self.term_width)
            sys.stdout.flush()
        else:
            sys.stdout.write('\r')

        if self.spin_thread:
            self.stop_running.set()
            self.spin_thread.join()

    def init_spin(self):
        # logger.info("Init Function")
        while not self.stop_running.is_set():
            # logger.info("Just keep spinning")

            # If there is a title, use it
            if self.title is not None:
                sys.stdout.write(f"{self.title}{self.suffix}{next(self.spinner_cycle)}")
                sys.stdout.flush()
                time.sleep(0.25)
                sys.stdout.write('\r')
                # sys.stdout.write('\b' * self.term_width)
                sys.stdout.flush()
            else:
                # No title specified, just be normal
                sys.stdout.write(next(self.spinner_cycle))
                sys.stdout.flush()
                time.sleep(0.25)
                sys.stdout.write('\b')
                sys.stdout.flush()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.disable:
            return False
        self.stop()
        if self.beep:
            sys.stdout.write('\7')
            sys.stdout.flush()
        return False

class Prompt:
    """
    Wait for user to push any key in an way that's nonblocking
    """
    def __init__(self, loop=None, end='', flush=True):
        self.loop = loop or asyncio.get_event_loop()
        self.q = asyncio.Queue(loop=self.loop)
        self.loop.add_reader(sys.stdin, self.got_input)
        self.end = end
        self.flush = flush

    def got_input(self):
        asyncio.ensure_future(self.q.put(sys.stdin.readline()), loop=self.loop)

    async def __call__(self, msg):
        sys.stdout.write(f"{msg}{self.end}")
        sys.stdout.flush()
        return (await self.q.get()).rstrip('\n')

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(name="gophish-cli", short_help="Useful GoPhish tools.", context_settings=CONTEXT_SETTINGS, invoke_without_command=False)
@click.option('-a', '--api-key', default='cb96f796693a7fb4baf9605e0d7c984151ff8487e87020c8150474158d1a9343', help='API key for GoPhish server', type=click.STRING)
@click.option('--server', help='GoPhish server address where it can be reached', type=click.STRING, required=True)
@click.option('--verify', default=False, help='Verify the SSL certificate', type=click.BOOL, show_default=True)
@click.option('--gophish-port', default=3333, help='GoPhish admin port', type=click.INT)
@click.option('--gophish-server', default='localhost', type=click.STRING, help='GoPhish server address. If you\'re not sure what this is, leave it blank')
@click.option('--ssh-port', default=22, help='Port SSH is running on the server.', type=click.INT)
@click.option('--ssh-key', help='Path to desired SSH key.', type=click.Path(exists=True, file_okay=True, dir_okay=True, readable=True, resolve_path=True, allow_dash=True), default=lambda: str(Path.home().joinpath('.ssh/')))
@click.option('--ssh-username', help='Specify an username to use for the SSH connection', type=click.STRING, required=True)
@click.pass_context
def cli(ctx, api_key, server, verify, gophish_port, gophish_server, ssh_port, ssh_key, ssh_username):
    """
    Group for holding GoPhish tools
    """

    loguru_fmt_str = "{level: <10} - {function: <20} - {message}"

    if ctx.parent.params['debug']:
        logger.add(sys.stdout, level="DEBUG", format=loguru_fmt_str)
    else:
        # logger.add(sys.stdout, level="INFO", filter=f"__main__", format=loguru_fmt_str)
        logger.add(sys.stdout, level="INFO", format=loguru_fmt_str)

    logger.debug("Starting group command")

    # Use Click's context manager to track common objects
    ctx.obj = {"tunnel_active": threading.Event(), "tasks_done": threading.Event(), "logger": logger, "thread_count": 1}
    logger.debug(f"Added to Click's Context Object: {ctx.obj}")

    # Get list of SSH keys
    ssh_key_files = get_ssh_client_keys(ctx)

    # Update context object
    ctx.obj.update({'ssh_key_files': ssh_key_files})
    logger.debug(f"Added to Click's Context Object: {ctx.obj}")


@cli.command(name='keep-open', context_settings=CONTEXT_SETTINGS, help="Hold SSH Connection Open")
@click.option('-p', '--port', help='Specify which port to use for the client side of the SSH tunnel. 0 is a random port', type=click.IntRange(min=0, max=65535), default=0, show_default=True)
@click.pass_context
def hold_open(ctx, port):
    """
    Hold open a SSH tunnel
    """
    logger = ctx.obj['logger']

    # Create event loop
    loop = asyncio.get_event_loop()
    run_client_future = asyncio.gather(run_client(ctx))
    hold_open_future = asyncio.gather(hold_open_shim(ctx))
    all_tasks = asyncio.gather(hold_open_future, run_client_future)

    results = loop.run_until_complete(all_tasks)

    loop.close()

async def hold_open_shim(ctx):
    """
    Function that controls the SSH tunnel
    """
    tunnel_active = ctx.obj['tunnel_active']
    tasks_done = ctx.obj['tasks_done']
    debug = ctx.parent.parent.params['debug']

    prompt = Prompt()

    if debug:
        # If debug is set, don't make the spinner
        while not tunnel_active.is_set():
            logger.debug(f"Is the tunnel active: {tunnel_active.is_set()}")
            # Don't loop so fast, give the CPU a chance to do something else
            await asyncio.sleep(0.1)
    else:
        with Spinner(title="Waiting on SSH tunnel to be ready", beep=False, disable=False, force=False):
            while not tunnel_active.is_set():
                # Don't loop so fast, give the CPU a chance to do something else
                await asyncio.sleep(0.1)

    # Now that the tunnel is ready, we can define 'gophish_port'
    # Use this in place of the defined 'gophish_port' as SSH will be listening on a dynamic port but always
    # forwarded to 'gophish_port'
    gophish_port = ctx.obj['listener_port']

    click.secho(f"[*] The SSH tunnel is up. Access to GoPhish via a web browser or script with this URL: ", bold=True)
    click.echo(f"https://{ctx.parent.params['gophish_server']}:{gophish_port}\n")

    # with Spinner(title="SSH Tunnel Is Active: ", beep=False, disable=False, force=False):
    #     time.sleep(0.1)  # await asyncio.sleep(5)

    await prompt("SSH Tunnel Is Active, press any key to stop ... ")

    click.secho(f"[*] Exiting tunnel")
    tasks_done.set()


@cli.command(name='start', context_settings=CONTEXT_SETTINGS, help="Start a New Campaign")
@click.option('-c', '--campaign-name', default='Test', type=click.STRING, help='Set the campaign name')
@click.option('--url', help='URL the campaign redirects to. Should be the domain of the server', type=click.STRING, required=True)
@click.option('-n', '--dry-run', help='Don\'t actually push the campaign, just show what it would have done', default=False, is_flag=True, type=click.BOOL)
@click.option('-g', '--group-name', help="The group name of targets", default="Test", show_default=True)
@click.pass_context
def start_campaign(ctx, campaign_name, url, dry_run, group_name):
    """
    Create a GoPhish campaign
    """

    logger = ctx.obj['logger']

    loop = asyncio.get_event_loop()
    run_client_future = asyncio.gather(run_client(ctx))
    campaign_start_future = asyncio.gather(campaign_start_shim(ctx, campaign_name, url, dry_run, group_name))

    all_tasks = asyncio.gather(campaign_start_future, run_client_future)

    results = loop.run_until_complete(all_tasks)

    loop.close()

    logger.debug(f"Finished event loop")

async def campaign_start_shim(ctx, campaign_name, url, dry_run, group_name, loop):
    """
    Run the blocking code in a executor
    """

    logger = ctx.obj['logger']

    logger.debug(f"Starting thread pool with {ctx.obj['thread_count']} threads")
    # Only create 2 threads because we only have 2 tasks
    with concurrent.futures.ThreadPoolExecutor(max_workers=ctx.obj['thread_count'], thread_name_prefix="ThreadPool1-") as pool:
        result = await loop.run_in_executor(pool, campaign_status_helper, ctx, campaign_name, url, dry_run, group_name)

def campaign_start_helper(ctx, campaign_name, url, dry_run, group_name):
    # Get all the parent options
    verify = ctx.parent.params['verify']
    api_key = ctx.parent.params['api_key']
    gophish_server = ctx.parent.params['gophish_server']
    tunnel_active = ctx.obj['tunnel_active']
    tasks_done = ctx.obj['tasks_done']
    debug = ctx.parent.parent.params['debug']

    if debug:
        # If debug is set, don't make the spinner
        while not tunnel_active.is_set():
            logger.debug(f"Is the tunnel active: {tunnel_active.is_set()}")
            # Don't loop so fast, give the CPU a chance to do something else
            asyncio.run(async_sleep_shim(1.0))
    else:
        with Spinner(title="Waiting on SSH tunnel to be ready", beep=False, disable=False, force=False):
            while not tunnel_active.is_set():
                # Don't loop so fast, give the CPU a chance to do something else
                asyncio.run(async_sleep_shim(1.0))

    # Now that the tunnel is ready, we can define 'gophish_port'
    # Use this in place of the defined 'gophish_port' as SSH will be listening on a dynamic port but always forwarded to 'gophish_port'
    gophish_port = ctx.obj['listener_port']

    api = Gophish(api_key, host=f"https://{gophish_server}:{gophish_port}", verify=verify)

    if dry_run:
        # Variables
        campaigns_in_list = list()
        # It's a dry run, don't actually post the campaign
        summaries = api.campaigns.summary()
        for c in summaries.campaigns:
            # Get all campaign data
            complete_date = c.completed_date
            create_date = c.created_date
            campaign_id = c.id
            launch_date = c.launch_date
            name = c.name
            send_by_date = c.send_by_date
            status = c.status
            stats = c.stats

            campaigns_in_list.append(dict(
                {"Completed Date": complete_date, "Created Date": create_date, "Campaign ID": campaign_id,
                 "Launch Date": launch_date, "Name": name, "Send By Date": send_by_date, "Status": status}))

        click.echo(tabulate(campaigns_in_list, headers="keys", tablefmt="fancy_grid"))

    else:
        # Variables
        campaigns_in_list = list()
        # Configure campaign
        groups = [Group(name=group_name)]
        page = Page(name='Office365Login')
        template = Template(name='Office365Template')
        smtp = SMTP(name='Office365_greenteohcapital_profile')
        url = url
        send_by_date = datetime.now(pytz.timezone('US/Mountain')) + timedelta(hours=2)
        campaign = Campaign(
            name=campaign_name, groups=groups, page=page,
            template=template, smtp=smtp, url=url, send_by_date=send_by_date)

        # Get all campaign data
        create_date = campaign.created_date
        launch_date = campaign.launch_date
        name = campaign.name
        send_by_date = campaign.send_by_date
        status = campaign.status
        groups = campaign.groups[0].name
        page = campaign.page
        template = campaign.template
        smtp = campaign.smtp

        campaigns_in_list.append(dict(
            {"Created Date": create_date, "Launch Date": launch_date, "Name": name, "Send By Date": send_by_date,
             "Groups": groups, "Page": page.name, "Template": template.name, "SMTP": smtp.name}))

        click.secho(f"\n[*] This is the campaign that's going to be created. Is this what you want?\n", bold=True)
        click.echo(tabulate(campaigns_in_list, headers="keys", tablefmt="fancy_grid"))

        # Real deal, post the campaign
        if click.confirm(f"You're making a real campaign, are you sure?", abort=True):
            # Variables
            campaigns_in_list = list()

            # click.secho(f"\nThis would have made a real campaign, but it didn't. Fix that code!", bold=True)
            campaign_post_return = api.campaigns.post(campaign)

            # Get all campaign data
            create_date = campaign_post_return.created_date
            launch_date = campaign_post_return.launch_date
            name = campaign_post_return.name
            send_by_date = campaign_post_return.send_by_date
            status = campaign_post_return.status
            groups = campaign_post_return.groups[0]["name"]
            page = campaign_post_return.page.name
            template = campaign_post_return.template.name
            smtp = campaign_post_return.smtp.name

            campaigns_in_list.append(dict(
                {"Created Date": create_date, "Launch Date": launch_date, "Name": name, "Send By Date": send_by_date,
                 "Groups": groups, "Page": page, "Template": template, "SMTP": smtp, "Status": status}))

            click.secho(tabulate(campaigns_in_list, headers="keys", tablefmt="fancy_grid"))
    logger.debug(f"Looks like everything is done, setting tasks_done flag")
    tasks_done.set()


@cli.command('status', short_help="General Campaign Information", context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--campaign-id', help="The ID of a specific campaign to get", default=0, show_default=True,
              type=click.INT)
@click.option('-g', '--group-id', help="Show the status of a specific group of targets", show_default=False, default=0)
@click.pass_context
def campaign_status(ctx, campaign_id, group_id):
    """
    Just get the campaign status, not details
    """
    logger = ctx.obj['logger']

    loop = asyncio.get_event_loop()
    run_client_future = asyncio.gather(run_client(ctx))
    campaign_status_future = asyncio.gather(campaign_status_shim(ctx, campaign_id, group_id, loop))

    all_tasks = asyncio.gather(campaign_status_future, run_client_future)

    results = loop.run_until_complete(all_tasks)

    loop.close()

    logger.debug(f"Finished event loop")


async def campaign_status_shim(ctx, campaign_id, group_id, loop):
    """
    Run the blocking code in a executor
    """
    thread_count = 2
    logger = ctx.obj['logger']

    logger.debug(f"Starting thread pool with {thread_count} threads")
    # Only create 2 threads because we only have 2 tasks
    with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count, thread_name_prefix="ThreadPool1-") as pool:
        result = await loop.run_in_executor(pool, campaign_status_helper, ctx, campaign_id, group_id)


def campaign_status_helper(ctx, campaign_id, group_id):
    """
    Just get the campaign status, not details
    """
    # Get all the parent options
    verify = ctx.parent.params['verify']
    api_key = ctx.parent.params['api_key']
    gophish_server = ctx.parent.params['gophish_server']
    logger = ctx.obj['logger']
    tunnel_active = ctx.obj['tunnel_active']
    tasks_done = ctx.obj['tasks_done']
    debug = ctx.parent.parent.params['debug']

    # Variables
    campaigns_in_list = list()
    stats_bool = False

    """
    Example campaign data
        {
        'completed_date': '2019-06-13T17:06:43.696866614Z',
        'created_date': '2019-06-13T16:34:07.811474483Z',
        'id': 11,
        'launch_date': '2019-06-13T16:31:00Z',
        'name': 'RealPhishingCampaign',
        'send_by_date': '0001-01-01T00:00:00Z',
        'stats': <gophish.models.Stat object at 0x7f0ecf8c56d8>,
        'status': 'Completed'
        }
        """

    if debug:
        # If debug is set, don't make the spinner
        while not tunnel_active.is_set():
            logger.debug(f"Is the tunnel active: {tunnel_active.is_set()}")
            # Don't loop so fast, give the CPU a chance to do something else
            asyncio.run(async_sleep_shim(1.0))
    else:
        with Spinner(title="Waiting on SSH tunnel to be ready", beep=False, disable=False, force=False):
            while not tunnel_active.is_set():
                # Don't loop so fast, give the CPU a chance to do something else
                asyncio.run(async_sleep_shim(1.0))

    # Now that the tunnel is ready, we can define 'gophish_port'
    # Use this in place of the defined 'gophish_port' as SSH will be listening on a dynamic port but always
    # forwarded to 'gophish_port'
    gophish_port = ctx.obj['listener_port']

    api = Gophish(api_key, host=f"https://{gophish_server}:{gophish_port}", verify=verify)

    # If the user didn't specify a campaign, get them all
    if campaign_id == 0:
        summaries = api.campaigns.summary()
        for c in summaries.campaigns:
            # Get all campaign data
            complete_date_raw = c.completed_date
            create_date_raw = c.created_date
            campaign_id = c.id
            launch_date = c.launch_date
            name = c.name
            send_by_date = c.send_by_date
            status = c.status
            stats = c.stats

            # Convert all the dates to be human readable
            create_date = pendulum.parse(create_date_raw).in_tz('America/Denver').to_day_datetime_string()

            # If the campaign isn't done yet, fill in the field rather than parsing a datetime string
            if status != "Completed":
                complete_date = "Campaign Not Completed Yet"
            else:
                complete_date = pendulum.parse(complete_date_raw)
                complete_date = complete_date.in_tz('America/Denver').to_day_datetime_string()

            launch_date = pendulum.parse(launch_date).in_tz('America/Denver').to_day_datetime_string()

            if send_by_date == "0001-01-01T00:00:00Z":
                # Send by date not set
                send_by_date = "Not Set"
            else:
                # Send by date has been set. Parse that datetime string
                send_by_date = pendulum.parse(send_by_date).in_tz('America/Denver').to_day_datetime_string()

            campaigns_in_list.append(dict(
                {"Campaign ID": campaign_id, "Launched Campaign": launch_date, "Name": name,
                 "Send By Date": send_by_date, "Completed Date": complete_date, "Status": status}))

        # click.secho(tabulate(campaigns_in_list, headers="keys", tablefmt="fancy_grid"))

    else:
        # User specified a campaign
        stats_bool = True

        # ToDo: Breakout status of users in group. Sent, scheduled, etc

        campaign_summary = api.campaigns.summary(campaign_id=campaign_id)
        # Get all campaign data
        complete_date = campaign_summary.completed_date
        create_date = campaign_summary.created_date
        campaign_id = campaign_summary.id
        launch_date = campaign_summary.launch_date
        name = campaign_summary.name
        send_by_date = campaign_summary.send_by_date
        status = campaign_summary.status
        stats = campaign_summary.stats

        stats_dict = [{"Total": stats.total, "Sent": stats.sent, "Opened": stats.opened, "Clicked": stats.clicked,
                       "Submitted Data": stats.submitted_data, "Error": stats.error}]

        # Convert all the dates to be human readable
        create_date = pendulum.parse(create_date).in_tz('America/Denver').to_day_datetime_string()

        # If the campaign isn't done yet, fill in the field rather than parsing a datetime string
        if status != "Completed":
            complete_date = "Campaign Not Completed Yet"
        else:
            complete_date = pendulum.parse(complete_date)
            complete_date = complete_date.in_tz('America/Denver').to_day_datetime_string()

        launch_date = pendulum.parse(launch_date).in_tz('America/Denver').to_day_datetime_string()

        if send_by_date == "0001-01-01T00:00:00Z":
            # Send by date not set
            send_by_date = "Not Set"
        else:
            # Send by date has been set. Parse that datetime string
            send_by_date = pendulum.parse(send_by_date).in_tz('America/Denver').to_day_datetime_string()

        campaigns_in_list.append(dict(
            {"Campaign ID": campaign_id, "Launched Campaign": launch_date, "Name": name,
             "Send By Date": send_by_date, "Completed Date": complete_date, "Status": status}))

    """
    {   'id': 1,
    'modified_date': datetime.datetime(2019, 6, 19, 21, 51, 27, 609662, tzinfo=tzutc()),
    'name': 'Test',
    'targets': [   <gophish.models.User object at 0x7fbf9f91bfd0>,
                   <gophish.models.User object at 0x7fbfa34a7cf8>]
    }
    """

    groups = api.groups.get()

    GroupInformation = collections.namedtuple('GroupInfo', 'id name targets modified_date')

    group_list = list()
    for group in groups:
        # For each group returned, put it's data into a useful list of named tuples
        modified_date = pendulum.instance(group.modified_date).in_tz('America/Denver').to_day_datetime_string()
        group_list.append(GroupInformation(group.id, group.name, group.targets, modified_date))

    # If group_id is 0, don't show all the group stats
    if group_id != 0:
        # Switch to True if group found
        found_group_bool = False

        if isinstance(group_id, int):
            # If group_id is a int, that might be the true group ID
            # Group ID is something besides 0
            for g in group_list:
                if group_id == g.id:
                    found_group_bool = True
                    # click.echo(f"Found group ID: {group_id}")
                    matched_group = g
                    break
                else:
                    # Group not found, do nothing
                    pass
        elif isinstance(group_id, str):
            # If the group_id is a string, that might be the group name
            for g in group_list:
                if group_id.lower() == g.name.lower():
                    found_group_bool = True
                    # click.echo(f"[*] Found group by name: {g}")
                    matched_group = g
                    break
                else:
                    # Group not found, do nothing
                    pass

        # Check if the group was found, if not, inform the user
        if not found_group_bool:
            # Not found
            click.secho(f"[!] The group '{group_id}' was not found! Try to use a real group this time.")
            raise click.Abort()
        else:
            tmp_list = list()
            # Found
            tmp_list.append({"ID": matched_group.id, "Name": matched_group.name,
                             "Number of Targets": len(matched_group.targets),
                             "Last Modified Date": matched_group.modified_date})
            # click.secho(f"[*] A group was found that matches!")
            # click.echo(tabulate(tmp_list, headers="keys", tablefmt="fancy_grid"))

            # for t in matched_group.targets:
            """
            t is a User Object:
            {'id': None, 'first_name': 'Bob', 'last_name': 'Johnson', 'email': 'bob.johnson@somewhere.com', 'position': 'CEO'}

            """
            # ToDo: Figure out any user info I might need

    else:
        tmp_list = list()
        for g in group_list:
            tmp_list.append({"ID": g.id, "Name": g.name, "Number of Targets": len(g.targets),
                             "Modified Date": g.modified_date})
        # click.secho(tabulate(tmp_list, headers="keys", tablefmt="fancy_grid"))

    # Group table
    click.secho(f"[*] Group Data", bold=True)
    click.echo(tabulate(tmp_list, headers="keys", tablefmt="fancy_grid"))

    # Main campaign table
    click.secho(f"\n[*] {name} General Information:", bold=True)
    click.secho(tabulate(campaigns_in_list, headers="keys", tablefmt="fancy_grid"))

    # Only show stats table when a user specifies a campaign
    if stats_bool:
        # Stats table
        click.secho(f"\n[*] {name} Stats:", bold=True)
        click.secho(tabulate(stats_dict, headers="keys", tablefmt="fancy_grid"))

    logger.debug(f"Looks like everything is done, setting tasks_done flag")
    tasks_done.set()


@cli.command('details', short_help="Campaign Details", context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--campaign-id', help="The ID of a specific campaign to get", default=0, show_default=True,
              type=click.INT)
@click.option('--all-data', help="Show all the results data, otherwise just show the name and current status",
              default=False, is_flag=True, show_default=True)
@click.option('--filter-out-sent', help="Don't show results for users with status \"Email Sent\"", default=False,
              is_flag=True, show_default=True)
@click.pass_context
def campaign_details(ctx, campaign_id, all_data, filter_out_sent):
    """
    Get campaign details
    """
    logger = ctx.obj['logger']

    loop = asyncio.get_event_loop()
    run_client_future = asyncio.gather(run_client(ctx))
    campaign_status_future = asyncio.gather(campaign_details_shim(ctx, campaign_id, all_data, filter_out_sent, loop))

    all_tasks = asyncio.gather(campaign_status_future, run_client_future)

    results = loop.run_until_complete(all_tasks)

    loop.close()

    logger.debug(f"Finished event loop")

async def campaign_details_shim(ctx, campaign_id, all_data, filter_out_sent, loop):
    """
    Run the blocking code in a executor
    """
    thread_count = 2
    logger = ctx.obj['logger']

    logger.debug(f"Starting thread pool with {thread_count} threads")
    # Only create 2 threads because we only have 2 tasks
    with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count, thread_name_prefix="ThreadPool1-") as pool:
        result = await loop.run_in_executor(pool, campaign_details_helper, ctx, campaign_id, all_data, filter_out_sent)

def campaign_details_helper(ctx, campaign_id, all_data, filter_out_sent):
    # Get all the parent options
    verify = ctx.parent.params['verify']
    api_key = ctx.parent.params['api_key']
    gophish_server = ctx.parent.params['gophish_server']
    logger = ctx.obj['logger']
    tunnel_active = ctx.obj['tunnel_active']
    tasks_done = ctx.obj['tasks_done']
    debug = ctx.parent.parent.params['debug']

    if debug:
        # If debug is set, don't make the spinner
        while not tunnel_active.is_set():
            logger.debug(f"Is the tunnel active: {tunnel_active.is_set()}")
            # Don't loop so fast, give the CPU a chance to do something else
            asyncio.run(async_sleep_shim(1.0))
    else:
        with Spinner(title="Waiting on SSH tunnel to be ready", beep=False, disable=False, force=False):
            while not tunnel_active.is_set():
                # Don't loop so fast, give the CPU a chance to do something else
                asyncio.run(async_sleep_shim(1.0))

    # Now that the tunnel is ready, we can define 'gophish_port'
    # Use this in place of the defined 'gophish_port' as SSH will be listening on a dynamic port but always forwarded to 'gophish_port'
    gophish_port = ctx.obj['listener_port']


    if all_data is None:
        all_data = False

    result_list = list()

    api = Gophish(api_key, host=f"https://{gophish_server}:{gophish_port}", verify=verify)

    details = api.campaigns.get(campaign_id=campaign_id)

    """
    # Details looks like this:

    {'completed_date': '0001-01-01T00:00:00Z',
    'created_date': '2019-06-19T22:14:14.364381018Z',
    'groups': [],
    'id': 33,
    'launch_date': '2019-06-19T22:13:00Z',
    'name': 'ClientTestCampaign',
    'page': <gophish.models.Page object at 0x7f1dd3be0240>,
    'results': [   <gophish.models.Result object at 0x7f1dd3be02e8>,
                   <gophish.models.Result object at 0x7f1dd3be0320>,
                   <gophish.models.Result object at 0x7f1dd3be0358>,
                   <gophish.models.Result object at 0x7f1dd3be0390>,
                   <gophish.models.Result object at 0x7f1dd3be0278>],
    'send_by_date': '2019-06-19T23:00:00Z',
    'smtp': <gophish.models.SMTP object at 0x7f1dd3be02b0>,
    'status': 'In progress',
    'template': <gophish.models.Template object at 0x7f1dd3be01d0>,
    'timeline': [   <gophish.models.TimelineEntry object at 0x7f1dd3be03c8>,
                    <gophish.models.TimelineEntry object at 0x7f1dd3be0400>,
                    <gophish.models.TimelineEntry object at 0x7f1dd3be0438>,
                    <gophish.models.TimelineEntry object at 0x7f1dd3be0470>,
                    <gophish.models.TimelineEntry object at 0x7f1dd3be04a8>,
                    <gophish.models.TimelineEntry object at 0x7f1dd3be04e0>,
                    <gophish.models.TimelineEntry object at 0x7f1dd3be0518>],
    'url': 'https://greenteohcapital.com'}    
    """
    try:
        for result in details.results:
            """
            # Results look like this
    
            {'email': 'clee@greentechcapital.com',
            'first_name': 'Catherine',
            'id': 'BcGwYNZ',
            'ip': '40.107.234.76',
            'last_name': 'Lee',
            'latitude': 38,
            'longitude': -97,
            'position': '',
            'status': 'Submitted Data'}
    
            # Just headers
            result_fields = ["id", "first_name", "last_name", "email", "position", "ip", "latitude", "longitude", "status"]
            result_dict = {"ID": result.id, "First Name": result.first_name, "Last Name": result.last_name, 
            "Email": result.email, "Position": result.position, "IP": result.ip, "Latitude": result.latitude, 
            "Longitude": result.longitude, "Status": result.status}
            """

            if all_data:
                # Show all the data including IP, lat and long
                result_dict = {"ID": result.id, "First Name": result.first_name, "Last Name": result.last_name,
                               "Email": result.email, "Position": result.position, "IP": result.ip,
                               "Latitude": result.latitude, "Longitude": result.longitude, "Status": result.status}

            else:
                # Just show the important bits
                if filter_out_sent is True:
                    if result.status != "Email Sent":
                        result_dict = {"First Name": result.first_name, "Last Name": result.last_name, "Email": result.email,
                                       "Status": result.status}
                        result_list.append(result_dict)
                else:
                    result_dict = {"First Name": result.first_name, "Last Name": result.last_name, "Email": result.email,
                                   "Status": result.status}
                    result_list.append(result_dict)

        click.echo(tabulate(result_list, headers="keys", tablefmt="fancy_grid"))
    except AttributeError as e:
        logger.critical(f"Something went wrong: {e}")
    logger.debug(f"Looks like everything is done, setting tasks_done flag")
    tasks_done.set()

if __name__ == "__main__":
    cli()