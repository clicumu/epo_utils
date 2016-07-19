import unittest
from unittest import mock
import string
import re
import requests_mock
import hypothesis.strategies as st
from hypothesis.extra import datetime as hyp_datetime
from hypothesis import given, assume
from epo_utils.ops import api
from epo_utils.ops.tests import utils


_date_formats = ['%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d',
                 '%y-%m-%d', '%Y%m%d', '%d%m%Y', '%y%m%d']


class APIInputTestCase(unittest.TestCase):

    @given(id_type=st.one_of(st.text(), st.sampled_from(api.VALID_IDTYPES)),
           number=utils.doc_numbers(),
           kind=st.one_of(st.characters(), st.none()),
           country=st.one_of(st.text(max_size=2), st.none()),
           raw_date=st.one_of(hyp_datetime.datetimes(min_year=1900), st.none()),
           date_format=st.sampled_from(_date_formats))
    def test_api_input_raises_ValueError_on_bad_input(self, id_type, number,
                                                      kind, country, raw_date,
                                                      date_format):
        invalid = date_format != '%Y%m%d' and raw_date is not None
        invalid |= (id_type not in api.VALID_IDTYPES)
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
        assume(new_type not in api.VALID_IDTYPES)
        api_input.id_type = new_type
        self.assertRaises(ValueError, api_input.to_id)
