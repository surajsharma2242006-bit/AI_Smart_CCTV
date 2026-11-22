"""Compatibility entry point for the project's consent-based face service."""
from face_service import erase_face_profile, identify_faces, library_available, register_face

__all__ = ["erase_face_profile", "identify_faces", "library_available", "register_face"]
