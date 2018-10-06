#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.appserver.policies.site_policies import get_possible_site_names

from nti.contentlibrary.interfaces import IRequestSiteNames

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IRequestSiteNames)
class _RequestSiteNames(object):

    def sites(self, unused_key):
        return get_possible_site_names()
    names = sites
