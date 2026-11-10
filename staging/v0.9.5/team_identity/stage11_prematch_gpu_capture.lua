-- ISS26 Stage 11: PCSX-Redux PREMATCH GPU provenance recorder.
-- Data-only, read-only. Never writes to game RAM or emulated CD.
-- Use as an additional Lua script when launching PCSX-Redux with Test Game.
-- This script uses only API calls proven by the user's Explorer recorder:
-- PCSX.Events.createEventListener, PCSX.getMemPtr, PCSX.getRegisters,
-- PCSX.GPU.getVRAM, takeScreenShot, startDump, stopDump, Support.File.open.

local ffi = require('ffi')
local dir = os.getenv('ISS26_PREMATCH_CAPTURE_DIR') or os.getenv('ISS26_EXPLORER_SESSION_DIR')
if not dir or dir == '' then error('Set ISS26_PREMATCH_CAPTURE_DIR') end
local sep = package.config:sub(1,1)
local function p(s) return dir .. sep .. s end

local frame = 0
local sawSelection = false
local running = false
local completed = false
local stopAt = 0
local captureAt = 0
local episode = 0
local maxFrames = tonumber(os.getenv('ISS26_PREMATCH_CAPTURE_FRAMES') or '') or 900
if maxFrames < 120 then maxFrames = 120 end
if maxFrames > 1800 then maxFrames = 1800 end

local function event(kind,detail)
  local f = io.open(p('stage11_trace_events.csv'), 'ab')
  if f then
    f:write(string.format('%d,%s,%s\n',frame,kind,tostring(detail or ''):gsub('[,\r\n]',';')))
    f:close()
  end
end

local function selectionBankVisible()
  local base = ffi.cast('const uint8_t*',PCSX.getMemPtr())
  local raw = ffi.string(base + 0x80200,640)
  return raw:find('BOSNIA',1,true) and raw:find('N.ZEAL',1,true)
end

local function snapshot(label)
  local ok,err = pcall(function()
    local base = ffi.cast('const uint8_t*',PCSX.getMemPtr())
    local f = assert(io.open(p(label..'_RAM.bin'),'wb'))
    f:write(ffi.string(base,0x200000));f:close()
    local vr=Support.File.open(p(label..'.vram'),'TRUNCATE')
    vr:writeMoveSlice(PCSX.GPU.getVRAM());vr:close()
    local shot=PCSX.GPU.takeScreenShot()
    local ss=Support.File.open(p(label..'.screen.raw'),'TRUNCATE')
    ss:writeMoveSlice(shot.data);ss:close()
    local r=PCSX.getRegisters()
    event('SNAPSHOT',label..'_pc_'..string.format('%08X',tonumber(r.pc)))
  end)
  if not ok then event('CAPTURE_ERROR',err) end
end

local function startCapture(origin)
  if running then event('ALREADY_RUNNING',origin);return end
  episode=episode+1
  local name=string.format('stage11_prematch_%02d_%08d',episode,frame)
  local ok,err=pcall(function() PCSX.GPU.startDump(p(name..'.gpd')) end)
  if not ok then event('GPU_START_ERROR',err);return end
  running=true;stopAt=frame+maxFrames;captureAt=frame+120
  snapshot(name..'_begin')
  event('GPU_START',name..'_'..origin)
end

local function stopCapture()
  if not running then return end
  snapshot(string.format('stage11_prematch_%02d_%08d_end',episode,frame))
  local ok,err=pcall(function() PCSX.GPU.stopDump() end)
  event(ok and 'GPU_STOP' or 'GPU_STOP_ERROR',ok and 'completed' or err)
  running=false;completed=true
end

-- This is a human-triggerable fallback. Create an empty file named
-- `prematch_now.request` in the capture directory while the label is visible.
-- Removing it after read avoids an unattended loop.
local function checkManualRequest()
  local f=io.open(p('prematch_now.request'),'rb')
  if not f then return end
  f:close();os.remove(p('prematch_now.request'))
  startCapture('manual_request')
end

local function onVSync()
  frame=frame+1
  if frame%30~=0 and not (running and frame>=stopAt) then return end
  if running then
    if frame>=stopAt then stopCapture();return end
    if frame>=captureAt then
      snapshot(string.format('stage11_prematch_%02d_%08d',episode,frame))
      captureAt=frame+120
    end
  end
  if frame%30==0 then
    local ok,visible=pcall(selectionBankVisible)
    if not ok then event('RAM_READ_ERROR',visible) end
    if ok then
      if visible and not sawSelection then
        sawSelection=true
        event('SELECT_BANK_PRESENT','BOSNIA/N.ZEAL')
      elseif not visible and sawSelection and not running and not completed then
        event('SELECT_BANK_REPLACED','overlay-transition')
        startCapture('automatic_on_bank_change')
      end
    end
    checkManualRequest()
  end
end

stage11PrematchRecorder = {listener=PCSX.Events.createEventListener('GPU::Vsync',onVSync)}
event('INITIALIZED','read-only_'..tostring(maxFrames)..'_frames')
