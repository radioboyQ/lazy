import csv
import io
import os


import click
from lxml import etree


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(name='reporting', context_settings=CONTEXT_SETTINGS, invoke_without_command=False)
@click.pass_context
def cli(ctx):
    """
    Parent command for the reporting subcommands
    """
    pass

@cli.command(name='nmap-service-parsing', context_settings=CONTEXT_SETTINGS, short_help='Parse a given Nmap file and output all accessable services')
@click.option('-p', '--nmap-path', type=click.Path(exists=True, file_okay=True, dir_okay=True, readable=True, resolve_path=True, allow_dash=True))
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

        print(output.getvalue())

    else:
        raise click.BadOptionUsage('You can\'t use a folder just yet.', ctx=ctx)
