logic:
  - always noglitches unless forced otherwise
  - Guarantees starting boots if any glitch mode

goal:
  - If ganonhunt and not entrance, pyramid is open or GT is 0 crystals
  - If ganonhunt and entrance, ganon is vanilla and pyramid is open
  - If ganon (crystals + aga2) and not entrance, GT crystals is always <= ganon crystals
  - If fast ganon, and not entrance, GT crystals is always >= ganon crystals
  - Trinity won't roll by default

collection_rate:
  - Turned on if completionist, shopsanity, or any pottery

mode:
  - If standard, boots hint is rolled, and insanity ER is off.
  - If standard enemizer, sword is assured.
  - If standard universal keys, you start with 3 keys.

ohko:
  - If ohko, enemizer is off
  - If ohko, pottery can't be dungeons, reduced, or lottery

enemizer:
  - If enemies are shuffled, enemy health cannot be hard or expert.

entrance:
  - If NOT entrance, take any caves are off.
  - If lean entrance, pottery can only be none, keys, or dungeons. And shopsanity is off.
  - If inverted entrance, links house is always shuffled
  - If insanity entrance, bombbag is always off and you have a starting flute.

doors:
  - If doors, some wild dungeon items are guaranteed
  - If doors, dungeon counters are always on 

pottery:
  - If any dungeon pottery is on, 'dungeon_counter' is on.
  - If pottery = dungeon or lottery, and it is not a triforce hunt, all dungeon items are wild.
  - If pottery is not none and not lottery, 'colorizepots' is on (pot checks are colored differently)

enemydrop:
  - Set to keys if any pottery is on, is
  - Underworld is currently not enabled 

dungeon_items:
  The options are: none, mc, s, b, mcs, mcb, mcsb
  - 'universal' keys can roll if wild keys have been rolled first
  - 'restrict_boss_items' (ambrosia) is rolled if there are any non-wild dungeon items

key_logic_algorithm:
  - Set to "partial" if door_shuffle, entrance, wild small keys, or keypotdropshuffle is on

triforcehunt:
  - Triforce Goal is rolled as a fraction of the available item pool. I.e 30 = 30 in 216, but in pottery lottery 30 = 152
  - The Goal options are 30, 40, 50, or 60 fractions
  - Triforce extra Pool is rolled as a % on top of the Goal. I.e. 10 = 3 extra pieces with a 30 goal in a 216 pool.
  - The extra pool options are 10%, 25%, 40%, 55%, 70%
  - Triforcehunt can be Ganonhunt, which means get the pieces and then kill ganon. You know this is the case when Muradahla is not present

startinventory:
 - There is a minimum and maximum item count.
 - Items are first rolled to attempt to put the settings within the points intervals
 - If the poins are within the point intervals, there is a chance to roll bonus items
 'An item' is a fluid concept. Some examples of "single" items in the weights
    - 3 Bosshearts
    - 2 Mail upgrades
    - Mushroom + Shovel
    - 420 Rupees
    - Ether + Quake
    - Capacity upgrades


metadata presented after rolling:
    - Final accumulated points for each attribute
    - Filler Algorithm used (balanced, major_only, dungeon_only)
    - Boss item restriction (none, mapcompass, dungeon)
    - Take any (none, random, fixed)
    - Pseudoboots (yes, no)
    - Boots Hint (yes, no)
    - Extra TF Pool XX% (percent more pieces in pool than required by goal)