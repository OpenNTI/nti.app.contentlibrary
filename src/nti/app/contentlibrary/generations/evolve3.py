#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 3

from zope import component

from zope.component.hooks import site

from nti.contentlibrary.interfaces import IContentPackageLibrary


def index_site(current_site, catalog, intids,  seen):
    with site(current_site):
        library = component.queryUtility(IContentPackageLibrary)
        if library is None:
            return

        def _recur(unit):
            doc_id = intids.queryId(unit)
            if doc_id is not None:
                catalog.index_doc(doc_id, unit)
            for child in unit.children or ():
                _recur(child)

        for package in library.contentPackages or ():
            if not package.ntiid in seen:
                _recur(package)
                seen.add(package.ntiid)


def evolve(context):
    pass
