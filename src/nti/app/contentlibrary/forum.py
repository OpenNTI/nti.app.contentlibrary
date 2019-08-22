#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Discussion board/forum objects.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from itertools import chain

from zope import schema
from zope import component
from zope import interface

from zope.cachedescriptors.property import cachedIn

from nti.app.contentlibrary.interfaces import IContentBoard
from nti.app.contentlibrary.interfaces import IContentForum
from nti.app.contentlibrary.interfaces import IContentCommentPost
from nti.app.contentlibrary.interfaces import IContentHeadlinePost
from nti.app.contentlibrary.interfaces import IContentHeadlineTopic

from nti.contentlibrary.interfaces import IContentPackageBundle

from nti.dataserver.authorization import ACT_READ

from nti.dataserver.authorization_acl import ace_allowing

from nti.dataserver.contenttypes.forums import MessageFactory as _

from nti.dataserver.contenttypes.forums.acl import CommunityForumACLProvider
from nti.dataserver.contenttypes.forums.acl import CommunityBoardACLProvider

from nti.dataserver.contenttypes.forums.board import GeneralBoard
from nti.dataserver.contenttypes.forums.board import AnnotatableBoardAdapter

from nti.dataserver.contenttypes.forums.forum import DEFAULT_FORUM_NAME

from nti.dataserver.contenttypes.forums.forum import GeneralForum

from nti.dataserver.contenttypes.forums.interfaces import IDefaultForum

from nti.dataserver.contenttypes.forums.post import GeneralHeadlinePost
from nti.dataserver.contenttypes.forums.post import GeneralForumComment

from nti.dataserver.contenttypes.forums.topic import GeneralHeadlineTopic

from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import system_user

from nti.dataserver.users.entity import Entity

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import Singleton

from nti.links.links import Link

from nti.ntiids.ntiids import TYPE_OID

from nti.ntiids.oids import to_external_ntiid_oid

from nti.publishing.interfaces import IDefaultPublished

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IContentBoard)
class ContentBoard(GeneralBoard):

    mime_type = mimeType = 'application/vnd.nextthought.forums.contentboard'

    # Override things related to ntiids.
    # These don't have global names, so they must be referenced
    # by OID. We are also IUseOIDForNTIID so our children
    # inherit this.
    NTIID_TYPE = _ntiid_type = TYPE_OID
    NTIID = cachedIn('_v_ntiid')(to_external_ntiid_oid)

    # Who owns this? Who created it?
    # Right now, we're saying "system" did it...
    # see also the sharing targets
    creator = system_user

    def createDefaultForum(self):
        if ContentForum.__default_name__ in self:
            return self[ContentForum.__default_name__]

        forum = ContentForum()
        forum.creator = self.creator
        self[forum.__default_name__] = forum
        interface.alsoProvides(forum, IDefaultForum)
        forum.title = _(DEFAULT_FORUM_NAME)

        errors = schema.getValidationErrors(IContentForum, forum)
        if errors:
            __traceback_info__ = errors
            raise errors[0][1]
        return forum


@interface.implementer(IContentBoard)
def ContentBoardAdapter(context):
    board = AnnotatableBoardAdapter(context, ContentBoard, IContentBoard)
    if board.creator is None or IContentPackageBundle.providedBy(context):
        board.creator = system_user
    return board


@interface.implementer(IContentForum)
class ContentForum(GeneralForum):

    __external_can_create__ = True

    mime_type = mimeType = 'application/vnd.nextthought.forums.contentforum'

    @property
    def _ntiid_mask_creator(self):
        return (self.creator != system_user)

    def xxx_isReadableByAnyIdOfUser(self, *unused_args, **unused_kwargs):
        # if we get here, we're authenticated
        # See above about the sharing stuff
        return True


@interface.implementer(IContentHeadlineTopic)
class ContentHeadlineTopic(GeneralHeadlineTopic):

    __external_can_create__ = True

    mimeType = 'application/vnd.nextthought.forums.contentheadlinetopic'

    DEFAULT_SHARING_TARGETS = ('Everyone',)
    publicationSharingTargets = DEFAULT_SHARING_TARGETS

    @property
    def sharingTargetsWhenPublished(self):
        # Instead of returning the default set from super, which would return
        # the dynamic memberships of the *creator* of this object, we
        # make it visible to the site community or the world
        # XXX NOTE: This will change as I continue to flesh out
        # the permissioning of the content bundles themselves
        # auth = IPrincipal( AUTHENTICATED_GROUP_NAME )
        # interface.alsoProvides(auth, IEntity)
        result = []
        for name in self.publicationSharingTargets:
            entity = Entity.get_entity(name)
            if entity is not None:
                result.append(entity)
        return tuple(result)

    @property
    def flattenedSharingTargetNames(self):
        result = super(ContentHeadlineTopic, self).flattenedSharingTargetNames
        if 'Everyone' in result:
            result.add('system.Everyone')
        return result

    def isSharedWith(self, wants):
        res = super(ContentHeadlineTopic, self).isSharedWith(wants)
        if not res:
            # again, implicitly with everyone
            res = IDefaultPublished.providedBy(self)
        return res

    def publish(self):
        folder = find_interface(self, IHostPolicyFolder, strict=False)
        if folder is not None:
            # find a community in site hierarchy
            names = chain((folder.__name__,),
                          get_component_hierarchy_names())
            for name in names:
                comm = Entity.get_entity(name or '')
                if ICommunity.providedBy(comm):  # we have community
                    self.publicationSharingTargets = (name,)
                    break
            else:
                self.publicationSharingTargets = ()  # no community
        else:  # global
            self.publicationSharingTargets = self.DEFAULT_SHARING_TARGETS
        return super(ContentHeadlineTopic, self).publish()

    def unpublish(self):
        # restore
        self.publicationSharingTargets = self.DEFAULT_SHARING_TARGETS
        return super(ContentHeadlineTopic, self).unpublish()


@interface.implementer(IContentHeadlinePost)
class ContentHeadlinePost(GeneralHeadlinePost):

    mime_type = mimeType = 'application/vnd.nextthought.forums.contentheadlinepost'


@interface.implementer(IContentCommentPost)
class ContentCommentPost(GeneralForumComment):

    mime_type = mimeType = 'application/vnd.nextthought.forums.contentforumcomment'

    def xxx_isReadableByAnyIdOfUser(self, *unused_args, **unused_kwargs):
        # if we get here, we're authenticated
        # See above about the sharing stuff
        return True


@component.adapter(IContentBoard)
class _ContentBoardACLProvider(CommunityBoardACLProvider):
    """
    We want exactly the same thing as the community gets:
    admins can create/delete forums, and the creator gets nothing special,
    with nothing inherited.
    """

    def _extend_acl_after_creator_and_sharing(self, acl):
        acl.append(ace_allowing(AUTHENTICATED_GROUP_NAME, ACT_READ, ContentBoard))
        # acl.append( ace_allowing( prin, ACT_CREATE, ContentBoard ))
        super(_ContentBoardACLProvider, self)._extend_acl_after_creator_and_sharing(acl)


@component.adapter(IContentForum)
class _ContentForumACLProvider(CommunityForumACLProvider):
    """
    Lets everyone create entries inside it right now.
    """

    def _get_sharing_target_names(self):
        return ('Everyone', AUTHENTICATED_GROUP_NAME)


@interface.implementer(IExternalMappingDecorator)
class ContentBoardLinkDecorator(Singleton):
    # XXX Very similar to the decorators for Community and PersonalBlog;
    # can we unify these?

    def decorateExternalMapping(self, context, mapping):
        # TODO: This may be slow, if the forum doesn't persistently
        # exist and we keep creating it and throwing it away (due to
        # not commiting on GET)
        board = IContentBoard(context, None)
        # Not checking security. If the community is visible to you, the forum
        # is too
        if board is not None:
            the_links = mapping.setdefault(LINKS, [])
            link = Link(board, rel=board.__name__)
            # link_belongs_to_user( link, context )
            the_links.append(link)
