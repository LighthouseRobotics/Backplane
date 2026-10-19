// Requires an already-built production shared-client bridge. No app/hub runs.
// bun test/tools/perf_fixture_codec_test.ts mobile/build/assets/bridge.js
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fixtureEvents } from "./perf_fixture";
const [bridge,...extra]=process.argv.slice(2);
if(!bridge || extra.length)throw new Error("usage: bun test/tools/perf_fixture_codec_test.ts BRIDGE.js");
(0,eval)(readFileSync(bridge,"utf8"));
const B=(globalThis as any).Backplane;
assert(B,"production Backplane bridge export missing");
function cbor(value:any):string {
  const out:number[]=[];
  function head(major:number,n:number){const tag=major<<5;if(n<24)out.push(tag|n);else if(n<256)out.push(tag|24,n);else if(n<65536)out.push(tag|25,n>>8,n&255);else out.push(tag|26,(n>>>24)&255,(n>>>16)&255,(n>>>8)&255,n&255);}
  function item(v:any){
    if(v===null)out.push(0xf6);else if(typeof v==="boolean")out.push(v?0xf5:0xf4);
    else if(typeof v==="number"){assert(Number.isInteger(v)&&v>=0);head(0,v);}
    else if(typeof v==="string"){const bytes=Buffer.from(v);head(3,bytes.length);for(const b of bytes)out.push(b);}
    else if(Array.isArray(v)){head(4,v.length);for(const entry of v)item(entry);}
    else{const entries=Object.entries(v);head(5,entries.length);for(const [key,entry]of entries){item(key);item(entry);}}
  }
  item(value);return Buffer.from(out).toString("base64");
}
const added=fixtureEvents().slice(-7);
function decoded(events:any[]){B.start("fixture-codec","{}");B.hubs(["fixture"]);B.recv("fixture",cbor({t:"log",since:0,head:events.length,items:events}),false,false);return JSON.parse(B.save());}
const state=decoded(added),bot=(node:any)=>typeof node?.$==="string"&&node.$.endsWith("/bot.Bot");
assert(state.nodes.filter(bot).length===2 && state.nodes.some((node:any)=>bot(node)&&node.id==="fixture-bot-0") && state.nodes.some((node:any)=>bot(node)&&node.thread==="fixture-bot-thread-1"));
console.log("ok production codec replays both BotSet events with correct thread identity");
assert(JSON.stringify(state).includes("fixture-review-room")&&JSON.stringify(state).includes("fixture-uber-identity"));
console.log("ok production codec retains room and uberbot identity");
const unknown=decoded(added.map(event=>event.$==="BotSet"?{...event,$:"UnknownFixtureEvent"}:event));
assert(unknown.nodes.filter(bot).length===0);
console.log("ok production codec rejects unknown bot-event negative control");
console.log("3 production codec controls passed");
