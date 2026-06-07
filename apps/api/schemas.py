from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class JobCreate(BaseModel):
    title: str
    description: str
    company: str | None = None
    location: str | None = None
    contract_type: str | None = None
    source: str | None = "manual"
    url: str | None = None
    salary: str | None = None
    seniority: str | None = None
    remote_policy: str | None = None
    skills: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class JobRead(BaseModel):
    id: UUID
    title: str
    description: str
    company: str | None = None
    location: str | None = None
    contract_type: str | None = None
    source: str | None = None
    url: str | None = None
    salary: str | None = None
    seniority: str | None = None
    remote_policy: str | None = None
    skills: list[str]
    raw_payload: dict[str, Any]
    indexed_chunks: int = 0
    is_indexed: bool = False
    created_at: datetime
    updated_at: datetime


class JobIndexResult(BaseModel):
    job_id: UUID
    chunks_indexed: int


class AdzunaImportRequest(BaseModel):
    country: str = "gb"
    what: str | None = None
    where: str | None = None
    count: int = Field(default=10, ge=1, le=100)
    index: bool = True
    results_per_page: int = Field(default=50, ge=1, le=50)


class ProviderImportResult(BaseModel):
    import_run_id: UUID
    source: str
    created: int
    skipped: int
    indexed: int
    job_ids: list[UUID]


class ProviderImportRunRead(BaseModel):
    id: UUID
    provider: str
    query: dict[str, Any]
    requested_count: int
    created_count: int
    skipped_count: int
    indexed_count: int
    status: str
    error: str | None = None
    created_at: datetime


class ProfileCreate(BaseModel):
    name: str | None = None
    cv_text: str = Field(min_length=1)
    target_roles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    seniority: str | None = None
    preferred_contract_types: list[str] = Field(default_factory=list)
    remote_preference: str | None = None

    @field_validator("cv_text")
    @classmethod
    def cv_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("CV text must not be blank")
        return value


class ProfileRead(BaseModel):
    id: UUID
    name: str | None = None
    cv_text: str
    cv_filename: str | None = None
    cv_content_type: str | None = None
    has_cv_file: bool = False
    target_roles: list[str]
    target_locations: list[str]
    skills: list[str]
    seniority: str | None = None
    preferred_contract_types: list[str]
    remote_preference: str | None = None
    extraction_warning: str | None = None
    created_at: datetime
    updated_at: datetime


class ProfileListRead(BaseModel):
    id: UUID
    name: str | None = None
    cv_preview: str
    cv_filename: str | None = None
    cv_content_type: str | None = None
    has_cv_file: bool = False
    target_roles: list[str]
    target_locations: list[str]
    skills: list[str]
    seniority: str | None = None
    preferred_contract_types: list[str]
    remote_preference: str | None = None
    created_at: datetime
    updated_at: datetime


class ProfileExperienceCreate(BaseModel):
    title: str = Field(min_length=1)
    company: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    description: str | None = None
    skills: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Experience title must not be blank")
        return value


class ProfileExperienceRead(ProfileExperienceCreate):
    id: UUID
    profile_id: UUID
    created_at: datetime
    updated_at: datetime


class ProfileProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    role: str | None = None
    url: str | None = None
    description: str | None = None
    skills: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name must not be blank")
        return value


class ProfileProjectRead(ProfileProjectCreate):
    id: UUID
    profile_id: UUID
    created_at: datetime
    updated_at: datetime


class ProfileSkillCreate(BaseModel):
    name: str = Field(min_length=1)
    category: str | None = None
    proficiency: str | None = None

    @field_validator("name")
    @classmethod
    def skill_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Skill name must not be blank")
        return value


class ProfileSkillRead(ProfileSkillCreate):
    id: UUID
    profile_id: UUID
    created_at: datetime
    updated_at: datetime


class ProfileEnrichmentRead(BaseModel):
    experiences: list[ProfileExperienceRead]
    projects: list[ProfileProjectRead]
    enriched_skills: list[ProfileSkillRead]


class SearchFilters(BaseModel):
    location: str | None = None
    contract_type: str | None = None
    company: str | None = None
    seniority: str | None = None
    remote_policy: str | None = None


class SearchRequest(BaseModel):
    query: str
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    job_id: UUID
    chunk_id: UUID
    chunk_index: int
    score: float
    title: str
    content: str
    section: str | None = None
    company: str | None = None
    location: str | None = None
    contract_type: str | None = None
    source: str | None = None
    url: str | None = None
    salary: str | None = None
    seniority: str | None = None
    remote_policy: str | None = None
    skills: list[str]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    profile_id: UUID | None = None
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=5, ge=1, le=10)


class ChatResponse(BaseModel):
    message: str
    tool: Literal[
        "search_jobs",
        "rank_jobs_for_profile",
        "list_profiles",
        "get_profile",
        "get_job_corpus_status",
        "import_mock_jobs",
        "import_adzuna_jobs",
        "fetch_job_offers",
        "none",
    ]
    jobs: list[SearchResult] = Field(default_factory=list)
    ranked_jobs: list["RankedJobResult"] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RankJobsRequest(BaseModel):
    profile_id: UUID
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=10, ge=1, le=50)


class RankedJobResult(BaseModel):
    job_id: UUID
    title: str
    final_score: float
    vector_score: float
    skill_overlap_score: float
    location_score: float
    contract_type_score: float
    recency_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    evidence: list[SearchResult]
    company: str | None = None
    location: str | None = None
    contract_type: str | None = None
    url: str | None = None


class ExplainRankedJobsRequest(BaseModel):
    profile_id: UUID
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=5, ge=1, le=10)
    model: str = "gpt-5.5"


class ExplainedRankedJobResult(BaseModel):
    job_id: UUID
    title: str
    final_score: float
    vector_score: float
    skill_overlap_score: float
    location_score: float
    contract_type_score: float
    recency_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    why_match: str
    cv_suggestions: list[str]
    evidence: list[SearchResult]
    company: str | None = None
    location: str | None = None
    contract_type: str | None = None
    url: str | None = None
