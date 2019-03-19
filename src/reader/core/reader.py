import logging
import datetime

from .storage import Storage
from .parser import RequestsParser
from .updater import update_feed
from .exceptions import ParseError, FeedNotFoundError

log = logging.getLogger('reader')


def feed_argument(feed):
    try:
        return feed.url
    except AttributeError:
        if isinstance(feed, str):
            return feed
        raise ValueError('feed')

def entry_argument(entry):
    try:
        return entry.feed.url, entry.id
    except AttributeError:
        if isinstance(entry, tuple) and len(entry) == 2:
            feed_url, entry_id = entry
            if isinstance(feed_url, str) and isinstance(entry_id, str):
                return entry
        raise ValueError('entry')


class Reader:

    """A feed reader.

    Args:
        path (str): Path to the reader database.

    Raises:
        StorageError

    """

    _get_entries_chunk_size = 2 ** 8

    def __init__(self, path=None):
        self._storage = Storage(path)
        self._parse = RequestsParser()
        self._post_entry_add_plugins = []

    def add_feed(self, feed):
        """Add a new feed.

        Args:
            feed (str or Feed): The feed URL.

        Raises:
            FeedExistsError
            StorageError

        """
        url = feed_argument(feed)
        now = self._now()
        return self._storage.add_feed(url, now)

    def remove_feed(self, feed):
        """Remove a feed.

        Also removes all of the feed's entries.

        Args:
            feed (str or Feed): The feed URL.

        Raises:
            FeedNotFoundError
            StorageError

        """
        url = feed_argument(feed)
        return self._storage.remove_feed(url)

    def get_feeds(self, sort='title'):
        """Get all the feeds.

        Args:
            sort (str): How to order feeds; one of ``'title'`` (by
                :attr:`~Feed.user_title` or :attr:`~Feed.title`, case
                insensitive; default), or ``'added'`` (last added first).

        Yields:
            :class:`Feed`: Sorted according to ``sort``.

        Raises:
            StorageError

        """
        if sort not in ('title', 'added'):
            raise ValueError("sort should be one of ('title', 'added')")
        return self._storage.get_feeds(sort=sort)

    def get_feed(self, feed):
        """Get a feed.

        Arguments:
            feed (str or Feed): The feed URL.

        Returns:
            Feed or None: The feed if it exists, None if it doesn't.

        Raises:
            StorageError

        """
        url = feed_argument(feed)
        feeds = list(self._storage.get_feeds(url=url))
        if len(feeds) == 0:
            return None
        elif len(feeds) == 1:
            return feeds[0]
        else:
            assert False, "shouldn't get here"  # pragma: no cover

    def set_feed_user_title(self, feed, title):
        """Set a user-defined title for a feed.

        Args:
            feed (str or Feed): The feed URL.
            title (str or None): The title, or None to remove the current title.

        Raises:
            FeedNotFoundError
            StorageError

        """
        url = feed_argument(feed)
        return self._storage.set_feed_user_title(url, title)

    def update_feeds(self, new_only=False):
        """Update all the feeds.

        Args:
            new_only (bool): Only update feeds that have never been updated.

        Raises:
            StorageError

        """
        for row in self._storage.get_feeds_for_update(new_only=new_only):
            try:
                self._update_feed(row)
            except FeedNotFoundError as e:
                log.info("update feed %r: feed removed during update", e.url)
            except ParseError as e:
                log.exception("update feed %r: error while getting/parsing feed, skipping; exception: %r", e.url, e.__cause__)

    def update_feed(self, feed):
        """Update a single feed.

        Args:
            feed (str or Feed): The feed URL.

        Raises:
            FeedNotFoundError
            StorageError

        """
        url = feed_argument(feed)
        rows = list(self._storage.get_feeds_for_update(url))
        if len(rows) == 0:
            raise FeedNotFoundError(url)
        elif len(rows) == 1:
            self._update_feed(rows[0])
        else:
            assert False, "shouldn't get here"  # pragma: no cover

    @staticmethod
    def _now():
        return datetime.datetime.utcnow()

    def _update_feed(self, feed_for_update):
        feed, new_entries = update_feed(feed_for_update, self._now(), self._parse, self._storage)

        for entry in new_entries:
            for plugin in self._post_entry_add_plugins:
                plugin(self, feed, entry)

    def get_entries(self, which='all', feed=None, has_enclosures=None):
        """Get all or some of the entries.

        Args:
            which (str): One of ``'all'``, ``'read'``, or ``'unread'``.
            feed (str or Feed or None): Only return the entries for this feed.
            has_enclosures (bool or None): Only return entries that (don't)
                have enclosures.

        Yields:
            :class:`Entry`: Last published/updated entries first.

        Raises:
            FeedNotFoundError: Only if `feed` is not None.
            StorageError

        """

        # If we ever implement pagination, consider following the guidance in
        # https://specs.openstack.org/openstack/api-wg/guidelines/pagination_filter_sort.html

        feed_url = feed_argument(feed) if feed is not None else None
        if which not in ('all', 'unread', 'read'):
            raise ValueError("which should be one of ('all', 'read', 'unread')")
        if has_enclosures not in (None, False, True):
            raise ValueError("has_enclosures should be one of (None, False, True)")
        chunk_size = self._get_entries_chunk_size

        last = None
        while True:

            entries = self._storage.get_entries(
                which=which,
                feed_url=feed_url,
                has_enclosures=has_enclosures,
                chunk_size=chunk_size,
                last=last,
            )

            # When chunk_size is 0, don't chunk the query.
            #
            # This will ensure there are no missing/duplicated entries, but
            # will block database writes until the whole generator is consumed.
            #
            # Currently not exposed through the public API.
            #
            if not chunk_size:
                entries = (e for e, _ in entries)
                yield from entries
                return

            entries = list(entries)
            if not entries:
                break

            _, last = entries[-1]

            entries = (e for e, _ in entries)
            yield from entries

    def mark_as_read(self, entry):
        """Mark an entry as read.

        Args:
            entry (tuple(str, str) or Entry): (feed URL, entry id) tuple.

        Raises:
            EntryNotFoundError
            StorageError

        """
        feed_url, entry_id = entry_argument(entry)
        self._storage.mark_as_read_unread(feed_url, entry_id, 1)

    def mark_as_unread(self, entry):
        """Mark an entry as unread.

        Args:
            entry (tuple(str, str) or Entry): (feed URL, entry id) tuple.

        Raises:
            EntryNotFoundError
            StorageError

        """
        feed_url, entry_id = entry_argument(entry)
        self._storage.mark_as_read_unread(feed_url, entry_id, 0)
