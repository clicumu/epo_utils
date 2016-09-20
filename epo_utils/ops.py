# -*- coding: utf-8 -*-
""" OPS-API call options as enums. """
import enum


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


class Endpoint(enum.Enum):
    """ Published-data service endpoints. """
    FullText = 'fulltext'
    Claims = 'claims'
    Description = 'description'
    Images = 'images'
    Equivalents = 'equivalents'
    Biblio = 'biblio'
    Abstract = 'abstract'
