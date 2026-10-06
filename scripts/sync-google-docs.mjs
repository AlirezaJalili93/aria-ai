import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const defaultFolderId = process.env.GOOGLE_DRIVE_FOLDER_ID || "1ciPeuNyLNQhA_v4Le15S33PKdLCuz1P1";
const apiKey = process.env.GOOGLE_DRIVE_API_KEY;

console.log(`[Google Docs Sync] Target Folder ID: ${defaultFolderId}`);
const currentDate = new Date().toISOString().split("T")[0];

async function syncDoc(docId, targetRelativePath, title) {
  const exportUrl = `https://docs.google.com/document/d/${docId}/export?format=txt`;
  console.log(`[Google Docs Sync] Fetching "${title}" (${docId})...`);

  try {
    const response = await fetch(exportUrl);
    if (!response.ok) {
      console.warn(`[Google Docs Sync] Could not export doc ${docId} directly (${response.status} ${response.statusText}). Auth or API key may be required.`);
      return false;
    }

    const rawText = await response.text();
    const header = `# ${title}\n\n- وضعیت منبع: Mirror from Google Drive\n- منبع حاکم: https://docs.google.com/document/d/${docId}/edit\n- تاریخ همگام‌سازی: ${currentDate}\n\n`;
    const finalContent = header + rawText;

    const fullPath = path.join(root, targetRelativePath);
    await mkdir(path.dirname(fullPath), { recursive: true });
    await writeFile(fullPath, finalContent, "utf8");
    console.log(`[Google Docs Sync] Successfully synced "${title}" to ${targetRelativePath}`);
    return true;
  } catch (error) {
    console.error(`[Google Docs Sync] Error syncing doc ${docId}:`, error.message);
    return false;
  }
}

async function fetchFolderFilesWithApiKey(folderId, key) {
  const url = `https://www.googleapis.com/drive/v3/files?q='${folderId}'+in+parents&key=${key}&fields=files(id,name,mimeType)`;
  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.error(`[Google Docs Sync] Drive API returned status ${res.status}`);
      return [];
    }
    const data = await res.json();
    return data.files || [];
  } catch (err) {
    console.error(`[Google Docs Sync] Drive API request failed:`, err.message);
    return [];
  }
}

async function main() {
  if (apiKey) {
    console.log(`[Google Docs Sync] Using GOOGLE_DRIVE_API_KEY to list folder files...`);
    const files = await fetchFolderFilesWithApiKey(defaultFolderId, apiKey);
    console.log(`[Google Docs Sync] Found ${files.length} files in folder.`);
    for (const file of files) {
      if (file.mimeType === "application/vnd.google-apps.document") {
        const targetPath = `docs/product/${file.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.md`;
        await syncDoc(file.id, targetPath, file.name);
      }
    }
  } else {
    console.log(`[Google Docs Sync] No GOOGLE_DRIVE_API_KEY provided.`);
    console.log(`[Google Docs Sync] Attempting fallback sync for known PRD document...`);
    // Known PRD ID from docs/product/product-brief.md
    const prdDocId = "1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg";
    const synced = await syncDoc(prdDocId, "docs/product/product-brief.md", "Product Brief — Aria AI MVP v1.0");
    if (!synced) {
      console.log(`\n============================================================`);
      console.log(`[Notice] To sync private or non-public Google Docs automatically:`);
      console.log(`1. Provide GOOGLE_DRIVE_API_KEY or GOOGLE_SERVICE_ACCOUNT_KEY in process.env`);
      console.log(`2. Or paste/export your Google Docs content manually into docs/`);
      console.log(`============================================================\n`);
    }
  }
}

main().catch((err) => {
  console.error("[Google Docs Sync] Execution error:", err);
  process.exitCode = 1;
});
