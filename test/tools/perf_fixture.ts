// Generated native before/after fixture. No user history or live providers.
// The output argument is required; importing this module performs no IO.
import { existsSync, readFileSync, writeFileSync } from "node:fs";

export const fixtureSha256 = "ac5f4374d7946569b420d7b2ca2d5890c99d54d323a819a6d66beaf2d824b543";
export const historySha256 = "242a722701dfca4c8b7d763575e3c8e6260eaa70a001abb52bef63a2fb9c098b";

export function fixtureEvents(): Record<string, unknown>[] {
  const events: Record<string, unknown>[] = [{$:"ProjectCreated",id:"fixture-project",title:"Synthetic hardware review",root:"/tmp/native-fixture-project",at:1}];
  for(let t=0;t<12;t++) {
    const id=`fixture-thread-${t}`;
    events.push({$:"ThreadCreated",id,project:"fixture-project",title:`Synthetic board review ${String(t).padStart(2,"0")}`,env:"local",branch:"",worktree:"",provider:"claude",model:"",at:2+t});
    for(let m=0;m<180-t*10;m++) {
      let text=`Message ${String(m).padStart(3,"0")}: regulator U3 enable through R12 to VBAT; inspect layout branch ${t}.\n\n`;
      text+="The next check compares routing, top and bottom assembly labels, and connector pin 1. ";
      if(t%3===1)text+="日本語の基板検査、電源と信号。 ";
      if(t%3===2)text+="Café α→β and 5 µF capacitor. ";
      text+="\n\n- Confirm clearance\n- Rebuild DRC\n- Save review notes";
      events.push({$:"MessagePosted",thread:id,msg:`fixture-message-${t}-${m}`,role:m%2?"assistant":"user",text,at:1000+t*200+m});
    }
  }
  // Normal mode selects the uberbot and posts to a room. An otherwise valid
  // history-only fixture cannot meet those workload guards.
  for(const [index,name] of ["Fixture Steward","Fixture Inspector"].entries()) {
    const thread=`fixture-bot-thread-${index}`,id=`fixture-bot-${index}`;
    events.push({$:"ThreadCreated",id:thread,project:"",title:name,env:"local",branch:"",worktree:"",provider:"claude",model:"",at:4000+index*2});
    events.push({$:"BotSet",id,name,thread,look:index,persona:"",at:4001+index*2});
  }
  events.push({$:"UberSet",bot:"fixture-bot-0",uid:"fixture-uber-identity",at:4010});
  events.push({$:"RoomSet",id:"fixture-review-room",name:"Synthetic board review",members:"fixture-bot-0\nfixture-bot-1",at:4011});
  events.push({$:"SettingSet",key:"restart.continue",value:"off",at:4012});
  return events;
}

export function fixtureJSONL(events=fixtureEvents()): string {
  return events.map(event=>JSON.stringify(event)).join("\n")+"\n";
}

if(import.meta.main) {
  const [output,...extra]=process.argv.slice(2);
  if(!output || extra.length) throw new Error("usage: bun test/tools/perf_fixture.ts OUTPUT.jsonl");
  const events=fixtureEvents(),bytes=fixtureJSONL(events);
  const sha256=new Bun.CryptoHasher("sha256").update(bytes).digest("hex");
  if(sha256!==fixtureSha256)throw new Error("generated fixture bytes differ from the reviewed fixture");
  if(existsSync(output) && readFileSync(output,"utf8")!==bytes)throw new Error("refusing to replace a different existing fixture");
  writeFileSync(output,bytes);
  console.log(JSON.stringify({events:events.length,bytes:Buffer.byteLength(bytes),sha256}));
}
