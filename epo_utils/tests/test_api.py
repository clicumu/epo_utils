import contextlib
import re
import string
import unittest
from datetime import datetime, timedelta
from unittest import mock

import epo_utils.ops.constants
import hypothesis.strategies as st
import requests
import requests_mock
from hypothesis import given, assume
from hypothesis.extra import datetime as hyp_datetime

from epo_utils.ops import api
from epo_utils.tests import utils

_date_formats = ['%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d',
                 '%y-%m-%d', '%Y%m%d', '%d%m%Y', '%y%m%d']


class APIInputTestCase(unittest.TestCase):

    @given(id_type=st.one_of(st.text(), st.sampled_from(
        epo_utils.constants.VALID_IDTYPES)),
           number=utils.doc_numbers(),
           kind=st.one_of(st.characters(), st.none()),
           country=st.one_of(st.text(max_size=2), st.none()),
           raw_date=st.one_of(hyp_datetime.datetimes(min_year=1900), st.none()),
           date_format=st.sampled_from(_date_formats))
    def test_api_input_raises_ValueError_on_bad_input(self, id_type, number,
                                                      kind, country, raw_date,
                                                      date_format):
        invalid = date_format != '%Y%m%d' and raw_date is not None
        invalid |= (id_type not in epo_utils.constants.VALID_IDTYPES)
        invalid |= country is not None and not country.strip()
        invalid |= kind is not None and not kind.strip()

        date = raw_date.strftime(date_format) if raw_date is not None else None

        if invalid:
            self.assertRaises(ValueError, api.APIInput,
                              id_type, number, kind, country, date)
        else:
            # Assert no error.
            api_input = api.APIInput(id_type, number, kind, country, date)
            self.assertIsInstance(api_input, api.APIInput)

    @given(utils.valid_api_input_args())
    def test_to_id_produces_correct_output(self, args):

        id_type, number, kind, country, date = args
        api_input = api.APIInput(id_type, number, kind, country, date)

        if re.match(r'(\d+[.,/]\d+)+', number) and id_type != 'classification':
            number = '({})'.format(number)

        parts = map(str, [i for i in (country, number, kind, date)
                          if i is not None])
        if id_type == 'epodoc':
            expected = ''.join(parts)
        elif id_type == 'classification':
            expected = str(number)
        else:
            expected = '.'.join(parts)

        self.assertEqual(expected, api_input.to_id())

    @given(utils.APIInputs, st.text())
    def test_to_id_raises_ValueError_on_bad_type(self, api_input, new_type):
        assume(new_type not in epo_utils.constants.VALID_IDTYPES)
        api_input.id_type = new_type
        self.assertRaises(ValueError, api_input.to_id)


class EPOClientTestCase(unittest.TestCase):

    def mock_auth(self, expires_in=10, succeed=True, token='token'):
        _mock = requests_mock.mock()
        _mock.post(epo_utils.constants.AUTH_URL, status_code=200 if succeed else 401,
                   json={'access_token': token, 'expires_in': expires_in})

        return _mock

    def mock_services(self, status_code=200, return_value='value'):
        matcher = re.compile(epo_utils.constants.URL_PREFIX)
        _mock = requests_mock.mock()
        _mock.post(matcher, status_code=status_code,
                   content=return_value)
        return _mock

    @contextlib.contextmanager
    def monkey_path_api_requests(self, method, mock_object=None):
        """ Monkey-patch the instance of `requests` used by api-module.

        Parameters
        ----------
        method : str
            Method of `requests` library to replace with
            `unittest.mock.MagicMock`
        mock_object : unittest.mock.Mock or requests_mock.mock, optional
            Replacment for `requests` library-method.

        Yields
        ------
        unittest.mock.MagicMock
        """
        attr = getattr(api.requests, method)
        mock_method = mock.MagicMock()
        setattr(api.requests, method, mock_method)
        try:
            yield mock_method
        finally:
            setattr(api.requests, method, attr)


class TestEPOClientCreation(EPOClientTestCase):

    @given(utils.valid_epo_client_args(enable_cache=False))
    def test_creation_doesnt_raise(self, args):
        api.EPOClient.authenticate = mock.MagicMock()
        client = api.EPOClient(*args)
        self.assertIsInstance(client, api.EPOClient)

    @given(utils.valid_epo_client_args())
    def test_create_with_cache_calls_requests_cache(self, args):
        api.EPOClient.authenticate = mock.MagicMock()
        api.requests_cache.install_cache = mock.MagicMock()
        accept_type, key, secret, _, cache_kwargs = args
        cache = True

        api.EPOClient(accept_type, key, secret, cache, cache_kwargs)
        kwargs = cache_kwargs or dict()
        self.assertTrue(api.requests_cache.install_cache.called_with(**kwargs))

    @given(utils.valid_epo_client_args(enable_cache=False),
           st.text(min_size=1, alphabet=string.ascii_letters),
           st.text(min_size=1, alphabet=string.ascii_letters))
    def test_client_auto_auths_with_key_and_secret(self, args, key, secret):
        accept_type, _, _, cache, cache_kwargs = args
        api.EPOClient.authenticate = mock.MagicMock()
        client = api.EPOClient(accept_type, key, secret, cache, cache_kwargs)
        self.assertTrue(api.EPOClient.authenticate.called)


class TestEPOClientAuth(EPOClientTestCase):

    @given(args=utils.valid_epo_client_args(must_have_auth=True))
    def test_returns_token_on_success(self, args):
        token_content = 'success'
        with self.mock_auth(token=token_content):
            client = api.EPOClient(*args)
            token = client.authenticate()
            self.assertIsInstance(token, api.Token)
            self.assertEqual(token.token, token_content)

    @given(args=utils.valid_epo_client_args())
    def test_returns_none_on_missing_creds(self, args):
        _, key, secret, _, _ = args
        assume(key is None or secret is None)
        with self.mock_auth(succeed=True):
            client = api.EPOClient(*args)
            token = client.authenticate()
            self.assertIsNone(token)

    @given(args=utils.valid_epo_client_args(),
           key=st.text(min_size=1, alphabet=string.ascii_letters),
           secret=st.text(min_size=1, alphabet=string.ascii_letters)
           )
    def test_raises_on_failed_auth(self, args, key, secret):
        accept_type, _, _, cache, cache_kwargs = args
        # Omit key and secret to prevent auto-auth.
        client = api.EPOClient(accept_type, None, None, cache, cache_kwargs)

        with self.mock_auth(succeed=False):
            client.key = key
            client.secret = secret
            self.assertRaises(requests.HTTPError, client.authenticate)


class TestEPOClientSearch(EPOClientTestCase):

    def setUp(self):
        self.__cache = api.requests_cache
        api.requests_cache = mock.MagicMock()

    def tearDown(self):
        api.requests_cache = self.__cache

    def make_client(self, args):
        with self.mock_auth(expires_in=1000):
            client = api.EPOClient(*args)

        return client

    @given(utils.valid_epo_client_args(),
           st.one_of(st.integers(), st.text()),
           st.text(),
           st.tuples(st.integers(), st.integers()))
    def test_invalid_service_raises_ValueError(self, args, service,
                                               query, f_range):
        client = self.make_client(args)
        with self.monkey_path_api_requests('post') as mock_post:
            self.assertRaises(ValueError, client.search, query,
                              f_range, service)
            self.assertFalse(mock_post.called)

    @given(utils.valid_epo_client_args(),
           utils.build_variable_tuples(st.one_of(st.integers(),
                                                 st.characters())),
           st.text())
    def test_invalid_fetch_range_raises_ValueError(self, args, f_range, query):
        client = self.make_client(args)
        if not len(f_range) == 2 and all(isinstance(i, int) for i in f_range):
            with self.monkey_path_api_requests('post') as mock_post:
                self.assertRaises(ValueError, client.search, query, f_range)
                self.assertFalse(mock_post.called)

    @given(utils.valid_epo_client_args(),
           st.tuples(st.integers(), st.integers()),
           st.text(),
           st.one_of(st.integers(), st.characters(), st.text()))
    def test_invalid_endpoint_raises_ValueError(self, args, f_range, query,
                                                endpoint):
        assume(endpoint != '')
        client = self.make_client(args)
        with self.monkey_path_api_requests('post') as mock_post:
            self.assertRaises(ValueError, client.search, query,
                              f_range, endpoint=endpoint)
            self.assertFalse(mock_post.called)

    @given(utils.valid_epo_client_args(must_have_auth=True),
           st.text(), st.tuples(st.integers(), st.integers()))
    def test_search_reauthenticates(self, args, query, f_range):
        client = self.make_client(args)
        client.token.expires = datetime.now() - timedelta(seconds=1)

        client.authenticate = mock.MagicMock()
        with self.monkey_path_api_requests('post'):
            client.search(query, f_range)
        self.assertTrue(client.authenticate.called)