import { type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type {
  AssetResolver,
  CanonicalGenerationAst,
  CanonicalPage,
  CanonicalSection,
  ComponentType,
  ResolvedAsset
} from "./types.js";
import {
  GenerationRendererError,
  arrayValue,
  assertCanonicalGenerationAst,
  booleanValue,
  integerValue,
  optionalText,
  recordValue,
  textValue
} from "./validation.js";

interface RenderContext {
  assets: ReadonlyMap<string, ResolvedAsset>;
}

interface RenderPageOptions {
  ast: unknown;
  path: string;
  assetResolver: AssetResolver;
}

interface SectionShellProps {
  section: CanonicalSection;
  heading?: string;
  children: ReactNode;
}

const SECTION_LABELS_FA_V1: Readonly<Record<ComponentType, string>> = {
  Navbar: "ناوبری",
  Hero: "معرفی",
  Footer: "پاورقی",
  FeatureGrid: "ویژگی‌ها",
  ServiceList: "خدمات",
  AboutSection: "درباره ما",
  CTA: "اقدام بعدی",
  Testimonial: "دیدگاه‌ها",
  FAQ: "پرسش‌های پرتکرار",
  ContactSection: "راه‌های تماس",
  PortfolioGrid: "نمونه‌کارها",
  Stats: "آمار",
  LogoCloud: "همکاران",
  SimpleForm: "فرم نمایشی"
};

const SURFACE_CLASS = {
  background: "aria-gen-surface-background",
  surface: "aria-gen-surface-default",
  surface_muted: "aria-gen-surface-muted"
} as const;
const TEXT_CLASS = { text: "aria-gen-text-default", text_muted: "aria-gen-text-muted" } as const;
const CONTAINER_CLASS = {
  content_max: "aria-gen-container-content",
  form_max: "aria-gen-container-form",
  text_measure: "aria-gen-container-text"
} as const;
const RESPONSIVE_CLASS: Readonly<Record<string, string>> = {
  "responsive.single_v1": "aria-gen-responsive-single",
  "responsive.split_v1": "aria-gen-responsive-split",
  "responsive.grid_2_v1": "aria-gen-responsive-grid-2",
  "responsive.grid_3_v1": "aria-gen-responsive-grid-3",
  "responsive.grid_4_v1": "aria-gen-responsive-grid-4",
  "responsive.inline_wrap_v1": "aria-gen-responsive-inline-wrap",
  "responsive.nav_collapse_v1": "aria-gen-responsive-nav"
};
const SAFE_RESOLVED_ASSET_SRC = /^\/[a-z0-9][a-z0-9/_-]*\.(?:png|svg|webp)$/;

function sectionClass(section: CanonicalSection): string {
  const responsiveClass = RESPONSIVE_CLASS[section.responsive_rule_ref];
  if (!responsiveClass) throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
  return [
    "aria-gen-section",
    `aria-gen-component-${section.component_type.toLowerCase()}`,
    `aria-gen-layout-${section.layout_variant.replaceAll("_", "-")}`,
    SURFACE_CLASS[section.style_token_refs.surface],
    TEXT_CLASS[section.style_token_refs.text],
    CONTAINER_CLASS[section.style_token_refs.container],
    responsiveClass
  ].join(" ");
}

function headingId(section: CanonicalSection): string {
  return `aria-gen-heading-${section.section_id}`;
}

function SectionShell({ section, heading, children }: SectionShellProps): ReactElement {
  const label = heading ?? SECTION_LABELS_FA_V1[section.component_type];
  return (
    <section className={sectionClass(section)} data-component={section.component_type} data-protected={section.protected_state}>
      <h2 className={heading ? "aria-gen-heading" : "aria-gen-visually-hidden"} id={headingId(section)}>
        {label}
      </h2>
      {children}
    </section>
  );
}

function asset(context: RenderContext, assetRef: string): ResolvedAsset {
  const resolved = context.assets.get(assetRef);
  if (!resolved) throw new GenerationRendererError("GENERATION_RENDERER_ASSET_NOT_AUTHORIZED");
  return resolved;
}

function AssetImage({ context, assetRef, altText, eager = false }: { context: RenderContext; assetRef: string; altText: string; eager?: boolean }): ReactElement {
  const resolved = asset(context, assetRef);
  return (
    <img
      alt={altText}
      className="aria-gen-media"
      decoding="async"
      height={resolved.height}
      loading={eager ? "eager" : "lazy"}
      src={resolved.src}
      width={resolved.width}
    />
  );
}

function ActionLink({ value, className = "aria-gen-action" }: { value: unknown; className?: string }): ReactElement {
  const action = recordValue(value);
  return <a className={className} href={textValue(action.target_path)}>{textValue(action.label)}</a>;
}

function Navbar({ section, context }: { section: CanonicalSection; context: RenderContext }): ReactElement {
  const content = recordValue(section.content);
  const logoRef = optionalText(content.brand_logo_asset_ref);
  return (
    <header className={sectionClass(section)} data-component="Navbar" data-protected={section.protected_state}>
      <nav aria-label="ناوبری اصلی" className="aria-gen-navbar">
        <div className="aria-gen-brand">
          {logoRef ? <AssetImage context={context} assetRef={logoRef} altText={textValue(content.brand_logo_alt_text)} /> : null}
          <span>{textValue(content.brand_text)}</span>
        </div>
        <ul className="aria-gen-link-list">
          {arrayValue(content.links).map((item, index) => {
            const link = recordValue(item);
            return <li key={`${section.section_id}-link-${index}`}><a href={textValue(link.target_path)}>{textValue(link.label)}</a></li>;
          })}
        </ul>
        {content.primary_action ? <ActionLink value={content.primary_action} /> : null}
      </nav>
    </header>
  );
}

function Hero({ section, context }: { section: CanonicalSection; context: RenderContext }): ReactElement {
  const content = recordValue(section.content);
  const mediaRef = optionalText(content.primary_media_asset_ref);
  return (
    <SectionShell section={section} heading={textValue(content.heading)}>
      {optionalText(content.eyebrow) ? <p className="aria-gen-eyebrow">{optionalText(content.eyebrow)}</p> : null}
      {optionalText(content.body) ? <p className="aria-gen-body">{optionalText(content.body)}</p> : null}
      <div className="aria-gen-actions">
        {content.primary_action ? <ActionLink value={content.primary_action} /> : null}
        {content.secondary_action ? <ActionLink className="aria-gen-action aria-gen-action-secondary" value={content.secondary_action} /> : null}
      </div>
      {mediaRef ? <AssetImage context={context} assetRef={mediaRef} altText={textValue(content.primary_media_alt_text)} eager /> : null}
    </SectionShell>
  );
}

function Footer({ section, context }: { section: CanonicalSection; context: RenderContext }): ReactElement {
  const content = recordValue(section.content);
  const logoRef = optionalText(content.brand_logo_asset_ref);
  return (
    <footer className={sectionClass(section)} data-component="Footer" data-protected={section.protected_state}>
      <div className="aria-gen-brand">
        {logoRef ? <AssetImage context={context} assetRef={logoRef} altText={textValue(content.brand_logo_alt_text)} /> : null}
        <span>{textValue(content.brand_text)}</span>
      </div>
      {content.links ? <nav aria-label="پیوندهای پاورقی"><ul className="aria-gen-link-list">{arrayValue(content.links).map((item, index) => {
        const link = recordValue(item);
        return <li key={`${section.section_id}-footer-link-${index}`}><a href={textValue(link.target_path)}>{textValue(link.label)}</a></li>;
      })}</ul></nav> : null}
      {optionalText(content.legal_text) ? <p>{optionalText(content.legal_text)}</p> : null}
    </footer>
  );
}

function CardGrid({ section, context, kind }: { section: CanonicalSection; context: RenderContext; kind: "feature" | "service" }): ReactElement {
  const content = recordValue(section.content);
  const heading = optionalText(content.heading);
  return (
    <SectionShell section={section} heading={heading}>
      {optionalText(content.body) ? <p className="aria-gen-body">{optionalText(content.body)}</p> : null}
      <div className="aria-gen-items">
        {arrayValue(content.items).map((value, index) => {
          const item = recordValue(value);
          const refKey = kind === "feature" ? "feature_media_asset_ref" : "service_media_asset_ref";
          const altKey = kind === "feature" ? "feature_media_alt_text" : "service_media_alt_text";
          const mediaRef = optionalText(item[refKey]);
          return (
            <article className="aria-gen-card" key={`${section.section_id}-item-${index}`}>
              <h3>{textValue(item.title)}</h3>
              <p>{textValue(item.description)}</p>
              {mediaRef ? <AssetImage context={context} assetRef={mediaRef} altText={textValue(item[altKey])} /> : null}
            </article>
          );
        })}
      </div>
    </SectionShell>
  );
}

function AboutSection({ section, context }: { section: CanonicalSection; context: RenderContext }): ReactElement {
  const content = recordValue(section.content);
  const mediaRef = optionalText(content.primary_media_asset_ref);
  return (
    <SectionShell section={section} heading={textValue(content.heading)}>
      <p className="aria-gen-body">{textValue(content.body)}</p>
      {content.highlights ? <ul>{arrayValue(content.highlights).map((value, index) => <li key={`${section.section_id}-highlight-${index}`}>{textValue(value)}</li>)}</ul> : null}
      {mediaRef ? <AssetImage context={context} assetRef={mediaRef} altText={textValue(content.primary_media_alt_text)} /> : null}
    </SectionShell>
  );
}

function CTA({ section }: { section: CanonicalSection }): ReactElement {
  const content = recordValue(section.content);
  return (
    <SectionShell section={section} heading={textValue(content.heading)}>
      {optionalText(content.body) ? <p className="aria-gen-body">{optionalText(content.body)}</p> : null}
      <ActionLink value={content.action} />
    </SectionShell>
  );
}

function Testimonial({ section, context }: { section: CanonicalSection; context: RenderContext }): ReactElement {
  const content = recordValue(section.content);
  return (
    <SectionShell section={section} heading={optionalText(content.heading)}>
      <div className="aria-gen-items">
        {arrayValue(content.items).map((value, index) => {
          const item = recordValue(value);
          const avatarRef = optionalText(item.author_avatar_asset_ref);
          return (
            <figure className="aria-gen-card" key={`${section.section_id}-quote-${index}`}>
              {avatarRef ? <AssetImage context={context} assetRef={avatarRef} altText={textValue(item.author_avatar_alt_text)} /> : null}
              <blockquote><p>{textValue(item.quote)}</p></blockquote>
              <figcaption>{textValue(item.author_name)}{optionalText(item.author_role) ? ` — ${optionalText(item.author_role)}` : ""}</figcaption>
            </figure>
          );
        })}
      </div>
    </SectionShell>
  );
}

function FAQ({ section }: { section: CanonicalSection }): ReactElement {
  const content = recordValue(section.content);
  return (
    <SectionShell section={section} heading={optionalText(content.heading)}>
      <div className="aria-gen-items">
        {arrayValue(content.items).map((value, index) => {
          const item = recordValue(value);
          return <article className="aria-gen-card" key={`${section.section_id}-faq-${index}`}><h3>{textValue(item.question)}</h3><p>{textValue(item.answer)}</p></article>;
        })}
      </div>
    </SectionShell>
  );
}

function ContactSection({ section }: { section: CanonicalSection }): ReactElement {
  const content = recordValue(section.content);
  return (
    <SectionShell section={section} heading={textValue(content.heading)}>
      {optionalText(content.body) ? <p className="aria-gen-body">{optionalText(content.body)}</p> : null}
      <dl className="aria-gen-definition-list">
        {arrayValue(content.methods).map((value, index) => {
          const item = recordValue(value);
          return <div key={`${section.section_id}-contact-${index}`}><dt>{textValue(item.label)}</dt><dd>{textValue(item.value)}</dd></div>;
        })}
      </dl>
    </SectionShell>
  );
}

function PortfolioGrid({ section, context }: { section: CanonicalSection; context: RenderContext }): ReactElement {
  const content = recordValue(section.content);
  return (
    <SectionShell section={section} heading={optionalText(content.heading)}>
      {optionalText(content.body) ? <p className="aria-gen-body">{optionalText(content.body)}</p> : null}
      <div className="aria-gen-items">
        {arrayValue(content.items).map((value, index) => {
          const item = recordValue(value);
          const mediaRef = optionalText(item.portfolio_media_asset_ref);
          return <article className="aria-gen-card" key={`${section.section_id}-portfolio-${index}`}><h3>{textValue(item.title)}</h3>{optionalText(item.summary) ? <p>{optionalText(item.summary)}</p> : null}{mediaRef ? <AssetImage context={context} assetRef={mediaRef} altText={textValue(item.portfolio_media_alt_text)} /> : null}</article>;
        })}
      </div>
    </SectionShell>
  );
}

function Stats({ section }: { section: CanonicalSection }): ReactElement {
  const content = recordValue(section.content);
  return (
    <SectionShell section={section} heading={optionalText(content.heading)}>
      <dl className="aria-gen-stats">{arrayValue(content.items).map((value, index) => {
        const item = recordValue(value);
        return <div className="aria-gen-card" key={`${section.section_id}-stat-${index}`}><dt>{textValue(item.label)}</dt><dd>{textValue(item.value)}</dd></div>;
      })}</dl>
    </SectionShell>
  );
}

function LogoCloud({ section, context }: { section: CanonicalSection; context: RenderContext }): ReactElement {
  const content = recordValue(section.content);
  return (
    <SectionShell section={section} heading={optionalText(content.heading)}>
      <ul className="aria-gen-logo-list">{arrayValue(content.items).map((value, index) => {
        const item = recordValue(value);
        return <li key={`${section.section_id}-logo-${index}`}><AssetImage context={context} assetRef={textValue(item.logo_asset_ref)} altText={textValue(item.logo_alt_text)} /><span className="aria-gen-visually-hidden">{textValue(item.name)}</span></li>;
      })}</ul>
    </SectionShell>
  );
}

function SimpleForm({ section }: { section: CanonicalSection }): ReactElement {
  const content = recordValue(section.content);
  if (content.submission_mode !== "preview_only") {
    throw new GenerationRendererError("GENERATION_RENDERER_INVALID_CANONICAL_AST");
  }
  return (
    <SectionShell section={section} heading={textValue(content.heading)}>
      {optionalText(content.body) ? <p className="aria-gen-body">{optionalText(content.body)}</p> : null}
      <fieldset className="aria-gen-fieldset">
        <legend className="aria-gen-visually-hidden">فرم نمایشی بدون ارسال</legend>
        <div className="aria-gen-fields">
          {arrayValue(content.fields).map((value, index) => {
            const field = recordValue(value);
            const key = textValue(field.key);
            const id = `aria-gen-field-${section.section_id}-${key}`;
            const type = textValue(field.type);
            const common = { id, maxLength: integerValue(field.max_length), required: booleanValue(field.required) };
            return (
              <div className="aria-gen-field" key={`${section.section_id}-field-${index}`}>
                <label htmlFor={id}>{textValue(field.label)}</label>
                {type === "textarea" ? <textarea {...common} /> : <input {...common} type={type} />}
              </div>
            );
          })}
          {optionalText(content.consent_label) ? <label className="aria-gen-consent"><input type="checkbox" />{optionalText(content.consent_label)}</label> : null}
        </div>
        <button className="aria-gen-action" type="button">{textValue(content.submit_label)}</button>
        <p className="aria-gen-preview-note">این فرم فقط برای پیش‌نمایش است و اطلاعاتی ارسال یا ذخیره نمی‌کند.</p>
      </fieldset>
    </SectionShell>
  );
}

const COMPONENT_RENDERERS: Readonly<Record<ComponentType, (section: CanonicalSection, context: RenderContext) => ReactElement>> = {
  Navbar: (section, context) => <Navbar section={section} context={context} />,
  Hero: (section, context) => <Hero section={section} context={context} />,
  Footer: (section, context) => <Footer section={section} context={context} />,
  FeatureGrid: (section, context) => <CardGrid section={section} context={context} kind="feature" />,
  ServiceList: (section, context) => <CardGrid section={section} context={context} kind="service" />,
  AboutSection: (section, context) => <AboutSection section={section} context={context} />,
  CTA: (section) => <CTA section={section} />,
  Testimonial: (section, context) => <Testimonial section={section} context={context} />,
  FAQ: (section) => <FAQ section={section} />,
  ContactSection: (section) => <ContactSection section={section} />,
  PortfolioGrid: (section, context) => <PortfolioGrid section={section} context={context} />,
  Stats: (section) => <Stats section={section} />,
  LogoCloud: (section, context) => <LogoCloud section={section} context={context} />,
  SimpleForm: (section) => <SimpleForm section={section} />
};

function resolveAssets(ast: CanonicalGenerationAst, resolver: AssetResolver): ReadonlyMap<string, ResolvedAsset> {
  const resolved = new Map<string, ResolvedAsset>();
  for (const assetRef of ast.assets) {
    const value = resolver.resolve(assetRef);
    if (!value || value.assetRef !== assetRef || !SAFE_RESOLVED_ASSET_SRC.test(value.src)) {
      throw new GenerationRendererError("GENERATION_RENDERER_ASSET_NOT_AUTHORIZED");
    }
    resolved.set(assetRef, value);
  }
  return resolved;
}

function renderPage(page: CanonicalPage, ast: CanonicalGenerationAst, context: RenderContext): ReactElement {
  const navbars = page.sections.filter((section) => section.component_type === "Navbar");
  const footers = page.sections.filter((section) => section.component_type === "Footer");
  const content = page.sections.filter((section) => section.component_type !== "Navbar" && section.component_type !== "Footer");
  return (
    <article className="aria-gen-page" data-project-type={ast.project_type} data-theme={ast.theme.mode} dir="rtl">
      {navbars.map((section) => <div key={section.section_id}>{COMPONENT_RENDERERS.Navbar(section, context)}</div>)}
      <main className="aria-gen-main">
        <h1 className="aria-gen-visually-hidden">{page.title}</h1>
        {content.map((section) => <div className="aria-gen-component-boundary" key={section.section_id}>{COMPONENT_RENDERERS[section.component_type](section, context)}</div>)}
      </main>
      {footers.map((section) => <div key={section.section_id}>{COMPONENT_RENDERERS.Footer(section, context)}</div>)}
    </article>
  );
}

export function renderCanonicalPage(options: RenderPageOptions): ReactElement {
  assertCanonicalGenerationAst(options.ast);
  const page = options.ast.pages.find((candidate) => candidate.path === options.path);
  if (!page) throw new GenerationRendererError("GENERATION_RENDERER_PAGE_NOT_FOUND");
  return renderPage(page, options.ast, { assets: resolveAssets(options.ast, options.assetResolver) });
}

export function renderCanonicalPageToStaticMarkup(options: RenderPageOptions): string {
  return `<!doctype html>${renderToStaticMarkup(renderCanonicalPage(options))}`;
}
