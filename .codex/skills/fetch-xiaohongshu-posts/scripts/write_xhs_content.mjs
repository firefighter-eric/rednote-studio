#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

function usage() {
  console.error(`Usage:
node write_xhs_content.mjs --notes NOTES.json --mapping MAPPING.json --base-dir data/food_notes/items [--update-manifest 2026-05-02] [--date-prefix] [--dry-run]

NOTES.json:
  [{"title":"小红书卡片标题","url":"https://www.xiaohongshu.com/user/profile/...","desc":"正文","postedAt":"2026-05-01T12:00:00+08:00","views":1000,"likes":88,"favorites":12,"comments":3,"shares":2}]

MAPPING.json:
  {"本地目录名":["小红书卡片标题"]}`);
}

function parseArgs(argv) {
  const args = { dryRun: false, datePrefix: false };
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--dry-run") {
      args.dryRun = true;
    } else if (arg === "--date-prefix") {
      args.datePrefix = true;
    } else if (arg === "--notes" || arg === "--mapping" || arg === "--base-dir" || arg === "--update-manifest") {
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

function normalizeEpoch(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  const milliseconds = number > 100000000000 ? number : number * 1000;
  const date = new Date(milliseconds);
  if (Number.isNaN(date.getTime())) return null;
  return formatShanghaiTime(date);
}

function formatShanghaiTime(date) {
  const shanghai = new Date(date.getTime() + 8 * 60 * 60 * 1000);
  return `${shanghai.toISOString().slice(0, 19)}+08:00`;
}

function normalizeDateString(value) {
  if (!value) return null;
  const text = String(value).trim();
  const epoch = text.match(/^\d{10,13}$/);
  if (epoch) return normalizeEpoch(text);

  const normalized = text
    .replace(/^(\d{4})[.:/年-](\d{1,2})[.:/月-](\d{1,2})日?/, "$1-$2-$3")
    .replace(/(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2}(?::\d{2})?)/, "$1T$2+08:00");
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return null;
  return formatShanghaiTime(date);
}

function extractPostedAt(html) {
  const patterns = [
    /"time":\s*"?(\d{10,13})"?/,
    /"publishTime":\s*"?(\d{10,13})"?/,
    /"createTime":\s*"?(\d{10,13})"?/,
    /"createdTime":\s*"?(\d{10,13})"?/,
    /"postedAt":\s*"((?:\\.|[^"\\])*)"/,
    /"publishDate":\s*"((?:\\.|[^"\\])*)"/,
    /"datePublished":\s*"((?:\\.|[^"\\])*)"/,
  ];
  for (const pattern of patterns) {
    const match = html.match(pattern);
    if (!match) continue;
    const value = match[1].includes("\\") ? decodeJsonString(match[1]) : match[1];
    const normalized = normalizeDateString(value);
    if (normalized) return normalized;
  }
  return null;
}

function extractLastUpdatedAt(html) {
  const patterns = [
    /"lastUpdateTime":\s*"?(\d{10,13})"?/,
    /"updatedTime":\s*"?(\d{10,13})"?/,
    /"lastUpdatedAt":\s*"((?:\\.|[^"\\])*)"/,
  ];
  for (const pattern of patterns) {
    const match = html.match(pattern);
    if (!match) continue;
    const value = match[1].includes("\\") ? decodeJsonString(match[1]) : match[1];
    const normalized = normalizeDateString(value);
    if (normalized) return normalized;
  }
  return null;
}

function normalizeMetric(value) {
  if (value == null || value === "") return null;
  if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value);
  const text = String(value).trim().replaceAll(",", "");
  const match = text.match(/^([\d.]+)\s*([万wWkK千]?)$/);
  if (!match) return null;
  const number = Number(match[1]);
  if (!Number.isFinite(number)) return null;
  const unit = match[2].toLowerCase();
  const multiplier = unit === "万" || unit === "w" ? 10000 : unit === "k" || unit === "千" ? 1000 : 1;
  return Math.round(number * multiplier);
}

function extractMetric(html, names) {
  for (const name of names) {
    const patterns = [
      new RegExp(`"${name}"\\s*:\\s*"?([0-9.,万wWkK千]+)"?`),
      new RegExp(`"${name}Count"\\s*:\\s*"?([0-9.,万wWkK千]+)"?`),
      new RegExp(`"${name}_count"\\s*:\\s*"?([0-9.,万wWkK千]+)"?`),
    ];
    for (const pattern of patterns) {
      const match = html.match(pattern);
      if (!match) continue;
      const metric = normalizeMetric(match[1]);
      if (metric != null) return metric;
    }
  }
  return null;
}

function extractEngagement(html, note) {
  return {
    views: normalizeMetric(note.views ?? note.viewCount ?? note.viewsCount) ?? extractMetric(html, ["view", "views", "read", "play"]),
    likes: normalizeMetric(note.likes ?? note.likeCount ?? note.likedCount) ?? extractMetric(html, ["like", "likes", "liked"]),
    favorites: normalizeMetric(note.favorites ?? note.collects ?? note.collectCount ?? note.favoriteCount) ?? extractMetric(html, ["collect", "favorite", "favorites", "fav"]),
    comments: normalizeMetric(note.comments ?? note.commentCount) ?? extractMetric(html, ["comment", "comments"]),
    shares: normalizeMetric(note.shares ?? note.shareCount) ?? extractMetric(html, ["share", "shares"]),
  };
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
  let status = "input";
  let html = "";
  if (!note.desc || !note.postedAt || note.likes == null || note.favorites == null) {
    const response = await fetch(note.url, {
      headers: {
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari/537.36",
      },
    });
    status = response.status;
    html = await response.text();
  }
  const desc = String(note.desc ?? "").trim() || extractDesc(html);
  const postedAt = note.postedAt ? normalizeDateString(note.postedAt) : extractPostedAt(html);
  const lastUpdatedAt = note.lastUpdatedAt ? normalizeDateString(note.lastUpdatedAt) : extractLastUpdatedAt(html);
  const engagement = extractEngagement(html, note);
  const noteId = note.noteId ?? note.note_id ?? note.url.match(/\/([0-9a-f]{24})(?:\?|$)/i)?.[1] ?? null;
  return {
    ...note,
    status,
    ok: Boolean(desc),
    postedAt,
    lastUpdatedAt,
    noteId,
    ipLocation: note.ipLocation ?? note.ip_location ?? null,
    engagement,
    ...normalizeNote(note.title, desc),
  };
}

function quoteYaml(value) {
  if (value == null) return "null";
  return `'${String(value).replaceAll("'", "''")}'`;
}

function readExistingMeta(file) {
  if (!fs.existsSync(file)) return {};
  const text = fs.readFileSync(file, "utf8");
  const result = {};
  for (const key of ["title", "content_title", "status", "meta_initialized_at"]) {
    const match = text.match(new RegExp(`^${key}:\\s*(.+)$`, "m"));
    if (!match) continue;
    const value = match[1].trim();
    result[key] = value === "null" ? null : value.replace(/^'|'$/g, "").replaceAll("''", "'");
  }
  return result;
}

function removeTopLevelBlock(lines, key) {
  const start = lines.findIndex((line) => line === `${key}:`);
  if (start === -1) return lines;
  let end = start + 1;
  while (end < lines.length && (lines[end].startsWith(" ") || lines[end].trim() === "")) {
    end += 1;
  }
  return [...lines.slice(0, start), ...lines.slice(end)];
}

function upsertScalar(lines, key, value, afterKey = null) {
  const rendered = `${key}: ${quoteYaml(value)}`;
  const index = lines.findIndex((line) => line.startsWith(`${key}:`));
  if (index !== -1) {
    lines[index] = rendered;
    return lines;
  }
  const afterIndex = afterKey ? lines.findIndex((line) => line.startsWith(`${afterKey}:`)) : -1;
  const insertAt = afterIndex === -1 ? lines.length : afterIndex + 1;
  lines.splice(insertAt, 0, rendered);
  return lines;
}

function buildNewMeta(dirName, notes) {
  const existing = {};
  return [
    "schema_version: 1",
    `title: ${quoteYaml(dirName.replace(/^\d{4}-\d{2}-\d{2}_/, ""))}`,
    "item_date: null",
    `directory_name: ${quoteYaml(dirName)}`,
    `content_title: ${quoteYaml(notes.length === 1 ? notes[0].cleanTitle : existing.content_title)}`,
    "status: 'ready'",
    "assets:",
    "  images:",
    "    - '1.jpg'",
    "    - '2.jpg'",
    "    - '3.jpg'",
    "  content: 'content.md'",
  ];
}

function writeMeta(file, dirName, notes) {
  const existing = readExistingMeta(file);
  const postedNotes = notes.filter((note) => note.postedAt);
  const postedAt = postedNotes.length ? postedNotes.map((note) => note.postedAt).sort()[0] : null;
  const itemDate = postedAt ? postedAt.slice(0, 10) : null;
  const sourceUrl = notes.length === 1 ? notes[0].url : null;
  const sourceTitle = notes.length === 1 ? notes[0].cleanTitle : null;
  const sourceNoteId = notes.length === 1 ? notes[0].noteId : null;
  let lines = fs.existsSync(file)
    ? fs.readFileSync(file, "utf8").split(/\r?\n/).filter((line, index, array) => index < array.length - 1 || line !== "")
    : buildNewMeta(dirName, notes);

  lines = upsertScalar(lines, "title", existing.title || dirName.replace(/^\d{4}-\d{2}-\d{2}_/, ""), "schema_version");
  lines = upsertScalar(lines, "item_date", itemDate, "title");
  lines = upsertScalar(lines, "directory_name", dirName, "item_date");
  lines = upsertScalar(lines, "content_title", notes.length === 1 ? notes[0].cleanTitle : existing.content_title, "directory_name");
  lines = upsertScalar(lines, "status", "ready", "content_title");
  const contentAssetIndex = lines.findIndex((line) => /^\s{2}content:/.test(line));
  if (contentAssetIndex !== -1) {
    lines[contentAssetIndex] = "  content: 'content.md'";
  }
  lines = removeTopLevelBlock(lines, "post_times");
  lines = removeTopLevelBlock(lines, "engagement");
  lines = removeTopLevelBlock(lines, "source");

  const postTimeBlock = [
    "post_times:",
    postedAt ? "  source: 'xiaohongshu'" : "  source: 'unavailable'",
    postedAt
      ? "  note: '这些时间来自小红书帖子发布时间。'"
      : "  note: '没有抓取到小红书发帖时间。'",
    "  notes:",
  ];
  if (postedNotes.length) {
    for (const note of postedNotes) {
      postTimeBlock.push(`    - title: ${quoteYaml(note.cleanTitle)}`);
      postTimeBlock.push(`      url: ${quoteYaml(note.url)}`);
      postTimeBlock.push(`      note_id: ${quoteYaml(note.noteId)}`);
      postTimeBlock.push(`      posted_at: ${quoteYaml(note.postedAt)}`);
      postTimeBlock.push(`      last_updated_at: ${quoteYaml(note.lastUpdatedAt)}`);
      postTimeBlock.push(`      ip_location: ${quoteYaml(note.ipLocation)}`);
    }
  } else {
    postTimeBlock.push("    []");
  }
  const engagementNotes = notes.filter((note) => note.engagement && Object.values(note.engagement).some((value) => value != null));
  const engagementBlock = [
    "engagement:",
    engagementNotes.length ? "  source: 'xiaohongshu_public_note_page'" : "  source: 'unavailable'",
    engagementNotes.length
      ? "  note: '这些数据来自小红书页面或传入的 notes JSON；公开页未提供观看/浏览量时 views 保持 null。'"
      : "  note: '尚未抓取到小红书观看、点赞、收藏数据。'",
  ];
  if (notes.length === 1 && notes[0].engagement) {
    engagementBlock.push(`  views: ${notes[0].engagement.views ?? "null"}`);
    engagementBlock.push(`  likes: ${notes[0].engagement.likes ?? "null"}`);
    engagementBlock.push(`  favorites: ${notes[0].engagement.favorites ?? "null"}`);
    engagementBlock.push(`  comments: ${notes[0].engagement.comments ?? "null"}`);
    engagementBlock.push(`  shares: ${notes[0].engagement.shares ?? "null"}`);
  } else {
    engagementBlock.push("  views: null");
    engagementBlock.push("  likes: null");
    engagementBlock.push("  favorites: null");
    engagementBlock.push("  comments: null");
    engagementBlock.push("  shares: null");
  }
  engagementBlock.push("  notes:");
  if (engagementNotes.length) {
    for (const note of engagementNotes) {
      engagementBlock.push(`    - title: ${quoteYaml(note.cleanTitle)}`);
      engagementBlock.push(`      url: ${quoteYaml(note.url)}`);
      engagementBlock.push(`      note_id: ${quoteYaml(note.noteId)}`);
      engagementBlock.push(`      views: ${note.engagement.views ?? "null"}`);
      engagementBlock.push(`      likes: ${note.engagement.likes ?? "null"}`);
      engagementBlock.push(`      favorites: ${note.engagement.favorites ?? "null"}`);
      engagementBlock.push(`      comments: ${note.engagement.comments ?? "null"}`);
      engagementBlock.push(`      shares: ${note.engagement.shares ?? "null"}`);
    }
  } else {
    engagementBlock.push("    []");
  }
  const sourceBlock = [
    "source:",
    "  platform: 'xiaohongshu'",
    `  url: ${quoteYaml(sourceUrl)}`,
    `  note_id: ${quoteYaml(sourceNoteId)}`,
    `  note_title: ${quoteYaml(sourceTitle)}`,
  ];
  const insertAt = lines.findIndex((line) => line === "tags:");
  if (insertAt === -1) {
    lines.push(...postTimeBlock, ...engagementBlock, ...sourceBlock, "tags: []", "notes:", "  health: null", "  environment: null");
  } else {
    lines.splice(insertAt, 0, ...postTimeBlock, ...engagementBlock, ...sourceBlock);
  }
  if (!lines.some((line) => line.startsWith("meta_initialized_at:"))) {
    lines.push(`meta_initialized_at: ${quoteYaml(existing.meta_initialized_at || new Date().toISOString().slice(0, 10))}`);
  }
  fs.writeFileSync(file, `${lines.join("\n")}\n`, "utf8");
}

function parseTopLevelScalar(text, key) {
  const match = text.match(new RegExp(`^${key}:\\s*(.+)$`, "m"));
  if (!match) return null;
  const value = match[1].trim();
  if (value === "null") return null;
  return value.replace(/^'|'$/g, "").replaceAll("''", "'");
}

function parseNestedScalar(text, block, key) {
  const start = text.match(new RegExp(`^${block}:\\n((?:^[ \\t].*\\n?)*)`, "m"));
  if (!start) return null;
  const match = start[1].match(new RegExp(`^[ \\t]+${key}:\\s*(.+)$`, "m"));
  if (!match) return null;
  const value = match[1].trim();
  if (value === "null") return null;
  const number = Number(value);
  if (Number.isFinite(number) && String(number) === value) return number;
  return value.replace(/^'|'$/g, "").replaceAll("''", "'");
}

function parsePostedAt(text) {
  const match = text.match(/^[ \t]+posted_at:\s*(.+)$/m);
  if (!match) return null;
  const value = match[1].trim();
  if (value === "null") return null;
  return value.replace(/^'|'$/g, "").replaceAll("''", "'");
}

function parseFirstCapturedAt(text) {
  const match = text.match(/^[ \t]+captured_at:\s*(.+)$/m);
  if (!match) return null;
  const value = match[1].trim();
  if (value === "null") return null;
  return value.replace(/^'|'$/g, "").replaceAll("''", "'");
}

function countImages(dir) {
  if (!fs.existsSync(dir)) return 0;
  return fs.readdirSync(dir).filter((name) => /^([1-9]\d*)\.jpg$/i.test(name)).length;
}

function yamlScalar(value) {
  if (value == null) return "null";
  if (typeof value === "boolean" || typeof value === "number") return String(value);
  return quoteYaml(value);
}

function writeManifest(baseDir, snapshotDate) {
  const dirs = fs.readdirSync(baseDir, { withFileTypes: true }).filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort();
  const summary = {
    total_items: 0,
    ready_items: 0,
    needs_content_items: 0,
    complete_assets: 0,
    image_only_items: 0,
    with_xiaohongshu_post_time: 0,
    without_xiaohongshu_post_time: 0,
    with_xiaohongshu_engagement: 0,
    without_xiaohongshu_engagement: 0,
    with_raw_exif_capture_time: 0,
  };
  const items = [];
  for (const dirName of dirs) {
    const dir = path.join(baseDir, dirName);
    const metaFile = path.join(dir, "meta.yaml");
    const text = fs.existsSync(metaFile) ? fs.readFileSync(metaFile, "utf8") : "";
    const imageCount = countImages(dir);
    const hasContent = fs.existsSync(path.join(dir, "content.md"));
    const postSource = parseNestedScalar(text, "post_times", "source") ?? "unavailable";
    const engagementSource = parseNestedScalar(text, "engagement", "source") ?? "unavailable";
    const postedAt = parsePostedAt(text);
    const firstCapturedAt = parseFirstCapturedAt(text);
    const item = {
      dir: dirName,
      title: parseTopLevelScalar(text, "title"),
      item_date: parseTopLevelScalar(text, "item_date"),
      status: parseTopLevelScalar(text, "status"),
      content_title: parseTopLevelScalar(text, "content_title"),
      images: imageCount,
      has_content: hasContent,
      has_meta: fs.existsSync(metaFile),
      post_times: { source: postSource, posted_at: postedAt },
      engagement: {
        source: engagementSource,
        views: parseNestedScalar(text, "engagement", "views"),
        likes: parseNestedScalar(text, "engagement", "likes"),
        favorites: parseNestedScalar(text, "engagement", "favorites"),
        comments: parseNestedScalar(text, "engagement", "comments"),
        shares: parseNestedScalar(text, "engagement", "shares"),
      },
      capture_times: {
        source: parseNestedScalar(text, "capture_times", "source") ?? "unavailable",
        first_captured_at: firstCapturedAt,
      },
    };
    items.push(item);
    summary.total_items += 1;
    if (item.status === "ready") summary.ready_items += 1;
    if (item.status === "needs_content") summary.needs_content_items += 1;
    if (imageCount === 3 && hasContent && fs.existsSync(metaFile)) summary.complete_assets += 1;
    if (imageCount === 3 && !hasContent && fs.existsSync(metaFile)) summary.image_only_items += 1;
    if (postedAt) summary.with_xiaohongshu_post_time += 1;
    else summary.without_xiaohongshu_post_time += 1;
    if (engagementSource !== "unavailable") summary.with_xiaohongshu_engagement += 1;
    else summary.without_xiaohongshu_engagement += 1;
    if (firstCapturedAt) summary.with_raw_exif_capture_time += 1;
  }

  const lines = [
    "schema_version: 1",
    `snapshot_date: ${quoteYaml(snapshotDate)}`,
    `snapshot_label: ${quoteYaml(`${snapshotDate} food_notes 状态`)}`,
    `base_dir: ${quoteYaml(path.relative(process.cwd(), baseDir) || baseDir)}`,
    "summary:",
  ];
  for (const [key, value] of Object.entries(summary)) lines.push(`  ${key}: ${value}`);
  lines.push(
    "time_policy:",
    "  directory_date_source: 'xiaohongshu_post_time_only'",
    "  note: 'item_date 只记录小红书帖子发布时间；raw EXIF 和文件系统时间只作辅助记录，不作为目录日期。'",
    "engagement_policy:",
    "  source: 'xiaohongshu_public_note_page'",
    "  fields: ['views', 'likes', 'favorites', 'comments', 'shares']",
    "  note: '点赞、收藏、评论、分享来自小红书公开笔记详情页；公开页未提供观看/浏览量时 views 保持 null。'",
    "items:",
  );
  for (const item of items) {
    lines.push(
      `  - dir: ${yamlScalar(item.dir)}`,
      `    title: ${yamlScalar(item.title)}`,
      `    item_date: ${yamlScalar(item.item_date)}`,
      `    status: ${yamlScalar(item.status)}`,
      `    content_title: ${yamlScalar(item.content_title)}`,
      `    images: ${item.images}`,
      `    has_content: ${item.has_content}`,
      `    has_meta: ${item.has_meta}`,
      "    post_times:",
      `      source: ${yamlScalar(item.post_times.source)}`,
      `      posted_at: ${yamlScalar(item.post_times.posted_at)}`,
      "    engagement:",
      `      source: ${yamlScalar(item.engagement.source)}`,
      `      views: ${yamlScalar(item.engagement.views)}`,
      `      likes: ${yamlScalar(item.engagement.likes)}`,
      `      favorites: ${yamlScalar(item.engagement.favorites)}`,
      `      comments: ${yamlScalar(item.engagement.comments)}`,
      `      shares: ${yamlScalar(item.engagement.shares)}`,
      "    capture_times:",
      `      source: ${yamlScalar(item.capture_times.source)}`,
      `      first_captured_at: ${yamlScalar(item.capture_times.first_captured_at)}`,
    );
  }
  const manifestPath = path.join(path.dirname(baseDir), `manifest_${snapshotDate}.yaml`);
  fs.writeFileSync(manifestPath, `${lines.join("\n")}\n`, "utf8");
  return { manifestPath, summary };
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

    const firstPostedAt = titles
      .map((title) => byTitle.get(title))
      .filter((note) => note?.postedAt)
      .map((note) => note.postedAt)
      .sort()[0];
    const targetDirName = args.datePrefix && firstPostedAt && !/^\d{4}-\d{2}-\d{2}_/.test(dirName)
      ? `${firstPostedAt.slice(0, 10)}_${dirName}`
      : dirName;
    const markdown = sections.length > 1
      ? `# ${dirName}\n\n${sections.join("\n\n---\n\n")}\n`
      : `${sections[0]}\n`;
    const outDir = path.join(args.baseDir, targetDirName);
    const outFile = path.join(outDir, "content.md");
    if (!args.dryRun) {
      fs.mkdirSync(outDir, { recursive: true });
      fs.writeFileSync(outFile, markdown, "utf8");
      writeMeta(path.join(outDir, "meta.yaml"), targetDirName, titles.map((title) => byTitle.get(title)).filter(Boolean));
    }
    written.push(outFile);
  }

  const result = { written, missing };
  if (args.updateManifest && !args.dryRun) {
    result.manifest = writeManifest(path.resolve(args.baseDir), args.updateManifest);
  }
  console.log(JSON.stringify(result, null, 2));
  if (missing.length) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
