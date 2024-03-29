#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zc.displayname.interfaces import IDisplayNameGenerator

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from nti.app.contentlibrary import LIBRARY_PATH_GET_VIEW

from nti.app.contentlibrary.decorators import AbstractLibraryPathLinkDecorator

from nti.app.contentlibrary.interfaces import IContentForum

from nti.contentlibrary.interfaces import IContentPackageBundle

from nti.dataserver.contenttypes.forums.interfaces import IPost
from nti.dataserver.contenttypes.forums.interfaces import ITopic
from nti.dataserver.contenttypes.forums.interfaces import IForum

from nti.dataserver.interfaces import ICommunity

from nti.dataserver.users.entity import Entity

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import Singleton

from nti.links.links import Link

from nti.ntiids.oids import to_external_ntiid_oid

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@component.adapter(IPost)
@interface.implementer(IExternalMappingDecorator)
class _PostLibraryPathLinkDecorator(Singleton):
    """
    Create a `LibraryPath` link to our post.
    """

    def decorateExternalMapping(self, context, result):
        # Use the OID NTIID rather than the 'physical' path because
        # the 'physical' path may not quite be traversable at this
        # point. Not sure why that would be, but the ILocation parents
        # had a root above dataserver.
        target_ntiid = to_external_ntiid_oid(context)
        if target_ntiid is None:
            logger.warn("Failed to get ntiid; not adding LibraryPath link for %s",
                        context)
            return

        _links = result.setdefault(LINKS, [])
        link = Link(target_ntiid,
                    rel=LIBRARY_PATH_GET_VIEW,
                    elements=(LIBRARY_PATH_GET_VIEW,))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)


@component.adapter(ITopic)
@interface.implementer(IExternalMappingDecorator)
class _TopicLibraryPathLinkDecorator(AbstractLibraryPathLinkDecorator):
    pass


@component.adapter(IForum)
@interface.implementer(IExternalMappingDecorator)
class _ForumLibraryPathLinkDecorator(AbstractLibraryPathLinkDecorator):
    pass


def _get_community():
    """
    Mimicing what happens during publish. For books, we want to display
    any viable site communities. This will not always be correct, some
    books are not available to everyone.
    """
    for name in get_component_hierarchy_names() or ():
        comm = Entity.get_entity(name or '')
        if ICommunity.providedBy(comm):
            return comm
    return None


@component.adapter(IContentForum)
@interface.implementer(IExternalObjectDecorator)
class _ContentPackageBundleForumDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        book = find_interface(original, IContentPackageBundle, strict=False)
        if book is not None:
            community = _get_community()
            if community is not None:
                external['DefaultSharedToNTIIDs'] = [community.NTIID]
                external['DefaultSharedToDisplayNames'] = [IDisplayNameGenerator(community)()]


@component.adapter(ITopic)
@interface.implementer(IExternalObjectDecorator)
class _ContentPackageBundleTopicDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        book = find_interface(original, IContentPackageBundle, strict=False)
        if book is not None:
            community = _get_community()
            if community is not None:
                external['ContainerDefaultSharedToNTIIDs'] = [community.NTIID]
                external['ContainerDefaultSharedToDisplayNames'] = [IDisplayNameGenerator(community)()]
