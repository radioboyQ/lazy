import logging
import os

# Third Party Apps
import click

# My library
from lazyLib.EmpireShellsLib import EmpirePushover

# Logging
# Quiet down Requests logging
logging.getLogger("requests").setLevel(logging.WARNING)

logger = logging.getLogger(os.path.basename(__file__)[:-3])
logger.setLevel(logging.DEBUG)
# create console handler and set level
ch = logging.StreamHandler()

ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter("%(message)s")
# add formatter to ch
ch.setFormatter(formatter)
# add ch to logger
logger.addHandler(ch)

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(
    name="shell-herder", context_settings=CONTEXT_SETTINGS, invoke_without_command=False
)
@click.pass_context
def cli(ctx):
    """
    When a shell lands in Metasploit/Empire, etc, send a notification via Pushover
    """
    pass


@cli.command(
    "empire",
    help="Send a notification when a shell lands in Empire.",
    context_settings=CONTEXT_SETTINGS,
)
@click.option(
    "--pushover-token",
    type=click.STRING,
    default=lambda: os.environ.get("PUSHOVER_TOKEN"),
    help="Pushover API app token. This is *not* you user token",
    required=True,
)
@click.option(
    "--pushover-user",
    type=click.STRING,
    default=lambda: os.environ.get("PUSHOVER_USER"),
    help="Pushover API user token. This is *not* you app token",
    required=True,
)
@click.option("--test", is_flag=True, default=False, help="Test the current setup")
@click.option(
    "-p",
    "--port",
    type=click.IntRange(1, 65535),
    default=1337,
    help="Port used to connect to Empire",
)
@click.option(
    "-u", "--username", type=click.STRING, default="admin", help="Username for Empire"
)
@click.option(
    "--password",
    type=click.STRING,
    default="Password123",
    help="Prompt for Empire Password",
)
@click.option(
    "-e",
    "--empire-api",
    type=click.STRING,
    default=lambda: os.environ.get("EMPIRE_API", ""),
    help="Empire API key if you're not using username and password",
)
@click.option(
    "-t",
    "--time-delay",
    type=click.INT,
    default=15,
    help="Interval to query Empire. All values are seconds!",
)
@click.option(
    "--verify-ssl", is_flag=True, default=False, help="Enforce SSL verification"
)
@click.option(
    "--https-proxy",
    type=click.STRING,
    help="Check Empire via a proxy, e.g. 'https://127.0.0.1:8080'",
)
@click.option(
    "--no-progress",
    is_flag=True,
    default=False,
    help="Don't display a progress bar for the timer",
)
@click.option("--debug", is_flag=True, default=False, help="Show debuging messages")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Don't send Pushover notifications, but do everything else",
)
@click.argument("EMPIRE-HOSTNAME", type=click.STRING)
@click.pass_context
def empire_notification(
    ctx,
    pushover_token,
    pushover_user,
    test,
    port,
    username,
    password,
    empire_api,
    time_delay,
    verify_ssl,
    https_proxy,
    no_progress,
    debug,
    dry_run,
    empire_hostname,
):
    """
    Watch dog CLI interface
    """
    empire_watcher = EmpirePushover(
        pushover_token,
        pushover_user,
        hostname=empire_hostname,
        port=port,
        username=username,
        passwd=password,
        empire_api=empire_api,
        time_delay=time_delay,
        ssl_verify=verify_ssl,
        proxies=https_proxy,
        no_progress_bar=no_progress,
        debug=debug,
        dry_run=dry_run,
    )

    # If test is true, send a test notification and request the Empire configuration
    if test:
        click.echo("[*] Testing the Pushover and Empire configuration")
        empire_watcher.test()
    else:
        empire_watcher.start_watching()


async def run_client():
    async with asyncssh.connect("159.65.35.135", username="gpsadmin") as conn:
        listener = await conn.forward_local_port("localhost", 3333, "localhost", 3333)
        print("Listening on port {}".format(listener.get_port()))
        await listener.wait_closed()


if __name__ == "__main__":
    cli()
