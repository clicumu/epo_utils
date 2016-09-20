# -*- coding: utf-8 -*-
""" Package level exceptions."""


class FetchFailed(Exception):
    """ Raised by API-client at 404:s. """


class ResourceNotFound(Exception):
    """ Raised at successful calls when resource is missing. """


class UnknownDocumentFormat(Exception):
    """ Raised when an unknown document is encountered. """


class QuotaPerHourExceeded(Exception):
    """ Raised when "X-Rejection-Reason" is "IndividualQuotaPerHour". """


class QuotaPerWeekExceeded(Exception):
    """ Raised when "X-Rejection-Reason" is "RegisteredQuotaPerWeek". """
