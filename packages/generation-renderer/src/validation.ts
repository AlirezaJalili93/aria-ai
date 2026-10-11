import {
  COMPONENT_TYPES,
  type CanonicalGenerationAst,
  type CanonicalPage,
  type CanonicalSection,
  type ComponentType,
  type StyleTokenRefs
} from "./types.js";

export type RendererErrorCode =
  | "GENERATION_RENDERER_CANONICAL_AST_REQUIRED"
  | "GENERATION_RENDERER_INVALID_CANONICAL_AST"
  | "GENERATION_RENDERER_PAGE_NOT_FOUND"
  | "GENERATION_RENDERER_ASSET_NOT_AUTHORIZED";

export class GenerationRendererError extends Error {
  readonly code: RendererErrorCode;

  constructor(code: RendererErrorCode) {
    super(code);
    this.name = "GenerationRendererError";
    this.code = code;
  }
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const PATH_PATTERN = /^\/$|^\/[a-z0-9]+(?:-[a-z0-9]+)*(?:\/[a-z0-9]+(?:-[a-z0-9]+)*)*$/;
const COMPONENT_SET = new Set<string>(COMPONENT_TYPES);
const PROJECT_TYPES = new Set(["landing", "corporate", "portfolio"]);
const SURFACES = new Set(["background", "surface", "surface_muted"]);
const TEXTS = new Set(["text", "text_muted"]);
const CONTAINERS = new Set(["content_max", "form_max", "text_measure"]);

export const LAYOUT_RESPONSIVE_V1: Readonly<Record<ComponentType, Readonly<Record<string, string>>>> = {
  Navbar: { horizontal: "responsive.nav_collapse_v1", centered: "responsive.nav_collapse_v1" },
  Hero: { centered: "responsive.single_v1", split_media_start: "responsive.split_v1", split_media_end: "responsive.split_v1" },
  Footer: { compact: "responsive.inline_wrap_v1", columns: "responsive.grid_4_v1" },
  FeatureGrid: { grid_2: "responsive.grid_2_v1", grid_3: "responsive.grid_3_v1" },
  ServiceList: { stacked: "responsive.single_v1", grid_2: "responsive.grid_2_v1", grid_3: "responsive.grid_3_v1" },
  AboutSection: { text_only: "responsive.single_v1", media_start: "responsive.split_v1", media_end: "responsive.split_v1" },
  CTA: { centered: "responsive.single_v1", split: "responsive.split_v1" },
  Testimonial: { single: "responsive.single_v1", grid_2: "responsive.grid_2_v1" },
  FAQ: { stacked: "responsive.single_v1", two_column: "responsive.grid_2_v1" },
  ContactSection: { stacked: "responsive.single_v1", split: "responsive.split_v1" },
  PortfolioGrid: { grid_2: "responsive.grid_2_v1", grid_3: "responsive.grid_3_v1" },
  Stats: { inline: "responsive.inline_wrap_v1", grid_2: "responsive.grid_2_v1", grid_4: "responsive.grid_4_v1" },
  LogoCloud: { grid: "responsive.grid_4_v1", inline_wrap: "responsive.inline_wrap_v1" },
  SimpleForm: { stacked: "responsive.single_v1", two_column: "responsive.grid_2_v1" }
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isStyleTokenRefs(value: unknown): value is StyleTokenRefs {
  if (!isRecord(value)) return false;
  return (
    SURFACES.has(String(value.surface)) &&
    TEXTS.has(String(value.text)) &&
    value.accent === "primary" &&
    value.border === "border" &&
    CONTAINERS.has(String(value.container))
  );
}

function assertSection(value: unknown, seenSectionIds: Set<string>): asserts value is CanonicalSection {
  if (!isRecord(value) || !isUuid(value.section_id) || seenSectionIds.has(value.section_id)) {
    throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
  }
  seenSectionIds.add(value.section_id);
  if (
    !COMPONENT_SET.has(String(value.component_type)) ||
    !isRecord(value.content) ||
    !isNonEmptyString(value.layout_variant) ||
    !isStyleTokenRefs(value.style_token_refs) ||
    !isNonEmptyString(value.responsive_rule_ref) ||
    !Array.isArray(value.source_requirement_ids) ||
    !value.source_requirement_ids.every(isUuid) ||
    (value.protected_state !== "unprotected" && value.protected_state !== "protected")
  ) {
    throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
  }
  const component = value.component_type as ComponentType;
  if (LAYOUT_RESPONSIVE_V1[component][value.layout_variant] !== value.responsive_rule_ref) {
    throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
  }
}

function assertPage(value: unknown, seenPageIds: Set<string>, seenPaths: Set<string>, seenSectionIds: Set<string>): asserts value is CanonicalPage {
  if (
    !isRecord(value) ||
    !isUuid(value.page_id) ||
    seenPageIds.has(value.page_id) ||
    !isNonEmptyString(value.title) ||
    typeof value.path !== "string" ||
    !PATH_PATTERN.test(value.path) ||
    seenPaths.has(value.path) ||
    !Array.isArray(value.sections) ||
    value.sections.length === 0
  ) {
    throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
  }
  seenPageIds.add(value.page_id);
  seenPaths.add(value.path);
  value.sections.forEach((section) => assertSection(section, seenSectionIds));
}

function visitReferences(value: unknown, paths: ReadonlySet<string>, assets: ReadonlySet<string>): void {
  if (Array.isArray(value)) {
    value.forEach((item) => visitReferences(item, paths, assets));
    return;
  }
  if (!isRecord(value)) return;
  for (const [key, child] of Object.entries(value)) {
    if (key === "target_path" && (typeof child !== "string" || !paths.has(child))) {
      throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
    }
    if ((key.endsWith("_asset_ref") || key === "logo_asset_ref") && (typeof child !== "string" || !assets.has(child))) {
      throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
    }
    visitReferences(child, paths, assets);
  }
}

export function assertCanonicalGenerationAst(value: unknown): asserts value is CanonicalGenerationAst {
  if (!isRecord(value) || value.schema_version !== "generation_ast_schema_v1") {
    throw new GenerationRendererError("GENERATION_RENDERER_CANONICAL_AST_REQUIRED");
  }
  if (
    !PROJECT_TYPES.has(String(value.project_type)) ||
    !isRecord(value.theme) ||
    (value.theme.mode !== "light" && value.theme.mode !== "dark") ||
    value.theme.token_profile !== "aria_semantic_v1" ||
    !Array.isArray(value.assets) ||
    !value.assets.every(isUuid) ||
    new Set(value.assets).size !== value.assets.length ||
    !Array.isArray(value.pages) ||
    value.pages.length === 0
  ) {
    throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
  }
  const pageIds = new Set<string>();
  const paths = new Set<string>();
  const sectionIds = new Set<string>();
  value.pages.forEach((page) => assertPage(page, pageIds, paths, sectionIds));
  visitReferences(value.pages, paths, new Set(value.assets));
}

export function recordValue(value: unknown): Record<string, unknown> {
  if (!isRecord(value)) throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
  return value;
}

export function textValue(value: unknown): string {
  if (typeof value !== "string") throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
  return value;
}

export function optionalText(value: unknown): string | undefined {
  if (value === undefined) return undefined;
  return textValue(value);
}

export function arrayValue(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
  return value;
}

export function booleanValue(value: unknown): boolean {
  if (typeof value !== "boolean") throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
  return value;
}

export function integerValue(value: unknown): number {
  if (!Number.isInteger(value)) throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
  return value as number;
}
