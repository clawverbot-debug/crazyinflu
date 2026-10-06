#!/usr/bin/env python3
"""Q4 copy for every character: Instagram bio (first line invites media buyers to @primeads_ai, in the character's voice,
≤150 chars) + 3 captions that point to @primeads_ai. Writes lab/copy_q4.json (read by the dashboard and the posting kits).
Rules: never promise results ("guarantee"), no fake numbers presented as facts, humour first, always in character."""
import json, os
H = "@primeads_ai"
C = {
 "otto":   (f"Q4 plan: precise. Accounts: {H} 🇩🇪", "Media buying engineer. Moves on beat.", [f"Q4 checklist: ✅ creatives ✅ budget ✅ {H}. Jawohl.", f"Precision dancing. Precision scaling. {H}", "Engineers don't panic in Q4. They dance."]),
 "tony":   (f"Survived every ban wave. Q4 ink: {H} 🏴‍☠️", "Ban wave survivor. Got the tattoo.", [f"Got 'BAN WAVE SURVIVOR' tattooed. Q4 I'm adding {H}.", "Ban wave hit at 2 am. Tony kept dancing.", f"Media buyers know. {H}"]),
 "gary":   (f"Two watches, one Q4 setup: {H} ⌚", "Fully connected uncle. Zero missed sales.", [f"Notification: 'campaign still live'. Uncle approves. {H}", "Two watches. Both say: scale.", f"Q4 gadgets: watch, glasses, {H}."]),
 "nils":   (f"Scaling Q4 from a beanbag. Ads via {H} 🌴", "Digital nomad, Bali.", [f"Canggu wifi: shaky. My ad accounts: not. {H}", "When the client asks for Q4 numbers from Bali:", f"Laptop, scooter, {H}. That's the stack."]),
 "carl":   (f"Q4 forecast: CPMs storm. Shelter: {H} ⛅", "Your daily CPM weatherman.", [f"Today: 100% chance of Q4 CPMs. Bring {H}.", "Storm warning: Black Friday. Carl is dancing anyway.", f"Clear skies for scaling with {H}."]),
 "barry":  (f"Surfing Q4 ban waves on {H} 🏄", "Ban waves come and go. Barry stays.", [f"Ban wave incoming. Board: {H}. Surf's up.", "Another wave. Another ride. Q4 edition.", f"Media buyers paddling out for Q4 👉 {H}"]),
 "boris":  (f"Head of anti-ban security. Q4 list: {H} 🕶️", "Nothing gets past me.", [f"Ban wave tried to get in. Not on the {H} list.", "Security is dancing. Accounts are fine.", f"You're on the Q4 list? {H}"]),
 "sal":    (f"Scale Daddy says: Q4 runs on {H} 📱", "Two phones. One plan: scale.", [f"Two phones. Both running {H}. Daddy is scaling.", "When Q4 budgets drop and you're ready:", f"Scale. {H}. Repeat."]),
 "vito":   (f"Q4 offer Meta can't refuse: {H} 🎩", "The Don of media buying.", [f"I made Q4 an offer it couldn't refuse. {H}", "Family first. Scaling second. Dance third.", f"Capisce? {H}"]),
 "rocco":  (f"Sexiest media buyer alive. Q4: {H} ⚡", "My ROAS dances too.", [f"Too sexy for disabled ad accounts. {H}", "Feel the lightning. Q4 is here.", f"Disco never died. Neither do my accounts. {H}"]),
 "hotline":(f"Grandpa's Q4 hotline ☎️ press 1 for {H}", "Answers at 2 am. Dances at 3.", [f"Hello, this is Grandpa. Q4 question? Call {H}.", "Please hold. Grandpa is dancing.", f"Support, but make it {H}."]),
 "chad":   (f"Iced coffee. Hot Q4 campaigns. {H} 🧋", "Digital nomad, Chiang Mai.", [f"Fisherman pants. Founder brain. {H} accounts.", "Sawasdee, Q4.", f"Chiang Mai office hours: 2 pm to whenever. Ads by {H}."]),
 "leo":    (f"Out of learning phase for Q4. Thanks {H} 📚", "Junior media buyer. Still learning.", [f"Learning phase: done. Q4: ready. {H}", "Don't touch the budget. Watch the dance.", f"Junior buyer, senior setup. {H}"]),
 "nico":   (f"2 am Q4 launches. Accounts: {H} 🌙", "Media buyer on night shift.", [f"2 am. Still live. {H}", "Coffee number four. Q4 number one.", f"Launching while you sleep with {H}."]),
 "victor": (f"Founder Q4 stack: vest, glasses, {H} 🦺", "Records every move.", [f"Recording this with my glasses for the {H} team.", "Vest on. Budget up.", f"Founders scale Q4 with {H}."]),
 "larry":  (f"3 badges, 1 tip for Q4: {H} 🎟️", "Professional conference attendee.", [f"Best talk at the conference? '{H} for Q4'.", "Three badges. One dance.", f"See you at the afterparty. Bring {H}."]),
 "zaki":   (f"Uncle Zaki raises Q4 budgets with {H}", "Raises budgets. Raises the roof.", [f"Zaki approves {H} for Q4.", "Again. Louder. Q4 edition.", f"Uncle mode: on. Accounts: {H}."]),
 "moha":   (f"Tonton scales Q4. Yalla: {H} 🌙", "Spends big. Dances bigger.", [f"Yalla, Q4. {H}", "The shoulders decide the budget.", f"Mashallah, still live. {H}"]),
 "tom":    (f"Take 47 wins Q4. Accounts: {H} 🎬", "Creative director.", [f"Action. Test. Scale with {H}.", "Take 47 was the winner. Q4 needs 48.", f"Cut. Print. Launch on {H}."]),
 "basil":  (f"Scaling Q4 with manners and {H} 🎩", "Gentleman media buyer since 1971.", [f"Quite right. Q4 calls for {H}.", "Seized by the rhythm, once more.", f"A gentleman never loses an ad account. {H}"]),
 "leroy":  (f"Media buying champ since 1971. Q4: {H}", "Still scaling. Still dancing.", [f"Champion since 1971. Q4 coach: {H}.", "Back by popular demand.", f"Grandpa's Q4 secret: {H}."]),
 "bruno":  (f"Sexiest affiliate alive. Q4: {H} 🔥", "Hot campaigns only.", [f"Fuego campaigns need {H} accounts.", "Too hot to stop. Q4 edition.", f"Bruno is back. So are his ads. {H}"]),
 "albert": (f"Professor of ROAS. Q4 lesson: {H} 🎓", "Tested 400 creatives. Danced to all.", [f"Fascinating: Q4 scales better on {H}.", "For science.", f"Class dismissed. Homework: {H}."]),
 "gustav": (f"Precise budgets. Precise Q4: {H} 🇩🇪", "Media buying engineer.", [f"Ordnung for Q4: {H}.", "Precisely on the beat.", f"Sehr gut. Q4 runs on {H}."]),
 "rashid": (f"Habibi, Q4 scaling from Dubai: {H} 🇦🇪", "Launch. Scale. Yalla.", [f"Wallah, one more campaign. {H}", "Habibi, watch this.", f"Dubai to the world, Q4 with {H}."]),
 "ricky":  (f"Coach says: Q4 reps on {H} 💪", "Raise the budget. Raise your knees.", [f"Knees up. Budgets up. {H}", "One more set before Black Friday.", f"Coach's Q4 program: {H}."]),
 "bilal":  (f"Business Bay founder. Q4 on {H} 🇦🇪", "Business Bay by day. Dance floor by night.", [f"Meeting at the rooftop: Q4 on {H}.", "Business Bay energy.", f"Yalla, scale. {H}"]),
 "olga":   (f"Former ballerina. Q4 scaler. {H} 🩰", "Graceful budgets only.", [f"Da. Q4 on {H}.", "Elegance is a choice. So is the ad account.", f"No comment. Only {H}."]),
 "ludmila":(f"Elegant Q4 budgets via {H} 🩰", "Former ballerina. Current scaler.", [f"Da. {H}", "Elegance is a choice.", f"Pirouette into Q4 with {H}."]),
 "benny":  (f"Boss move for Q4: {H} 💼", "Runs the ads. Runs the party.", [f"The party starts when the {H} accounts are live.", "Business, then dance.", f"Boss move: {H}."]),
 "betty":  (f"Black Friday queen. Q4 runs on {H} 🛍️", "Countdown mode, all year.", [f"Countdown started. Accounts: {H}.", "Sold out. Dancing.", f"Black Friday mode: {H}."]),
 "roxanne":(f"ROAS Queen's Q4 crown: {H} 👑", "Agency owner. Dance floor owner.", [f"The numbers love me. So does {H}.", "Board meeting, then dance floor.", f"Queen of Q4 ROAS. {H}"]),
 "rosa":   (f"Auntie's Q4 tip for media buyers: {H}", "Agency owner. Clients happy.", [f"Mmm-hmm. Auntie said {H} for Q4.", "Auntie arrived. Make some room.", f"Clients happy, auntie dancing. {H}"]),
 "brenda": (f"Auntie survived every ban wave. Q4: {H}", "Ban waves come and go. Auntie stays.", [f"Mmm-hmm. {H}", "Auntie arrived. Clear the floor.", f"Ban wave? Auntie called {H}."]),
 "tina":   (f"6 phones, 6 tests, 1 Q4 setup: {H} 📱", "Creative strategist.", [f"Winner found. Scaling it on {H}.", "Six phones. Six tests. One dance.", f"Testing my moves too. {H}"]),
 "silvia": (f"55, still scaling Q4 with {H} 🔥", "Ecom founder. Older than your pixel.", [f"55. Still scaling. {H}", "Older than your pixel. Still faster.", f"Retired? Never. Q4 on {H}."]),
 "odette": (f"Mamie, 79, scales Q4 with {H} 💎", "Grandma's ads never sleep.", [f"Oh là là, Q4. Mamie uses {H}.", "Grandma is online.", f"Still got it. Still {H}."]),
 "gisele": (f"Mamie media buyer, 78. Q4: {H} 🪩", "Scaled before it was cool.", [f"Not bad for 78. {H}", "Grandma is back for Q4.", f"Oh là là, {H}."]),
 "kidceo": (f"9 y/o CEO. Dad scales Q4 with {H} 🧃", "Already scaling. Ask my dad.", [f"Meeting after recess: Q4 on {H}.", "Scaled before bedtime.", f"Dad, the budget. And {H}."]),
 "vera":   (f"Quiet budget. Loud Q4. {H} 🖤", "Agency owner.", [f"No comment. {H}", "Budget doubled.", f"Elegance scales on {H}."]),
 "ugcgranny":(f"Honest Q4 review, sweetie: {H} 🧶", "UGC creator, 82.", [f"Hi sweeties, honest review: {H} for Q4.", "Take two, darling.", f"Grandma converts. {H}"]),
 "mamiedrop":(f"Mamie dropshipper, 81. Q4 on {H} 📦", "Launched in 20 min. Knitted for 2 h.", [f"Grandma shipped it. Ads on {H}.", "Orders up. Knitting down.", f"Black Friday? Mamie has {H}."]),
 "mila":   (f"Mom of 3, ROAS of 4. Q4: {H} 💪", "Gym at 6. Ads at 7.", [f"Gym at 6. {H} at 7.", "Still scaling.", f"Media buyer moms know: {H}."]),
 "kiki":   (f"CPM hunter. Q4 accounts: {H} 💗", "Tested 40 creatives. Then danced.", [f"CPM down. Mood up. {H}", "Hot girl CPM.", f"Q4 ready with {H}."]),
 "rocky":  (f"Night media buyer 🦝 Q4 on {H}", "Works at 2 am. Raids trash at 3.", [f"2 am crew runs on {H}.", "Night shift.", f"Trash can wait. Q4 campaigns first. {H}"]),
 "pepe":   (f"Small dog. Big Q4 spend. {H} 🐾", "CEO.", [f"Business. {H}.", "Small dog. Big deals.", f"Respect the boss. Respect {H}."]),
 "don":    (f"Business is business. Q4: {H} 🐶", "CEO of the ad account.", [f"The boss is dancing. Accounts by {H}.", "Respect.", f"Business is business. {H}"]),
 "hoot":   (f"Awake at 2 am for Q4. {H} 🦉", "Watching your campaigns.", [f"who who who scales Q4? {H}", "up all night", f"tiny night shift, big {H}"]),
 "lulu":   (f"Tiny media buyer 🐑 Q4: {H}", "Baa-sed on data.", [f"baa-baa-boogie with {H}", "tiny steps, big moves", f"again again. {H}"]),
 "capi":   (f"Tiny buyer, big Q4. {H} 🐾", "Small budget. Big moves.", [f"wiggle wiggle {H}", "tiny but groovy", f"again again, Q4. {H}"]),
}
# Post captions and bios are VARIED on purpose (6 Oct, Thibault): nothing may look templated across posts or accounts,
# never ask people to comment, test with / without hashtags and short / long texts. Each caption carries a variant
# label so results can be compared later (pool snapshots). Choices are deterministic per character + post number.
import hashlib
def rnd(*k):
    return int(hashlib.md5("|".join(map(str, k)).encode()).hexdigest(), 16)
PITCH = [  # ways to point at Prime Ads without a call to comment
    f"Q4 accounts that stay live → {H}", f"My ad accounts live at {H}", f"Built to stay live: {H}", f"Scaling Q4 on {H} accounts",
    f"Agency accounts for Meta via {H}", f"{H} keeps the campaigns running", f"Media buyers know where: {H}", f"Good vibes, live accounts: {H}",
    f"Q4 stack = creatives + budget + {H}", f"Spend more, worry less. {H}", f"Ad accounts sorted by {H}", f"The Q4 setup: {H}",
    f"{H} for the ones who scale", f"Running Meta at scale with {H}", f"Ask the {H} team about Q4"]
TAGS = ["#metaads", "#mediabuyer", "#facebookads", "#fbads", "#mediabuying", "#performancemarketing", "#affiliatemarketing", "#clickbank",
        "#clickfunnels", "#ecommerce", "#dropshipping", "#digitalmarketing", "#adsmanager", "#metaadvertising", "#scaling", "#q4",
        "#blackfriday", "#roas", "#ppc", "#paidsocial", "#growthmarketing", "#shopifystore", "#affiliate", "#onlinebusiness", "#marketingagency"]
STORY = ["Client called at 2 am. Account still live. Back to dancing.", "Budget doubled on Monday. Nobody panicked.",
         "Ban wave news this morning. Coffee, then this.", "Q4 starts now. Some of us are ready.", "Third campaign scaled today. Celebrated properly.",
         "They said Q4 would be chaos. It's a party.", "Learning phase finished. Had to celebrate.", "Black Friday prep: done. Mood: this."]
FORMATS = [  # (label, builder)
    ("V1 hook only", lambda h, c, k: h),
    ("V2 hook + 2-3 tags", lambda h, c, k: f"{h}\n\n{tags(c, k, 2 + rnd(c, k, 't') % 2)}"),
    ("V3 hook + pitch, no tags", lambda h, c, k: f"{h}\n{pitch(c, k, h)}" if pitch(c, k, h) else h),
    ("V4 hook + pitch + 3-5 tags", lambda h, c, k: "\n\n".join(x for x in [h, pitch(c, k, h), tags(c, k, 3 + rnd(c, k, 'n') % 3)] if x)),  # Instagram caps posts at 5 hashtags (Dec 2025)
    ("V5 story + pitch + 1-2 tags", lambda h, c, k: "\n\n".join(x for x in [STORY[rnd(c, k, 's') % len(STORY)] + " " + h, pitch(c, k, h), tags(c, k, 1 + rnd(c, k, 'm') % 2)] if x)),
    ("V6 one line, lowercase", lambda h, c, k: h.lower().rstrip(".")),
]
def tags(c, k, n):
    pool = sorted(TAGS, key=lambda t: rnd(c, k, t))
    return " ".join(pool[:n])
def pitch(c, k, hook):
    return "" if H in hook else PITCH[rnd(c, k, "p") % len(PITCH)]
def posts_for(cid, caps, tics):
    hooks = [x for pair in zip(caps, tics + [""] * 3) for x in pair if x][:6]
    out = []
    for k in range(10):
        fmt = (rnd(cid, "f") + k) % len(FORMATS)              # each account starts on a different format, then rotates
        h = hooks[k % len(hooks)]
        label, build = FORMATS[fmt]
        out.append({"variant": label, "text": build(h, cid, k)})
    return out
BIO_T = [  # bio shapes: handle on line 1, on line 2, one-liner, three lines
    lambda l1, l2, t, c: f"{l1}\n{l2}",
    lambda l1, l2, t, c: f"{l2}\n{PITCH[rnd(c, 'b') % len(PITCH)]}",
    lambda l1, l2, t, c: f"{l1}",
    lambda l1, l2, t, c: f"{l2}\n{l1}\n{t}",
    lambda l1, l2, t, c: f"{l2.rstrip('.')} · {PITCH[rnd(c, 'b2') % len(PITCH)]}",
]
TICS = {}
out = {}
bad = []
CHAR_TICS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tics.json"))) if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tics.json")) else {}
for seed, (cid, (l1, l2, caps)) in enumerate(C.items()):
    tics = CHAR_TICS.get(cid, [])
    # never "AI character" in bios (Thibault, 5 Oct); shape varies per account
    bt = rnd(cid, "bio") % len(BIO_T)
    bio = BIO_T[bt](l1, l2, (tics or [l2])[0], cid)
    if len(bio) > 150: bad.append((cid, len(bio)))
    out[cid] = {"bio": bio, "bio_variant": ["B1 2 lines, handle first", "B2 2 lines, handle second", "B3 one line", "B4 3 lines", "B5 one line with ·"][bt],
                "captions": caps, "posts": posts_for(cid, caps, tics)}
assert not bad, bad
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "copy_q4.json"), "w"), ensure_ascii=False, indent=1)
print(len(out), "characters; longest bio", max(len(v["bio"]) for v in out.values()), "; longest post", max(len(x["text"]) for v in out.values() for x in v["posts"]))
for x in out["barry"]["posts"][:5]: print("--", x["variant"], "\n" + x["text"])
print("== bios"); [print(repr(out[c]["bio"])) for c in ["barry", "otto", "tony", "carl", "vito"]]
