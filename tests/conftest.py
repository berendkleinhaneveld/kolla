import textwrap

import pytest

from kolla import sfc


def load(source):
    source = textwrap.dedent(source)
    return sfc.sfc.load_from_string(source)


@pytest.fixture
def parse_source():
    yield load
