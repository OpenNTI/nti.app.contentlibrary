#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.contentlibrary.interfaces import IContentValidator

@interface.implementer(IContentValidator)
class ReStructuredTextValidator(object):
    
    def validate(self, content=b''):
        pass