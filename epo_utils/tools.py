# -*- coding: utf-8 -*-
""" Module for dealing text-data."""
from argparse import _ActionsContainer

import langid
import collections


def filter_language(docs, attribute, lang='en', filter_empty=True):
    """ Filter document collection on language.

    Parameters
    ----------
    docs : Sequence[epo_utils.documents.ExchangeDocument]
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


def make_meta_dict(doc, class_resolutions=(2, 3), n_classes=2):
    """

    Parameters
    ----------
    doc : epo_utils.documents.ExchangeDocument
        Document to parse.
    class_resolutions : tuple[int]
        Class resolutions to parse.
    n_classes : int
        Number of classes to include sorted according to frequency.

    Returns
    -------

    """
    meta = collections.OrderedDict()
    meta['country'] = doc.country
    meta['date'] = next((ref.date for ref in doc.publication_reference
                         if ref is not None), None)
    meta['kind'] = next((ref.kind for ref in doc.publication_reference
                         if ref is not None), None)
    app = next(iter(doc.applicants), None)
    meta['first applicant'] = app.epodoc if app is not None else None

    inv = next(iter(doc.inventors), None)
    meta['first inventor'] = inv.epodoc if inv is not None else None

    for class_scheme in ('CPC', 'IPC', 'IPCR'):
        class_list = doc.classifications.get(class_scheme, list())

        for n in class_resolutions:
            n = n + 1 if n > 1 else n
            classes_at_res = [c[:n] for c in class_list]
            counter = collections.Counter(classes_at_res)
            picked_w_counts = counter.most_common(n_classes)
            unzipped = list(zip(*picked_w_counts))
            picked = unzipped[0] if unzipped else ()
            filled_picked = picked + (None, ) * (n_classes - len(picked))

            for i, class_ in enumerate(filled_picked, start=1):
                label = '{}:{} - {}'.format(class_scheme, n, i)
                meta[label] = class_

    return meta
