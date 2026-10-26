# Servicio de documentos clínicos: valida, guarda, lista y descarga documentos según los permisos.
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from app.models import HealthDocument, HealthDocumentType, User, UserRole
from app.schemas.health_documents import HealthDocumentSearchItem, HealthDocumentSearchResponse
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.health_document_repository import HealthDocumentRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.file_storage import FileStorage


class HealthDocumentNotFoundError(Exception):
    pass


class HealthDocumentAccessError(Exception):
    pass


class HealthDocumentValidationError(Exception):
    pass


ALLOWED_HEALTH_DOCUMENT_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}


class HealthDocumentService:
    def __init__(
        self,
        documents: HealthDocumentRepository,
        profiles: ProfileRepository,
        appointments: AppointmentRepository,
        storage: FileStorage,
        max_file_size: int,
    ):
        self.documents = documents
        self.profiles = profiles
        self.appointments = appointments
        self.storage = storage
        self.max_file_size = max_file_size

    def upload(
        self,
        current_user: User,
        file: BinaryIO,
        filename: str,
        content_type: str | None,
        document_type: HealthDocumentType,
        description: str | None,
    ) -> HealthDocument:
        profile = self.profiles.get_patient(current_user.id)
        if profile is None:
            raise HealthDocumentValidationError("Patient profile not found")
        self._validate_content_type(content_type)
        document_id = uuid4()
        key = self._storage_key(profile.id, document_id, filename)
        try:
            self.storage.save(file, key, self.max_file_size)
        except ValueError as error:
            raise HealthDocumentValidationError(str(error)) from error
        try:
            return self.documents.create(
                HealthDocument(
                    id=document_id,
                    patient_id=profile.id,
                    tipo=document_type,
                    file_url=key,
                    descripcion=description,
                )
            )
        except Exception:
            self.storage.path_for(key).unlink(missing_ok=True)
            raise

    def list_for_patient(self, current_user: User) -> list[HealthDocument]:
        profile = self.profiles.get_patient(current_user.id)
        if profile is None:
            raise HealthDocumentValidationError("Patient profile not found")
        return self.documents.list_for_patient(profile.id)

    def search(self, current_user: User, query: str, document_type=None, page=1, page_size=20):
        """Search metadata within the same access scope as document downloads."""
        if current_user.role not in (UserRole.PATIENT, UserRole.PROFESSIONAL):
            raise HealthDocumentAccessError("HEALTH_DOCUMENT_SEARCH_FORBIDDEN")
        query = query.strip()
        if not query or len(query) > 100 or page < 1 or not 1 <= page_size <= 100:
            raise HealthDocumentValidationError("INVALID_DOCUMENT_SEARCH")
        search = (
            self.documents.search_for_patient if current_user.role == UserRole.PATIENT
            else self.documents.search_for_professional
        )
        rows, total = search(current_user.id, query, document_type, (page - 1) * page_size, page_size)
        return HealthDocumentSearchResponse(
            documents=[HealthDocumentSearchItem(
                id=document.id, patient_user_id=patient_user_id, tipo=document.tipo,
                descripcion=document.descripcion, fecha_subida=document.fecha_subida,
            ) for document, patient_user_id in rows],
            total=total, page=page, page_size=page_size,
        )

    def list_for_professional(self, patient_id: UUID, professional_id: UUID) -> list[HealthDocument]:
        profile = self.profiles.get_patient(patient_id)
        if profile is None:
            raise HealthDocumentNotFoundError("Patient profile not found")
        self._require_professional_access(profile, professional_id)
        return self.documents.list_for_patient(profile.id)

    def download_for_patient(self, document_id: UUID, current_user: User):
        document = self._get(document_id)
        profile = self.profiles.get_patient(current_user.id)
        if profile is None or document.patient_id != profile.id:
            raise HealthDocumentAccessError("Document does not belong to this patient")
        return document, self._path(document)

    def download_for_professional(self, document_id: UUID, patient_id: UUID, professional_id: UUID):
        document = self._get(document_id)
        profile = self.profiles.get_patient(patient_id)
        if profile is None or document.patient_id != profile.id:
            raise HealthDocumentAccessError("Document does not belong to this patient")
        self._require_professional_access(profile, professional_id)
        return document, self._path(document)

    def _get(self, document_id: UUID) -> HealthDocument:
        document = self.documents.get(document_id)
        if document is None:
            raise HealthDocumentNotFoundError("Health document not found")
        return document

    def _path(self, document: HealthDocument):
        path = self.storage.path_for(document.file_url)
        if not path.is_file():
            raise HealthDocumentNotFoundError("Health document file not found")
        return path

    def _require_professional_access(self, profile, professional_id: UUID) -> None:
        if not profile.share_health_data:
            raise HealthDocumentAccessError("The patient has not shared health data")
        if not self.appointments.has_shared_appointment(profile.user_id, professional_id):
            raise HealthDocumentAccessError("No shared appointment with this patient")

    @staticmethod
    def _validate_content_type(content_type: str | None) -> None:
        if content_type not in ALLOWED_HEALTH_DOCUMENT_CONTENT_TYPES:
            raise HealthDocumentValidationError("Health document must be a PDF, JPEG, or PNG file")

    @staticmethod
    def _storage_key(patient_id: UUID, document_id: UUID, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        return f"health_documents/{patient_id}/{document_id}{suffix}"
