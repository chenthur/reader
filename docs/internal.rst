
Internal API
============

This part of the documentation covers the internal interfaces of *reader*,
which are useful for plugins,
or if you want to use low-level functionality
without using :class:`~reader.Reader` itself.

.. warning::

    As of version |version|,
    the internal API is **not** part of the public API;
    it is not stable yet and might change without any notice.


Parser
------

.. module:: reader._parser

.. autofunction:: default_parser

.. autoclass:: Parser
    :members:
    :special-members: __call__


.. module:: reader._requests_utils

.. autoclass:: SessionFactory(...)
    :members:
    :special-members: __call__

.. autoclass:: SessionWrapper(...)
    :members:


Protocols
~~~~~~~~~

.. module:: reader._parser
    :noindex:

.. autoclass:: FeedArgument
    :members:

.. autoclass:: RetrieverType
    :members:
    :special-members: __call__

.. autoclass:: FeedForUpdateRetrieverType
    :members:
    :show-inheritance:

.. autoclass:: ParserType
    :members:
    :special-members: __call__

.. autoclass:: HTTPAcceptParserType
    :members:
    :show-inheritance:

.. autoclass:: EntryPairsParserType
    :members:
    :show-inheritance:


.. module:: reader._requests_utils
    :noindex:

.. autoclass:: RequestHook
    :members:
    :special-members: __call__

.. autoclass:: ResponseHook
    :members:
    :special-members: __call__


Data objects
~~~~~~~~~~~~

.. module:: reader._parser
    :noindex:

.. autoclass:: RetrieveResult
    :members:

.. module:: reader._types

.. autoclass:: ParsedFeed
    :members:

.. autoclass:: FeedData
    :members:
    :undoc-members:

.. autoclass:: EntryData
    :members:
    :undoc-members:

.. todo:: the following should be in the storage section, when we get one

.. autoclass:: FeedForUpdate
    :members:

.. autoclass:: EntryForUpdate
    :members:


Recipes
-------

.. include:: ../examples/parser_only.py
    :start-after: """
    :end-before: """  # docstring-end

.. literalinclude:: ../examples/parser_only.py
    :start-after: """  # docstring-end