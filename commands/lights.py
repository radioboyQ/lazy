import click
from lifxlan import LifxLAN, WARM_WHITE, PINK

# My Junk
from lazyLib import lazyTools

__version__ = '1.0'

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group('lights', help='Base command for the controlling the lights.', context_settings=CONTEXT_SETTINGS, cls=lazyTools.AliasedGroup)
@click.pass_context
def cli(ctx):
    """
    Base command for controlling the lights
    """

@cli.command('out', help='Turns off all Lifx bulbs on the local network.')
@click.pass_context
def lights_out(ctx):
    """
    Turns off all Lifx bulbs on the local network.
    """

    num_lights = None

    lifx = LifxLAN(num_lights, verbose=False)

    # get devices
    devices = lifx.get_lights()
    labels = []
    for device in devices:
        # pprint(vars(device))
        labels.append({'label': device.get_label(), 'ip_addr': device.get_ip_addr()})

    if ctx.parent.parent.params['verbose'] == True:
        click.echo("Found Bulbs:")
        for label in labels:
            print('[-] Label: {}\n[->] IP Address: {}'.format(label['label'], label['ip_addr']))

    lifx.set_power_all_lights("off", rapid=True)

@cli.command('normal', help='Sets the bulbs to a normal color.')
@click.pass_context
def normal(ctx):
    """
    Set all the lights to normal
    """

    num_lights = None

    lifx = LifxLAN(num_lights, verbose=False)

    # get devices
    devices = lifx.get_lights()

    for device in devices:
        # Set color
        device.set_color(WARM_WHITE, rapid=True)

@cli.command('pink', help='Sets the bulbs to pink.')
@click.pass_context
def normal(ctx):
    """
    Set all the lights to pink
    """

    num_lights = None

    lifx = LifxLAN(num_lights, verbose=False)

    # get devices
    devices = lifx.get_lights()

    for device in devices:
        # Set color
        device.set_color(PINK, rapid=True)