#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from zope.security.interfaces import IPrincipal

from nti.app.contentlibrary._permissioned import _set_user_ticket
from nti.app.contentlibrary._permissioned import _memcached_client

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentUnitAssociations

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import get_courses_for_packages

from nti.traversal.traversal import find_interface


def _on_operation_on_scope_membership(record, unused_event):
    principal = IPrincipal(record.Principal, None)
    if principal is not None:
        _set_user_ticket(principal.pid, _memcached_client())


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectAddedEvent)
def _on_enroll_record(record, event):
    _on_operation_on_scope_membership(record, event)


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectRemovedEvent)
def _on_unenroll_record(record, event):
    _on_operation_on_scope_membership(record, event)


@component.adapter(IContentUnit)
@interface.implementer(IContentUnitAssociations)
class _CourseContentUnitAssociations(object):

    def __init__(self, *args):
        pass

    def associations(self, context):
        result = []
        package = find_interface(context, IContentPackage, strict=False)
        if package is not None:
            courses = get_courses_for_packages(packages=(package.ntiid,))
            for course in courses or ():
                # favor catalog entries
                entry = ICourseCatalogEntry(course, None)
                if entry is not None:
                    result.append(entry)
                else:
                    result.append(course)
        return result or ()
