import asyncio
import csv
import io
import os
from pprint import pprint
import sys
import subprocess

import arrow
import asyncssh
import click
from lxml import etree

# My Junk
from lazyLib import lazyTools
from lazyLib import LazyCustomTypes

__version__ = '2.8'


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(name='projects', short_help='Useful project tools. Creating projects, naming reports, etc.', context_settings=CONTEXT_SETTINGS, invoke_without_command=False, cls=lazyTools.AliasedGroup)
@click.pass_context
def cli(ctx):
    """
    Group for project related tasks
    - Report naming convention
    - Upload data to QNAP
    """
    pass


@cli.command(name='report-name', help='Generate proper report names. ')
@click.option('-s', '--client-short', help='Client three letter abbreviation.', type=click.STRING, required=True)
@click.option('-u', '--user-initials', help='User\'s three initials', type=click.STRING, default='SAF')
@click.option('-t', '--report-type', help='The type of report to create', required=True)
@click.pass_context
def report_name(ctx, client_short, user_initials, report_type):
    """
    Generate report names
    Example report name: '{client_short}_{report_type}_{YYYY}-{MM}-{DD}_{user_initials}_v0.1.docx'
    Example WSR: '{client_short}_WSR_{date}.docx'
    """

    if report_type.upper() == 'WSR':
        click.secho('{client_short}_{report_type}_{date}_Project_Status_Report.docx'.format(client_short=client_short.upper(), report_type=report_type.upper(), date=arrow.utcnow().to('local').format('YYYY-MM-DD')))
    else:
        click.secho('{client_short}_{report_type}_{date}_{user_initials}_v0.1.docx'.format(client_short=client_short.upper(), report_type=report_type.upper(), date=arrow.utcnow().to('local').format('YYYY-MM-DD'), user_initials=user_initials))


@cli.command(name='nmap-service-parsing', context_settings=CONTEXT_SETTINGS, short_help='Parse a given Nmap file and output all accessable services')
@click.option('-p', '--nmap-path', type=click.Path(exists=True, file_okay=True, dir_okay=True, readable=True, resolve_path=True, allow_dash=True), required=True)
@click.pass_context
def nmap_parser(ctx, nmap_path):
    """
    Parse a given nmap file into a nice table for Word with all given services and ports
    """

    headers = ['Host', 'Port', 'Protocol', 'Application', 'Version']

    output = io.StringIO()
    final_data = list()

    # Check if the file given is an XML file
    if os.path.isfile(nmap_path) and nmap_path.endswith('xml'):

        tree = etree.parse(nmap_path)

        root = tree.getroot()

        for h in root.xpath('./host'):
            for hostAttrib in h:
                if hostAttrib.tag == 'address':
                    addr = hostAttrib.attrib['addr']
                elif hostAttrib.tag == 'ports':
                    for ports in hostAttrib:
                        if ports.tag == 'port':
                            protocol = ports.attrib['protocol']
                            portNumber = ports.attrib['portid']
                            for service in ports:
                                if service.tag == 'service':
                                    application =service.attrib['name']
                                    try:
                                        version = service.attrib['product']
                                    except KeyError:
                                        version = ""
                    data = {'Host': addr, 'Port': portNumber, 'Protocol': protocol, 'Application': application, 'Version': version}
                    final_data.append(data)

        writer = csv.DictWriter(output, headers)
        writer.writeheader()
        writer.writerows(final_data)

        click.secho(output.getvalue())

    else:
        raise click.BadOptionUsage('You can\'t use a folder just yet.', ctx=ctx)


@cli.command(name='upload', context_settings=CONTEXT_SETTINGS, short_help='Upload/Push a project directory to QNAP')
@click.argument('projects', type=click.STRING, nargs=-1)
@click.option('-s', '--share-name', help='Name of the share from the config file.', default='QNAP', type=click.STRING)
@click.option('-y', '--year', type=click.IntRange(2013, 2100), default=arrow.now().format('YYYY'), help='Pick a year after 2013. Default is the current year.')
@click.pass_context
def upload_qnap(ctx, projects, year, share_name):
    """
    Upload project directories to QNAP
    - Check that the local *dir* exists
    - Check if QNAP is mounted
    - Copy local dir to QNAP folder
    """
    # ToDo: Add functionality to only upload Deliverables, Evidence, Administrative, or Retest

    configOptions = lazyTools.TOMLConfigImport(ctx.parent.parent.params['config_path'])

    remotePath = '/Volumes/ProServices/Projects/{year}/'.format(year=year)

    sync_push_cmd = ["rsync", "-zarvhuW"]

    for proj in projects:

        fullPath = os.path.join(configOptions['local-config']['projects-folder'], proj)

        if lazyTools.dir_exists(fullPath):
            # Path exists locally

            # Check if the share is mounted
            share_status = os.path.ismount(configOptions['share'][share_name.lower()]['mount_point'])

            if share_status == False:
                click.secho('[!] The share isn\'t mounted. Mount it and try again.', fg='red')
                sys.exit(1)

            sync_push_cmd.append('fullPath')

            try:
                p = subprocess.Popen(sync_push_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                for lines in iter(p.stdout.readline, b''):
                    for line in lines.split('\r'):
                        print("[s] %s" % line.strip())
            except Exception as e:
                    click.secho('[!] Failed to upload.', fg='red')
                    print(e)
            finally:
                click.secho('[*] Upload success.', fg='green')
                
        else:
            raise click.BadArgumentUsage('The project folder {} doesn\'t exist!'.format(proj))


@cli.command(name='test-setup', help='Sets up remote host for a pentest.')
@click.argument('host', type=click.STRING)
@click.option('-p', '--port', help='Port number to access jump box.', type=click.IntRange(1, 655535), default=2222)
@click.option('-u', '--username', help='Username to log in.', type=click.STRING, default='root')
@click.option('-c', '--cert', help='Cert to use for the connection.', type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True, allow_dash=True), default='/Users/scottfraser/.ssh/known_hosts')
@click.argument('cmd-file', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.pass_context
def test_setup(ctx, host, port, username, cert, cmd_file):
    """
    Set up a jump box for an upcoming pen test.
    """
    # Create SSHTools instance
    ssh = lazyTools.SSHTools(username=username, host=host, port=port, known_hosts=cert)

    cmd_list = list()

    with open(cmd_file, 'r') as f:
        for l in f:
            if l.startswith('#'):
                # Commented command in cmd_file
                pass
            else:
                cmd_list.append(l.strip())

    loop = asyncio.get_event_loop()
    try:
        result_dict = loop.run_until_complete(ssh.single_client_multiple_commands(cmd_list))
    except (OSError, asyncssh.Error) as exc:
        sys.exit('SSH connection failed: ' + str(exc))

    for host in result_dict:
        for cmd in result_dict[host]:
            click.echo('Standard Out for {}: \n{}'.format(cmd, result_dict[host][cmd]['result_stdout']))
            click.echo(75*'-')
            click.echo('\n')
            click.echo('Standard Error for {}: \n{}'.format(cmd, result_dict[host][cmd]['result_stderr']))


@cli.command(name='copy-id', help='Works like \'ssh-copy-id\' but works on other ports and is simpler.')
@click.argument('host', type=click.STRING)
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=False)
@click.option('-p', '--port', help='Port number for remote server. Defaults to port 22', type=LazyCustomTypes.port, default=22)
@click.option('-u', '--username', help='Username to log in.', type=click.STRING, default='root')
@click.option('-i', '--id-file', help='ID file to copy. Defaults to \'~/.ssh/id_rsa.pub\'.', type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True, allow_dash=True), default='{}/.ssh/id_rsa.pub'.format(os.environ['HOME']))
@click.option('-a', '--authorized-keys-file', help='Location of the \'authorized_keys\' file on the remote host.', type=click.Path(exists=False, file_okay=True, dir_okay=False, resolve_path=False, allow_dash=True), default='~/.ssh/authorized_keys')
@click.pass_context
def copy_id(ctx, host, password, port, username, id_file, authorized_keys_file):
    """
    Copies SSH ID file to a given host
    """
    # Commands to ensure that 'authorized_keys' is there
    cmdList = ['mkdir -p $HOME/.ssh/; touch ~/.ssh/authorized_keys; chmod 644 ~/.ssh/authorized_keys']

    # Create SSHTools instance
    ## Assume we are not using a cert to connect, just the password
    ssh = lazyTools.SSHTools(username=username, host=host, port=port, password=password, known_hosts=None)

    loop = asyncio.get_event_loop()
    try:
        for cmd in cmdList:
            results = loop.run_until_complete(ssh.run_client(cmd))
        results = loop.run_until_complete(ssh.upload_file(srcFilePath=id_file, destFilePath=authorized_keys_file, progressBar=False))
    except (OSError, asyncssh.Error) as exc:
        sys.exit('[!] Operation failed: ' + str(exc))

    click.echo('[*] Uploaded your SSH keys successfully.')


if __name__ == '__main__':
    cli()