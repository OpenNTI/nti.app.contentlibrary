#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.appserver.policies.site_policies import get_possible_site_names

from nti.contentlibrary.interfaces import IRequestSiteNames

@interface.implementer(IRequestSiteNames)
class _RequestSiteNames(object):

	def sites(self, key):
		return get_possible_site_names()