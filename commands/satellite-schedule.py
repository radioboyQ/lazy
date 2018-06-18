import json
import logging
import os
from pathlib import Path
from pprint import pprint
import sys

# Third Party Apps
import click
import pendulum


from lazyLib import lazyTools
from lazyLib.n2yo import n2yolib


# Logging
# Quiet down Requests logging
logging.getLogger("requests").setLevel(logging.WARNING)

logger = logging.getLogger(os.path.basename(__file__)[:-3])
logger.setLevel(logging.DEBUG)
# create console handler and set level
ch = logging.StreamHandler()

ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter('%(message)s')
# add formatter to ch
ch.setFormatter(formatter)
# add ch to logger
logger.addHandler(ch)

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(name="satellite-utils", context_settings=CONTEXT_SETTINGS, invoke_without_command=False, cls=lazyTools.AliasedGroup)
@click.option("-n", "--refresh-noaa", help="Refresh the cached NOAA satellite ID numbers.", is_flag=True, default=False)
@click.option("-p", "--refresh-prediction", help="Refresh the satellite predictions", is_flag=True, default=False)
@click.option("-a", "--refresh-all", help="Refresh all caches", is_flag=True, default=False)
@click.option("--num-days", help="Set the number of days to request. Default is 5", type=click.INT, default=5)
@click.pass_context
def cli(ctx, refresh_noaa, refresh_prediction, refresh_all, num_days):
    """
    Utilities for listening to satellites, specifically NOAA satellites
    """
    sat_pass_data = dict()

    configOptions = lazyTools.TOMLConfigImport(ctx.parent.params["config_path"])

    norad_cache_pth = Path(configOptions["satellite"]["norad-cache-file"])
    prediction_cache_pth = Path(configOptions["satellite"]["prediction-cache-file"])
    sat_list = configOptions["satellite"]["satellite-names"]
    api_key = configOptions["satellite"]["api-key"]
    observer_alt = configOptions["satellite"]["observer_alt"]
    observer_lat = configOptions["satellite"]["observer_lat"]
    observer_lng = configOptions["satellite"]["observer_lng"]
    min_elevation = configOptions["satellite"]["min_elevation"]

    n2yo = n2yolib("EY8PE3-34D8LM-G7DEUT-3TNS", configOptions["pushover"]["token"], configOptions["pushover"]["user"])


    # Check if NORAD cache file does not exist or there is a forced refresh
    if not norad_cache_pth.exists() or refresh_noaa or refresh_all:
        n2yolib.norad_cache_refresh(norad_cache_pth, sat_list)

    # Check if the prediction cache file does not exist or there is a forced refresh
    if not prediction_cache_pth.exists() or refresh_prediction or refresh_all:
        n2yo = n2yolib(api_key, configOptions["pushover"]["token"], configOptions["pushover"]["user"])

    # Get age of prediction cache file
    prediction_cache_pth_dt_period = pendulum.now() - pendulum.from_timestamp(os.path.getmtime(prediction_cache_pth), tz=pendulum.now().timezone_name)

    # If it's older than 12 hours, refresh it
    if prediction_cache_pth_dt_period.in_hours() >= 12 or refresh_prediction or refresh_all or not prediction_cache_pth.exists():

        click.echo("Refreshing local prediction cache. ", err=True)

        if not norad_cache_pth.exists():
            # Create Norad Satellite ID cache file
            n2yolib.norad_cache_refresh(norad_cache_pth, configOptions["satellite"]["satellite-names"])

        sat_id_dict = json.loads(norad_cache_pth.open('r').read())

        for name in sat_id_dict:
            # Get NORAD ID number
            id = sat_id_dict[name]

            # Request sat data with ID number
            sat_pass_data[name] = n2yo.radio_pass(id, observer_lat, observer_lng, observer_alt, num_days, min_elevation).json()
        prediction_cache_pth.open("w").write(json.dumps(sat_pass_data))

        # pprint(json.loads(prediction_cache_pth.open("r").read()), indent=4)

    if refresh_noaa or refresh_all:
        n2yolib.norad_cache_refresh(norad_cache_pth, configOptions["satellite"]["satellite-names"])


@cli.command('next-pass', help='Display when the next satellite is going to pass overhead', context_settings=CONTEXT_SETTINGS)
@click.argument('N-PASSES', default=3, type=click.INT)
@click.option('--pushover-only', help='Only send a notification via Pushover, do not show anything on STDOUT. Useful for scripting.', is_flag=True, default=False)
@click.pass_context
def notification(ctx, pushover_only, n_passes):
    # help='Next N passed to show predictions for all satellites. Default is 1',

    configOptions = lazyTools.TOMLConfigCTXImport(ctx)
    prediction_cache_pth = Path(configOptions["satellite"]["prediction-cache-file"])

    n2yo = n2yolib("EY8PE3-34D8LM-G7DEUT-3TNS", configOptions["pushover"]["token"], configOptions["pushover"]["user"])

    # Determine if we are printing to the screen or just Pushover

    sat_data = json.loads(prediction_cache_pth.open("r").read())

    next_passes = n2yo.n_passes(sat_data, n_passes)
    pushover_msg = next_passes[0]
    if pushover_only:
        n2yo.pushover_notification(pushover_msg)
    else:
        n2yo.pushover_notification(pushover_msg)
        for i in next_passes:
            click.echo(i)

@cli.command('schedule-capture', help='Schedule an \'at\' job to run and capture the SDR data.', context_settings=CONTEXT_SETTINGS)
@click.pass_context
def schedule_capture(ctx):
    """
    Schedule the 'at' jobs for wav capture
    """

    