import asyncio
import textwrap

import pytest

from kolla import sfc


# async def miniloop():
#     await asyncio.sleep(0)


# @pytest.fixture
# def process_events():
#     loop = asyncio.get_event_loop_policy().get_event_loop()

#     def run():
#         loop.run_until_complete(miniloop())

#     yield run


def load(source):
    source = textwrap.dedent(source)
    return sfc.sfc.load_from_string(source)


@pytest.fixture
def parse_source():
    yield load
