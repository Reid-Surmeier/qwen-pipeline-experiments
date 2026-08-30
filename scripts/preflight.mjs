#!/usr/bin/env node

import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const requestPath = process.argv[2];
if (!requestPath) {
  console.error("usage: node scripts/preflight.mjs <request.json>");
  process.exit(2);
}

const request = JSON.parse(await readFile(resolve(requestPath), "utf8"));
const failures = [];

function inspectVideo(path) {
  const result = spawnSync(
    "ffprobe",
    [
      "-v",
      "error",
      "-select_streams",
      "v:0",
      "-show_entries",
      "stream=width,height",
      "-of",
      "json",
      resolve(path),
    ],
    { encoding: "utf8" },
  );
  if (result.error || result.status !== 0) return null;
  try {
    const stream = JSON.parse(result.stdout).streams?.[0];
    if (!Number.isInteger(stream?.width) || !Number.isInteger(stream?.height)) return null;
    return { width: stream.width, height: stream.height };
  } catch {
    return null;
  }
}

if (request.provider !== "openrouter") failures.push("paid provider must be openrouter");
if (request.requested_count !== 1) failures.push("qualification requests exactly one output");
if (Number(request.estimated_cost_usd) >= 5) failures.push("estimated cost exceeds the authorized cap");

for (const reference of request.reference_inputs ?? []) {
  if (!reference.path || !reference.sha256) {
    failures.push("every reference needs a path and sha256");
    continue;
  }
  try {
    const bytes = await readFile(resolve(reference.path));
    const digest = createHash("sha256").update(bytes).digest("hex");
    if (digest !== reference.sha256) failures.push(`reference hash mismatch: ${reference.path}`);
  } catch {
    failures.push(`reference does not exist: ${reference.path}`);
  }
}

if (request.mode === "seedance-video-study") {
  const videos = (request.reference_inputs ?? []).filter((item) => item.kind === "video");
  if (videos.length !== 1) failures.push("seedance requires exactly one hash-locked video reference");
  if (videos.length === 1) {
    const declaredWidth = videos[0].media?.width;
    const declaredHeight = videos[0].media?.height;
    const inspected = inspectVideo(videos[0].path);
    if (!Number.isInteger(declaredWidth) || !Number.isInteger(declaredHeight)) {
      failures.push("seedance reference video needs inspected integer width and height");
    }
    if (!inspected) {
      failures.push("seedance reference video could not be inspected with ffprobe");
    } else if (declaredWidth !== inspected.width || declaredHeight !== inspected.height) {
      failures.push(
        `declared dimensions do not match inspected video: declared ${declaredWidth}x${declaredHeight}, ` +
          `inspected ${inspected.width}x${inspected.height}`,
      );
    }
    if (
      inspected &&
      request.model === "bytedance/seedance-2.0-mini" &&
      inspected.width * inspected.height < 407_696
    ) {
      failures.push(
        `seedance reference video needs at least 407696 pixels for Mini r2v; got ${inspected.width * inspected.height}`,
      );
    }
  }
  const payloadVideos = request.provider_payload?.input_references?.filter(
    (item) => item.type === "video_url" && item.video_url?.url,
  ) ?? [];
  if (payloadVideos.length !== 1) failures.push("provider payload requires exactly one video_url");
  if (videos.length === 1 && payloadVideos.length === 1 && videos[0].url !== payloadVideos[0].video_url.url) {
    failures.push("declared video reference does not match the provider payload");
  }
}

if (request.mode === "qwen-image-study") {
  if (!request.assembly?.required) failures.push("authoritative pixels require deterministic Assembly");
  if (!request.assembly?.region) failures.push("Assembly requires an explicit edit region");
  const images = (request.reference_inputs ?? []).filter((item) => item.kind === "image");
  const payloadImages = request.provider_payload?.input_references?.filter(
    (item) => item.type === "image_url" && item.image_url?.url,
  ) ?? [];
  if (
    images.length !== 1 ||
    payloadImages.length !== 1 ||
    images[0].url !== payloadImages[0].image_url.url
  ) {
    failures.push("provider payload requires the exact declared image reference");
  }
}

if (failures.length) {
  console.error(JSON.stringify({ status: "refused", safe_to_spend: false, failures }, null, 2));
  process.exit(1);
}

const requestSha256 = createHash("sha256")
  .update(JSON.stringify(request))
  .digest("hex");
console.log(JSON.stringify({ status: "ready", safe_to_spend: true, request_sha256: requestSha256 }, null, 2));
