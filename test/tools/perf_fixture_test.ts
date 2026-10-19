// Fixture/stand-in controls only; no hub or native app is launched.
// Normally run in the repo. --repo ROOT supports reviewing an isolated proposal.
import assert from "node:assert/strict";
import { chmodSync, existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";
import { fixtureEvents, fixtureJSONL, fixtureSha256, historySha256 } from "./perf_fixture";

const args=process.argv.slice(2);
assert(args.length===0 || (args.length===2 && args[0]==="--repo"),"usage: bun test/tools/perf_fixture_test.ts [--repo ROOT]");
const repo=resolve(args[1] ?? join(import.meta.dir,"../.."));
const {FixtureBots}=await import(pathToFileURL(join(repo,"test/tools/perf_guard.ts")).href);
const {standinScript}=await import(pathToFileURL(join(repo,"test/tools/perf_standin.ts")).href);
let checks=0;
function check(name:string,condition:unknown) {assert(condition,name);console.log(`ok ${name}`);checks++;}
const rows=fixtureEvents(),bytes=fixtureJSONL(rows),history=rows.slice(0,-7);
const hash=(value:string)=>new Bun.CryptoHasher("sha256").update(value).digest("hex");
function prerequisites(events:Record<string,unknown>[]) {
  const bots=new FixtureBots(),rooms:any[]=[];
  for(const event of events){bots.apply(event);if(event.$==="RoomSet")rooms.push(event);}
  return {bots,rooms:rooms.filter(room=>room.members.split("\n").some((id:string)=>bots.threads.get(id)))};
}
const before=prerequisites(history),after=prerequisites(rows);
check("fixture generation is deterministic",bytes===fixtureJSONL());
check("reviewed fixture count/bytes/hash match",rows.length===1520 && Buffer.byteLength(bytes)===556794 && hash(bytes)===fixtureSha256);
check("all original history bytes are preserved",history.length===1513 && hash(fixtureJSONL(history))===historySha256);
check("history-only negative control misses normal prerequisites",before.rooms.length===0 && !before.bots.uber);
check("uberbot maps to a fixture thread",Boolean(after.bots.threads.get(after.bots.uber)));
check("room participants map to two local fixture bots",after.rooms.length===1 && after.rooms[0].members.split("\n").length===2 && after.rooms[0].members.split("\n").every((id:string)=>after.bots.threads.get(id)));
check("twelve non-bot history threads remain",rows.filter(event=>event.$==="ThreadCreated" && ![...after.bots.threads.values()].includes(event.id as string)).length===12);
check("persisted events cannot resume a turn or schedule a wake",rows.every(event=>["ProjectCreated","ThreadCreated","MessagePosted","BotSet","RoomSet","UberSet","SettingSet"].includes(event.$ as string)));
check("all fixture providers use the stand-in protocol",rows.filter(event=>event.$==="ThreadCreated").every(event=>event.provider==="claude" && event.worktree===""));
check("restart continuation is disabled",rows.some(event=>event.$==="SettingSet" && event.key==="restart.continue" && event.value==="off"));

const temp=mkdtempSync(join(tmpdir(),"bp-perf-fixture-test-"));
try {
  const env={HOME:temp,PATH:"/usr/bin:/bin"};
  const generator=join(import.meta.dir,"perf_fixture.ts"),output=join(temp,"fixture.jsonl");
  const missing=spawnSync(process.execPath,[generator],{env,encoding:"utf8"});
  check("generator requires an explicit output argument",missing.status!==0 && missing.stderr.includes("OUTPUT.jsonl"));
  const generated=spawnSync(process.execPath,[generator,output],{env,encoding:"utf8"});
  check("standalone generator writes the reviewed bytes and receipt",generated.status===0 && readFileSync(output,"utf8")===bytes && JSON.parse(generated.stdout).sha256===fixtureSha256);
  writeFileSync(output,"retain previous fixture\n");
  const overwritten=spawnSync(process.execPath,[generator,output],{env,encoding:"utf8"});
  check("generator preserves an existing different fixture",overwritten.status!==0 && readFileSync(output,"utf8")==="retain previous fixture\n");
  const fake=join(temp,"fake"),blocks=join(temp,"blocks"),fallback=join(temp,"fallback"),marker=join(temp,"fallback-used"),log=join(temp,"agents.log");
  for(const path of [fake,blocks,fallback])mkdirSync(path);
  writeFileSync(join(fake,"claude"),standinScript);chmodSync(join(fake,"claude"),0o755);
  for(const name of ["claude","codex","grok","muse"]){writeFileSync(join(fallback,name),`#!/bin/sh\nprintf used > '${marker}'\n`);chmodSync(join(fallback,name),0o755);}
  const source=readFileSync(join(repo,"src/core/standin.bend"),"utf8");
  const body=source.split("def Standin.sh() -> String:\n")[1].split("\n\ndef ")[0];
  const shell=[...body.matchAll(/"(?:[^"\\]|\\.)*"/g)].map(match=>JSON.parse(match[0])).join("");
  const isolated={...env,PATH:`${fake}:${blocks}:${fallback}:/usr/bin:/bin`,FAKE_LOG:log};
  const prepared=spawnSync("/bin/sh",["-c",shell,"sh",fake,blocks,"BACKPLANE-STANDIN-MISSING","claude","codex","grok","muse"],{env:isolated,encoding:"utf8"});
  check("production stand-in binding prepares private blocks",prepared.status===0 && prepared.stdout===fake);
  const protocol=spawnSync(join(fake,"claude"),[],{env:isolated,input:"",encoding:"utf8"});
  check("production stand-in starts no turn on empty input",protocol.status===0 && existsSync(log) && !readFileSync(log,"utf8").includes("TURN"));
  const blocked=spawnSync("/bin/sh",["-c","codex"],{env:isolated,encoding:"utf8"});
  check("absent provider cannot fall through to another executable",blocked.status===127 && blocked.stderr.includes("never used") && !existsSync(marker));
} finally {rmSync(temp,{recursive:true,force:true});}
console.log(`${checks} fixture/isolation controls passed`);
