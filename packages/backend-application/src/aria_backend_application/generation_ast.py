from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Collection, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import NoReturn, Protocol
from uuid import UUID, uuid4

CANDIDATE_SCHEMA_VERSION = "generation_ast_candidate_v1"
CANONICAL_SCHEMA_VERSION = "generation_ast_schema_v1"
COMPONENT_REGISTRY_VERSION = "component_registry_v1"
PROJECT_TYPES = frozenset({"landing", "corporate", "portfolio"})
COMPONENT_TYPES = frozenset(
    {
        "Navbar",
        "Hero",
        "Footer",
        "FeatureGrid",
        "ServiceList",
        "AboutSection",
        "CTA",
        "Testimonial",
        "FAQ",
        "ContactSection",
        "PortfolioGrid",
        "Stats",
        "LogoCloud",
        "SimpleForm",
    }
)
PATH_PATTERN = re.compile(
    r"^/$|^/[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$"
)
FORM_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
STYLE_VALUES = {
    "surface": frozenset({"background", "surface", "surface_muted"}),
    "text": frozenset({"text", "text_muted"}),
    "accent": frozenset({"primary"}),
    "border": frozenset({"border"}),
    "container": frozenset({"content_max", "form_max", "text_measure"}),
}
LAYOUT_RESPONSIVE: dict[str, dict[str, str]] = {
    "Navbar": {
        "horizontal": "responsive.nav_collapse_v1",
        "centered": "responsive.nav_collapse_v1",
    },
    "Hero": {
        "centered": "responsive.single_v1",
        "split_media_start": "responsive.split_v1",
        "split_media_end": "responsive.split_v1",
    },
    "Footer": {
        "compact": "responsive.inline_wrap_v1",
        "columns": "responsive.grid_4_v1",
    },
    "FeatureGrid": {
        "grid_2": "responsive.grid_2_v1",
        "grid_3": "responsive.grid_3_v1",
    },
    "ServiceList": {
        "stacked": "responsive.single_v1",
        "grid_2": "responsive.grid_2_v1",
        "grid_3": "responsive.grid_3_v1",
    },
    "AboutSection": {
        "text_only": "responsive.single_v1",
        "media_start": "responsive.split_v1",
        "media_end": "responsive.split_v1",
    },
    "CTA": {
        "centered": "responsive.single_v1",
        "split": "responsive.split_v1",
    },
    "Testimonial": {
        "single": "responsive.single_v1",
        "grid_2": "responsive.grid_2_v1",
    },
    "FAQ": {
        "stacked": "responsive.single_v1",
        "two_column": "responsive.grid_2_v1",
    },
    "ContactSection": {
        "stacked": "responsive.single_v1",
        "split": "responsive.split_v1",
    },
    "PortfolioGrid": {
        "grid_2": "responsive.grid_2_v1",
        "grid_3": "responsive.grid_3_v1",
    },
    "Stats": {
        "inline": "responsive.inline_wrap_v1",
        "grid_2": "responsive.grid_2_v1",
        "grid_4": "responsive.grid_4_v1",
    },
    "LogoCloud": {
        "grid": "responsive.grid_4_v1",
        "inline_wrap": "responsive.inline_wrap_v1",
    },
    "SimpleForm": {
        "stacked": "responsive.single_v1",
        "two_column": "responsive.grid_2_v1",
    },
}
MEDIA_REQUIRED_LAYOUTS = {
    "Hero": frozenset({"split_media_start", "split_media_end"}),
    "AboutSection": frozenset({"media_start", "media_end"}),
}


class GenerationAstValidationError(ValueError):
    """A stable, content-safe Generation AST validation failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AssetAuthorization:
    asset_ref: UUID
    authorized_for_generation: bool


class AssetRegistryPort(Protocol):
    async def authorize_for_generation(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        asset_refs: tuple[UUID, ...],
    ) -> tuple[AssetAuthorization, ...]: ...


class GenerationOutputFinalizer(Protocol):
    async def finalize_validated_output(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        job_id: UUID,
        generation_ast: Mapping[str, object],
    ) -> None:
        """Persist the valid AST and Job success in one atomic boundary."""


@dataclass(frozen=True, slots=True)
class FinalizeGenerationOutputCommand:
    account_id: UUID
    project_id: UUID
    job_id: UUID
    candidate: object
    pinned_requirement_ids: frozenset[UUID]


class GenerationOutputService:
    def __init__(
        self,
        *,
        asset_registry: AssetRegistryPort,
        finalizer: GenerationOutputFinalizer,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._asset_registry = asset_registry
        self._finalizer = finalizer
        self._id_factory = id_factory

    async def execute(
        self, command: FinalizeGenerationOutputCommand
    ) -> dict[str, object]:
        candidate = validate_generation_candidate(
            command.candidate,
            pinned_requirement_ids=command.pinned_requirement_ids,
        )
        asset_refs = tuple(
            UUID(value)
            for value in _uuid_list(
                candidate["assets"],
                maximum=100,
                code="GENERATION_ASSET_REFERENCE_INVALID",
            )
        )
        authorizations = await self._asset_registry.authorize_for_generation(
            account_id=command.account_id,
            project_id=command.project_id,
            asset_refs=asset_refs,
        )
        _require_asset_authorization(asset_refs, authorizations)
        canonical = enrich_generation_candidate(candidate, id_factory=self._id_factory)
        await self._finalizer.finalize_validated_output(
            account_id=command.account_id,
            project_id=command.project_id,
            job_id=command.job_id,
            generation_ast=canonical,
        )
        return canonical


def validate_generation_candidate(
    value: object,
    *,
    pinned_requirement_ids: Collection[UUID],
) -> dict[str, object]:
    root = _object(
        value,
        required={"schema_version", "project_type", "theme", "assets", "pages"},
    )
    if root["schema_version"] != CANDIDATE_SCHEMA_VERSION:
        _fail("GENERATION_SCHEMA_INVALID")
    project_type = root["project_type"]
    if project_type not in PROJECT_TYPES:
        _fail("GENERATION_SCHEMA_INVALID")
    theme = _validate_theme(root["theme"])
    assets = _uuid_list(root["assets"], maximum=100, code="GENERATION_ASSET_REFERENCE_INVALID")
    pages_value = _array(root["pages"], minimum=1, maximum=12)
    allowed_requirements = {str(value) for value in pinned_requirement_ids}
    normalized_pages: list[dict[str, object]] = []
    paths: set[str] = set()
    target_paths: set[str] = set()
    used_assets: set[str] = set()
    total_sections = 0
    for page_value in pages_value:
        page = _object(page_value, required={"title", "path", "sections"})
        title = _single_line(page["title"], maximum=160)
        path = _path(page["path"])
        if path in paths:
            _fail("GENERATION_PATH_DUPLICATE")
        paths.add(path)
        sections_value = _array(page["sections"], minimum=1, maximum=30)
        total_sections += len(sections_value)
        if total_sections > 120:
            _fail("GENERATION_LIMIT_EXCEEDED")
        normalized_sections: list[dict[str, object]] = []
        for section_value in sections_value:
            section, section_targets, section_assets = _validate_section(
                section_value,
                allowed_requirement_ids=allowed_requirements,
            )
            normalized_sections.append(section)
            target_paths.update(section_targets)
            used_assets.update(section_assets)
        normalized_pages.append(
            {"title": title, "path": path, "sections": normalized_sections}
        )
    if not target_paths <= paths:
        _fail("GENERATION_NAVIGATION_TARGET_INVALID")
    declared_assets = set(assets)
    if used_assets != declared_assets:
        _fail("GENERATION_ASSET_REFERENCE_INVALID")
    return {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "project_type": project_type,
        "theme": theme,
        "assets": assets,
        "pages": normalized_pages,
    }


def enrich_generation_candidate(
    candidate: Mapping[str, object],
    *,
    id_factory: Callable[[], UUID] = uuid4,
) -> dict[str, object]:
    result = deepcopy(dict(candidate))
    result["schema_version"] = CANONICAL_SCHEMA_VERSION
    pages = result["pages"]
    if not isinstance(pages, list):
        _fail("GENERATION_SCHEMA_INVALID")
    seen_ids: set[str] = set()
    for page in pages:
        if not isinstance(page, dict):
            _fail("GENERATION_SCHEMA_INVALID")
        page_id = str(id_factory())
        if page_id in seen_ids:
            _fail("GENERATION_SCHEMA_INVALID")
        seen_ids.add(page_id)
        page["page_id"] = page_id
        sections = page.get("sections")
        if not isinstance(sections, list):
            _fail("GENERATION_SCHEMA_INVALID")
        for section in sections:
            if not isinstance(section, dict):
                _fail("GENERATION_SCHEMA_INVALID")
            section_id = str(id_factory())
            if section_id in seen_ids:
                _fail("GENERATION_SCHEMA_INVALID")
            seen_ids.add(section_id)
            section["section_id"] = section_id
            section["protected_state"] = "unprotected"
    return result


def _validate_theme(value: object) -> dict[str, str]:
    theme = _object(value, required={"mode", "token_profile"})
    if theme["mode"] not in {"light", "dark"}:
        _fail("GENERATION_SCHEMA_INVALID")
    if theme["token_profile"] != "aria_semantic_v1":
        _fail("GENERATION_SCHEMA_INVALID")
    return {"mode": str(theme["mode"]), "token_profile": "aria_semantic_v1"}


def _validate_section(
    value: object,
    *,
    allowed_requirement_ids: set[str],
) -> tuple[dict[str, object], set[str], set[str]]:
    section = _object(
        value,
        required={
            "component_type",
            "content",
            "layout_variant",
            "style_token_refs",
            "responsive_rule_ref",
            "source_requirement_ids",
        },
    )
    component = section["component_type"]
    if not isinstance(component, str) or component not in COMPONENT_TYPES:
        _fail("GENERATION_COMPONENT_UNSUPPORTED")
    layout = section["layout_variant"]
    responsive = section["responsive_rule_ref"]
    if not isinstance(layout, str) or not isinstance(responsive, str):
        _fail("GENERATION_LAYOUT_RESPONSIVE_MISMATCH")
    if LAYOUT_RESPONSIVE[component].get(layout) != responsive:
        _fail("GENERATION_LAYOUT_RESPONSIVE_MISMATCH")
    style_tokens = _validate_style_tokens(section["style_token_refs"])
    requirement_ids = _uuid_list(
        section["source_requirement_ids"],
        maximum=50,
        code="GENERATION_REQUIREMENT_REFERENCE_INVALID",
    )
    if not set(requirement_ids) <= allowed_requirement_ids:
        _fail("GENERATION_REQUIREMENT_REFERENCE_INVALID")
    content, target_paths, assets = _validate_component_content(
        component, section["content"]
    )
    if (
        layout in MEDIA_REQUIRED_LAYOUTS.get(component, frozenset())
        and "primary_media_asset_ref" not in content
    ):
        _fail("GENERATION_COMPONENT_CONTENT_INVALID")
    return (
        {
            "component_type": component,
            "content": content,
            "layout_variant": layout,
            "style_token_refs": style_tokens,
            "responsive_rule_ref": responsive,
            "source_requirement_ids": requirement_ids,
        },
        target_paths,
        assets,
    )


def _validate_style_tokens(value: object) -> dict[str, str]:
    tokens = _object(value, required=set(STYLE_VALUES))
    result: dict[str, str] = {}
    for key, allowed in STYLE_VALUES.items():
        token = tokens[key]
        if not isinstance(token, str) or token not in allowed:
            _fail("GENERATION_SCHEMA_INVALID")
        result[key] = token
    return result


def _validate_component_content(
    component: str, value: object
) -> tuple[dict[str, object], set[str], set[str]]:
    validator = _CONTENT_VALIDATORS[component]
    content = validator(value)
    return content, _collect_target_paths(content), _collect_asset_refs(content)


def _navbar(value: object) -> dict[str, object]:
    content = _object(
        value,
        required={"brand_text", "links"},
        optional={"primary_action", "brand_logo_asset_ref", "brand_logo_alt_text"},
    )
    result: dict[str, object] = {
        "brand_text": _single_line(content["brand_text"], maximum=80),
        "links": _links(content["links"], minimum=1, maximum=12),
    }
    _optional_action(content, result, "primary_action")
    _optional_asset_pair(content, result, "brand_logo")
    return result


def _hero(value: object) -> dict[str, object]:
    content = _object(
        value,
        required={"heading"},
        optional={
            "eyebrow",
            "body",
            "primary_action",
            "secondary_action",
            "primary_media_asset_ref",
            "primary_media_alt_text",
        },
    )
    result: dict[str, object] = {
        "heading": _single_line(content["heading"], maximum=160)
    }
    _optional_single(content, result, "eyebrow", maximum=80)
    _optional_multi(content, result, "body", maximum=4000)
    _optional_action(content, result, "primary_action")
    _optional_action(content, result, "secondary_action")
    _optional_asset_pair(content, result, "primary_media")
    return result


def _footer(value: object) -> dict[str, object]:
    content = _object(
        value,
        required={"brand_text"},
        optional={"links", "legal_text", "brand_logo_asset_ref", "brand_logo_alt_text"},
    )
    result: dict[str, object] = {
        "brand_text": _single_line(content["brand_text"], maximum=80)
    }
    if "links" in content:
        result["links"] = _links(content["links"], minimum=0, maximum=12)
    _optional_multi(content, result, "legal_text", maximum=500)
    _optional_asset_pair(content, result, "brand_logo")
    return result


def _feature_grid(value: object) -> dict[str, object]:
    return _item_section(
        value,
        item_asset_prefix="feature_media",
        item_required={"title", "description"},
        maximum=12,
    )


def _service_list(value: object) -> dict[str, object]:
    return _item_section(
        value,
        item_asset_prefix="service_media",
        item_required={"title", "description"},
        maximum=12,
    )


def _item_section(
    value: object,
    *,
    item_asset_prefix: str,
    item_required: set[str],
    maximum: int,
) -> dict[str, object]:
    content = _object(value, required={"items"}, optional={"heading", "body"})
    result: dict[str, object] = {}
    _optional_single(content, result, "heading", maximum=160)
    _optional_multi(content, result, "body", maximum=4000)
    items = _array(content["items"], minimum=1, maximum=maximum)
    normalized_items: list[dict[str, object]] = []
    for item_value in items:
        item = _object(
            item_value,
            required=item_required,
            optional={f"{item_asset_prefix}_asset_ref", f"{item_asset_prefix}_alt_text"},
        )
        normalized: dict[str, object] = {
            "title": _single_line(item["title"], maximum=160),
            "description": _single_line(item["description"], maximum=600),
        }
        _optional_asset_pair(item, normalized, item_asset_prefix)
        normalized_items.append(normalized)
    result["items"] = normalized_items
    return result


def _about(value: object) -> dict[str, object]:
    content = _object(
        value,
        required={"heading", "body"},
        optional={
            "highlights",
            "primary_media_asset_ref",
            "primary_media_alt_text",
        },
    )
    result: dict[str, object] = {
        "heading": _single_line(content["heading"], maximum=160),
        "body": _multi_line(content["body"], maximum=4000),
    }
    if "highlights" in content:
        highlights = _array(content["highlights"], minimum=1, maximum=8)
        result["highlights"] = [
            _single_line(item, maximum=160) for item in highlights
        ]
    _optional_asset_pair(content, result, "primary_media")
    return result


def _cta(value: object) -> dict[str, object]:
    content = _object(value, required={"heading", "action"}, optional={"body"})
    result: dict[str, object] = {
        "heading": _single_line(content["heading"], maximum=160),
        "action": _action(content["action"]),
    }
    _optional_multi(content, result, "body", maximum=4000)
    return result


def _testimonial(value: object) -> dict[str, object]:
    content = _object(value, required={"items"}, optional={"heading"})
    result: dict[str, object] = {}
    _optional_single(content, result, "heading", maximum=160)
    items = _array(content["items"], minimum=1, maximum=8)
    normalized_items: list[dict[str, object]] = []
    for item_value in items:
        item = _object(
            item_value,
            required={"quote", "author_name"},
            optional={
                "author_role",
                "author_avatar_asset_ref",
                "author_avatar_alt_text",
            },
        )
        normalized: dict[str, object] = {
            "quote": _multi_line(item["quote"], maximum=4000),
            "author_name": _single_line(item["author_name"], maximum=80),
        }
        _optional_single(item, normalized, "author_role", maximum=80)
        _optional_asset_pair(item, normalized, "author_avatar")
        normalized_items.append(normalized)
    result["items"] = normalized_items
    return result


def _faq(value: object) -> dict[str, object]:
    content = _object(value, required={"items"}, optional={"heading"})
    result: dict[str, object] = {}
    _optional_single(content, result, "heading", maximum=160)
    items = _array(content["items"], minimum=1, maximum=12)
    result["items"] = [
        _question_answer(item_value) for item_value in items
    ]
    return result


def _question_answer(value: object) -> dict[str, object]:
    item = _object(value, required={"question", "answer"})
    return {
        "question": _single_line(item["question"], maximum=160),
        "answer": _multi_line(item["answer"], maximum=4000),
    }


def _contact(value: object) -> dict[str, object]:
    content = _object(value, required={"heading", "methods"}, optional={"body"})
    result: dict[str, object] = {
        "heading": _single_line(content["heading"], maximum=160)
    }
    _optional_multi(content, result, "body", maximum=4000)
    methods = _array(content["methods"], minimum=1, maximum=6)
    normalized_methods: list[dict[str, object]] = []
    for method_value in methods:
        method = _object(method_value, required={"kind", "label", "value"})
        if method["kind"] not in {"email", "phone", "address"}:
            _fail("GENERATION_COMPONENT_CONTENT_INVALID")
        normalized_methods.append(
            {
                "kind": method["kind"],
                "label": _single_line(method["label"], maximum=80),
                "value": _single_line(method["value"], maximum=600),
            }
        )
    result["methods"] = normalized_methods
    return result


def _portfolio(value: object) -> dict[str, object]:
    content = _object(value, required={"items"}, optional={"heading", "body"})
    result: dict[str, object] = {}
    _optional_single(content, result, "heading", maximum=160)
    _optional_multi(content, result, "body", maximum=4000)
    items = _array(content["items"], minimum=1, maximum=12)
    normalized_items: list[dict[str, object]] = []
    for item_value in items:
        item = _object(
            item_value,
            required={"title"},
            optional={"summary", "portfolio_media_asset_ref", "portfolio_media_alt_text"},
        )
        normalized: dict[str, object] = {
            "title": _single_line(item["title"], maximum=160)
        }
        _optional_single(item, normalized, "summary", maximum=600)
        _optional_asset_pair(item, normalized, "portfolio_media")
        normalized_items.append(normalized)
    result["items"] = normalized_items
    return result


def _stats(value: object) -> dict[str, object]:
    content = _object(value, required={"items"}, optional={"heading"})
    result: dict[str, object] = {}
    _optional_single(content, result, "heading", maximum=160)
    items = _array(content["items"], minimum=1, maximum=12)
    normalized: list[dict[str, object]] = []
    for item_value in items:
        item = _object(item_value, required={"value", "label"})
        normalized.append(
            {
                "value": _single_line(item["value"], maximum=80),
                "label": _single_line(item["label"], maximum=80),
            }
        )
    result["items"] = normalized
    return result


def _logo_cloud(value: object) -> dict[str, object]:
    content = _object(value, required={"items"}, optional={"heading"})
    result: dict[str, object] = {}
    _optional_single(content, result, "heading", maximum=160)
    items = _array(content["items"], minimum=1, maximum=20)
    normalized: list[dict[str, object]] = []
    for item_value in items:
        item = _object(
            item_value,
            required={"name", "logo_asset_ref", "logo_alt_text"},
        )
        normalized.append(
            {
                "name": _single_line(item["name"], maximum=80),
                "logo_asset_ref": _uuid_text(item["logo_asset_ref"]),
                "logo_alt_text": _alt_text(item["logo_alt_text"]),
            }
        )
    result["items"] = normalized
    return result


def _simple_form(value: object) -> dict[str, object]:
    content = _object(
        value,
        required={"heading", "fields", "submit_label", "submission_mode"},
        optional={"body", "consent_label"},
    )
    if content["submission_mode"] != "preview_only":
        _fail("GENERATION_COMPONENT_CONTENT_INVALID")
    result: dict[str, object] = {
        "heading": _single_line(content["heading"], maximum=160),
        "submit_label": _single_line(content["submit_label"], maximum=80),
        "submission_mode": "preview_only",
    }
    _optional_multi(content, result, "body", maximum=4000)
    _optional_single(content, result, "consent_label", maximum=160)
    fields = _array(content["fields"], minimum=1, maximum=8)
    keys: set[str] = set()
    normalized_fields: list[dict[str, object]] = []
    for field_value in fields:
        field = _object(
            field_value,
            required={"key", "type", "label", "required", "max_length"},
        )
        key = field["key"]
        field_type = field["type"]
        if not isinstance(key, str) or FORM_KEY_PATTERN.fullmatch(key) is None:
            _fail("GENERATION_COMPONENT_CONTENT_INVALID")
        if key in keys:
            _fail("GENERATION_COMPONENT_CONTENT_INVALID")
        keys.add(key)
        if not isinstance(field_type, str) or field_type not in {
            "text",
            "email",
            "tel",
            "textarea",
        }:
            _fail("GENERATION_COMPONENT_CONTENT_INVALID")
        maximum = 2000 if field_type == "textarea" else 320
        max_length = field["max_length"]
        if (
            not isinstance(max_length, int)
            or isinstance(max_length, bool)
            or not 1 <= max_length <= maximum
        ):
            _fail("GENERATION_COMPONENT_CONTENT_INVALID")
        if not isinstance(field["required"], bool):
            _fail("GENERATION_COMPONENT_CONTENT_INVALID")
        normalized_fields.append(
            {
                "key": key,
                "type": field_type,
                "label": _single_line(field["label"], maximum=80),
                "required": field["required"],
                "max_length": max_length,
            }
        )
    result["fields"] = normalized_fields
    return result


_CONTENT_VALIDATORS: dict[str, Callable[[object], dict[str, object]]] = {
    "Navbar": _navbar,
    "Hero": _hero,
    "Footer": _footer,
    "FeatureGrid": _feature_grid,
    "ServiceList": _service_list,
    "AboutSection": _about,
    "CTA": _cta,
    "Testimonial": _testimonial,
    "FAQ": _faq,
    "ContactSection": _contact,
    "PortfolioGrid": _portfolio,
    "Stats": _stats,
    "LogoCloud": _logo_cloud,
    "SimpleForm": _simple_form,
}


def _action(value: object) -> dict[str, str]:
    action = _object(value, required={"label", "target_path"})
    return {
        "label": _single_line(action["label"], maximum=80),
        "target_path": _path(action["target_path"]),
    }


def _links(value: object, *, minimum: int, maximum: int) -> list[dict[str, str]]:
    return [_action(item) for item in _array(value, minimum=minimum, maximum=maximum)]


def _optional_action(
    source: Mapping[str, object], result: dict[str, object], key: str
) -> None:
    if key in source:
        result[key] = _action(source[key])


def _optional_single(
    source: Mapping[str, object], result: dict[str, object], key: str, *, maximum: int
) -> None:
    if key in source:
        result[key] = _single_line(source[key], maximum=maximum)


def _optional_multi(
    source: Mapping[str, object], result: dict[str, object], key: str, *, maximum: int
) -> None:
    if key in source:
        result[key] = _multi_line(source[key], maximum=maximum)


def _optional_asset_pair(
    source: Mapping[str, object], result: dict[str, object], prefix: str
) -> None:
    ref_key = f"{prefix}_asset_ref"
    alt_key = f"{prefix}_alt_text"
    has_ref = ref_key in source
    has_alt = alt_key in source
    if has_ref != has_alt:
        _fail("GENERATION_COMPONENT_CONTENT_INVALID")
    if has_ref:
        result[ref_key] = _uuid_text(source[ref_key])
        result[alt_key] = _alt_text(source[alt_key])


def _collect_target_paths(value: object) -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "target_path" and isinstance(child, str):
                paths.add(child)
            else:
                paths.update(_collect_target_paths(child))
    elif isinstance(value, list):
        for child in value:
            paths.update(_collect_target_paths(child))
    return paths


def _collect_asset_refs(value: object) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("_asset_ref") and isinstance(child, str):
                refs.add(child)
            else:
                refs.update(_collect_asset_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(_collect_asset_refs(child))
    return refs


def _require_asset_authorization(
    expected: Sequence[UUID], authorizations: Sequence[AssetAuthorization]
) -> None:
    expected_set = set(expected)
    actual: dict[UUID, bool] = {}
    for authorization in authorizations:
        if authorization.asset_ref in actual:
            _fail("GENERATION_ASSET_NOT_AUTHORIZED")
        actual[authorization.asset_ref] = authorization.authorized_for_generation
    if set(actual) != expected_set or not all(actual.values()):
        _fail("GENERATION_ASSET_NOT_AUTHORIZED")


def _object(
    value: object,
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail("GENERATION_SCHEMA_INVALID")
    optional = optional or set()
    if set(value) != required | optional.intersection(value):
        if {"page_id", "section_id", "protected_state"} & set(value):
            _fail("GENERATION_APPLICATION_FIELD_FORBIDDEN")
        _fail("GENERATION_SCHEMA_INVALID")
    return value


def _array(value: object, *, minimum: int, maximum: int) -> list[object]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        _fail("GENERATION_LIMIT_EXCEEDED")
    return value


def _single_line(value: object, *, maximum: int) -> str:
    if not isinstance(value, str):
        _fail("GENERATION_COMPONENT_CONTENT_INVALID")
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized or len(normalized) > maximum or _has_forbidden_control(normalized):
        _fail("GENERATION_COMPONENT_CONTENT_INVALID")
    return normalized


def _multi_line(value: object, *, maximum: int) -> str:
    if not isinstance(value, str):
        _fail("GENERATION_COMPONENT_CONTENT_INVALID")
    normalized = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n")).strip()
    if not normalized or len(normalized) > maximum:
        _fail("GENERATION_COMPONENT_CONTENT_INVALID")
    if any(_is_control(character) and character != "\n" for character in normalized):
        _fail("GENERATION_COMPONENT_CONTENT_INVALID")
    return normalized


def _alt_text(value: object) -> str:
    if not isinstance(value, str):
        _fail("GENERATION_COMPONENT_CONTENT_INVALID")
    normalized = unicodedata.normalize("NFC", value).strip()
    if len(normalized) > 160 or _has_forbidden_control(normalized):
        _fail("GENERATION_COMPONENT_CONTENT_INVALID")
    return normalized


def _path(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 120
        or PATH_PATTERN.fullmatch(value) is None
    ):
        _fail("GENERATION_PATH_INVALID")
    return value


def _uuid_text(value: object) -> str:
    if not isinstance(value, str):
        _fail("GENERATION_SCHEMA_INVALID")
    try:
        parsed = UUID(value)
    except ValueError:
        _fail("GENERATION_SCHEMA_INVALID")
    return str(parsed)


def _uuid_list(value: object, *, maximum: int, code: str) -> list[str]:
    values = _array(value, minimum=0, maximum=maximum)
    try:
        normalized = [_uuid_text(item) for item in values]
    except GenerationAstValidationError as exc:
        raise GenerationAstValidationError(code) from exc
    if len(normalized) != len(set(normalized)):
        _fail(code)
    return normalized


def _has_forbidden_control(value: str) -> bool:
    return any(_is_control(character) for character in value)


def _is_control(character: str) -> bool:
    codepoint = ord(character)
    return codepoint <= 0x1F or 0x7F <= codepoint <= 0x9F


def _fail(code: str) -> NoReturn:
    raise GenerationAstValidationError(code)
