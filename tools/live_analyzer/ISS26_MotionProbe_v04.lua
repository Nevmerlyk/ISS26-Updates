-- ISS26 Motion Probe v0.4 — read-only CPU movement command logger
-- ISS Pro Evolution 2 Europe (SLES03321), clean disc, PCSX-Redux.
-- Run after kickoff in Debug > Lua Console:
-- dofile(os.getenv("USERPROFILE") .. "/ISS26/ISS26_MotionProbe_v04.lua")
-- Commands: ISS26Motion.status(), ISS26Motion.mark("event"), ISS26Motion.stop()
-- No writes to PS1 RAM, no modifications to game image or memory card.
--
-- Evidence: function 0x800271C4 reads object's +0x33A and +0x330,
-- calls 0x8001D0A0 and 0x8001CF0C to calculate X/Y step,
-- then updates source X/Y (+2/+6). We watch writes to those inputs.
-- Field names "magnitude", "heading" are provisional hypotheses.

local BASE, STRIDE = 0x7627C, 0x38C
local MAX_EVENTS, FLUSH_EVERY = 25000, 250
if _G.ISS26Motion and type(_G.ISS26Motion.stop) == "function" then
  _G.ISS26Motion.stop()
end

local folder = (os.getenv("USERPROFILE") or ".") .. "\\ISS26\\"
local prefix = folder .. "ISS26_MotionProbe_" .. os.date("%Y%m%d_%H%M%S")
local function makeFile(path)
  local f,err = io.open(path,"wb")
  assert(f,"Cannot create "..path..": "..tostring(err))
  return f
end
local writes=makeFile(prefix.."_command_writers.csv")
local samples=makeFile(prefix.."_movement_samples.csv")
local markers=makeFile(prefix.."_markers.csv")
writes:write("vsync,player,field,address,width,oldfield,pc,opcode,ra,sp,a0,a1,a2,a3,s0,v0,v1,t0,t1\n")
samples:write("vsync,Ball_X,Ball_Y,Kahn_X,Kahn_Y,Kahn_magnitude,Kahn_heading,Kahn_angle2,Barthez_X,Barthez_Y,Barthez_magnitude,Barthez_heading,Barthez_angle2\n")
markers:write("vsync,label\n")
local nframe, events, rows = 0, 0, 0
local active, capped = true, false
local handles, counts = {}, {}

local function u8(p,off) return tonumber(p[off]) end
local function u16(p,off) return u8(p,off)+256*u8(p,off+1) end
local function s16(p,off) local v=u16(p,off);return v>=32768 and v-65536 or v end
local function u32(p,off)
 return u16(p,off)+65536*u16(p,off+2)
end
local function hx(v)
 return string.format("%08X",v)
end
local def = {
  {"Kahn","magnitude",1,0x330,4},
  {"Kahn","heading",1,0x33A,1},
  {"Kahn","angle2",1,0x33D,1},
  {"Barthez","magnitude",12,0x330,4},
  {"Barthez","heading",12,0x33A,1},
  {"Barthez","angle2",12,0x33D,1}
}

local function posSample()
 local ptr=PCSX.getMemPtr()
 local function fields(i)
  local b=BASE+STRIDE*i
  return {s16(ptr,b+2),s16(ptr,b+6),u32(ptr,b+0x330),u8(ptr,b+0x33A),u8(ptr,b+0x33D)}
 end
 local ball=fields(0)
 local kahn=fields(1)
 local barthez=fields(12)
 local row={nframe,ball[1],ball[2],
    kahn[1],kahn[2],kahn[3],kahn[4],kahn[5],
    barthez[1],barthez[2],barthez[3],barthez[4],barthez[5]}
 samples:write(table.concat(row,",").."\n")
 rows=rows+1
end

_G.ISS26Motion={}
ISS26Motion.vsync=PCSX.Events.createEventListener("GPU::Vsync",function()
 if not active then return end
 nframe=nframe+1
 posSample()
 if nframe%300==0 then
  writes:flush();samples:flush();markers:flush()
 end
end)

for i,d in ipairs(def) do
 local player,field,index,offset,width=d[1],d[2],d[3],d[4],d[5]
 local address=0x80000000+BASE+STRIDE*index+offset
 local label=player.."_"..field
 counts[label]=0
 handles[i]=PCSX.addBreakpoint(address,"Write",width,"ISS26 motion "..label,function(a,w,cause)
  if not active then return end
  if events>=MAX_EVENTS then
    if not capped then
      capped=true
      print("ISS26 Motion Probe capped at "..MAX_EVENTS.." events. Stop and send logs.")
      writes:flush()
    end
    return
  end
  local ptr=PCSX.getMemPtr()
  local reg=PCSX.getRegisters()
  local g=reg.GPR.n
  local pc=tonumber(reg.pc)
  local off=(tonumber(a)%0x200000)
  local value=(width==4) and u32(ptr,off) or u8(ptr,off)
  local instr=u32(ptr,pc%0x200000)
  events=events+1
  counts[label]=counts[label]+1
  writes:write(string.format(
   "%d,%s,%s,%08X,%d,%u,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X\n",
   nframe,player,field,tonumber(a),tonumber(w),value,pc,instr,
   tonumber(g.ra),tonumber(g.sp),tonumber(g.a0),tonumber(g.a1),
   tonumber(g.a2),tonumber(g.a3),tonumber(g.s0),
   tonumber(g.v0),tonumber(g.v1),tonumber(g.t0),tonumber(g.t1)))
  if events%FLUSH_EVERY==0 then writes:flush() end
  -- An explicit 'return false' would delete this breakpoint.
 end,"ISS26 "..label)
end

function ISS26Motion.mark(label)
 if not active then return end
 label=tostring(label):gsub("[\r\n,]","_"):sub(1,120)
 markers:write(nframe..","..label.."\n");markers:flush();writes:flush()
 print("ISS26 Motion marker: "..label.." Vsync="..nframe)
end
function ISS26Motion.status()
 print(string.format("ISS26 Motion: frames=%d rows=%d writes=%d capped=%s",
  nframe,rows,events,tostring(capped)))
 for _,d in ipairs(def) do
  local key=d[1].."_"..d[2]
  print(key.."="..counts[key])
 end
 print("Files: "..prefix.."_*")
end
function ISS26Motion.stop()
 if not active then return end
 active=false
 if ISS26Motion.vsync then ISS26Motion.vsync:remove();ISS26Motion.vsync=nil end
 for i,bp in ipairs(handles) do
  if bp then pcall(function() bp:remove() end) end
  handles[i]=nil
 end
 if writes then writes:flush();writes:close();writes=nil end
 if samples then samples:flush();samples:close();samples=nil end
 if markers then markers:flush();markers:close();markers=nil end
 print("ISS26 Motion Probe STOPPED: frames="..nframe.." writes="..events)
 print("Send files: "..prefix.."_*")
end

print("ISS26 Motion Probe v0.4 STARTED — six persistent input-field write hooks")
print("This logs motion commands, not yet AI decision reasoning.")
print("ISS26Motion.status() | ISS26Motion.mark('event') | ISS26Motion.stop()")
print("Files: "..folder)
