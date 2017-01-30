#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import sys

from docutils import frontend

from docutils import nodes

from docutils.parsers.rst import Parser

from docutils.utils import new_reporter

from zope import interface

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from nti.app.contentlibrary import MessageFactory as _

from nti.app.externalization.error import raise_json_error

from nti.contentlibrary.interfaces import IContentValidator


@interface.implementer(IContentValidator)
class ReStructuredTextValidator(object):

    settings = frontend.OptionParser(
                    components=(Parser,)).get_default_values()

    def _do_validate(self, content):
        try:
            parser = Parser()  # XXX: NTI directives should be included
            reporter = new_reporter("contents", self.settings)
            document = nodes.document(self.settings, reporter, source='contents')
            parser.parse(content, document)
        except Exception:
            exc_info = sys.exc_info()
            request = get_current_request()
            raise_json_error(request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 u'message': _("Cannot parse reStructuredText."),
                                 u'code': 'CannotParseReStructuredText',
                             },
                             exc_info[2])

    def validate(self, content=b''):
        if content:
            self._do_validate(content)
