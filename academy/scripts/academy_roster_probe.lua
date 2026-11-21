-- ISS26 remote diagnostics demo: read-only native roster bytes (Test Game only).
-- This file runs only after SHA-256 review and explicit user approval.
if os.getenv("ISS26_ROOKIE_EXAM")~="1" and
   os.getenv("ISS26_ROOKIE_ML_EXAM")~="1" then
  local n=0
  ISS26RemoteRosterProbe=PCSX.Events.createEventListener("GPU::Vsync",function()
    n=n+1
    if n<=1800 and n%300==0 then
      local ok,ptr=pcall(PCSX.getMemPtr)
      if ok and ptr then
        local mem=ffi.cast("const uint8_t*",ptr)
        append("academy-remote-roster-probe.tsv",string.format(
          "%d\t%02X\t%02X\tRAW_CANDIDATE_ONLY",
          frame,tonumber(mem[0xF5EEA]),tonumber(mem[0xF5EEB])))
      end
    end
  end)
end
