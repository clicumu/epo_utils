# -*- coding: utf-8 -*-
""" This module contains classes for high-level access to EPO-OPS. """
from bs4 import BeautifulSoup
import enum
import requests
import logging

from epo_utils.ops.documents import ExchangeDocument, OPSPublicationReference
from epo_utils.ops import api


class ResourceNotFound(Exception):
    pass


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
    CooperateivePatentClassification = 'cpc'
    InventorAndApplicant = 'ia'
    TitleAbstract = 'ta'
    TitleAbstractInventorApplicant = 'txt'
    ApplicationPublicationPriority = 'num'
    IPC = 'ipc'
    ICPCPC = 'cl'
    CQL = 'cql'


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

    def get_publication(self, number, country_code=None, id_type=None,
                        kind_code=None, date=None, **kwargs):
        """ Retrieve publication and unfold response text into `dict`.

        Parameters
        ----------
        number : str, int
            Publication number.
        country_code : str, optional
            Publication country code.
        kind_code : str, optional
            Pubication kind.
        date : str, optional
            YYYYMMDD-date.
        **kwargs
            Keyword arguments passed to
            :meth:`epo_ops.RegisteredClient.published_data`.
        Returns
        -------
        documents : dict[str, ExchangeDocument]
            Documents in response.
        response : requests.Response
            Response-object.
        """
        request_input = api.APIInput(
            id_type, number, kind_code, country_code, date
        )

        try:
            response = self.client.fetch_published_data(
                api.ReferenceType.Publication, request_input
            )
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logging.info('Nothing for: {}'.format(request_input.to_id()))
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
        elif inner.find_next('exchange-document').get('status') == 'not found':
            logging.info('Exchange document. not found.')
            raise ResourceNotFound(request_input.to_id())

        docs_xml = inner.find_all('exchange-document')

        documents = dict()
        for doc in docs_xml:
            # '\nEP\n1000000\nA1\n20000517\n' => 'EP.1000000.A1.20000517'
            id_ = '.'.join(doc.find('document-id').text.strip().split())
            documents[id_] = ExchangeDocument(doc)

        return documents, response

    def search_published(self, field, query, range_begin=1, range_end=25):
        """ Search EPO `field` after `query`.

        If `field` is `SearchFields.CQL` `query` will be interpreted
        as a free form search string and executed as is.

        Parameters
        ----------
        field : SearchFields
            EPO-OPS search field.
        query : str
            Query-parameter of full query if  `field` is `SearchFields.CQL`.
        range_begin, range_end : int
            Specification of number of search results to receive.
            Results `range_begin` to `range_end` are retrieved.

        Returns
        -------
        list[OPSPublicationReference]
            Parsed references in search results.
        requests.Response
            Response object.
        """
        def search(query):
            return self.client.search(query, range_begin, range_end)

        # Perform search.
        if field == SearchFields.CQL:
            response = search(query)
        else:
            query_string = '{0}={1}'.format(field.value, query)
            response = search(query_string)

        # Parse results.
        soup = BeautifulSoup(response.text, 'lxml')
        results = [OPSPublicationReference(tag)
                   for tag in soup.find_all('ops:publication-reference')]

        return results, response
