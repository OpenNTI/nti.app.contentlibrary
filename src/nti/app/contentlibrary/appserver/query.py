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

from nti.appserver.interfaces import IUserContainersQuerier
from nti.appserver.interfaces import IContainedObjectsQuerier

from nti.contentlibrary.indexed_data import get_catalog as lib_catalog

from nti.contentlibrary.indexed_data.interfaces import IAudioIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import IVideoIndexedDataContainer

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIPollRef
from nti.contenttypes.presentation.interfaces import INTISurveyRef

from nti.dataserver.interfaces import IUser

from nti.ntiids import ntiids

from nti.site.site import get_component_hierarchy_names


@component.adapter(IUser)
@interface.implementer(IUserContainersQuerier)
class _LibraryContainersQuerier(object):

    def __init__(self, user=None):
        self.user = user

    def query(self, user, ntiid, *unused_args, **unused_kwargs):
        containers = ()
        user = self.user if user is None else user
        if ntiid != ntiids.ROOT:
            containers = set()
            library = component.queryUtility(IContentPackageLibrary)
            if library is not None:
                containers.update(library.childrenOfNTIID(ntiid))
            containers.add(ntiid)  # item
            # include media containers.
            catalog = lib_catalog()
            if catalog is not None:  # test mode
                # Should this be all types, or is that too expensive?
                sites = get_component_hierarchy_names()
                objects = catalog.search_objects(container_ntiids=containers,
                                                 sites=sites,
                                                 container_all_of=False,
                                                 provided=(INTIVideo, INTIAudio,
                                                           INTIPollRef, INTISurveyRef))
                for obj in objects:
                    ntiid = getattr(obj, 'target', None) or obj.ntiid
                    containers.add(ntiid)
        return containers
    __call__ = query


@interface.implementer(IContainedObjectsQuerier)
class _ContainedObjectsQuerier(object):

    @classmethod
    def _get_container_leaf(cls, ntiid):
        library = component.getUtility(IContentPackageLibrary)
        paths = library.pathToNTIID(ntiid) if library is not None else None
        return paths[-1] if paths else None

    @classmethod
    def _container_assessments(cls, units, ntiid):
        results = []
        try:
            from nti.assessment.interfaces import IQAssessmentItemContainer
            for unit in units + [cls._get_container_leaf(ntiid)]:
                container = IQAssessmentItemContainer(unit, None)
                if not container:
                    continue
                for asm_item in container.assessments():
                    results.append(asm_item)
        except ImportError:
            pass
        return results

    @classmethod
    def _scan_media(cls, ntiid):
        results = []
        unit = cls._get_container_leaf(ntiid)
        if unit is None:
            return results
        for provided in (IVideoIndexedDataContainer, IAudioIndexedDataContainer):
            for media_data in provided(unit).values():
                results.append(media_data)
        return results

    @classmethod
    def _scan_quizzes(cls, ntiid):
        library = component.queryUtility(IContentPackageLibrary)
        # Quizzes are often subcontainers, so we look at the parent and its children
        # TODO: Is this what we want for all implementations?
        units = []
        results = []
        children = library.childrenOfNTIID(ntiid) if library else ()
        for unit in children or ():
            unit = ntiids.find_object_with_ntiid(unit)
            if unit is not None:
                units.append(unit)
        results.extend(cls._container_assessments(units, ntiid))
        return results

    @classmethod
    def _get_legacy_contained(cls, container_ntiid):
        results = []
        results.extend(cls._scan_media(container_ntiid))
        results.extend(cls._scan_quizzes(container_ntiid))
        return results

    @classmethod
    def _get_contained(cls, container_ntiid):
        catalog = lib_catalog()
        sites = get_component_hierarchy_names()
        objects = catalog.search_objects(container_ntiids=(container_ntiid,),
                                         sites=sites)
        if not objects:
            # Needed for non-persistent courses
            objects = cls._get_legacy_contained(container_ntiid)
        return objects

    def query(self, ntiid):
        return self._get_contained(ntiid)
    __call__ = query
