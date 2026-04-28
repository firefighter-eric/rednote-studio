#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

function usage() {
  console.error(`Usage:
node write_xhs_content.mjs --notes NOTES.json --mapping MAPPING.json --base-dir data/food_notes [--dry-run]

NOTES.json:
  [{"title":"小红书卡片标题","url":"https://www.xiaohongshu.com/user/profile/..."}]

MAPPING.json:
  {"本地目录名":["小红书卡片标题"]}`);
}

function parseArgs(argv) {
  const args = { dryRun: false };
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--dry-run") {
      args.dryRun = true;
    } else if (arg === "--notes" || arg === "--mapping" || arg === "--base-dir") {
      args[arg.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = argv[++i];
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  if (!args.notes || !args.mapping || !args.baseDir) {
    usage();
    process.exit(2);
  }
  return args;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function decodeJsonString(raw) {
  return JSON.parse(`"${raw}"`);
}

function extractDesc(html) {
  const match = html.match(/"desc":"((?:\\.|[^"\\])*)"/);
  return match ? decodeJsonString(match[1]).trim() : "";
}

function normalizeNote(title, desc) {
  let cleanTitle = title;
  const embeddedTitle = desc.match(/(?:^|\n)标题：([^\n]+)/);
  if (embeddedTitle) {
    cleanTitle = embeddedTitle[1].trim();
    desc = desc.replace(/\n?标题：[^\n]+\n?/, "\n").trim();
  }
  return { cleanTitle, desc };
}

async function fetchNote(note) {
  const response = await fetch(note.url, {
    headers: {
      "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari/537.36",
    },
  });
  const html = await response.text();
  const desc = extractDesc(html);
  return {
    ...note,
    status: response.status,
    ok: Boolean(desc),
    ...normalizeNote(note.title, desc),
  };
}

async function main() {
  const args = parseArgs(process.argv);
  const notes = readJson(args.notes);
  const mapping = readJson(args.mapping);
  const byTitle = new Map();

  for (const note of notes) {
    if (!note.title || !note.url) {
      throw new Error("Each note must have title and url");
    }
    const fetched = await fetchNote(note);
    byTitle.set(note.title, fetched);
    console.error(`${fetched.ok ? "ok" : "MISS"} ${fetched.status} ${note.title} -> ${fetched.desc.length}`);
  }

  const written = [];
  const missing = [];

  for (const [dirName, titles] of Object.entries(mapping)) {
    if (!Array.isArray(titles) || titles.length === 0) {
      throw new Error(`Mapping for ${dirName} must be a non-empty title array`);
    }
    const sections = [];
    for (const title of titles) {
      const note = byTitle.get(title);
      if (!note || !note.ok) {
        missing.push(`${dirName}: ${title}`);
        continue;
      }
      const heading = titles.length > 1 ? `## ${note.cleanTitle}` : `# ${note.cleanTitle}`;
      sections.push(`${heading}\n\n${note.desc}`);
    }
    if (!sections.length) continue;

    const markdown = sections.length > 1
      ? `# ${dirName}\n\n${sections.join("\n\n---\n\n")}\n`
      : `${sections[0]}\n`;
    const outDir = path.join(args.baseDir, dirName);
    const outFile = path.join(outDir, "content.md");
    if (!args.dryRun) {
      fs.mkdirSync(outDir, { recursive: true });
      fs.writeFileSync(outFile, markdown, "utf8");
    }
    written.push(outFile);
  }

  console.log(JSON.stringify({ written, missing }, null, 2));
  if (missing.length) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
