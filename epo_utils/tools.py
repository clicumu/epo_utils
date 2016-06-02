# -*- coding: utf-8 -*-
""" Module for dealing text-data."""
import langid


def filter_language(docs, attribute, lang='en', filter_empty=True):
    """ Filter document collection on language.

    Parameters
    ----------
    docs : Sequence[api.ops.documents.ExchangeDocument]
        Documents to filter.
    attribute : str
        Text attribute to filter on.
    lang : str
        Language code, default "en"
    filter_empty : bool
        If True, empty strings will be filtered as well.

    Yields
    ------
    api.ops.documents.ExchangeDocument
    """
    for doc in docs:
        text = getattr(doc, attribute)

        if filter_empty and not text:
            continue

        elif text:
            if langid.classify(text) == lang:
                yield doc

        elif not text:
            yield doc
