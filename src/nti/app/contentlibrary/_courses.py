#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from zope.security.interfaces import IPrincipal

from nti.app.contentlibrary._permissioned import _set_user_ticket
from nti.app.contentlibrary._permissioned import _memcached_client

from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

def _on_operation_on_scope_membership(record, event):
	principal = record.Principal
	if principal != None:
		pid = IPrincipal(principal).id
		_set_user_ticket(pid, _memcached_client())

@component.adapter(ICourseInstanceEnrollmentRecord, IObjectAddedEvent)
def _on_enroll_record(record, event):
	_on_operation_on_scope_membership(record , event)

@component.adapter(ICourseInstanceEnrollmentRecord, IObjectRemovedEvent)
def _on_unenroll_record(record, event):
	_on_operation_on_scope_membership(record , event)
