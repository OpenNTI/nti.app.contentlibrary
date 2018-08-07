#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Adapters for application-level events.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.contentlibrary.interfaces import IContentUnit

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

logger = __import__('logging').getLogger(__name__)


@component.adapter(IContentUnit)
@interface.implementer(ICompletableItemCompletionPolicy)
class DefaultContentUnitCompletionPolicy(object):
    """
    A simple completion policy that only cares about submissions for completion.
    """

    def __init__(self, obj):
        self.content_unit = obj

    def is_complete(self, progress):
        result = None
        if progress is not None and progress.HasProgress:
            result = CompletedItem(Item=progress.Item,
                                   Principal=progress.User,
                                   CompletedDate=progress.LastModified)
        return result


@component.adapter(IContentUnit, ICompletionContext)
@interface.implementer(ICompletableItemCompletionPolicy)
def _content_completion_policy(content_unit, context):
    """
    Fetch the :class:`ICompletableItemCompletionPolicy` for this
    :class:`IContentUnit` and :class:`ICompletionContext`.
    """
    # First see if we have a specific policy set on our context.
    context_policies = ICompletionContextCompletionPolicyContainer(context)
    try:
        result = context_policies[content_unit.ntiid]
    except KeyError:
        # Ok, fetch the default
        result = ICompletableItemCompletionPolicy(content_unit)
    return result

