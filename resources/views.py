"""
RGU Hub Backend - Resources App Views
 
This module contains Django REST Framework ViewSets for handling API requests
related to study materials, subjects, and material types.
 
ViewSets Overview:
- MaterialTypeViewSet: Read-only access to material types
- SubjectMaterialViewSet: CRUD operations for study materials with filtering
- SubjectViewSet: Read-only access to subjects with course/year/semester filtering
 
API Endpoints:
- GET /material-types/ - List all material types
- GET /materials/ - List all materials
- GET /materials/?subject=slug - Filter by subject slug
- GET /materials/?type=slug - Filter by material type slug
- GET /subjects/ - List all subjects
- GET /subjects/?course=BSCN - Filter by program
- GET /subjects/?course=BSCN&sem=1 - Filter by program and semester
- GET /subjects/?course=BSCN&year=1 - Filter by program and year
 
Author: RGU Hub Development Team
Last Updated: 2025
"""
 
from rest_framework import viewsets
from .models import SubjectMaterial, Subject, MaterialType
from .serializers import SubjectMaterialSerializer, SubjectSerializer, MaterialTypeSerializer
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework.pagination import PageNumberPagination
import logging
 
logger = logging.getLogger(__name__)
 
class MaterialTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for MaterialType model.
    
    Provides list and retrieve operations for material types.
    Used by frontend to populate material type filters and displays.
    
    Endpoints:
    - GET /material-types/ - List all material types
    - GET /material-types/{id}/ - Get specific material type
    
    Response Format:
    {
        "id": 1,
        "name": "Notes",
        "slug": "notes",
        "description": "Lecture notes and handouts",
        "icon": "book-open",
        "color": "primary"
    }
    """
    queryset = MaterialType.objects.all()
    serializer_class = MaterialTypeSerializer

class MaterialPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100
 
class SubjectMaterialViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for SubjectMaterial model with advanced filtering.
    
    Supports filtering by subject slug and material type slug.
    Provides full CRUD operations for study materials.
    Rate limited to 30 requests/minute per IP to prevent bot scraping.
    
    Endpoints:
    - GET /materials/ - List all materials
    - GET /materials/?subject=bn101-anatomy-physiology - Filter by subject
    - GET /materials/?type=notes - Filter by material type
    - GET /materials/?subject=bn101&type=pyq - Combined filtering
    - POST /materials/ - Create new material
    - PUT/PATCH /materials/{id}/ - Update material
    - DELETE /materials/{id}/ - Delete material
    
    Query Parameters:
    - subject: Subject slug (e.g., "bn101-anatomy-physiology")
    - type: Material type slug (e.g., "notes", "pyq", "question-bank")
    
    Response Format:
    {
        "id": 1,
        "subject_id": 1,
        "subject_code": "BN101",
        "subject_name": "Anatomy and Physiology",
        "material_type": {
            "id": 1,
            "name": "Notes",
            "slug": "notes"
        },
        "title": "anatomy_notes.pdf",
        "url": "https://res.cloudinary.com/...",
        "description": "Comprehensive anatomy notes",
        "year": 2023,
        "month": "July",
        "is_active": true,
        "created_at": "2023-07-15T10:30:00Z"
    }
    """
    queryset = SubjectMaterial.objects.all()
    serializer_class = SubjectMaterialSerializer
    pagination_class = MaterialPagination 
 
    @method_decorator(ratelimit(key='ip', rate='30/m', block=True))
    def list(self, request, *args, **kwargs):
        """
        Override list method to add custom filtering logic.
        
        Filters materials by:
        1. Subject slug (if provided)
        2. Material type slug (if provided)
        
        Logs filtering operations for debugging.
        Rate limited to 30 requests/minute per IP.
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
    
    Provides list and retrieve operations for subjects with advanced filtering
    by program, semester, or year.
    
    Endpoints:
    - GET /subjects/ - List all subjects
    - GET /subjects/?course=BSCN - Filter by program short name
    - GET /subjects/?course=BSCN&sem=1 - Filter by program and semester
    - GET /subjects/?course=BSCN&year=1 - Filter by program and year
    - GET /subjects/{id}/ - Get specific subject
    
    Query Parameters:
    - course: Program short name (case-insensitive, e.g., "BSCN", "BPT")
    - sem: Semester number (e.g., 1, 2, 3, 4)
    - year: Year number (e.g., 1, 2, 3, 4)
    
    Response Format:
    {
        "id": 1,
        "code": "BN101",
        "name": "Anatomy and Physiology",
        "subject_type": "THEORY",
        "slug": "bscn-1-bn101-anatomy-physiology",
        "term": 1,
        "term_slug": "bscn-cbcs-2022-semester-1",
        "materials_count": 5
    }
    """
    queryset = Subject.objects.select_related(
        "term", "term__syllabus", "term__syllabus__program"
    )
    serializer_class = SubjectSerializer
 
    def get_queryset(self):
        """
        Override get_queryset to add custom filtering logic.
        
        Filters subjects by:
        1. Program (course) - case insensitive
        2. Semester number (if sem parameter provided)
        3. Year number (if year parameter provided)
        
        Returns empty queryset for invalid semester/year values.
        """
        qs = super().get_queryset()
        course = self.request.query_params.get("course")
        year = self.request.query_params.get("year")
        sem = self.request.query_params.get("sem")
 
        if not course:
            return qs  # no course provided, return all
 
        # make course case-insensitive
        qs = qs.filter(term__syllabus__program__short_name__iexact=course)
 
        if sem:
            try:
                sem = int(sem)
                qs = qs.filter(term__term_type="SEMESTER", term__term_number=sem)
            except (TypeError, ValueError):
                return qs.none()  # invalid sem
        elif year:
            try:
                year = int(year)
                qs = qs.filter(term__term_type="YEAR", term__term_number=year)
            except (TypeError, ValueError):
                return qs.none()  # invalid year
 
        return qs