# -*- coding: utf-8 -*-
""" epo_utils is a high-level library for accessing the European Patent Office's
("EPO") Open Patent Services ("OPS") v.3.1. epo_utils provides classes
 for connecting and fetching from the OPS-REST-API as well as wrapper classes
 for fetched documents.
"""
from .api import APIInput, EPOClient
from .connection import OPSConnection
from .documents import ExchangeDocument, FullTextDocument, FullTextInquiry, \
    DocumentID, InquiryResult, OPSPublicationReference, PublicationReference, \
    ApplicationReference, PriorityClaim, Citation, PatentCitation, \
    NonPatentCitation, Party
from . import constants
from .exceptions import FetchFailed, ResourceNotFound, UnknownDocumentFormat
from . import ops
from . import tools

__all__ = [OPSConnection, ops, ExchangeDocument, DocumentID, Party,
           FullTextDocument, FullTextInquiry, InquiryResult,
           OPSPublicationReference, PublicationReference, ApplicationReference,
           PriorityClaim, Citation, PatentCitation, NonPatentCitation, constants,
           FetchFailed, ResourceNotFound, UnknownDocumentFormat, EPOClient,
           APIInput, tools]