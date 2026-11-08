-- ISS26 Live Analyzer v0.1 (read-only experimental recorder)
-- PCSX-Redux / ISS Pro Evolution 2 (Europe, SLES03321)
--
-- HOW TO RUN (Windows, in an actual game):
--   Debug > Lua > Show Lua Console
--   dofile("C:/ISS26/ISS26_LiveAnalyzer.lua")
--
-- HOW TO STOP (in Lua console):
--   ISS26.stop()
--
-- IMPORTANT: CPU RAM is scanned every SAMPLE_EVERY emulated frames, not
-- on every MIPS memory write. Fast writes between samples are not seen.
-- Player/ball minimap packets are logged once per GPU vsync.
--
-- This script never writes to emulated RAM or the disc.

local ffi = require("ffi")

-- Standard PS1 main RAM and chunk size. Requires 8MB expansion DISABLED.
local RAM_SIZE = 0x200000
local BLOCK_SIZE = 4096
local SAMPLE_EVERY = 5 -- 5 ~ 10-12 RAM scans/sec; 1 = every vsync (slower)
local MAP_BASE = 0x549A6
local MAP_STRIDE = 10

local names = {
  "Ball", "Kahn", "Nowotny", "Matthaus", "Linke",
  "Jeremies", "Hamann", "Zeige", "Deisler", "Schneider",
  "Rink", "Bierhoff", "Barthez", "Desailly", "Blanc",
  "Lizarazu", "Thuram", "Petit", "Deschamps", "Henry",
  "Djorkaeff", "Zidane", "Anelka"
}

-- The recorder expects Germany v France in the original lineup.
-- Other matchups are still recorded, but the CSV player names are not valid.
local function headerTitle()
  local cols = { "vsync" }
  for i = 1, #names do
    cols[#cols + 1] = names[i] .. "_X"
    cols[#cols + 1] = names[i] .. "_Y"
  end
  return table.concat(cols, ",") .. "\n"
end

if _G.ISS26 and type(_G.ISS26.stop) == "function" then
  _G.ISS26.stop()
end

-- memcmp from Windows C runtime: fast C-side comparisons of RAM blocks.
pcall(ffi.cdef, [[
  int memcmp(const void *a, const void *b, size_t n);
]])
local crt = ffi.load("msvcrt")
local ram = PCSX.getMemPtr()
assert(ram ~= nil, "PCSX.getMemPtr() returned nil")

local home = os.getenv("USERPROFILE") or "."
local prefix = home .. "\\Downloads\\ISS26_" .. os.date("%Y%m%d_%H%M%S")
local function openOrError(path)
  local file, err = io.open(path, "wb")
  assert(file, "Cannot create " .. path .. ": " .. tostring(err))
  return file
end

local baseline = openOrError(prefix .. "_baseline_RAM.bin")
baseline:write(ffi.string(ram, RAM_SIZE))
baseline:close()

-- Delta format:
-- 8-byte ASCII magic: ISS26D1\0
-- repeated records: uint32le(vsync), uint32le(RAM offset),
--                   uint16le(length), raw new bytes[length].
-- A baseline + records reconstructs the sampled RAM.
local deltas = openOrError(prefix .. "_RAM_deltas.bin")
deltas:write("ISS26D1\0")
local positions = openOrError(prefix .. "_positions.csv")
positions:write(headerTitle())
local info = openOrError(prefix .. "_readme.txt")
info:write("ISS26 Live Analyzer v0.1\r\n")
info:write("Game: SLES03321; expected matchup Germany vs France\r\n")
info:write("RAM size: 2097152 bytes\r\n")
info:write("RAM sampling: every " .. SAMPLE_EVERY .. " GPU vsyncs\r\n")
info:write("RAM deltas: 8-byte ISS26D1\\0 header; then LE32 frame, LE32 offset, LE16 length, bytes\r\n")
info:write("Player packets: 0x800549A6 plus i*10; XY at +6 and +8, signed LE16\r\n")
info:write("NOTE: only main RAM sampled. Not a trace of every MIPS read/write.\r\n")
info:close()

local prior = ffi.new("uint8_t[?]", RAM_SIZE)
ffi.copy(prior, ram, RAM_SIZE)

local frame, samples, changed, runs, positionRows, dumps = 0, 0, 0, 0, 0, 0
local lastFlush = 0
local active = true
local outputPaths = { prefix .. "_baseline_RAM.bin",
                      prefix .. "_RAM_deltas.bin",
                      prefix .. "_positions.csv" }

local function le16(x)
  return string.char(x % 256, math.floor(x / 256) % 256)
end
local function le32(x)
  return string.char(
    x % 256,
    math.floor(x / 256) % 256,
    math.floor(x / 65536) % 256,
    math.floor(x / 16777216) % 256
  )
end
local function u16(off)
  return tonumber(ram[off]) + 256 * tonumber(ram[off + 1])
end
local function s16(off)
  local x = u16(off)
  return x >= 32768 and x - 65536 or x
end
local function isMinimapPacket()
  local a, b = MAP_BASE + MAP_STRIDE, MAP_BASE + 12 * MAP_STRIDE
  return
    u16(MAP_BASE) == 0 and
    u16(MAP_BASE + 2) == 0x0808 and
    u16(MAP_BASE + 4) == 0x5890 and
    u16(a) == 0x2100 and
    u16(a + 2) == 0x0808 and
    u16(a + 4) == 0x5880 and
    u16(b) == 0x2100 and
    u16(b + 4) == 0x5888
end

local function writePositions()
  if not isMinimapPacket() then return end
  local row = { tostring(frame) }
  for i = 0, 22 do
    local off = MAP_BASE + i * MAP_STRIDE
    row[#row + 1] = tostring(s16(off + 6))
    row[#row + 1] = tostring(s16(off + 8))
  end
  positions:write(table.concat(row, ",") .. "\n")
  positionRows = positionRows + 1
end

local function scanRAM()
  ram = PCSX.getMemPtr()
  samples = samples + 1
  for block = 0, RAM_SIZE - 1, BLOCK_SIZE do
    local p = ram + block
    local old = prior + block
    if crt.memcmp(p, old, BLOCK_SIZE) ~= 0 then
      local x, limit = block, block + BLOCK_SIZE
      while x < limit do
        if ram[x] == prior[x] then
          x = x + 1
        else
          local start = x
          repeat
            x = x + 1
          until x == limit or ram[x] == prior[x]
          local length = x - start
          deltas:write(le32(frame), le32(start), le16(length))
          deltas:write(ffi.string(ram + start, length))
          changed = changed + length
          runs = runs + 1
        end
      end
      ffi.copy(old, p, BLOCK_SIZE)
    end
  end
end

_G.ISS26 = {}
function ISS26.capture()
  dumps = dumps + 1
  local filename = prefix .. string.format("_frame_%07d_%02d_RAM.bin", frame, dumps)
  local f = openOrError(filename)
  f:write(ffi.string(PCSX.getMemPtr(), RAM_SIZE))
  f:close()
  print("ISS26 snapshot saved: " .. filename)
end
function ISS26.status()
  print(string.format(
    "ISS26 active=%s frame=%d scans=%d positions=%d changedBytes=%d deltaRuns=%d",
    tostring(active), frame, samples, positionRows, changed, runs))
  print("Output prefix: " .. prefix)
end
function ISS26.stop()
  if not active then return end
  active = false
  if ISS26.listener then
    ISS26.listener:remove()
    ISS26.listener = nil
  end
  if positions then positions:flush(); positions:close(); positions = nil end
  if deltas then deltas:flush(); deltas:close(); deltas = nil end
  local filename = prefix .. "_final_RAM.bin"
  local final = openOrError(filename)
  final:write(ffi.string(PCSX.getMemPtr(), RAM_SIZE))
  final:close()
  print(string.format(
    "ISS26 STOPPED frame=%d scans=%d positions=%d changedBytes=%d deltaRuns=%d",
    frame, samples, positionRows, changed, runs))
  print("Files: " .. prefix .. "_*")
end

ISS26.listener = PCSX.Events.createEventListener("GPU::Vsync", function()
  if not active then return end
  frame = frame + 1
  ram = PCSX.getMemPtr()
  writePositions()
  if frame % SAMPLE_EVERY == 0 then scanRAM() end
  if frame - lastFlush >= 300 then
    lastFlush = frame
    deltas:flush()
    positions:flush()
  end
end)

print("ISS26 Live Analyzer STARTED (read-only).")
print("Folder: " .. home .. "\\Downloads\\")
print("Memory comparison every " .. SAMPLE_EVERY .. " vsyncs.")
print("IMPORTANT: This cannot capture multiple writes to a byte between samples.")
print("Lua console: ISS26.status() | ISS26.capture() | ISS26.stop()")
