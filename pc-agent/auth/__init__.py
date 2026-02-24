"""ProgressEye 인증 패키지 공개 API."""

from __future__ import annotations


class AuthError(Exception):
    """인증 관련 사용자 정의 예외."""


__all__ = [
    "AuthError",
    "GoogleOAuth",  # from auth.google_oauth
    "FirebaseAuth",  # from auth.firebase_auth
    "TokenManager",  # from auth.token_manager
]
