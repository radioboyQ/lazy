import arrow
import click

__version__ = '1.0'

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

