import csv
import io
import os
import sys

import arrow
import click
from lxml import etree

__version__ = '2.0'

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(name='projects', short_help='Useful project tools. Creating projects, naming reports, etc.', context_settings=CONTEXT_SETTINGS, invoke_without_command=False)
@click.pass_context
def cli(ctx):
    """
    Group for project related tasks
    - Report naming convention
    - Upload data to QNAP
    """
    pass

@cli.command(name='report-name', help='Generate proper report names. ')
@click.option('-s', '--client-short', help='Client three letter abbreviation.', type=click.STRING)
@click.option('-u', '--user-initials', help='User\'s three initials', type=click.STRING, default='SAF')
@click.option('-t', '--report-type', help='The type of report to create', type=click.Choice(['EPT', 'IPT', 'RSE', 'ept', 'ipt', 'rse']))
@click.pass_context
def report_name(ctx, client_short, user_initials, report_type):
    """
    Generate report names
    Example report name: '{client_short}_{report_type}_{YYYY}-{MM}-{DD}_{user_initials}_v0.1.docx'
    """
    utc = arrow.utcnow()
    click.secho('{client_short}_{report_type}_{date}_{user_initials}_v0.1.docx'.format(client_short=client_short.upper(), report_type=report_type.upper(), date=utc.to('local').format('YYYY-MM-DD'), user_initials=user_initials))

@cli.command(name='nmap-service-parsing', context_settings=CONTEXT_SETTINGS, short_help='Parse a given Nmap file and output all accessable services')
@click.option('-p', '--nmap-path', type=click.Path(exists=True, file_okay=True, dir_okay=True, readable=True, resolve_path=True, allow_dash=True), required=True)
@click.pass_context
def nmap_parser(ctx, nmap_path):
    """
    Parse a given nmap file into a nice table for Word with all given services and ports
    """

    headers = ['Host', 'Port', 'Protocol', 'Application', 'Version']
    output = io.StringIO()
    finalData = list()

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
                    finalData.append(data)

        writer = csv.DictWriter(output, headers)
        writer.writeheader()
        writer.writerows(finalData)

        click.secho(output.getvalue())

    else:
        raise click.BadOptionUsage('You can\'t use a folder just yet.', ctx=ctx)