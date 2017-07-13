#!/usr/bin/env python
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.interface.interfaces import ComponentLookupError

from nti.app.contentlibrary.utils import role_for_content_bundle
from nti.app.contentlibrary.utils import role_for_content_package

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IRenderableContentPackage
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentUnit
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackage

from nti.dataserver import authorization

from nti.dataserver.authorization_acl import _ACL
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_denying_all
from nti.dataserver.authorization_acl import acl_from_ace_lines

from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import ALL_PERMISSIONS
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME

from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.interfaces import ISupplementalACLProvider

from nti.ntiids import ntiids

from nti.property.property import LazyOnClass as _LazyOnClass

from nti.traversal import traversal


@component.adapter(IContentUnit)
@interface.implementer(IACLProvider)
class _TestingLibraryTOCEntryACLProvider(object):
    """
    Allows all authenticated users access to library entries.
    This class is for testing only, never for use in a production scenario.
    """

    def __init__(self, context):
        self.context = context

    @property
    def __parent__(self):
        return self.context.__parent__

    @Lazy
    def __acl__(self):
        return (ace_allowing(AUTHENTICATED_GROUP_NAME,
                             ALL_PERMISSIONS,
                             _TestingLibraryTOCEntryACLProvider),)


# TODO: This could be (and was) registered for a simple IDelimitedHierarchyEntry.
# There is none of that separate from the contentpackage/unit though, so it shouldn't
# be needed in that capacity.


class _AbstractDelimitedHierarchyEntryACLProvider(object):
    """
    Checks a hierarchy entry for the existence of a file (typically .'.nti_acl'), 
    and if present, reads an ACL from it.

    Otherwise, the ACL allows all authenticated users access.
    """

    def __init__(self, context):
        self.context = context

    _acl_sibling_entry_name = '.nti_acl'

    #: If defined by a subclass, this will be checked
    #: when `_acl_sibling_entry_name` does not exist.
    _acl_sibling_fallback_name = None

    _default_allow = True
    _add_default_deny_to_acl_from_file = False

    __parent__ = property(lambda self: self.context.__parent__)

    @Lazy
    def __acl__(self):
        provenance = self._acl_sibling_entry_name
        acl_string = self.context.read_contents_of_sibling_entry(self._acl_sibling_entry_name)
        if acl_string is None and self._acl_sibling_fallback_name is not None:
            provenance = self._acl_sibling_fallback_name
            acl_string = self.context.read_contents_of_sibling_entry(self._acl_sibling_fallback_name)
        if acl_string is not None:
            try:
                __acl__ = self._acl_from_string(self.context,
                                                acl_string,
                                                provenance)
                # Empty files (those that do exist but feature no valid ACL lines)
                # are considered a mistake, an overlooked accident. In the interest of trying
                # to be secure by default and not allow oversights through, call them out.
                # This results in default-deny
                if not __acl__:
                    raise ValueError("ACL file had no valid contents.")
                if self._add_default_deny_to_acl_from_file:
                    __acl__.append(ace_denying_all('Default Deny After File ACL'))
            except (ValueError, AssertionError, TypeError, ComponentLookupError):
                logger.exception("Failed to read acl from %s/%s; denying all access.",
                                 self.context, self._acl_sibling_entry_name)
                __acl__ = _ACL((ace_denying_all('Default Deny Due to Parsing Error'),))
        elif self._default_allow:
            __acl__ = _ACL((ace_allowing(AUTHENTICATED_GROUP_NAME,
                                         ALL_PERMISSIONS,
                                         _AbstractDelimitedHierarchyEntryACLProvider),))
        else:
            __acl__ = ()  # Inherit from parent
        return __acl__

    def _acl_from_string(self, context, acl_string, provenance=None):
        return acl_from_ace_lines(acl_string.splitlines(), provenance or context)


def _supplement_acl_with_content_role(self, context, acl):
    """
    Add read-access to a pseudo-group based on the (lowercased) NTIID of the
    closest containing content package.

    It is important to do this both for the root and sublevels of the tree that
    allow ACLs to be specified in files, because we may be putting a default
    Deny entry there. (The default deny at the sub files is needed to be sure
    that we can properly mix granting and denying access and forces acl files
    to be very specific.)
    """

    package = traversal.find_interface(context, IContentPackage, strict=False)
    # Some tests need this safety
    if package is not None and package.ntiid:
        parts = ntiids.get_parts(package.ntiid)
        if parts and parts.provider and parts.specific:
            package_role = role_for_content_package(package)
            acl = acl + ace_allowing(package_role,
                                     authorization.ACT_READ,
                                     self)
    return acl


@interface.implementer(IACLProvider)
@component.adapter(IDelimitedHierarchyContentPackage)
class _DelimitedHierarchyContentPackageACLProvider(_AbstractDelimitedHierarchyEntryACLProvider):
    """
    For content packages that are part of a hierarchy,
    read the ACL file if they have one, and also add read-access to a pseudo-group
    based on the (lowercased) NTIID of the closest containing content package.

    If they have no ACL, then any authenticated user is granted access to the content.

    If they do have an ACL, then we force the last entry to be a global denial. Thus,
    if you specifically want to allow everyone, you must put that in the ACL file.
    """

    _add_default_deny_to_acl_from_file = True

    @Lazy
    def __acl__(self):
        acl = super(_DelimitedHierarchyContentPackageACLProvider, self).__acl__
        # Make sure our content admin comes first.
        admin_ace = ace_allowing(authorization.ROLE_CONTENT_ADMIN,
                                 authorization.ACT_READ,
                                 self)
        acl.insert(0, admin_ace)
        return acl

    def _acl_from_string(self, context, acl_string, provenance=None):
        acl = super(_DelimitedHierarchyContentPackageACLProvider, self)._acl_from_string(context,
                                                                                         acl_string,
                                                                                         provenance=provenance)
        acl = _supplement_acl_with_content_role(self, context, acl)
        return acl


@interface.implementer(IACLProvider)
@component.adapter(IDelimitedHierarchyContentUnit)
class _DelimitedHierarchyContentUnitACLProvider(_AbstractDelimitedHierarchyEntryACLProvider):
    """
    For content units, we look for an acl file matching their ordinal
    path from the containing content package (e.g., first section of
    first chapter uses ``.nti_acl.1.1``). If such a file does not exist,
    we have no opinion on the ACL and inherit it from our parent. If
    such a file does exist but is empty, it is treated as if it denied
    all access; this is considered a mistake.

    As a special case, for those items that are directly beneath a
    content package (e.g. chapters), if there is no specific file, we
    will use a file named ``.nti_acl.default``. This permits easily
    granting access to the whole content package (through
    ``.nti_acl``), letting it show up in libraries, etc, generally
    denying access to children (through ``.nti_acl.default``), but
    providing access to certain subunits (through the ordinal files).
    In this case, we will also place a default global denial as the
    last entry in the ACL, forcing permissioning to be at this level
    (e.g., the parent ACL from the content package is thus effectively
    NOT inherited.)
    """

    _default_allow = False

    def __init__(self, context):
        super(_DelimitedHierarchyContentUnitACLProvider, self).__init__(context)
        ordinals = []
        ordinals.append(context.ordinal)
        parent = context.__parent__
        while (    parent is not None
               and IContentUnit.providedBy(parent)
               and not IContentPackage.providedBy(parent)):
            ordinals.append(parent.ordinal)
            parent = parent.__parent__

        ordinals.reverse()
        path = u'.'.join(str(i) for i in ordinals)
        self._acl_sibling_entry_name = \
            _AbstractDelimitedHierarchyEntryACLProvider._acl_sibling_entry_name + '.' + path

        # a "chapter"; we don't do this at every level for efficiency (TODO:
        # For best caching, we need to read this off the ContentPackage)
        if len(ordinals) == 1:
            self._acl_sibling_fallback_name = \
                _AbstractDelimitedHierarchyEntryACLProvider._acl_sibling_entry_name + '.default'
            self._add_default_deny_to_acl_from_file = True

    def _acl_from_string(self, context, acl_string, provenance=None):
        acl = super(_DelimitedHierarchyContentUnitACLProvider, self)._acl_from_string(context,
                                                                                      acl_string,
                                                                                      provenance=provenance)
        if self._acl_sibling_fallback_name:
            return _supplement_acl_with_content_role(self, context, acl)
        else:
            return acl


@interface.implementer(IACLProvider)
@component.adapter(IRenderableContentPackage)
class _RenderableContentPackageACLProvider(object):
    """
    Renderable content packages give admin users all-access. We also
    supplement this acl with any :class:`ISupplementalACLProvider`
    subscribers.

    XXX: Should we do this for all content packages (if no acl file)?
    """

    def __init__(self, context):
        self.context = context

    @Lazy
    def __acl__(self):
        aces = []
        # By default, all admins and the creator have all-access to this
        # content package.
        for prin in (authorization.ROLE_CONTENT_ADMIN,
                     authorization.ROLE_ADMIN,
                     self.context.creator):
            if prin is None:
                continue
            admin_ace = ace_allowing(prin, ALL_PERMISSIONS, self)
            aces.append(admin_ace)
        # Now add in any supplemental providers.
        for supplemental in component.subscribers((self.context,), ISupplementalACLProvider):
            for supplemental_ace in supplemental.__acl__ or ():
                if supplemental_ace is not None:
                    aces.append(supplemental_ace)
        # Deny the rest (maybe we mark a content package if it is publicly
        # accessible...)
        aces.append(ACE_DENY_ALL)
        acl = acl_from_aces(aces)
        return acl


@interface.implementer(IACLProvider)
@component.adapter(IContentPackageLibrary)
class _ContentPackageLibraryACLProvider(object):

    def __init__(self, context):
        pass

    @_LazyOnClass
    def __acl__(self):
        # Got to be here after the components are registered, not at the class
        return _ACL((ace_allowing(AUTHENTICATED_GROUP_NAME,
                                  authorization.ACT_READ,
                                  _ContentPackageLibraryACLProvider),))


@interface.implementer(IACLProvider)
@component.adapter(IContentPackageBundleLibrary)
class _ContentPackageBundleLibraryACLProvider(object):

    def __init__(self, context):
        pass

    @_LazyOnClass
    def __acl__(self):
        # Got to be here after the components are registered, not at the class
        return _ACL((ace_allowing(AUTHENTICATED_GROUP_NAME,
                                  authorization.ACT_READ,
                                  _ContentPackageLibraryACLProvider),))


@interface.implementer(IACLProvider)
@component.adapter(IContentPackageBundle)
class _ContentPackageBundleACLProvider(object):
    """
    Historically, IContentPackageBundles have been always available. Now we
    preserve that behavior by default and allow access to be restricted (and
    granted via an API).
    """

    def __init__(self, context):
        self.context = context

    @Lazy
    def __acl__(self):
        aces = []
        # By default, all admins and the creator have all-access.
        for prin in (authorization.ROLE_CONTENT_ADMIN,
                     authorization.ROLE_ADMIN,
                     getattr(self.context, 'creator', None)):
            if prin is None:
                continue
            admin_ace = ace_allowing(prin, ALL_PERMISSIONS, type(self))
            aces.append(admin_ace)
        # Now our bundle role
        bundle_role = role_for_content_bundle(self.context)
        aces.append(ace_allowing(bundle_role,
                                 authorization.ACT_READ,
                                 type(self)))
        # Restrict, if necessary.
        if self.context.RestrictedAccess:
            aces.append(ACE_DENY_ALL)
        acl = acl_from_aces(aces)
        return acl
