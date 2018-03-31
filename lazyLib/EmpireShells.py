import logging
from pprint import pprint
import sys
import time

import click
from notifiers import get_notifier
from requests import Request, Session, packages

packages.urllib3.disable_warnings()


class EmpirePushover(object):
    """
    Class to contain the logic and support functions for querying an Empire server for new sessions
    """

    def __init__(self, pushover_app_token, pushover_user_token, hostname, port=1337, username=None, passwd=None, empire_api=None, time_delay=15, ssl_verify=False, proxies=None, no_progress_bar=True, debug=False, dry_run=False):

        self.pushover_app_token = pushover_app_token
        self.pushover_user_token = pushover_user_token
        self.hostname = hostname
        self.port = port
        self.username = username
        self.passwd = passwd
        self.empire_api = empire_api
        self.time_delay = time_delay
        self.ssl_verify = ssl_verify
        self.proxies = proxies
        self.no_progress_bar = no_progress_bar
        self.debug = debug
        self.dry_run = dry_run
        self.session = Session()
        self.known_sessions = dict()
        self.p = get_notifier('pushover')

        if self.empire_api is None:
            self.password_auth()

    def password_auth(self):
        """
        Log into Empire with a username and password and get API token
        """
        uname_password = {'username': self.username, 'password': self.passwd}
        req = Request('POST', 'https://{}:{}/api/admin/login'.format(self.hostname, self.port), json=uname_password)
        prepped_req = req.prepare()
        resp = self.session.send(prepped_req, verify=self.ssl_verify)
        self.empire_api = resp.json()['token']



    def start_watching(self):
        """
        Loop until quit checking for new agents
        """
        while True:
            try:
                response_json = self.get_agents()

                # Check to see if any new agents have shown up since last time
                self.check_new_agents(response_json)

                if not self.no_progress_bar:
                    tick = self.time_delay
                    with click.progressbar(length=self.time_delay, label='Time Until Next Check', show_eta=False) as bar:
                        while tick > 0:
                            tick = tick - 1
                            time.sleep(1)
                            bar.update(1)
                else:
                    tick = self.time_delay
                    while tick > 0:
                        tick = tick - 1
                        time.sleep(1)

            except KeyboardInterrupt:
                # ToDo: Fix this garbage with proper error trapping
                click.echo('[!] Keyboard interrupt has been caught. Exiting.')
                sys.exit()

    def check_new_agents(self, response_json):
        """
        Check the passed in JSON blob for any new agents we haven't seen before
        """

        for a in response_json['agents']:
            if a['ID'] not in self.known_sessions:
                try:
                    msg = '[+] New agent found.\n[+] ID: {}\n[+] Hostname: {}\n[+] Internal IP: {}\n[+] Username: {}'.format(a['ID'], a['hostname'], a['internal_ip'], a['username'])
                    logging.info(msg)

                    if not self.dry_run:
                        pushover_response = self.p.notify(user=self.pushover_user_token, token=self.pushover_app_token, title='New Agent Phoned Home', message=msg)

                        # Pushover won't raise an exception like a normal library so we end up here:
                        if pushover_response.status == 'Failure':
                            # Something went wrong! Good luck!
                            # ToDo: Fix this garbage with proper error trapping
                            logging.error('[!] Something went wrong when we were trying to use Pushover!\n[*] Check your API keys and ensure they are correct.\n[!] Exiting.')
                            raise click.Abort()

                except:
                    # Something went wrong! Good luck!
                    # ToDo: Fix this garbage with proper error trapping
                    logging.error('[!] Something went wrong when we were trying to use Pushover!\n[!] Exiting.')
                    raise click.Abort()

                finally:
                    # Add the ID to self.known_sessions
                    self.known_sessions.update({a['ID']: a})

            else:
                # Skip known IDs
                if self.debug:
                    click.echo('[*] Already seen agent ID {}'.format(a['ID']))

    def _empire_request(self, method, url, data_json=None, headers=None):
        """
        Function to make calls against the API service
        """
        if url.startswith('/api/'):
            full_url = 'https://{}:{}{}?token={}'.format(self.hostname, self.port, url, self.empire_api)
        else:
            full_url = 'https://{}:{}/api/{}?token={}'.format(self.hostname, self.port, url, self.empire_api)

        method = method.upper()

        if data_json is None and headers is None:
            req = Request(method, full_url)
            prepped_req = req.prepare()
        elif data_json is not None and headers is None:
            req = Request(method, full_url, json=data_json)
            prepped_req = req.prepare()
        elif data_json is not None and headers is not None:
            req = Request(method, full_url, json=data_json, headers=headers)
            prepped_req = req.prepare()

        resp = self.session.send(prepped_req, proxies=self.proxies, verify=self.ssl_verify)

        if resp.status_code is not 200:
            return False, resp.status_code

        else:
            return resp.json(), resp.status_code

    def get_listners(self):
        """
        Get all active listeners
        """

        return self._empire_request('GET', 'listeners')

    def get_agents(self):
        """
        Get all active listeners
        """

        response_json, response_status = self._empire_request('GET', 'agents')

        if response_status == 200:
            return response_json
        else:
            # Something bad happened, good luck!
            # ToDo: Fix this garbage with proper error trapping
            pass

    def test(self):
        """
        Test the Pushover and Empire configuration
        """

        # Check pushover
        pushover_response = self.p.notify(user=self.pushover_user_token, token=self.pushover_app_token, title='ShellHerder Test', message='HELLO?! CAN YOU HEAR ME?!')

        # Pushover won't raise an exception like a normal library so we end up here:
        if pushover_response.status == 'Failure':
            # ToDo: Convert these statements to logging statements
            click.echo('[!] Pushover encountered an issue. Check your API keys and try again.')
        else:
            # ToDo: Convert these statements to logging statements
            click.echo(('[*] Pushover seems to have worked successfully'))


        # Check Empire
        response_json, response_status = self._empire_request('GET', 'config')

        if response_status == 200:
            # ToDo: Convert these statements to logging statements
            click.echo('[*] This is your Empire\'s configuration:')
            click.echo(pprint(response_json['config'], indent=4))
