"""
RGU Hub Backend - Resources App Views

This module contains Django REST Framework ViewSets for handling API requests
related to study materials, subjects, and material types.

ViewSets Overview:
- MaterialTypeViewSet: Read-only access to material types (cached 15 min)
- SubjectMaterialViewSet: CRUD operations for study materials (throttled 30/min)
- SubjectViewSet: Read-only access to subjects (cached 15 min)

Author: RGU Hub Development Team
Last Updated: 2025
"""

from rest_framework import viewsets
from rest_framework.throttling import AnonRateThrottle
from .models import SubjectMaterial, Subject, MaterialType
from .serializers import SubjectMaterialSerializer, SubjectSerializer, MaterialTypeSerializer
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
import logging

logger = logging.getLogger(__name__)


class MaterialTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for MaterialType model.
    Cached for 15 minutes to reduce database hits.
    """
    queryset = MaterialType.objects.all()
    serializer_class = MaterialTypeSerializer

    @method_decorator(cache_page(60 * 15))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class SubjectMaterialViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for SubjectMaterial model with advanced filtering.
    Throttled to 30 requests/minute per IP to prevent bot scraping.
    NOT cached so throttling works correctly.
    """
    queryset = SubjectMaterial.objects.all()
    serializer_class = SubjectMaterialSerializer
    throttle_classes = [AnonRateThrottle]  # 30/minute from settings.py

    def list(self, request, *args, **kwargs):
        """
        Filters materials by subject slug and/or material type slug.
        """
        subject_slug = request.query_params.get("subject")
        material_type = request.query_params.get("type")

        logger.info(f"[SubjectMaterialViewSet] Request received with subject slug: {subject_slug}, material type: {material_type}")

        qs = self.queryset
        if subject_slug:
            qs = qs.filter(subject__slug=subject_slug)
            logger.info(f"[SubjectMaterialViewSet] After subject filter: {qs.count()} materials")

        if material_type:
            qs = qs.filter(material_type__slug=material_type)
            logger.info(f"[SubjectMaterialViewSet] After material type filter: {qs.count()} materials")

        logger.info(f"[SubjectMaterialViewSet] Final queryset count: {qs.count()}")
        self.queryset = qs
        return super().list(request, *args, **kwargs)


class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for Subject model with course and term filtering.
    Cached for 15 minutes to reduce database hits.
    """
    queryset = Subject.objects.select_related(
        "term", "term__syllabus", "term__syllabus__program"
    )
    serializer_class = SubjectSerializer

    @method_decorator(cache_page(60 * 15))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        course = self.request.query_params.get("course")
        year = self.request.query_params.get("year")
        sem = self.request.query_params.get("sem")

        if not course:
            return qs

        qs = qs.filter(term__syllabus__program__short_name__iexact=course)

        if sem:
            try:
                sem = int(sem)
                qs = qs.filter(term__term_type="SEMESTER", term__term_number=sem)
            except (TypeError, ValueError):
                return qs.none()
        elif year:
            try:
                year = int(year)
                qs = qs.filter(term__term_type="YEAR", term__term_number=year)
            except (TypeError, ValueError):
                return qs.none()

        return qs