"""
enclosure_tags
~~~~~~~~~~~~~~

Fix tags for MP3 enclosures (e.g. podcasts).

Adds a "with tags" link to a version of the file with tags set as follows:

* the entry title as title
* the feed title as album
* the entry/feed author as author

This plugin needs additional dependencies, use the ``unstable-plugins`` extra
to install them:

.. code-block:: bash

    pip install reader[unstable-plugins]

To load::

    READER_APP_PLUGIN='reader._plugins.enclosure_tags:init' \\
    python -m reader serve

Implemented for :issue:`50`.
Became a plugin in :issue:`52`.
Streaming added in :issue:`344.

"""

import io
from urllib.parse import urlparse

import mutagen.mp3
import requests
from flask import Blueprint
from flask import request
from flask import Response
from flask import stream_with_context
from flask import url_for


blueprint = Blueprint('enclosure_tags', __name__)


ALL_TAGS = ('album', 'title', 'artist', 'genre')


@blueprint.route('/enclosure-tags', defaults={'filename': None})
@blueprint.route('/enclosure-tags/<filename>')
def enclosure_tags(filename):
    tags = {}
    for tag in ALL_TAGS:
        if value := request.args.get(tag):
            tags[tag] = value

    # TODO: handle raise_for_status() exceptions nicely
    headers, chunks = update_tags_requests(request.args['url'], tags)

    def iter_chunks():
        # Send the headers as soon as possible.
        # Some browsers wait for the headers before showing the "Save As" dialog.
        yield ''
        yield from chunks

    return Response(stream_with_context(iter_chunks()), headers=headers)


def update_tags_requests(url, tags, *, session=requests):
    """update_tags_requests(url, ...) -> (headers, iter_chunks())"""

    response = requests.get(url, stream=True)
    response.raise_for_status()

    headers = {}

    if content_disposition := response.headers.get('content-disposition'):
        headers['content_disposition'] = content_disposition
        response.raw.name = content_disposition
    else:
        response.raw.name = urlparse(url).path.split('/')[-1]

    old_prefix, new_prefix = update_tags(response.raw, tags)

    try:
        content_length = int(response.headers.get('content-length', ''))
    except ValueError:
        pass
    else:
        content_length = content_length - len(old_prefix) + len(new_prefix)
        headers['content-length'] = str(content_length)

    if content_type := response.headers.get('content-type'):
        headers['content-type'] = content_type

    def iter_chunks():
        with response:
            yield new_prefix
            yield from response.iter_content(2**18)

    return headers, iter_chunks()


def update_tags(file, tags):
    """update_tags(file, ...) -> (old_prefix, new_prefix)

    Rewrite the prefix of file to update ID3v2 tags.

    """
    prefix = b''
    easy = None
    for size in [2**17, 2**17, 2**18, 2**19, 2**19, 2**19]:
        chunk = file.read(size)
        if not chunk:
            break
        prefix += chunk
        try:
            easy = mutagen.mp3.EasyMP3(io.BytesIO(prefix))
        except mutagen.MutagenError:
            # TODO: debug logging
            pass
        else:
            break

    if easy is None:
        return prefix, prefix

    if easy.info.sketchy:
        return prefix, prefix

    offset = easy.info.frame_offset

    for tag, value in tags.items():
        easy[tag] = value

    out = io.BytesIO()
    easy.save(out)

    return prefix, out.getvalue() + prefix[offset:]


def enclosure_tags_filter(enclosure, entry):
    filename = urlparse(enclosure.href).path.split('/')[-1]
    if not filename.endswith('.mp3'):
        return []

    args = {'url': enclosure.href, 'filename': filename}
    if entry.title:
        args['title'] = entry.title
    if entry.feed.title:
        args['album'] = entry.feed.title
    if entry.author or entry.feed.author:
        args['artist'] = entry.author or entry.feed.author

    return [('with tags', url_for('enclosure_tags.enclosure_tags', **args))]


def init(app):
    app.register_blueprint(blueprint)
    app.reader_additional_enclosure_links.append(enclosure_tags_filter)
