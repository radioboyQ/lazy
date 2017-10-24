import asyncio

import asyncssh
import click

__version__ = '1.0'


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


@click.group('denhac', help='Commands to help with denhac server administration.')
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
