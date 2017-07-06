import click

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(name='projects', short_help='Useful project tools. Creating projects, naming reports, etc.', context_settings=CONTEXT_SETTINGS)
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
@click.option('-t', '--report-type', help='The type of report to create', type=click.Choice(['EPT', 'IPT', 'RSE']))
def report_name(ctx, client_short, user_initials, report_type):
    """
    Generate report names
    
    """

