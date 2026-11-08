-- ISS26 World Probe v0.3 (experimental, read-only)
-- PCSX-Redux / SLES03321 / clean original ISS Pro Evolution 2 (Europe)
-- Breakpoints target source X/Y read by minimap writer, NOT the minimap output.
-- Start: dofile(os.getenv("USERPROFILE") .. "/ISS26/ISS26_WorldProbe_v03.lua")
-- Status: ISS26World.status()
-- Mark: ISS26World.mark("Kahn leaves box")
-- Stop: ISS26World.stop()
-- Requires PCSX-Redux with Enable Debugger and CPU Interpreter.
-- No modification to emulated game data.
-- IMPORTANT: breakpoint callbacks must not return false, which removes them.

local MAP_SOURCE_BASE = 0x7627C -- offset into emulated 2MiB RAM
local PLAYER_STRIDE = 0x38C     -- 908 bytes: ball index 0, Germany 1-11, France 12-22
local MAX_WRITE_EVENTS = 50000
local FLUSH_EVERY = 300

if _G.ISS26World and type(_G.ISS26World.stop) == "function" then
  _G.ISS26World.stop()
end

local folder = (os.getenv("USERPROFILE") or ".") .. "\\ISS26\\"
local prefix = folder .. "ISS26_WorldProbe_" .. os.date("%Y%m%d_%H%M%S")
local function newFile(path)
  local f,err = io.open(path,"wb")
  assert(f, "Cannot create " .. path .. ": " .. tostring(err))
  return f
end

local names = {"Ball", "Kahn", "Nowotny", "Matthaus", "Linke", "Jeremies",
 "Hamann", "Zeige", "Deisler", "Schneider", "Rink", "Bierhoff",
 "Barthez", "Desailly", "Blanc", "Lizarazu", "Thuram", "Petit",
 "Deschamps", "Henry", "Djorkaeff", "Zidane", "Anelka"}

local watch = {
 {"Ball_X",0,2}, {"Ball_Y",0,6},
 {"Kahn_X",1,2}, {"Kahn_Y",1,6},
 {"Barthez_X",12,2}, {"Barthez_Y",12,6}
}

local log = newFile(prefix .. "_source_writers.csv")
local positions = newFile(prefix .. "_source_positions.csv")
local marks = newFile(prefix .. "_markers.csv")
log:write("vsync,watch,address,width,pc,ra,sp,a0,a1,a2,a3,s0,v0,v1\n")
local header={"vsync"}
for i=1,#names do
 header[#header+1]=names[i].."_rawX"
 header[#header+1]=names[i].."_rawY"
end
positions:write(table.concat(header,",").."\n")
marks:write("vsync,label\n")

local frame, eventCount, rowCount = 0, 0, 0
local active, capped = true, false
local handles = {}
local counts={}

local function value16(ptr, off)
 local value = tonumber(ptr[off]) + 256*tonumber(ptr[off+1])
 return value >= 32768 and value - 65536 or value
end
local function writeSourcePositions()
 local ptr = PCSX.getMemPtr()
 local row={tostring(frame)}
 for i=0,22 do
  local o=MAP_SOURCE_BASE + i*PLAYER_STRIDE
  row[#row+1]=tostring(value16(ptr,o+2))
  row[#row+1]=tostring(value16(ptr,o+6))
 end
 positions:write(table.concat(row,",").."\n")
 rowCount = rowCount+1
end

_G.ISS26World={}
ISS26World.vsync=PCSX.Events.createEventListener("GPU::Vsync",function()
 if not active then return end
 frame=frame+1
 writeSourcePositions()
 if frame%300==0 then
  log:flush(); positions:flush(); marks:flush()
 end
end)

for i,w in ipairs(watch) do
 local label, index, fieldOffset = w[1],w[2],w[3]
 local address = 0x80000000 + MAP_SOURCE_BASE + index*PLAYER_STRIDE + fieldOffset
 counts[label]=0
 handles[i]=PCSX.addBreakpoint(address,"Write",2,"ISS26 world "..label,
  function(addr,width,cause)
   if not active then return end
   if eventCount >= MAX_WRITE_EVENTS then
    if not capped then
     capped=true
     log:flush()
     print("ISS26 World Probe reached the event cap. Run ISS26World.stop().")
    end
    return
   end
   local r=PCSX.getRegisters()
   local n=r.GPR.n
   eventCount=eventCount+1
   counts[label]=counts[label]+1
   log:write(string.format("%d,%s,%08X,%d,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X\n",
    frame,label,tonumber(addr),tonumber(width),tonumber(r.pc),tonumber(n.ra),
    tonumber(n.sp),tonumber(n.a0),tonumber(n.a1),tonumber(n.a2),
    tonumber(n.a3),tonumber(n.s0),tonumber(n.v0),tonumber(n.v1)))
   if eventCount%FLUSH_EVERY==0 then log:flush() end
   return
  end,"ISS26 source "..label)
end

local function safeLabel(label)
 return tostring(label):gsub("[\r\n,]","_"):sub(1,100)
end
function ISS26World.mark(label)
 if not active then return end
 label=safeLabel(label)
 marks:write(frame..","..label.."\n")
 marks:flush()
 log:flush()
 print("ISS26 World event: "..label.." frame "..frame)
end
function ISS26World.status()
 print(string.format("ISS26 World Probe active=%s frames=%d positionRows=%d writerEvents=%d capped=%s",
  tostring(active),frame,rowCount,eventCount,tostring(capped)))
 for _,w in ipairs(watch) do print(w[1].."="..counts[w[1]]) end
 print("Files: "..prefix.."_*")
end
function ISS26World.stop()
 if not active then return end
 active=false
 if ISS26World.vsync then ISS26World.vsync:remove(); ISS26World.vsync=nil end
 for i,bp in ipairs(handles) do
  if bp then pcall(function() bp:remove() end) end
  handles[i]=nil
 end
 if log then log:flush();log:close();log=nil end
 if positions then positions:flush();positions:close();positions=nil end
 if marks then marks:flush();marks:close();marks=nil end
 print(string.format("ISS26 World Probe STOPPED, frames=%d writerEvents=%d",frame,eventCount))
 print("Files: "..prefix.."_*")
end

print("ISS26 World Probe v0.3 STARTED (read only)")
print("Watching source of minimap XY with 6 PERSISTENT write breakpoints")
print("Fix in v0.3: all breakpoint callbacks now return nil, not false")
print("ISS26World.status() | ISS26World.mark('event') | ISS26World.stop()")
print("Files in "..folder)