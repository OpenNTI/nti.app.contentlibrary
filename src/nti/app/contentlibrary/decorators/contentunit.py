#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.interfaces import IRequest

from zope import component
from zope import interface

from nti.app.contentlibrary import VIEW_CONTENTS
from nti.app.contentlibrary import LIBRARY_ADAPTER
from nti.app.contentlibrary import VIEW_PUBLISH_CONTENTS

from nti.app.contentlibrary.decorators import get_ds2

from nti.app.contentlibrary.interfaces import IContentUnitContents

from nti.app.publishing import VIEW_PUBLISH
from nti.app.publishing import VIEW_UNPUBLISH

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.interfaces import IEditableContentPackage
from nti.contentlibrary.interfaces import IRenderableContentPackage

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

from nti.ntiids.ntiids import find_object_with_ntiid

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IExternalMappingDecorator)
@component.adapter(IEditableContentPackage, IRequest)
class EditablePackageDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorates with `contents` rel if we are an editor.
    """

    def _predicate(self, context, unused_result):
        result = self._is_authenticated \
             and has_permission(ACT_CONTENT_EDIT, context, self.request)
        return result

    def _need_publish_contents_link(self, context):
        """
        A rel for fetching the published contents of a
        IRenderableContentPackage. This is only necessary
        if we have our `contents` modified after our
        publishLastModified time.
        """
        return context.contents_last_modified \
           and context.publishLastModified \
           and context.contents_last_modified > context.publishLastModified

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        rels = (VIEW_CONTENTS,)
        if self._need_publish_contents_link(context):
            rels = (VIEW_CONTENTS, VIEW_PUBLISH_CONTENTS,)
        for rel in rels:
            link = Link(context,
                        rel=rel,
                        elements=('@@%s' % rel,))
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@interface.implementer(IExternalMappingDecorator)
@component.adapter(IRenderableContentPackage, IRequest)
class RenderablePackagePublishLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, unused_result):
        result = self._is_authenticated \
             and has_permission(ACT_CONTENT_EDIT, context, self.request)
        return result

    def _do_decorate_external(self, context, result):
        # We always want to return the PUBLISH rel since the client
        # may not update state for every edit/PUT.
        rels = (VIEW_UNPUBLISH, VIEW_PUBLISH)
        if not context.is_published():
            rels = (VIEW_PUBLISH,)
        path = '/%s/%s/%s' % (get_ds2(self.request),
                              LIBRARY_ADAPTER,
                              context.ntiid)
        _links = result.setdefault(LINKS, [])
        for rel in rels:
            link = Link(path, rel=rel, elements=('@@%s' % rel,),
                        ignore_properties_of_target=True)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(IContentUnitContents)
@interface.implementer(IExternalMappingDecorator)
class ContentUnitContentsDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, unused_result):
        unit = find_object_with_ntiid(context.ntiid)
        result = self._is_authenticated \
             and has_permission(ACT_CONTENT_EDIT, unit, self.request)
        return result

    def _do_decorate_external(self, context, result):
        unit = find_object_with_ntiid(context.ntiid)
        result['version'] = unit.version
        result['length'] = len(context.data or '')
