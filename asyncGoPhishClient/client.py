import asyncio
import aiohttp

# from gophish.api import (campaigns, groups, pages, smtp, templates)
from asyncGoPhishClient.api import campaigns, groups, pages, smtp, templates

DEFAULT_URL = 'http://localhost:3333'


class GophishClient(object):
    """ A standard HTTP REST client used by Gophish """

    def __init__(self, api_key, host=DEFAULT_URL, **kwargs):
        self.api_key = api_key
        self.host = host
        self._client_kwargs = kwargs
        self.campaigns = campaigns.API(self.client)
        self.groups = groups.API(self.client)
        self.pages = pages.API(self.client)
        self.smtp = smtp.API(self.client)
        self.templates = templates.API(self.client)

    async def execute(self, method, path, **kwargs):
        """ Executes a request to a given endpoint, returning the result """

        url = "{}{}".format(self.host, path)
        kwargs.update(self._client_kwargs)
        async with aiohttp.request(method, url, params={"api_key": self.api_key}, **kwargs) as response:
            # response = requests.request( method, url, params={"api_key": self.api_key}, **kwargs)
            return response

class Gophish(object):
    def __init__(self, api_key, host=DEFAULT_URL, client=GophishClient, **kwargs):
        self.client = client(api_key, host=host, **kwargs)
        self.campaigns = campaigns.API(self.client)
        self.groups = groups.API(self.client)
        self.pages = pages.API(self.client)
        self.smtp = smtp.API(self.client)
        self.templates = templates.API(self.client)
