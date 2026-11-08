# ISS26 v0.9.3 Preview — national flag corruption fix

Independent clean-original European PS1 patch. **Preview; requires in-game visual verification.**

Changes from v0.9.2:
- Removed the experimental multi-country shared bitmap packing which made Congo, Cabo Verde, Bosnia and New Zealand flags mix colours and geometry.
- Restored unique flag styles for all 17 updated national teams. Senegal uses the existing dedicated Cameroon-style tricolour with central star and a corrected green/yellow/red CLUT, without changing other national flags.
- Restored absent 4bpp flag atlas blocks for new national styles 52–60 across team selection DATSEL2/DATSEL3, editor EDT_2D/EDTR_2D and all 34 GDC stadium resource variants.
- Updated only the corresponding ISO file sizes and verified game loader sector-count entries.
- Preserved existing team names from the prior releases, 37 other national graphic styles, all 24 club crests, squad data and existing audio.
- Patch built from **clean original Track 01**, not layered over previous patches. 1412 modified sectors, 3,371,868 bytes of XOR-only data. Original BIN/CUE remain untouched.
- Passed read-back of new texture records in all affected resources, sector EDC/ECC verification, and independent clean-original patch application with full output SHA-256 match.

**Still not corrected:** historic world map and old USSR/Russia-highlight geometry; large club crests; modern player rosters; background music. Those are outside this national-flags-only release.

**Important:** in-game appearance has not been verified yet, and there may still be PS1 rendering quirks. This release is an experimental fix, not a final flags completion claim.
