from notifiers import get_notifier
import json
import pendulum
import requests
from requests_html import HTMLSession

import operator

class n2yolib(object):

    def __init__(self, api_key, pushover_app_token, pushover_user_token, ssl_verify=True, min_elevation=20):
        """
        Init the class
        :param api_key: str
        :param ssl_verify: SSL checking enabled by default
        """
        self.api_key = api_key
        self.ssl_verify = ssl_verify
        self.base_url = "https://www.n2yo.com/rest/v1/satellite/{stub}"
        self.min_elevation = float(min_elevation)
        self.p = get_notifier('pushover')
        self.pushover_app_token = pushover_app_token
        self.pushover_user_token = pushover_user_token


    def radio_pass(self, id, observer_lat, observer_lng, observer_alt, days, min_elevation):
        """
        Request passes for the next N days above N elevation.
        :param id: int
        :param observer_lat: float
        :param observer_lng: float
        :param observer_alt: float
        :param days: int
        :param min_elevation: int
        :return: json
        """

        stub_url = "radiopasses/{id}/{observer_lat}/{observer_lng}/{observer_alt}/{days}/{min_elevation}/&apiKey={api_key}".format(id=id, observer_lat=observer_lat, observer_lng=observer_lng, observer_alt=observer_alt, days=days, min_elevation=min_elevation, api_key=self.api_key)

        full_url = self.base_url.format(stub=stub_url)

        # return full_url

        return requests.get(full_url, verify=self.ssl_verify)

    def parse_pass_data(self, resp):
        """
        Parse existing dictionary into list of dictionaries
        :param resp: dict
        :return: list
        """

        headers = list()
        headers_dict = {"Satellite Name": "satname", "Max Elevation": "maxEl", "Start Time - Local": "startUTC",
                        "End Time - Local": "endUTC", "Start Time - UTC": "startUTC", "End Time - UTC": "endUTC",
                        "Duration": "null"}
        for h in headers_dict:
            headers.append(h)

        final_table = list()
        for pass_count in range(0, resp["info"]["passescount"]):
            # Reset the dict for each row
            final_row = dict()

            # Get the epoch start and end times once
            start_utc_epoch = resp["passes"][pass_count]["startUTC"]
            end_utc_epoch = resp["passes"][pass_count]["endUTC"]

            # Add raw epoch times
            final_row["Start Time - UTC - Epoch"] = start_utc_epoch
            final_row["End Time - UTC - Epoch"] = end_utc_epoch

            # Add satellite name
            final_row["Satellite Name"] = resp["info"]["satname"]

            # Get maximum elevation over horizon
            elevation = resp["passes"][pass_count]["maxEl"]
            final_row["Max Elevation"] = elevation

            # Start times
            dt = pendulum.from_timestamp(start_utc_epoch, tz=0)
            final_row["Start Time - UTC"] = dt.format('YYYY MMMM DD - dddd - HH:mm:ss')
            final_row["Start Time - Local"] = dt.in_timezone(pendulum.now().timezone_name).format(
                'YYYY MMMM DD - dddd - HH:mm:ss')

            # End times
            dt = pendulum.from_timestamp(end_utc_epoch, tz=0)
            final_row["End Time - UTC"] = dt.format('YYYY MMMM DD - dddd - HH:mm:ss')
            final_row["End Time - Local"] = dt.in_timezone(pendulum.now().timezone_name).format(
                'YYYY MMMM DD - dddd - HH:mm:ss')

            # Get Duration
            duration_seconds = end_utc_epoch - start_utc_epoch
            final_row["Duration"] = pendulum.from_timestamp(duration_seconds).format('HH:mm:ss')

            final_table.append(final_row)

        return final_table

    def epoch_to_utc(self, raw_epoch):
        """
        Convert raw Epoch time to UTC Epoch time
        :param raw_epoch: int
        :return: pendulum.datetime.DateTime
        """
        return pendulum.from_timestamp(raw_epoch, tz=0)

    def epoch_to_local(self, raw_epoch):
        """
        Convert raw Epoch time to local timezone
        :param raw_epoch: int
        :return: pendulum.datetime.DateTime
        """

        dt = pendulum.from_timestamp(raw_epoch, tz=0)

        return dt.in_timezone(pendulum.now().timezone_name)

    def dt_format(self, dt, military=True):
        """
        Format dt object to use DayName, 23:01:01 PM
        """
        if military:
            return dt.format('dddd, hh:mm:ss A')
        else:
            return dt.format('dddd, HH:mm:ss')

    def seconds_to_start(self, raw_epoch):
        """
        Seconds until start of pass
        """

        # Convert UTC Epoch time to be timezone aware of UTC
        dt = pendulum.from_timestamp(raw_epoch, tz=0)

        # Convert timezone from UTC to local time
        epoch_pass_start_local = dt.in_timezone(pendulum.now().timezone_name).int_timestamp

        epoch_now_local = pendulum.now().int_timestamp

        return epoch_pass_start_local - epoch_now_local

    def epoch_to_local_human(self, raw_epoch):
        """
        Convert raw epoch time to local time and humanize it
        """

        dt = pendulum.from_timestamp(raw_epoch, tz=0)

        dt = dt.in_timezone(pendulum.now().timezone_name)

        return dt

    def next_pass(self, sat_data):
        """
        Return list with the next passes listed that have a elevation greater than min_elevation
        """
        next_pass_list = list()

        next_pass_dict = dict()
        for sat_name in sat_data:
            # Determine the closest pass for each satellite that's above min_alt
            for p in sat_data[sat_name]["passes"]:
                # Add sat name
                p.update({"name": sat_name})
                if p['maxEl'] > self.min_elevation:
                    next_pass_list.append(p)
        next_pass_list = sorted(next_pass_list, key=operator.itemgetter("startUTC"))

        return next_pass_list

    def n_passes(self, sat_data, num_passes=3):
        """
        Return a string of the next num_passes human readable format
        """
        final_list = list()
        next_passes = self.next_pass(sat_data)
        current_epoch_time = pendulum.now(pendulum.now().timezone_name).int_timestamp

        for n in list(range(num_passes)):
            if next_passes[n]["startUTC"] > current_epoch_time:
                # Format start time
                dt_start = self.epoch_to_local(next_passes[n]["startUTC"])
                dt_start_formatted = self.dt_format(dt_start)
                # Max elevation
                max_elevation = next_passes[n]["maxEl"]
                # Duration
                human_duration = self.epoch_to_utc(next_passes[n]["endUTC"]).diff_for_humans(self.epoch_to_utc(next_passes[n]["startUTC"]), absolute=True)
                # Satellite Name
                sat_name = next_passes[n]["name"]

                # Put it all together
                final_list.append("Starting on {dt_start_formatted}, {sat_name} will be overhead for {human_duration} with a height of {max_elevation} degrees.".format(sat_name=sat_name, human_duration=human_duration, dt_start_formatted=dt_start_formatted, max_elevation=int(max_elevation), non_military=self.dt_format(dt_start, military=False)))

        return final_list

    def pushover_notification(self, msg_str):
        """
        Send a notification via Pushover
        """
        # resp_error = self.p.notify(user=self.pushover_user_token, token=self.pushover_app_token, title="Satellite Prediction",message=msg_str).errors

        # if resp_error is not None:
            # return resp_error[0]
        pass

    @staticmethod
    def norad_sat_id_lookup(sat_names):
        """
        Lookup NORAD ID number by name
        """

        sat_dict = dict()
        result_dict = dict()

        session = HTMLSession()

        r = session.get('https://www.n2yo.com/satellites/?c=3')

        r.html.find('#categoriestab', first=True)

        weather = r.html.find('#categoriestab', first=True)

        sat_table_raw_list = list(weather.text.split('\n'))

        sat_table_raw_list.remove("[minutes]")

        # Ignore the "Action" column
        headers = sat_table_raw_list[0:5]

        # Remove headers from table after getting a list, including "Action"
        for i in range(0, 6):
            sat_table_raw_list.pop(0)

        while len(sat_table_raw_list) >= 6:
            sat_dict[sat_table_raw_list[0]] = sat_table_raw_list[1]
            for i in range(0, 6):
                sat_table_raw_list.pop(0)

        for name in sat_names:
            if name in sat_dict:
                result_dict[name] = sat_dict[name]

        return result_dict

    @staticmethod
    def norad_cache_refresh(cache_pth, sat_list):
        """
        Refresh the NORAD ID cache file
        """
        norad_id_dict = n2yolib.norad_sat_id_lookup(sat_list)
        with open(cache_pth, 'w') as f:
            json.dump(norad_id_dict, f)
