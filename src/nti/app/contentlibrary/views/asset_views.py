#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from requests.structures import CaseInsensitiveDict

from zope import component

from zope.component.hooks import site as current_site

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary.subscribers import can_be_removed
from nti.app.contentlibrary.subscribers import removed_registered
from nti.app.contentlibrary.subscribers import clear_content_package_assets

from nti.app.contentlibrary.utils.common import remove_package_inaccessible_assets

from nti.app.contentlibrary.views.sync_views import _AbstractSyncAllLibrariesView

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.common.string import is_true

from nti.contentlibrary.interfaces import IContentPackage

from nti.contentlibrary.utils import get_content_package_site

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import IContentBackedPresentationAsset

from nti.contenttypes.presentation import iface_of_asset as iface_of_thing

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.recorder.record import remove_transaction_history

from nti.site.hostpolicy import get_host_site

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


def _read_input(request):
    result = CaseInsensitiveDict()
    if request:
        if request.body:
            values = read_body_as_external_object(request)
        else:
            values = request.params
        result.update(values)
    return result


@view_config(name='assets')
@view_config(name='GetPresentationAssets')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               context=IContentPackage,
               permission=nauth.ACT_SYNC_LIBRARY,
               name='GetPresentationAssets')
class GetPackagePresentationAssetsView(AbstractAuthenticatedView):

    def _unit_assets(self, package):
        result = {}
        def recur(unit):
            for child in unit.children or ():
                recur(child)
            container = IPresentationAssetContainer(unit)
            result.update(container)
        recur(package)
        return result

    def __call__(self):
        package = self.context
        result = LocatedExternalDict()
        items = result[ITEMS] = self._unit_assets(package)
        result[ITEM_COUNT] = result[TOTAL] = len(items)
        return result


@view_config(context=IContentPackage)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_SYNC_LIBRARY,
               name='ResetPresentationAssets')
class ResetPackagePresentationAssetsView(_AbstractSyncAllLibrariesView):

    def _unit_assets(self, package):
        result = []
        def recur(unit):
            for child in unit.children or ():
                recur(child)
            container = IPresentationAssetContainer(unit)
            for key, value in container.items():
                if IContentBackedPresentationAsset.providedBy(value):
                    result.append((key, value, container))
        recur(package)
        return result

    def _do_call(self):
        package = self.context
        values = self.readInput()
        force = is_true(values.get('force'))

        seen = set()
        result = LocatedExternalDict()
        items = result[ITEMS] = []
        site_name = get_content_package_site(package)
        with current_site(get_host_site(site_name)):
            registry = component.getSiteManager()
            # remove using catalog
            items.extend(
                clear_content_package_assets(package, force=force)
            )
            # remove anything left in containters
            for ntiid, item, container in self._unit_assets(package):
                if can_be_removed(item, force=force):
                    container.pop(ntiid, None)
                if ntiid not in seen:
                    seen.add(ntiid)
                    provided = iface_of_thing(item)
                    if removed_registered(provided,
                                          ntiid,
                                          force=force,
                                          registry=registry) is not None:
                        items.append(item)
                        remove_transaction_history(item)
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result


@view_config(context=IDataserverFolder)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_NTI_ADMIN,
               name='RemovePackageInaccessibleAssets')
class RemovePackageInaccessibleAssetsView(AbstractAuthenticatedView,
                                          ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        return _read_input(self.request)

    def __call__(self):
        endInteraction()
        try:
            result = remove_package_inaccessible_assets()
        finally:
            restoreInteraction()
        return result
