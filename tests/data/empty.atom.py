import datetime

from reader import Content
from reader import Enclosure
from reader.core.types import EntryData
from reader.core.types import FeedData


feed = FeedData(url='{}empty.atom'.format(url_base))

entries = [
    EntryData(
        id='urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a',
        updated=None,
        # added by feedparser
        link='urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a',
    )
]
