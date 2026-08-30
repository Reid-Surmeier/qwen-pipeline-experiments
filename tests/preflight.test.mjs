import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

test("Qwen refuses a declared reference that is absent from the provider payload", async () => {
  const request = JSON.parse(await readFile("requests/qwen-image-study.json", "utf8"));
  delete request.provider_payload.input_references;
  const directory = await mkdtemp(join(tmpdir(), "qwen-preflight-"));
  const requestPath = join(directory, "request.json");
  await writeFile(requestPath, JSON.stringify(request));

  try {
    const result = spawnSync("node", ["scripts/preflight.mjs", requestPath], {
      encoding: "utf8",
    });
    assert.equal(result.status, 1);
    assert.match(result.stderr, /provider payload requires the exact declared image reference/);
  } finally {
    await rm(directory, { recursive: true });
  }
});
