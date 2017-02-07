#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division2
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from pyramid.interfaces import IRequest

from nti.app.contentlibrary.interfaces import IContentUnitInfo

from nti.app.publishing import VIEW_PUBLISH
from nti.app.publishing import VIEW_UNPUBLISH

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IRenderableContentPackage

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import SingletonDecorator

from nti.links.links import Link

from nti.ntiids.ntiids import is_valid_ntiid_string

LINKS = StandardExternalFields.LINKS


def get_content_package_paths(ntiid):
    library = component.queryUtility(IContentPackageLibrary)
    paths = library.pathToNTIID(ntiid) if library else ()
    return paths


def get_content_package_ntiid(ntiid):
    paths = get_content_package_paths(ntiid)
    result = paths[0].ntiid if paths else None
    return result


@interface.implementer(IExternalMappingDecorator)
@component.adapter(IContentUnitInfo, IRequest)
class _ContentUnitInfoDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorates context with ContentPackage NTIID
    """

    def _predicate(self, context, result):
        result = self._is_authenticated and context.contentUnit is not None
        if result:
            try:
                ntiid = context.contentUnit.ntiid
                result = bool(is_valid_ntiid_string(ntiid))
            except AttributeError:
                result = False
        return result

    def _do_decorate_external(self, context, result):
        ntiid = get_content_package_ntiid(context.contentUnit.ntiid)
        if ntiid is not None:
            result['ContentPackageNTIID'] = ntiid


@component.adapter(IContentUnitInfo, IRequest)
@interface.implementer(IExternalMappingDecorator)
class _ContentUnitInfoTitleDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorates context with ContentPackage title.
    """

    def _predicate(self, context, result):
        result = self._is_authenticated and context.contentUnit is not None
        if result:
            try:
                context.contentUnit.title
            except AttributeError:
                result = False
        return result

    def _do_decorate_external(self, context, result):
        result['Title'] = context.contentUnit.title


@interface.implementer(IExternalMappingDecorator)
@component.adapter(IContentPackageBundle)
class _ContentBundlePagesLinkDecorator(object):
    """
    Places a link to the pages view of a content bundle.
    """

    __metaclass__ = SingletonDecorator

    def decorateExternalMapping(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context, rel='Pages', elements=('Pages',))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)


@interface.implementer(IExternalMappingDecorator)
@component.adapter(IRenderableContentPackage, IRequest)
class RenderablePackagePublishLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, result):
        result =    self._is_authenticated \
                and has_permission(ACT_CONTENT_EDIT, context, self.request)
        return result

    def _do_decorate_external(self, context, result):
        if not context.is_published():
            rels = (VIEW_PUBLISH,)
        elif (context.lastModified or 0) > (context.publishLastModified or 0):
            # Published with recent modifications, give user the option to publish
            # and render again.
            rels = (VIEW_UNPUBLISH, VIEW_PUBLISH)
        else:
            rels = (VIEW_UNPUBLISH,)
        ds2 = self.request.path_info_peek()
        path = '/%s/Library/%s' % (ds2, context.ntiid)
        _links = result.setdefault(LINKS, [])
        for rel in rels:
            link = Link(path, rel=rel, elements=(rel,),
                        ignore_properties_of_target=True)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)
