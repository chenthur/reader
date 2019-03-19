import logging
import datetime

import attr

from .exceptions import NotModified

log = logging.getLogger('reader')


def update_feed(old_feed, now, parser, storage):
    updater = Updater(old_feed, now, parser, storage)
    updater()
    return updater.new_feed, updater.new_entries


@attr.s
class Updater:

    old_feed = attr.ib()
    now = attr.ib()
    parser = attr.ib()
    storage = attr.ib()

    new_feed = attr.ib(default=None)
    new_entries = attr.ib(default=attr.Factory(list))
    updated_entries = attr.ib(default=attr.Factory(list))

    def __attrs_post_init__(self):
        if self.old_feed.stale:
            # db_updated=None not ot tested (removing it causes no tests to fail).
            #
            # This only matters if last_updated is None *and* db_updated is
            # not None. The way the code is, this shouldn't be possible
            # (last_updated is always set if the feed was updated at least
            # once, unless the database predates last_updated).
            #
            self.old_feed = self.old_feed._replace(updated=None, http_etag=None, http_last_modified=None)
            log.info("update feed %r: feed marked as stale, ignoring updated, http_etag and http_last_modified", self.url)

    @property
    def url(self):
        return self.old_feed.url

    @property
    def stale(self):
        return self.old_feed.stale

    def parse_feed(self):
        return self.parser(self.url,
                           self.old_feed.http_etag,
                           self.old_feed.http_last_modified)

    def update_feed_last_updated(self):
        self.storage.update_feed_last_updated(self.url, self.now)

    def update_feed(self, parse_result):
        self.storage.update_feed(self.url,
                                 parse_result.feed,
                                 parse_result.http_etag,
                                 parse_result.http_last_modified,
                                 self.now)

    def should_update_feed(self, new):
        old = self.old_feed
        log.debug("update feed %r: old updated %s, new updated %s", self.url, old.updated, new.updated)

        if not old.last_updated:
            log.info("update feed %r: feed has no last_updated, treating as updated", self.url)
            feed_was_updated = True

            assert not old.updated, "updated must be None if last_updated is None"

        elif not new.updated:
            log.info("update feed %r: feed has no updated, treating as updated", self.url)
            feed_was_updated = True
        else:
            feed_was_updated = not(new.updated
                                   and old.updated
                                   and new.updated <= old.updated)

        should_be_updated = self.stale or feed_was_updated

        if not should_be_updated:
            # Some feeds have entries newer than the feed.
            # https://github.com/lemon24/reader/issues/76
            log.info("update feed %r: feed not updated, updating entries anyway", self.url)

        return should_be_updated

    def should_update_entry(self, new, old):
        updated = new.updated

        if self.stale:
            log.debug("update entry %r of feed %r: feed marked as stale, updating anyway", new.id, self.url)
        elif not new.updated:
            log.debug("update entry %r of feed %r: has no updated, updating but not changing updated", new.id, self.url)
            updated = old.updated or self.now
        elif old.updated and new.updated <= old.updated:
            log.debug("update entry %r of feed %r: entry not updated, skipping (old updated %s, new updated %s)", new.id, self.url, old.updated, new.updated)
            return 0, 0, updated

        log.debug("update entry %r of feed %r: entry added/updated", new.id, self.url)
        return (0, 1, updated) if not old.exists else (1, 0, updated)

    def get_entry_pairs(self, entries):
        for entry in entries:
            yield entry, self.storage.get_entry_for_update(self.url, entry.id)

    def get_entries_to_update(self, entries):
        last_updated = self.now
        for new_entry, old_entry in reversed(list(self.get_entry_pairs(entries))):
            assert new_entry.feed is None
            entry_updated, entry_new, updated = self.should_update_entry(new_entry, old_entry)

            if entry_updated or entry_new:
                yield entry_new, new_entry, updated, last_updated

            last_updated += datetime.timedelta(microseconds=1)

    def update_entries(self, entries):
        entries_to_update = self.get_entries_to_update(entries)

        updated_entries = []
        new_entries = []

        def prepare_entries_for_update():
            for entry_new, entry, updated, last_updated in entries_to_update:
                if entry_new:
                    new_entries.append(entry)
                else:
                    updated_entries.append(entry)
                yield self.url, entry, updated, last_updated

        self.storage.add_or_update_entries(prepare_entries_for_update())

        return updated_entries, new_entries

    def __call__(self):
        try:
            parse_result = self.parse_feed()
        except NotModified:
            log.info("update feed %r: feed not modified, skipping", self.url)
            # The feed shouldn't be considered new anymore.
            self.update_feed_last_updated()
            return None, ()

        should_update_feed = self.should_update_feed(parse_result.feed)
        updated_entries, new_entries = self.update_entries(parse_result.entries)

        if should_update_feed:
            self.update_feed(parse_result)
        elif new_entries or updated_entries:
            self.update_feed_last_updated()

        log.info("update feed %r: updated (updated %d, new %d)",
                 self.url, len(updated_entries), len(new_entries))

        self.new_feed = parse_result.feed
        self.new_entries = new_entries
        self.updated_entries = updated_entries

