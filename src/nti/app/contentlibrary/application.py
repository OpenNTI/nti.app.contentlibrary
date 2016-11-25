#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.processlifetime import IApplicationTransactionOpenedEvent

@component.adapter(IApplicationTransactionOpenedEvent)
def _sync_global_library(_):
	library = component.getGlobalSiteManager().queryUtility(IContentPackageLibrary)
	if library is not None:
		# Ensure the library is enumerated at this time during startup
		# when we have loaded all the basic ZCML slugs but while
		# we are in control of the site.
		# NOTE: We are doing this in a transaction for the dataserver
		# to allow loading the packages to make persistent changes.
		library.syncContentPackages()
