## 3.1

Major feature update

new:
 - music & audiobook submissions
 - basic threading in API requests (up to ~5x speedup for season packs)
 - multi-episode submissions
 - config migration (API keys now embedded, imgur re-auth required)*

<sub><sub><sub>*if you encounter issues, delete the entire `[Imgur]` section from your config.</sub></sub></sub> 

fixed:
 - bug in source selection
 - IMDb cast ordering (stars are now always first)

## 3.0.3

Minor feature update

new: ptpimg support (thanks znedw!  
fixed: episode naming

## 3.0.2

Maintenance update (thanks plotski, eeeeve, ...)

breaking change: dropped Python 2 support

new:
 - "AKA" for international titles

fixed:
 - lotsa new codecs
 - 4K!
 - mediainfo changes
 - tvdb_api changes  

## 3.0

Complete rewrite

new: 
 - automated submission
 - data copying for submission  
 - PROPER parsing
 - scene check
 - torrent black-holing
 - persistent config file
 - Python 3 support