import click


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    # Base Commands
    print("Main program execute")


@cli.group()
@click.option("-s", "--server", help="Specify the server type")
@click.option(
    "-p", "--port", help="Specify the Nessus port number", type=int, default=8834
)
def nessus(server):
    print("Nessus Command")


@nessus.group()
def export_scan():
    print("Export Scans")


def closeOutFunction():
    click.echo("MECO Shutdown")


if __name__ == "__main__":
    cli()
