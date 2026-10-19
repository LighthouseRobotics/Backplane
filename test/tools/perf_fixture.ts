// Deterministic generated fixture for native before/after comparisons.
// No copied user events, credentials, repositories, or live providers.
import { writeFileSync } from "node:fs";
const output = process.argv[2];
if (!output) throw new Error("usage: bun test/tools/perf_fixture.ts OUTPUT.jsonl");
const events: object[] = [{ $: "ProjectCreated", id: "fixture-project", title: "Synthetic hardware review", root: "/tmp/native-fixture-project", at: 1 }];
for (let t=0;t<12;t++) {
  const id = `fixture-thread-${t}`;
  events.push({ $: "ThreadCreated", id, project: "fixture-project", title: `Synthetic board review ${String(t).padStart(2,"0")}`, env: "local", branch: "", worktree: "", provider: "claude", model: "", at: 2+t });
  for (let m=0;m<180-t*10;m++) {
    let text = `Message ${String(m).padStart(3,"0")}: regulator U3 enable through R12 to VBAT; inspect layout branch ${t}.\n\n`;
    text += "The next check compares routing, top and bottom assembly labels, and connector pin 1. ";
    if (t%3===1) text += "日本語の基板検査、電源と信号。 ";
    if (t%3===2) text += "Café α→β and 5 µF capacitor. ";
    text += "\n\n- Confirm clearance\n- Rebuild DRC\n- Save review notes";
    events.push({ $: "MessagePosted", thread: id, msg: `fixture-message-${t}-${m}`, role: m%2 ? "assistant" : "user", text, at:1000+t*200+m });
  }
}
const bytes = events.map(e => JSON.stringify(e)).join("\n")+"\n";
writeFileSync(output,bytes);
console.log(JSON.stringify({events:events.length,bytes:Buffer.byteLength(bytes),sha256:new Bun.CryptoHasher("sha256").update(bytes).digest("hex")}));
