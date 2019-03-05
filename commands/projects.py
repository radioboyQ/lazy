import asyncio
import csv
from io import StringIO
import os
import logging
from pathlib import Path
from pprint import pprint
import sys
import subprocess

import arrow
import asyncssh
import click
from lxml import etree, html
import requests

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
@click.option('-n', '--client-name', help='Client name', type=click.STRING, required=True)
@click.option('-t', '--report-type', help='The type of report to create', default='draft', type=click.Choice(['draft', 'final']), required=True)
@click.option('-p', '--project-type', help='Project type; Internal Penetration Test, Hardware Assessment, etc.', type=click.STRING, required=True)
@click.pass_context
def report_name(ctx, client_name, report_type, project_type):
    """
    Generate report names
    Example report name: 'Coalfire Labs - [Client Name] - [Proj.Type {No Abbreviations}] - [Submission Date] - DRAFT.docx'
    """
    now = arrow.utcnow().to('local').format('YYYY-MM-DD')
    if report_type == 'draft':
        click.secho(f'Coalfire Labs - {client_name} - {project_type} - {now} - DRAFT.docx')
    elif report_type == 'final':
        click.secho(f'Coalfire Labs - {client_name} - {project_type} - {now} - FINAL.docx')
    
    
    # if report_type.upper() == 'WSR':
    #     click.secho('{client_short}_{report_type}_{date}_Project_Status_Report.docx'.format(client_short=client_short.upper(), report_type=report_type.upper(), date=arrow.utcnow().to('local').format('YYYY-MM-DD')))
    # else:
    #     click.secho('{client_short}_{report_type}_{date}_{user_initials}_v0.1.docx'.format(client_short=client_short.upper(), report_type=report_type.upper(), date=arrow.utcnow().to('local').format('YYYY-MM-DD'), user_initials=user_initials))


@cli.command(name='nmap-service-parsing', context_settings=CONTEXT_SETTINGS, short_help='Parse a given Nmap file and output all accessable services')
@click.option('-p', '--nmap-path', type=click.Path(exists=True, file_okay=True, dir_okay=True, readable=True, resolve_path=True, allow_dash=True), required=True)
@click.pass_context
def nmap_parser(ctx, nmap_path):
    """
    Parse a given nmap file into a nice table for Word with all given services and ports
    """

    headers = ['Host', 'Port', 'Protocol', 'Application', 'Version']

    output = StringIO()
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

@cli.command('desmond-ssh-update', help="Command to sync the local SSH config to the current status of the drones")
@click.option('--debug', help="Debug flag", is_flag=True, default=False)
@click.option('--verbose', help="Verbose flag", is_flag=True, default=False)
@click.pass_context
def desmond_ssh_update(ctx, debug, verbose):
    """
    Update SSH Config with the current status of the drones
    """
    """
    - Parse Desmond page
    - Read in the SSH config fileAIO-BlackHat-Scraping
    """
    logger = logging.getLogger("Desmond-Device-Parser")
    if debug:
        console_log_level = 10
    elif verbose:
        console_log_level = 20
    else:
        console_log_level = 30

    def parse_desmond(desmond_url, timeout=5.0):
        """
        Parse Desmond HTML page
        """
        headers = ["Name", "Status", "Time Online", "IP", "Device Type", "Client Password"]
        table_list = list()
        output_fmt = list()
        s = requests.Session()

        ssh_cfg = """Host\tcoalfire-drone-{drone_name}
        \t\tHostname\t\t{drone_ip}
        \t\tPort\t\t\t22
        \t\tUser\t\t\troot
        \t\tIdentityFile\t~/.ssh/id_ed25519
        \t\tStrictHostKeyChecking no
        \t\tUserKnownHostsFile /dev/null
        \t\tLocalForward 8834 127.0.0.1:8834
        \t\tRemoteForward 3142 127.0.0.1:8888\n
        \t\t# Forward port 80 and port 8000 to local Apache instance
		\t\tRemoteForward 80 127.0.0.1:80
		\t\tRemoteForward 8000 127.0.0.1:80"""

        try:
            logger.debug(f'Requesting the Desmond device\'s page from: {desmond_url}')
            logger.debug(f'Using timeout {timeout}')
            r = s.get(desmond_url, timeout=timeout)
        except requests.exceptions.Timeout:
            er_str = f"[!] Failed to connecto to Desmond at {desmond_url}, are you on the VPN?"
            click.secho(er_str, fg="red")
            logger.error(f"Desmond request timed out to {desmond_url}, server did not respond.")
            raise click.Abort()
        except requests.exceptions.ConnectionError:
            er_str = f"[!] Failed to connect to Desmond at {desmond_url}. Check to ensure you\'re on the VPN."
            click.secho(f"[!] Failed to connect to Desmond at {desmond_url}. Check to ensure you\'re on the VPN.",
                        fg="red")
            logger.debug(f"Connection failed. Is Desmond down? Are you on the VPN?")
            raise click.Abort()
        else:
            # Check if the status isn't success
            try:
                r.raise_for_status()
            except requests.exceptions.HTTPError:
                click.secho(f"Received response code {r.status_code}.", fg="red")
                raise click.Abort()
            else:
                # Everything worked, parse the HTML page
                parsed = html.parse(StringIO(desmond_url))
                root = parsed.getroot()
                xpath_obj = root.xpath('/html/body/table/tbody')
                pprint(xpath_obj)
                # for i in root:
                #     if i.tag == 'body':
                #         for j in i:
                #             if j.tag == 'table':
                #                 for h in j:
                #                     if h.tag == 'thead':
                #                         pass
                #                     elif h.tag == 'tbody':
                #                         for k in h.getchildren():
                #                             tmp_lst = list()
                #                             for l in k.getchildren():
                #                                 tmp_lst.append(l.text)
                #                             table_list.append(tmp_lst)
                # for i in table_list:
                #     output_fmt.append(ssh_cfg.format(drone_name=i[0].lower(), drone_ip=i[3]))
                #
                # return output_fmt

    def read_ssh_config(ssh_config_path):
        """
        Function to read the custom part of the SSH config file
        Returns a list of lists representing the file
        """
        custom_ssh_config = list()

        logger.debug(f"Using the SSH config file: {str(ssh_config_path)}")

        with open(str(ssh_config_path), 'r') as f:
            for line in f.readlines():
                if line.startswith("#========================================="):
                    break
                else:
                    # Reading the custom SSH config
                    custom_ssh_config.append([line])
        return custom_ssh_config

    configOptions = lazyTools.TOMLConfigCTXImport(ctx)
    # pprint(configOptions['desmond']['desmond_url'], indent=4)
    # print(configOptions['desmond']['ssh_path'])

    # Base logger
    logger.setLevel(logging.DEBUG)
    # Create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(console_log_level)
    # Create log format
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    # Set the format
    ch.setFormatter(formatter)
    # Add console handler to main logger
    logger.addHandler(ch)

    desmond_devices = parse_desmond(configOptions['desmond']['desmond_url'])

    custom_ssh_config = read_ssh_config(Path(configOptions['desmond']['ssh_path']).expanduser())

    # pprint(desmond_devices)



    # pprint(custom_ssh_config)

# if __name__ == "__main__":
#     cli()
