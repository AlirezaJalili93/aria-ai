export const COMPONENT_TYPES = [
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
  "SimpleForm"
] as const;

export type ComponentType = (typeof COMPONENT_TYPES)[number];
export type ProjectType = "landing" | "corporate" | "portfolio";
export type ThemeMode = "light" | "dark";

export interface StyleTokenRefs {
  surface: "background" | "surface" | "surface_muted";
  text: "text" | "text_muted";
  accent: "primary";
  border: "border";
  container: "content_max" | "form_max" | "text_measure";
}

export interface CanonicalSection {
  section_id: string;
  protected_state: "unprotected" | "protected";
  component_type: ComponentType;
  content: Record<string, unknown>;
  layout_variant: string;
  style_token_refs: StyleTokenRefs;
  responsive_rule_ref: string;
  source_requirement_ids: string[];
}

export interface CanonicalPage {
  page_id: string;
  title: string;
  path: string;
  sections: CanonicalSection[];
}

export interface CanonicalGenerationAst {
  schema_version: "generation_ast_schema_v1";
  project_type: ProjectType;
  theme: {
    mode: ThemeMode;
    token_profile: "aria_semantic_v1";
  };
  assets: string[];
  pages: CanonicalPage[];
}

export interface ResolvedAsset {
  assetRef: string;
  src: string;
  width: number;
  height: number;
}

export interface AssetResolver {
  resolve(assetRef: string): ResolvedAsset | null;
}
