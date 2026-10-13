"""Button scripts (tools/drive.py syntax) from power-on, shared by the verify_*.py scripts.

NEW_GAME: title -> new game -> name entry (start = default レオン) -> stats (a = accept) -> bonus points ->
ship name -> prologue (the king's audience, with レオン's face at about frame 5500) -> Lisbon town, 1502-02-21,
at frame 11766. HARBOR walks to the harbor master (frame 12236); DEPART leaves port (the sea is drawn by frame
13856).
"""
PROLOGUE = ("w1800 start w200 a:10 w200 start:10 w200 a:10 w200 a:300 w100 down:10 w50 a:300 w100 down:10 w50 "
            "a:300 w100 a:10 w300 a:10 w300 start:10 w300 a:10 w300")
NEW_GAME = PROLOGUE + " a:10 w60 a:10 w60 a:10 w60 a:10 w60 a:10 w60" * 14
FACE_SAVE = 5400                # savestate in the prologue; "w66 a:10" then shows レオン's face
FACE_STEPS = "w66 a:10"
FACE_SHOT = 250
TOWN_SAVE = 11420               # savestate shortly before the town screen is built
TOWN_STEPS = ""                 # no presses: the town is drawn by itself
TOWN_SHOT = 340                 # town screen complete
HARBOR = " w100 down:30 w60 down:30 w60 left:30 w100"
HARBOR_SAVE = 12230             # at the harbor master, before the departure menu
DEPART = "a:10 w100 a:10 w100 a:10 w700 a:10 w600"
SEA_SHOT = 13856 - HARBOR_SAVE
