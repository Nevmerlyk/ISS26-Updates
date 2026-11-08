-- ISS26 AI Probe v0.1: read-only PCSX-Redux CPU-write breakpoint sampler
-- Target: original ISS Pro Evolution 2 Europe SLES03321, Germany vs France.
-- Prerequisites: Debugger enabled, CPU = Interpreter, match running.
-- Run in Debug > Lua > Lua Console:
-- dofile(os.getenv("USERPROFILE") .. "/ISS26/ISS26_AI_Probe.lua")
-- Stop: ISS26Probe.stop()
--
-- This records the writers of *minimap* coordinates, NOT yet the GK AI source.
-- Read only: does not write to emulated RAM, input state, or game image.

local MAX_EVENTS = 30000  -- hard safety cap against runaway logs
local FLUSH_EVERY = 250
local dir = (os.getenv("USERPROFILE") or ".") .. "\\ISS26\\"
local prefix = dir .. "ISS26_AIProbe_" .. os.date("%Y%m%d_%H%M%S")

if _G.ISS26Probe and type(_G.ISS26Probe.stop) == "function" then
  _G.ISS26Probe.stop()
end

local watches = {
  { "Ball_X",   0x800549AC },
  { "Ball_Y",   0x800549AE },
  { "Kahn_X",   0x800549B6 },
  { "Kahn_Y",   0x800549B8 },
  { "Barthez_X",0x80054A24 },
  { "Barthez_Y",0x80054A26 },
}

local function fopen(path)
  local f, err = io.open(path, "wb")
  assert(f, "Cannot create " .. path .. ": " .. tostring(err))
  return f
end
local log = fopen(prefix .. "_writers.csv")
local marks = fopen(prefix .. "_markers.csv")
log:write("vsync,watch,address,width,pc,ra,sp,a0,a1,v0\n")
marks:write("vsync,label\n")
local eventCount, frame = 0, 0
local active, capped = true, false
local counts, bp = {}, {}

_G.ISS26Probe = {}
local function cleanLabel(x)
  return tostring(x):gsub("[\r\n,]", "_"):sub(1, 120)
end

ISS26Probe.vsync = PCSX.Events.createEventListener("GPU::Vsync", function()
  frame = frame + 1
  if log and frame % 300 == 0 then log:flush(); marks:flush() end
end)

for i, info in ipairs(watches) do
  local label, target = info[1], info[2]
  counts[label] = 0
  bp[i] = PCSX.addBreakpoint(target, "Write", 2, "ISS26 minimap " .. label, function(address, width, cause)
    if not active then return false end
    if eventCount >= MAX_EVENTS then
      if not capped then
        capped = true
        print("ISS26 AI Probe hit MAX_EVENTS; stop and send the log.")
      end
      return false
    end
    local r = PCSX.getRegisters()
    local n = r.GPR.n
    eventCount = eventCount + 1
    counts[label] = counts[label] + 1
    log:write(string.format("%d,%s,%08X,%d,%08X,%08X,%08X,%08X,%08X,%08X\n",
      frame, label, tonumber(address), tonumber(width),
      tonumber(r.pc), tonumber(n.ra), tonumber(n.sp),
      tonumber(n.a0), tonumber(n.a1), tonumber(n.v0)))
    if eventCount % FLUSH_EVERY == 0 then log:flush() end
  end, "ISS26 " .. label)
end

function ISS26Probe.mark(label)
  if not active then return end
  marks:write(string.format("%d,%s\n",frame,cleanLabel(label)))
  marks:flush()
  log:flush()
  print("ISS26 AI Probe marker: " .. cleanLabel(label) .. " at Vsync " .. frame)
end

function ISS26Probe.status()
  print(string.format("ISS26 AI Probe frame=%d writeEvents=%d cap=%s", frame, eventCount, tostring(capped)))
  for _, w in ipairs(watches) do print(w[1] .. ": " .. counts[w[1]]) end
  print("Saved to: " .. prefix .. "_writers.csv")
end

local tracing = false
function ISS26Probe.traceStart()
  if not (PCSX.CPU and PCSX.CPU.Trace) then
    print("This PCSX-Redux build does not expose PCSX.CPU.Trace")
    return false
  end
  if tracing then print("Trace already active"); return true end
  PCSX.CPU.Trace.clear()
  PCSX.CPU.Trace.enable()
  tracing = true
  ISS26Probe.mark("CPU_TRACE_START")
  print("CPU trace recording; stop promptly to limit the file size!")
  return true
end

function ISS26Probe.traceStop()
  if not tracing then print("No CPU trace active"); return end
  PCSX.CPU.Trace.disable()
  tracing = false
  ISS26Probe.mark("CPU_TRACE_STOP")
  local path = prefix .. "_cpu_trace.bin"
  local success = PCSX.CPU.Trace.save(path)
  print("ISS26 CPU trace save=" .. tostring(success) .. " path=" .. path)
end

function ISS26Probe.stop()
  if not active then return end
  if tracing then ISS26Probe.traceStop() end
  active = false
  if ISS26Probe.vsync then ISS26Probe.vsync:remove(); ISS26Probe.vsync = nil end
  -- Breakpoint handles must stay alive until explicit cleanup.
  for i, handle in ipairs(bp) do
    -- Safe to call remove outside a breakpoint callback.
    if handle then pcall(function() handle:remove() end) end
    bp[i] = nil
  end
  if log then log:flush();log:close();log=nil end
  if marks then marks:flush();marks:close();marks=nil end
  print(string.format("ISS26 AI Probe STOPPED after %d Vsyncs, %d write events.", frame, eventCount))
  print("Send: " .. prefix .. "_writers.csv and _markers.csv")
end

print("ISS26 AI Probe started: 6 read-only write breakpoints on minimap XY.")
print("Commands: ISS26Probe.status() | ISS26Probe.mark('event') | ISS26Probe.stop()")
print("Optional short CPU trace: ISS26Probe.traceStart() then ISS26Probe.traceStop()")
print("Data folder: " .. dir)
