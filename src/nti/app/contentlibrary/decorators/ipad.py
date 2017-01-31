#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator


class _IPad120BundleContentPackagesAdjuster(AbstractAuthenticatedRequestAwareDecorator):
    """
    there is a class naming issue parsing this data right now which is
    parsing the objects coming from the server with Class:
    NTIContentPackage to an object that isn't a descendant of
    NTIUserData. I have no idea why we didn't see this when we were
    testing. The issue has been in the version all along but I think
    maybe it only gets triggered when we head down certain code paths.
    It seems like the main code path was turning these into NTIIDs
    that were then cross referenced into Library/Main but there is a
    merge/update path that isn't doing that and when we resolve a
    class for this data we find a non NTIUserData and that causes
    things to crash. Since this and all prior versions require
    Library/Main to have all accessible ContentPackages anyway I'm
    hoping you can just conditionally externalize those objects as
    NTIIDs for this specific version of the ipad app.
    """

    _BAD_UAS = ("NTIFoundation DataLoader NextThought/1.2.0",)

    def _predicate(self, context, result):
        ua = self.request.environ.get('HTTP_USER_AGENT', '')
        if not ua:
            return False

        for bua in self._BAD_UAS:
            if ua.startswith(bua):
                return True

    def _do_decorate_external(self, context, result):
        # Depending on what we're registered on, the result
        # may already contain externalized values or still ContentPackage
        # objects.
        new_packages = []
        for x in result['ContentPackages']:
            ntiid = None
            try:
                ntiid = x.get('NTIID')
            except AttributeError:
                pass
            if not ntiid:
                ntiid = getattr(x, 'ntiid', None) or getattr(x, 'NTIID', None)
            if ntiid:
                new_packages.append(ntiid)
        result['ContentPackages'] = new_packages
