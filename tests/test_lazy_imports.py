import os
import pkgutil
import subprocess
import sys
import textwrap

import pytest
from utils import parametrize_dict

import reader.plugins
from reader._feedparser import FeedparserParser
from reader._feedparser_lazy import feedparser
from reader._http_utils import parse_accept_header
from reader._http_utils import unparse_accept_header


# these tests take ~1s in total
pytestmark = pytest.mark.slow


ALL_PLUGINS = [
    'reader.' + m.name for m in pkgutil.iter_modules(reader.plugins.__path__)
]


CODE_FMT = f"""
from reader import make_reader

# "maximal" reader
reader = make_reader(
    ':memory:',
    feed_root='',
    search_enabled=True,
    plugins={ALL_PLUGINS},
)

{{code}}

import sys
print(*sys.modules)
"""


def get_imported_modules(code):
    # we don't want pytest-cov importing stuff in the subprocess
    # https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html
    # https://github.com/pytest-dev/pytest-cov/blob/v4.0.0/src/pytest-cov.embed
    env = dict(os.environ)
    for k in list(env):
        if k.startswith('COV_CORE_'):
            env.pop(k)

    process = subprocess.run(
        [sys.executable, '-c', CODE_FMT.format(code=textwrap.dedent(code))],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    assert process.returncode == 0, process.stderr

    return process.stdout.split()


LAZY_MODULES = frozenset(
    """\
    bs4
    requests
    feedparser
    urllib.request
    multiprocessing
    """.split()
)


# all in a single script to save time

NO_IMPORTS = """\
reader.add_feed('file:feed.rss')  # but not http://
list(reader.get_entries())
list(reader.search_entries('entry'))
reader._parser.session_factory.response_hooks.append('unused')
""", set()  # fmt: skip


# urllib.request being imported by requests/bs4 makes these kinda brittle, but eh...

S_ADD_HTTP = "reader.add_feed('http://example.com')", {
    'requests',
    'urllib.request',
}
S_UPDATE_FEEDS = "reader.update_feeds()", {
    'requests',
    'urllib.request',
}
S_UPDATE_FEEDS_WORKERS = "reader.update_feeds(workers=2)", {
    'requests',
    'urllib.request',
    'multiprocessing',
}
S_UPDATE_SEARCH = """\
from reader._types import EntryData, EntryUpdateIntent
from datetime import datetime
reader.add_feed('one', allow_invalid_url=False)
dt = datetime(2010, 1, 1)
entry = EntryData('one', 'entry', summary='summary')
reader._storage.add_or_update_entry(EntryUpdateIntent(entry, dt, dt, dt, dt))
reader.update_search()
""", {
    'bs4',
    'urllib.request',
}


SNIPPETS = {k: v for k, v in locals().items() if k.startswith('S_')}


@parametrize_dict('code, expected_modules', SNIPPETS)
def test_only_expected_modules_are_imported(code, expected_modules):
    modules = set(get_imported_modules(code))
    actual_modules = LAZY_MODULES & modules
    # sanity check
    assert 'reader' in modules
    assert actual_modules == expected_modules, expected_modules


def test_feedparserparser_http_accept_up_to_date():
    assert FeedparserParser.http_accept == unparse_accept_header(
        t for t in parse_accept_header(feedparser.http.ACCEPT_HEADER) if '*' not in t[0]
    )