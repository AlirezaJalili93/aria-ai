import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const root = path.resolve(process.cwd(), "evals/gap-detection/gap_detection_eval_v1");
const fixtureRoot = path.join(root, "fixtures");

const types = [
  "missing_information",
  "ambiguity",
  "conflict",
  "unsupported_assumption",
  "decision_required",
  "scope_risk"
];
const projects = ["landing", "corporate", "portfolio"];
const typeText = {
  missing_information: "مسیر تماس نهایی برای دریافت درخواست مشتری مشخص نشده است.",
  ambiguity: "مشخص نیست اولویت اصلی صفحه معرفی خدمات است یا دریافت سرنخ فروش.",
  conflict: "در یک بخش فرم تماس ضروری اعلام شده و در بخش دیگر فرم تماس حذف شده است.",
  unsupported_assumption: "فرض شده است پرداخت آنلاین لازم است، اما در ورودی مشتری تأییدی برای آن وجود ندارد.",
  decision_required: "درباره انتخاب بین فرم کوتاه و رزرو نوبت هنوز تصمیمی ثبت نشده است.",
  scope_risk: "محدوده پروژه هم‌زمان شامل وب‌سایت، اپلیکیشن موبایل و پنل مدیریتی شده است."
};
const severityFor = (type, index) => {
  if (type === "missing_information" || type === "conflict" || type === "unsupported_assumption") return "critical";
  return index % 2 === 0 ? "high" : "medium";
};
const ruleFor = (type, severity) => {
  if (severity !== "critical") return null;
  if (type === "missing_information") return "CGR-001";
  if (type === "conflict") return "CGR-002";
  if (type === "unsupported_assumption") return "CGR-003";
  return null;
};

function sourceRef(id) {
  return { source_id: `${id}_src`, source_version_id: `${id}_src_v1`, start_offset: 0, end_offset: 24 };
}

function buildFixture(index) {
  const fixtureId = `fa_gap_${String(index).padStart(3, "0")}`;
  const projectType = projects[(index - 1) % projects.length];
  const isNoGap = index > 15;
  const type = types[(index - 1) % types.length];
  const ref = sourceRef(fixtureId);
  const requirementIds = type === "conflict" ? [`${fixtureId}_req_a`, `${fixtureId}_req_b`] : [];
  const contextItems = [
    {
      context_item_id: `${fixtureId}_ctx_1`,
      item_type: type === "unsupported_assumption" ? "assumption" : "fact",
      content: isNoGap ? "مخاطب و اقدام اصلی صفحه به‌صورت روشن ثبت شده است." : typeText[type],
      source_refs: [ref],
      status: type === "unsupported_assumption" ? "proposed" : "confirmed"
    }
  ];
  const requirements = requirementIds.map((id, requirementIndex) => ({
    requirement_id: id,
    status: requirementIndex === 0 ? "confirmed" : "draft",
    priority: "must"
  }));
  const gaps = isNoGap ? [] : [{
    gold_gap_id: `${fixtureId}_gold_1`,
    gap_type: type,
    severity: severityFor(type, index),
    source_refs_expectation: type === "missing_information" ? "empty" : "required",
    source_refs: type === "missing_information" ? [] : [ref],
    affected_requirement_ids: requirementIds,
    critical_for_scope: severityFor(type, index) === "critical",
    critical_rule_id: ruleFor(type, severityFor(type, index)),
    semantic_group_id: `${fixtureId}_group_1`
  }];
  const candidates = gaps.map((gap) => ({
    candidate_id: `${fixtureId}_candidate_1`,
    gold_gap_id: gap.gold_gap_id,
    semantically_unsupported: false,
    critical_for_scope: gap.critical_for_scope,
    source_refs_expectation: gap.source_refs_expectation
  }));
  return {
    fixture_id: fixtureId,
    eval_set_id: "gap_detection_eval_v1",
    language: "fa",
    project_type: projectType,
    input: {
      context_version: 1,
      source_versions: [{ source_id: ref.source_id, source_version_id: ref.source_version_id, canonical_length: 64 }],
      context_items: contextItems,
      requirements
    },
    expected_output: { no_gap: isNoGap, gaps },
    evaluation_annotations: {
      deterministic_output_candidate_ids: candidates.map((candidate) => candidate.candidate_id),
      candidate_annotations: candidates,
      semantic_duplicate_groups: []
    },
    metadata: {
      synthetic: true,
      segment: isNoGap ? "clear" : ["incomplete", "ambiguous", "contradictory", "unsupported", "mixed", "scope_risk"][index % 6],
      difficulty: index % 3 === 0 ? "hard" : index % 2 === 0 ? "intermediate" : "basic",
      phenomena: isNoGap ? ["no_gap"] : [type, gaps[0].critical_for_scope ? "critical" : "non_critical"],
      fixture_version: "1"
    }
  };
}

await mkdir(fixtureRoot, { recursive: true });
const fixtures = Array.from({ length: 20 }, (_, index) => buildFixture(index + 1));
for (const fixture of fixtures) {
  await writeFile(path.join(fixtureRoot, `${fixture.fixture_id}.json`), `${JSON.stringify(fixture, null, 2)}\n`, "utf8");
}
await writeFile(path.join(root, "manifest.json"), `${JSON.stringify({
  eval_set_id: "gap_detection_eval_v1",
  version: "1",
  fixture_schema_version: "1",
  report_schema_version: "1",
  metric_version: "1",
  threshold_version: "1",
  human_review_rubric_version: "1",
  expected_fixture_count: 20,
  fixture_ids: fixtures.map((fixture) => fixture.fixture_id),
  gap_types: types,
  project_types: projects,
  critical_rule_pack_version: "critical_gap_rule_pack_v1",
  provider_boundary: {
    contract_provider: "fake_deterministic",
    model_quality_provider: "real_provider_deferred",
    real_provider_selection: "G02/G03_deferred"
  },
  immutability: "gold_change_requires_new_eval_set_version"
}, null, 2)}\n`, "utf8");
