#!/usr/bin/env python3
# coding: utf-8

import aiohttp
import asyncio
import collections
import datetime
import time
from xmlrpc.client import ServerProxy

from pypi_create_index_html import main as create_index
from pypi_create_index_html import enhance_packages

MAX_PKGS = 5000  # or try 1000
PYPI_URL = 'https://pypi.python.org/pypi'
PYPI_FMT = PYPI_URL + '/{}/json'

fields = 'pkg_name downloads py2only py3 release url'
pkg_info = collections.namedtuple('pkg_info', fields)
FMT = '{pkg_name:30}{release:13}{py3}  {py2only}'
py2_only_classifier = 'Programming Language :: Python :: 2 only'
py3_classifier = 'Programming Language :: Python :: 3'


def header():
    fmt = '{:30}{:13}{}'
    return '\n'.join((fmt.format('Module name', 'Latest', 'Python 3?'),
                      fmt.format('=' * 11, '=' * 6, '=' * 9)))


async def fetch_json(session, url):
    with aiohttp.Timeout(10):
        async with session.get(url) as response:
            assert response.status == 200
            return await response.json()


async def get_package_info(session, pkg_name, downloads):
    info = (await fetch_json(session, PYPI_FMT.format(pkg_name)))['info']
    classifiers = '\n'.join(info['classifiers'])
    py2only = py2_only_classifier in classifiers
    py3 = py3_classifier in classifiers
    release = info['version']
    url = info['package_url']
    return pkg_info(pkg_name, downloads, py2only, py3, release, url)


def create_tasks(session, max_pkgs=MAX_PKGS):
    client = ServerProxy(PYPI_URL)
    return [get_package_info(session, pkg_name, downloads)
            for pkg_name, downloads in client.top_packages(max_pkgs)]


async def get_packages_info(max_pkgs=MAX_PKGS, start_time=None):
    await asyncio.sleep(1)  # ensure the server is highly responsive on bootup
    fmt = 'Gathering Python 3 support info on the top {:,} PyPI packages...'
    print(fmt.format(max_pkgs))
    start_time = start_time or time.time()
    packages = []
    with aiohttp.ClientSession() as session:
        tasks = create_tasks(session, max_pkgs)
        while tasks:
            current_block, tasks = tasks[:200], tasks[200:]
            packages += await asyncio.gather(*current_block)
            if len(packages) == 200:
                html = create_index(packages).splitlines()
                html = '\n'.join(line.rstrip() for line in html if line.strip())
                with open('index.html', 'w') as out_file:
                    out_file.write(html)
                print('index.html written with {:,} packages after {:.2f} '
                      'seconds.'.format(len(packages),
                                        time.time() - start_time))
    return enhance_packages(packages), datetime.datetime.utcnow()


def get_from_pypi(loop, max_pkgs=MAX_PKGS, start_time=None):
    start_time = start_time or time.time()
    asyncio.sleep(0.5)  # give the server a half a second to come up
    # loop = asyncio.get_event_loop()
    return loop.run_until_complete(get_packages_info(max_pkgs, start_time))


if __name__ == '__main__':
    from pypi_io_utils import write_packages
    start = time.time()
    packages = get_from_pypi(asyncio.get_event_loop(), MAX_PKGS, start)
    print(time.time() - start, 'seconds')  # 5000 packages in 25 seconds on Bluemix
    exit()
    write_packages(packages)
    print(header())
    for package in packages:
        # print(FMT.format(**package_info._asdict()))
        # print(package._asdict())
        print(tuple(package))

    losers = [package for package in packages if not package.py3]
    print('\n{} Python 2 ONLY packages:'.format(len(losers)))
    if losers:
        print(header())
        print('\n'.join(FMT.format(**package._asdict()) for package in losers))
    else:
        print('Nirvana has been achieved!')

    print(time.time() - start, 'seconds')
