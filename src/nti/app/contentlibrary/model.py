#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.app.contentlibrary.interfaces import IContentUnitContents

from nti.property.property import alias

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured


@interface.implementer(IContentUnitContents)
class ContentUnitContents(SchemaConfigured):
    createDirectFieldProperties(IContentUnitContents)

    mime_type = mimeType = 'application/vnd.nextthought.contentunit.contents'

    contents = alias('data')
