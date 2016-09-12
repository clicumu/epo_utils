# -*- coding: utf-8 -*-
""" Module for making calls to EPO-OPS REST-API.

This module contain classes and functions to get data from
[EPO-OPS API](http://www.epo.org/searching-for-patents/technical/espacenet/ops.html)
"""
import logging
import time
import re
from datetime import datetime, timedelta
from collections import namedtuple
from base64 import b64encode
import enum

import requests
try:
    import requests_cache
except ImportError:
    _HAS_CACHE = False
else:
    _HAS_CACHE = True

from epo_utils.ops.documents import DocumentID


AUTH_URL = 'https://ops.epo.org/3.1/auth/accesstoken'
""" str : Authorization URL. """

URL_PREFIX = 'https://ops.epo.org/3.1/rest-services'
""" str: Base URL for all calls to API. """

VALID_ENDPOINTS = [
    'fulltext',
    'claims',
    'description',
    'images',
    'equivalents',
    'biblio',
    'abstract',
    '',
]
""" list[str] : EPO:s available API endpoints."""

VALID_IDTYPES = ('epodoc', 'docdb', 'original', 'classification')
""" list[str] : Valid API-input formats. """


class Services(enum.Enum):
    """ EPO-OPS service - service url-infix mapping."""
    Family = 'family'
    Numbers = 'number-service'
    Published = 'published-data'
    PublishedSearch = 'published-data/search'
    Register = 'register'
    RegisterSearch = 'register/search'
    Classification = 'classification/cpc'


class ReferenceType(enum.Enum):
    """ EPO-OPS API-call reference-types. """
    Publication = 'publication'
    Application = 'application'
    Priority = 'priority'


class SearchFields(enum.Enum):
    """
    CQL search field identifiers according to:
    https://worldwide.espacenet.com/help?locale=en_EP&method=handleHelpTopic&topic=fieldidentifier
    """
    Inventor = 'in'
    Applicant = 'pa'
    Title = 'ti'
    Abstract = 'ab'
    PriorityNumber = 'pr'
    PublicationNumber = 'pn'
    ApplicationNumber = 'ap'
    PublicationDate = 'pd'
    CitedDocument = 'ct'
    CooperativePatentClassification = 'cpc'
    InventorAndApplicant = 'ia'
    TitleAbstract = 'ta'
    TitleAbstractInventorApplicant = 'txt'
    ApplicationPublicationPriority = 'num'
    IPC = 'ipc'
    ICPCPC = 'cl'
    CQL = 'cql'


class APIInput:
    """
    Simple wrapper around API-input.
    """
    def __init__(self, id_type, number, kind=None, country=None, date=None):
        if id_type not in VALID_IDTYPES:
            raise ValueError('invalid id_type: {}'.format(id_type))
        if date is not None:
            date = str(date)
            try:
                datetime.strptime(date, '%Y%m%d')
            except ValueError:
                raise ValueError('date must be in YYYYMMDD-format')
            else:
                if len(date) != 8:
                    raise ValueError('date must be in YYYYMMDD-format')
        if country is not None and not country.strip():
            raise ValueError('country cant be empty if provided')
        if kind is not None and not kind.strip():
            raise ValueError('kind cant be empty if provided')

        self.id_type = id_type
        self.number = str(number)
        self.kind = kind
        self.country = country
        self.date = date

    @classmethod
    def from_document_id(cls, document_id):
        """ Convert instance of :class:`epo_utils.ops.documents.DocumentID`
        to `APIInput`.

        Parameters
        ----------
        document_id : epo_utils.ops.documents.DocumentID
            Document-ID to translate.

        Returns
        -------
        APIInput
        """
        if not isinstance(document_id, DocumentID):
            raise ValueError('document_id must be DocumentID-instance')

        return cls(document_id.id_type, document_id.doc_number,
                   document_id.kind, document_id.country, document_id.date)

    def to_id(self):
        """ Format as valid API-input ID.

        Returns
        -------
        str
        """
        if (',' in self.number or '.' in self.number or '/' in self.number) \
                and self.id_type != 'classification':
            number = '({})'.format(self.number)
        else:
            number = self.number

        parts = (part for part in [self.country, number, self.kind, self.date]
                 if part is not None)

        if self.id_type == 'original':
            id_ = '.'.join(parts).replace(' ', '%20')
        elif self.id_type == 'docdb':
            id_ = '.'.join(parts)
        elif self.id_type == 'epodoc':
            id_ = ''.join(parts)
        elif self.id_type == 'classification':
            return number
        else:
            raise ValueError('invalid id_type: {}'.format(self.id_type))

        return id_

    def __repr__(self):
        module = self.__class__.__module__
        class_name = self.__class__.__name__
        return '<{0}.{1}: {2}>'.format(module, class_name, self.to_id())


Token = namedtuple('Token', ['token', 'expires'])


class EPOClient:
    """ A simple client to call EPO-OPS REST-API using `requests`.

    Parameters
    ----------
    accept_type : str
        Http accept type.
    key : str, optional
        EPO OPS user key.
    secret : str, optional
        EPO OPS user secret.
    cache : bool
        If True, try to use `requests_cache` for caching. Default False.
    cache_kwargs : dict, optional.
        Passed to :py:func:`requests_cache.install_cache` as keyword
        arguments if provided.

    Attributes
    ----------
    secret : str
    key : str
    token : Token or None
    quota_per_hour_used : int
    quota_per_week_used : int
    """

    def __init__(self, accept_type='xml', key=None, secret=None, cache=False,
                 cache_kwargs=None):
        if accept_type.startswith('application/'):
            self.accept_type = accept_type
        else:
            self.accept_type = 'application/{}'.format(accept_type)

        if cache and _HAS_CACHE:
            logging.info('Installs cache.')
            requests_cache.install_cache(**(cache_kwargs or dict()))
        elif cache:
            raise ValueError('cache is set to True but requests_cache '
                             'is not available.')

        self.secret = secret
        self.key = key
        self.quota_per_hour_used = 0
        self.quota_per_week_used = 0

        if all([secret, key]):
            logging.debug('Auth provided.')
            self.token = self.authenticate()
        else:
            logging.debug('Auth not provided')
            self.token = None

        self._last_call = {
            'search': None,
            'retrieval': None,
            'inpadoc': None,
            'images': None,
            'other': None
        }
        self._next_call = self._last_call.copy()

    def fetch(self, service, ref_type, api_input, endpoint='',
              options=None, extra_headers=None):
        """ Generic function to fetch data from the EPO-OPS API.

        Parameters
        ----------
        service : Services
            OPS-service to fetch from.
        ref_type : ReferenceType
            OPS-reference type of data to fetch.
        api_input : APIInput, list[APIInput]
            Input to API-call.
        endpoint : str
            API-endpoint to call.
        options : list, optional
            API-call constitents.
        extra_headers : dict, optional
            Additional or custom headers to be used.
        use_post : bool
            If True, POST will be used for request.

        Returns
        -------
        requests.Response
        """
        if not isinstance(ref_type, ReferenceType):
            raise ValueError('invalid ref_type: {}'.format(ref_type))
        if not isinstance(service, Services):
            raise ValueError('invalid service: {}'.format(service))
        if endpoint not in VALID_ENDPOINTS:
            raise ValueError('invalid endpoint: {}'.format(endpoint))

        try:
            input_text = ','.join(i.to_id() for i in api_input)
        except TypeError:
            input_text = api_input.to_id()
            id_types = {api_input.id_type}
        else:
            id_types = {i.id_type for i in api_input}

        if len(id_types) > 1:
            raise ValueError('non-matching id-types')

        options = options or list()
        url = build_ops_url(service, ref_type, id_types.pop(),
                            endpoint, options)

        headers = self._make_headers(extra_headers)

        logging.debug('Makes request to: {}\nheaders: {}'.format(url, headers))

        response = self.post('retrieval', url, input_text, headers=headers)
        return response

    def search(self, query, fetch_range, service=Services.PublishedSearch,
               endpoint='', extra_headers=None):
        """ Post a GET-search query.

        Parameters
        ----------
        query : str
            Query string.
        fetch_range : tuple[int, int]
            Get entries `fetch_range[0]` to `fetch_range[1]`.
        service : Services
            Which service to use for search.
        endpoint : str, list[str]
            Endpoint(s) to search.
        extra_headers : dict, optional
            Additional or custom headers to be used.

        Returns
        -------
        requests.Response
        """
        if not isinstance(service, Services):
            raise ValueError('invalid service: {}'.format(service))
        if not isinstance(endpoint, (list, tuple)):
            endpoint = [endpoint]
        if not all(e in VALID_ENDPOINTS for e in endpoint):
            invalid = filter(lambda e: e not in VALID_ENDPOINTS,
                             endpoint)
            raise ValueError('invalid endpoint: {}'.format(next(invalid)))
        if not len(fetch_range) == 2 \
                and all(isinstance(i, int) for i in fetch_range):
            raise ValueError('invalid fetch_range: {}'.format(fetch_range))

        headers = self._make_headers(
            {'Accept': 'application/exchange+xml',
             'X-OPS-Range': '{}-{}'.format(*fetch_range)}
        )
        headers.update(extra_headers or dict())

        url = build_ops_url(service, options=endpoint)

        logging.info('Sends query: {}'.format(query))
        response = self.post('search', url, headers=headers, data={'q': query})
        logging.info('Query successful.')

        return response

    def authenticate(self):
        """ If EPO-OPS customer key and secret is available
        get access-token.

        Returns
        -------
        token : Token
            Token and expiration time.
        """
        if not all([self.secret, self.key]):
            return None

        logging.info('Attempts to authenticate.')

        # Post base 64-encoded credentials to get access-token.
        credentials = '{0}:{1}'.format(self.key, self.secret)
        encoded_creds = b64encode(credentials.encode('ascii')).decode('ascii')
        headers = {'Authorization': 'Basic {}'.format(encoded_creds)}
        payload = {'grant_type': 'client_credentials'}
        response = requests.post(AUTH_URL, headers=headers, data=payload)
        response.raise_for_status()
        logging.info('Authentication succeeded.')

        # Parse response.
        content = response.json()
        token = content['access_token']
        expires_in = int(content['expires_in'])
        expires = datetime.now() + timedelta(seconds=expires_in)
        token = Token(token, expires)
        return token

    def post(self, service, *args, **kwargs):
        """ Makes an auto-throttled POST to the OPS-API.

        Parameters
        ----------
        service : str
            OPS-system called.
        *args
            Positional arguments passed to :py:`requests.post`
        **kwargs
            Keyword arguments passed to :py:`requests.post`

        Returns
        -------
        requests.Response
        """
        logging.debug(
            '{} POST\nargs: {}\nkwargs: {}'.format(service,args, kwargs))

        response = self._throttled_call(service, requests.post, *args, **kwargs)
        response.raise_for_status()

        return response

    def get(self, service, *args, **kwargs):
        """ Makes an auto-throttled GET-call to the OPS-API.

        Parameters
        ----------
        service : str
            OPS-system called.
        *args
            Positional arguments passed to :py:`requests.get`
        **kwargs
            Keyword arguments passed to :py:`requests.get`

        Returns
        -------
        requests.Response
        """
        logging.debug(
            '{} POST\nargs: {}\nkwargs: {}'.format(service, args, kwargs))

        response = self._throttled_call(service, requests.get, *args, **kwargs)
        response.raise_for_status()

        return response

    def _throttled_call(self, service, request, *args, **kwargs):
        """

        Parameters
        ----------
        service : str
        request : Callable
        *args
            Positional arguments passed to `request`
        **kwargs
            Keyword arguments passed to :py:`request`

        Returns
        -------
        requests.Response
        """
        logging.debug('Throttle with: {}'.format(service))
        if service not in self._last_call:
            raise ValueError('Invalid service: {}'.format(service))

        next_call = self._next_call[service]
        now = datetime.now()

        if next_call is not None and now < next_call:
            diff = next_call - now
            time.sleep(diff.seconds + diff.microseconds / 1e6)

        self._last_call[service] = datetime.now()
        response = request(*args, **kwargs)

        # The OPS-API sets its request-limit by minute, which is updated
        # for each call. Therefore, the throttling delay is set to
        # 60 sec / calls per minute.
        throttle_header = response.headers['X-Throttling-Control']
        pattern = r'{}=([a-z]+):(\d+)'.format(service)
        color, n_str = re.search(pattern, throttle_header).groups()
        n_per_min = int(n_str)
        delay = 60 / n_per_min  # Delay in seconds.
        seconds = int(delay)
        milliseconds = int((delay - seconds) * 1e3)
        next_delta = timedelta(seconds=seconds, milliseconds=milliseconds)

        self._next_call[service] = self._last_call[service] + next_delta

        # Update quota used.
        q_per_h = int(response.headers['X-IndividualQuotaPerHour-Used'])
        q_per_w = int(response.headers['X-RegisteredQuotaPerWeek-Used'])
        self.quota_per_hour_used = q_per_h
        self.quota_per_week_used = q_per_w

        return response

    def _make_headers(self, extras=None):
        """ Prepare request headers.

        Parameters
        ----------
        extras : dict, optional
            Extra headers which should be used.

        Returns
        -------
        dict
        """
        headers = {'Accept': self.accept_type}
        if self.token is not None:
            if self.token is None or datetime.now() > self.token.expires:
                # Refresh token if is expired or missing.
                self.token = self.authenticate()

            headers['Authorization'] = 'Bearer {}'.format(self.token.token)

        headers.update(extras or dict())

        return headers


def build_ops_url(service, reference_type=None, id_type=None,
                  endpoint=None, options=None):
    """ Prepare an url for calling the OPS-API.

    If `only_input_format` is False the URL will be formatted as::

    :py:const:`URL_PREFIX`/service/reference-type/inputformat/input/[endpoint]/[constituent(s)]

    Otherwise it will be formatted::

    :py:const:`URL_PREFIX`/service/reference-type/inputformat/[endpoint]/[constituent(s)]

    Parameters
    ----------
    service : Services
        OPS-service.
    reference_type : ReferenceType, optional
        Reference type to call.
    endpoint : str, optional
        Optional endpoint.
    options : list, optional
        Optional constituents.

    Returns
    -------
    url : str
        Formatted url.
    """
    url_parts = [
        URL_PREFIX,
        service.value if service is not None else None,
        reference_type.value if reference_type is not None else None,
        id_type if input is not None else None,
        endpoint,
        ','.join(options) if options is not None else None
    ]
    present_parts = filter(None, url_parts)
    url = '/'.join(present_parts)
    logging.debug('Built url: {}'.format(url))
    return url


__all__ = [
    AUTH_URL,
    URL_PREFIX,
    VALID_ENDPOINTS,
    Services,
    ReferenceType,
    SearchFields,
    EPOClient,
    Token,
    APIInput
]