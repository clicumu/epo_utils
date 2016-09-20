# -*- coding: utf-8 -*-
""" This module contains classes for high-level access to EPO-OPS. """
import collections
import logging

import epo_utils.ops.constants
import epo_utils.ops.exceptions
import requests
from bs4 import BeautifulSoup

import epo_utils.ops
from epo_utils.exceptions import ResourceNotFound, UnknownDocumentFormat

from epo_utils import documents
from epo_utils import api


class OPSConnection:
    """ A high-level user-facing wrapper for calling EPO-OPS API.

    Parameters
    ----------
    key : str
        Client key.
    secret : str
        Client secret
    **kwargs
        Keyword arguments passed to :class:`epo_utils.ops.api.EPOClient`-
        constructor.

    Attributes
    ----------
    client : epo_utils.ops.api.EPOClient
    """
    def __init__(self, key, secret, **kwargs):
        self.client = api.EPOClient(key=key, secret=secret, **kwargs)

    def get_publication(self, *request_inputs, **kwargs):
        """ Retrieve publication and unfold response text into `dict`.

        Parameters
        ----------
        *request_inputs : epo_utils.ops.api.APIInput, epo_utils.ops.documents.DocumentID
            One or more api-inputs or document-ID:s to fetch.
        **kwargs
            Keyword arguments passed to
            :meth:`epo_utils.ops.api.EPOClient.fetch`.

        Returns
        -------
        fetched_documents : dict[str, ExchangeDocument]
            Documents in response.
        response : requests.Response
            Response-object.
        """
        if all(isinstance(in_, documents.DocumentID) for in_ in request_inputs):
            request_inputs = [api.APIInput.from_document_id(did)
                              for did in request_inputs]
        elif not all(isinstance(in_, api.APIInput) for in_ in request_inputs):
            logging.debug('Bad input: '.format(request_inputs))
            raise ValueError('inputs must be APIInput-instances.')

        if 'endpoint' not in kwargs:
            kwargs['endpoint'] = 'biblio'

        ids_debug_str = ', '.join(i.to_id() for i in request_inputs)
        logging.info('Attempts fetch for: {}'.format(ids_debug_str))
        try:
            response = self.client.fetch(
                epo_utils.ops.Services.Published,
                epo_utils.ops.ReferenceType.Publication,
                list(request_inputs),
                **kwargs
            )
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logging.info('Nothing for: {}'.format(ids_debug_str))
                # Raise separate error if nothing was found.
                raise ResourceNotFound(str(e))
            else:
                raise

        soup = BeautifulSoup(response.text, 'lxml')
        inner = soup.find('ops:world-patent-data')

        # No documents were fetched.
        if inner is None:
            logging.info('xml lacked ops:world-patent-data tag.')
            return None, response

        if inner.find('exchange-document') is not None:
            tag_name = 'exchange-document'
            doc_class = documents.ExchangeDocument

        elif inner.find('ftxt:fulltext-document') is not None:
            tag_name = 'ftxt:fulltext-document'
            doc_class = documents.FullTextDocument

        elif inner.find('ops:fulltext-inquiry') is not None:
            tag_name = 'ops:fulltext-inquiry'
            doc_class = documents.FullTextInquiry

        else:
            raise UnknownDocumentFormat('no document with known format found.')

        if inner.find_next(tag_name).get('status') == 'not found':
            logging.info('Document not found.')
            raise ResourceNotFound(ids_debug_str)

        logging.info('Fetch succeeded.')
        docs_xml = inner.find_all(tag_name)

        fetched_documents = dict()
        for doc in docs_xml:
            doc_object = doc_class(doc)
            fetched_documents[doc_object.id] = doc_object

        return fetched_documents, response

    def find_equivalents(self, *request_inputs):
        """ Search EPO for equivalent documents.

        Simple call to OPS equivalents endpoint is done. Currently no
        support for combined endpoints.

        Parameters
        ----------
        *request_inputs : epo_utils.ops.api.APIInput, epo_utils.ops.documents.DocumentID
            One or more api-inputs or document-ID:s to fetch

        Returns
        -------
        dict[epo_utils.ops.api.APIInput, epo_utils.ops.documents.InquiryResult]
        requests.Response
        """
        if all(isinstance(in_, documents.DocumentID) for in_ in request_inputs):
            request_inputs = [api.APIInput.from_document_id(did)
                              for did in request_inputs]
        elif not all(isinstance(in_, api.APIInput) for in_ in request_inputs):
            raise ValueError('inputs must be APIInput-instances.')

        equivalents = dict()

        # OPS-endpoint equivalents does not support bulk-retrieval, it only
        # returns results from the first ID requested. Therefore, one call
        # must be made for each input.
        for request_input in request_inputs:
            response = self.client.fetch(epo_utils.ops.Services.Published,
                                         epo_utils.ops.ReferenceType.Publication,
                                         request_input,
                                         endpoint='equivalents')
            soup = BeautifulSoup(response.text, 'lxml')
            inquiry = soup.find('ops:equivalents-inquiry')

            if inquiry is not None:
                req_equivalents = [
                    documents.InquiryResult(tag)
                    for tag in inquiry.find_all('ops:inquiry-result')
                    ]
            else:
                req_equivalents = []

            equivalents[request_input] = req_equivalents

        return equivalents, response

    def search_published(self, field, query, fetch_range=(1, 25),
                         num_publications=None, endpoint=''):
        """ Search EPO `field` after `query`.

        If `field` is `SearchFields.CQL` `query` will be interpreted
        as a free form search string and executed as is.

        Endpoints supported by EPO: full-cycle, biblio, abstract

        Parameters
        ----------
        field : epo_utils.ops.api.SearchFields
            EPO-OPS search field.
        query : str
            Query-parameter of full query if  `field` is `SearchFields.CQL`.
        fetch_range : tuple[int, int]
            Get entries `fetch_range[0]` to `fetch_range[1]` inclusive.
        num_publications : int, optional
            If provided, overrides `fetch_range`. Fetches `num_publications`
            latest publications.
        endpoint : str
            Published data endpoint.

        Returns
        -------
        list[OPSPublicationReference]
            Parsed references in search results.
        requests.Response
            Response object.
        """
        end_results = list()
        if num_publications is not None:
            fetch_range = [1, num_publications]
        else:
            num_publications = fetch_range[1] - fetch_range[0] + 1
        logging.debug(
            'Preparing to fetch {} publications'.format(num_publications))

        while len(end_results) < num_publications:
            start = fetch_range[0] + (0 if not end_results else len(end_results))
            end = min(start + 99, fetch_range[1])
            logging.debug('Fetching start: {}, end: {}'.format(start, end))

            # Perform search.
            if field == epo_utils.ops.SearchFields.CQL:
                response = self.client.search(query, (start, end),
                                              endpoint=endpoint)
            else:
                query_string = '{0}={1}'.format(field.value, query)
                response = self.client.search(query_string, (start, end),
                                              endpoint=endpoint)

            # Parse results.
            soup = BeautifulSoup(response.text, 'lxml')

            if not endpoint:
                results = [documents.OPSPublicationReference(tag)
                           for tag in soup.find_all('ops:publication-reference')]
            else:
                results = [documents.ExchangeDocument(tag)
                           for tag in soup.find_all('exchange-document')]

            logging.debug('{} parsed publications.'.format(len(results)))
            end_results.extend(results)

            if not results or len(results) < (end - start + 1):
                break

        return end_results, response

    def find_fulltext(self, request_input, endpoint):
        """

        Parameters
        ----------
        request_input : APIInput/DocumentID, list[APIInput]/list[DocumentID]

        endpoint: str, tuple[str]

        Returns
        -------

        """
        if not isinstance(request_input, collections.Sequence):
            request_input = [request_input]

        if all(isinstance(in_, documents.DocumentID) for in_ in request_input):
            request_input = [api.APIInput.from_document_id(did)
                             for did in request_input]
        elif not all(isinstance(in_, api.APIInput) for in_ in request_input):
            raise ValueError('inputs must be APIInput-instances.')

        Result = collections.namedtuple(
            '{}Result'.format(endpoint.capitalize()),
            ['substitution', 'text_instance']
        )

        # Since OPS-fulltext only supports a few country codes, try to find
        # patent-equivalents from supported countries...
        lacking_fulltext = [in_ for in_ in request_input
                            if in_.country not in epo_utils.constants.HAS_FULLTEXT]

        # ... Also find patents with correct country codes which lacks
        # full-text anyway.
        lacking_fulltext += [in_ for in_ in request_input
                             if in_ not in lacking_fulltext
                             and not self._has_fulltext(in_, endpoint)]

        # Find equivalent patents which do have the searched full-text.
        lacking_fulltext_eqv, _ = self.find_equivalents(*lacking_fulltext)
        substitutions = dict()
        for input_, equivalents in lacking_fulltext_eqv.items():
            in_correct_country = [eq for eq in equivalents
                                  if eq.country in epo_utils.constants.HAS_FULLTEXT]
            has_fulltext = (eq for eq in in_correct_country
                            if self._has_fulltext(eq, 'claims'))
            sub_w_fulltext = next(has_fulltext, None)
            substitutions[input_] = sub_w_fulltext

        results = dict()

        # And finally collect the full-text instances.
        non_replaced = list(set(request_input) - set(lacking_fulltext))
        for input_ in non_replaced:
            ft_dict, _ = self.get_publication(input_, endpoint=endpoint)
            ft_instance = next(val for val in ft_dict.values())
            results[input_] = Result(None, ft_instance)

        for input_, substitution in substitutions.items():
            if substitution is None:
                results[input_] = Result(None, None)
            else:
                ft_dict, _ = self.get_publication(substitution, endpoint=endpoint)
                ft_instance = next(val for val in ft_dict.values())
                results[input_] = Result(
                    api.APIInput.from_document_id(substitution),
                    ft_instance)

        return results

    def _has_fulltext(self, api_input, endpoint):
        """

        Parameters
        ----------
        api_input

        Returns
        -------

        """
        try:
            ft_inquiry_d, _ = self.get_publication(api_input, endpoint='fulltext')
        except epo_utils.exceptions.FetchFailed:
            return False
        ft_inquiry = next(val for val in ft_inquiry_d.values())

        return any(t.desc == endpoint for t in ft_inquiry.full_text_instances)
