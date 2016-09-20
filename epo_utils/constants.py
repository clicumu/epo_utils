# -*- coding: utf-8 -*-
""" Package level constants."""

AUTH_URL = 'https://ops.epo.org/3.1/auth/accesstoken'
""" str : Authorization URL. """

URL_PREFIX = 'https://ops.epo.org/3.1/rest-services'
""" str: Base URL for all calls to API. """

VALID_ENDPOINTS = frozenset((
    'fulltext',
    'claims',
    'description',
    'images',
    'equivalents',
    'biblio',
    'abstract',
    ''
))
""" frozenset[str] : EPO:s available API endpoints."""

VALID_IDTYPES = frozenset(('epodoc', 'docdb', 'original', 'classification'))
""" frozenset[str] : Valid API-input formats. """

HAS_FULLTEXT = frozenset(('EP', 'WO', 'AT', 'CA', 'CH', 'GB', 'ES'))
""" frozenset[str] : Country codes supporting full-text inquiry (OPS v3.1) """
