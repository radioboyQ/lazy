import os
import sys
import atexit
import time
import requests
import json

import requests

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class nessus6Lib(object):
    """
    Library to connect to a given Nessus server
    """
    '''
    Scanner object
    '''
    def __init__(self, url, login='', password='', api_akey='', api_skey='',
                 insecure=False, ca_bundle=''):
        self.api_akey = None
        self.api_skey = None
        self.use_api = False
        self.name = ''
        self.policy_name = ''
        self.debug = False
        self.format = ''
        self.format_start = ''
        self.format_end = ''
        self.http_response = ''
        self.plugins = {}
        self.names = {}
        self.files = {}
        self.cisco_offline_configs = ''
        self.permissions = ''
        self.policy_id = ''
        self.policy_object = ''
        self.pref_cgi = ''
        self.pref_paranoid = ''
        self.pref_supplied = ''
        self.pref_thorough = ''
        self.pref_max_checks = ''
        self.pref_receive_timeout = ''
        self.set_safe_checks = ''
        self.pref_verbose = ''
        self.pref_silent_dependencies = ''
        self.res = {}
        self.scan_id = ''
        self.scan_name = ''
        self.scan_template_uuid = ''
        self.scan_uuid = ''
        self.tag_id = ''
        self.tag_name = ''
        self.targets = ''
        self.policy_template_uuid = ''
        self.token = ''
        self.url = url
        self.ver_feed = ''
        self.ver_gui = ''
        self.ver_plugins = ''
        self.ver_svr = ''
        self.ver_web = ''
        self.ca_bundle = ca_bundle
        self.insecure = True
        self.auth = []
        self.host_vulns = {}
        self.plugin_output = {}
        self.host_details = {}
        self.host_ids = {}

        if insecure and hasattr(requests, 'packages'):
            requests.packages.urllib3.disable_warnings()

        if (api_akey and api_skey):
            self.api_akey = api_akey
            self.api_skey = api_skey
            self.use_api = True
        else:
            # Initial login to get our token for all subsequent transactions
            self._login(login, password)

            # Register a call to the logout action automatically
            atexit.register(self.action, action="session",
                            method="delete", retry=False)

        # self._get_permissions()
        # self._get_scanner_id()

################################################################################
    def _login(self, login="", password=""):
        if login and password:
            self.auth = [login,password]

        self.action(action="session",
                    method="post",
                    extra={"username": self.auth[0], "password": self.auth[1]},
                    private=True,
                    retry=False)

        try:
            self.token = self.res["token"]

        except KeyError:
            if self.res["error"]:
                print("It looks like you're trying to login into a Nessus 5")
                print("instance. Exiting.")
                sys.exit(0)

################################################################################

    def __enter__(self):
        return self

    def __exit__(self,exception_type, exception_value, traceback):
        self._log_out()

################################################################################
    def _get_permissions(self):
        '''
        All development has been conducted using and administrator account which
        had the permissions '128'
        '''
        self.action(action="session", method="get")
        self.permissions = self.res['permissions']

################################################################################
    def _get_scanner_id(self):
        '''
        Pull in information about scanner. The ID is necessary, everything else
        is "nice to have" for debugging.
        '''
        self.action(action="scanners", method="get")

        try:
            for scanner in self.res["scanners"]:
                    if scanner["type"] == "local":
                        self.scanner_id = scanner['id']
                        self.ver_plugins = scanner['loaded_plugin_set']
                        self.ver_gui = scanner['ui_version']
                        self.ver_svr = scanner['engine_version']
                        self.ver_feed = scanner['license']['type']
        except:
            pass


################################################################################

    def _log_out(self):
        """
        Kill session with remote host
        """
        # self.action(action = "session",method = "delete", retry = False)
        pass

################################################################################

    def action(self, action, method, extra={}, files={}, json_req=True, download=False, private=False, retry=True):
        '''
        Generic actions for REST interface. The json_req may be unneeded, but
        the plugin searching functionality does not use a JSON-esque request.
        This is a backup setting to be able to change content types on the fly.
        '''
        payload = {}
        payload.update(extra)
        if self.use_api:
            headers = {'X-ApiKeys': 'accessKey=' + self.api_akey +
                       '; secretKey=' + self.api_skey}
        else:
            headers = {'X-Cookie': 'token=' + str(self.token)}

        if json_req:
            headers.update({'Content-type': 'application/json',
                            'Accept': 'text/plain'})
            payload = json.dumps(payload)

        url = "%s/%s" % (self.url, action)
        if self.debug:
            if private:
                print("JSON    : **JSON request hidden**")
            else:
                print("JSON    :")
                print(payload)

            print("HEADERS :")
            print(headers)
            print("URL     : %s " % url)
            print("METHOD  : %s" % method)
            print("\n")

        # Figure out if we should verify SSL connection (possibly with a user
        # supplied CA bundle). Default to true.
        if self.insecure:
            verify = False
        elif self.ca_bundle:
            verify = self.ca_bundle
        else:
            verify = True

        try:
            print(method)
            print(url)
            print(payload)
            req = requests.request(method, url, data=payload, files=files,
                                   verify=False, headers=headers)

            if not download and req.text:
                # try:
                #     self.res = req.json()
                # except json.decoder.JSONDecodeError:
                #     print(self.url)
                #     print(req.text)
                #     sys.exit()
                self.res = req.json()
            elif not req.text:
                self.res = {}

            if req.status_code != 200 and req.json()['error'] == 'Invalid Credentials':
                raise NessusException.InvalidCredentials('Provided credentials didn\'t work')
            elif req.status_code != 200 and req.json()['error'] == 'The requested file was not found':
                # print(req.text)
                # print(action)
                # print(method)
                # sys.exit()
                raise NessusException.RequestedFileNotFound('Requested file not found')
            elif req.status_code != 200:
                print("*****************START ERROR*****************")
                if private:
                    print("JSON    : **JSON request hidden**")
                else:
                    print("JSON    :")
                    print(payload)
                    print(files)

                print("HEADERS :")
                print(headers)
                print("URL     : %s " % url)
                print("METHOD  : %s" % method)
                print("RESPONSE: %d" % req.status_code)
                print("\n")
                self.pretty_print()
                print("******************END ERROR******************")

            if self.debug:
                # This could also contain "pretty_print()" but it makes a lot of
                # noise if enabled for the entire scan.
                print("RESPONSE CODE: %d" % req.status_code)

            if download:
                return req.content
        except requests.exceptions.SSLError as ssl_error:
            raise SSLException('%s for %s.' % (ssl_error, url))
        except requests.exceptions.ConnectionError:
            raise NessusException.FailureToConnect("Could not connect to %s.\nExiting!\n" % url) from None


        if self.res and "error" in self.res and retry:
            if self.res["error"] == "You need to log in to perform this request":
                self._login()
                self.action(action=action, method=method, extra=extra, files=files,
                            json_req=json_req, download=download, private=private,
                            retry=False)


################################################################################



    def upload(self, upload_file, file_contents=""):
        '''
        Upload a file that can be used to import a policy or add an audit file
        to a policy. If file_contents are not provided then upload_file is
        treated as a full path to a file and opened.
        '''
        if not file_contents:
            file_contents = open(upload_file, 'rb')
            upload_file = os.path.basename(upload_file)

        files = {'': upload_file,
                 'Filedata': file_contents}

        self.action(action="file/upload",
                    method="post",
                    files=files,
                    json_req=False)

################################################################################
    def scan_import(self, scan_name, dest_folder: int):
        """
        You must upload a scan before you can import it!
        """
        data = {'file': scan_name, 'folder_id': dest_folder}
        self.action(action="scans/import",
                    method="post",
                    extra=data,
                    json_req=True)

################################################################################
    def download_scan(self, scan_id, export_format="nessus", dbpasswd=""):
        running = True
        counter = 0
        self.scan_id = scan_id

        self.action("scans/" + str(self.scan_id), method="get")
        if (export_format == "db"):
            data = {"format": "db", "password": dbpasswd}
        else:
            data = {'format': export_format}
        self.action("scans/" + str(self.scan_id) + "/export",
                    method="post",
                    extra=data)

        file_id = self.res['file']
        # print('Download for file id ' + str(self.res['file']) + '.')
        while running:
            time.sleep(2)
            counter += 2
            self.action("scans/" + str(self.scan_id) + "/export/"
                        + str(file_id) + "/status",
                        method="get")
            running = self.res['status'] != 'ready'
            # sys.stdout.write(".")
            # sys.stdout.flush()
            if counter % 60 == 0:
                 pass # print("")
        #
        # print("")

        content = self.action("scans/" + str(self.scan_id) + "/export/" + str(file_id) + "/download", method="get", download=True)
        return content

################################################################################

    def list_scans(self):

        # List all scans and their containing folder
        self.action(action="scans", method="get", download=False)
        return self.res

################################################################################
    def pretty_print(self):
        '''
        Used for debugging and error conditions to easily see the returned
        structure.
        '''
        print(json.dumps(self.res, sort_keys=False, indent=2))
        print("\n")

################################################################################

class NessusException(Exception):
    """General Exception"""
    class FailureToConnect(Exception):
        """Failed to connect to specified server"""
    class InvalidCredentials(Exception):
        """Bad creds"""
    class RequestedFileNotFound(Exception):
        """File requested from server not found"""


class SSLException(Exception):
    pass