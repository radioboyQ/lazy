#!/usr/bin/env python

from setuptools import setup

setup(
    name="lazy",
    version="1.0",
    description="A collection of commands to make life lazier",
    author="Scott Fraser",
    author_email="quincy.fraser@gmail.com",
    url="https://github.com/radioboyQ/lazy",
    packages=["commands", "lazyLib"],
    py_modules=["lazy"],
    entry_points="""
        [console_scripts]
        lazy=lazy:cli
    """,
    install_requires=[
        "pendulum",
        "boto3",
        "gophish",
        "aiohttp",
        "lifxlan",
        "tabulate",
        "arrow",
        "toml",
        "notifiers",
        "asyncssh",
        "click",
        "pytz",
        "click_spinner",
        "requests_html",
        "cchardet",
        "aiodns",
        "dataset",
    ],
)
