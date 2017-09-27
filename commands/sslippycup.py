# Python Standard Library
import os
import sys

# Third Party Libraries
import click
from lxml import etree

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.command(short_help='Display all the hosts and ports associated with a Nessus plugin.', context_settings=CONTEXT_SETTINGS)
@click.argument('nessus_files', nargs=-1, type=click.Path(exists=True, file_okay=True, dir_okay=True, resolve_path=True,readable=True))
@click.option('-p', '--plugin-id', help='Plugin ID to export hostname and ports for. Default plugin: \'SSL Certificate Information\' : 10863', type=click.STRING, default='10863')
@click.pass_context
def cli(ctx, nessus_files, plugin_id):
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
            for (dirpath, dirnames, filenames) in os.walk(entry):
                for fn in filenames:
                    if fn.split('.')[-1:][0] == 'nessus':
                        nessus_list.append((dirpath, fn))

    # Make sure we actually found a Nessus file to upload
    if len(nessus_list) == 0:
        click.secho('[!] No Nessus files were specified.', fg='red')
        click.secho('[*] Exiting.', fg='green')
        sys.exit()

    for file in nessus_list:
        nessus_file_path = os.path.join(file[0], file[1])
        if os.path.isfile(nessus_file_path):
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

    for host_port in outlist:
        click.echo(host_port)