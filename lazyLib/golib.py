# Standard Libraries
from pprint import pprint

# Third party Libraries
import aiohttp
import async_timeout

class golib(object):

    def __init__(self, api_key, hostname, port, verify=False):
        self.api_key = api_key
        self.hostname = hostname
        self.port = port
        self.verify = verify
        self.host = 'https://{host}:{port}'.format(host=hostname, port=port)
        self.auth_success = False


    async def execute(self, method, path):
        """ Executes a request to a given endpoint, returning the result """

        url = "{}{}".format(self.host, path)

        if method.lower() == 'get':
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=self.verify)) as session:
                async with async_timeout.timeout(10):
                    async with session.get(url) as response:
                        return response.status

    async def auth_test(self, start_event):
        """
        Test authentication against the GoPhish host
        """
        await start_event.wait()
        if await self.execute('get', '/api/campaigns/?api_key={}'.format(self.api_key)) == 200:
            self.auth_success = True
