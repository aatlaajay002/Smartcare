"""
Offline health-assistant engine (used when no LLM key is set, and to pick the right doctor even when an LLM answers).
It understands typos and joined words ("stomachache"), detects WHAT KIND of question was asked (how-to, causes, diet, medicine,
duration, is-it-serious, which-doctor, plain symptom) and writes a differently-shaped answer for each, always tied to the topic asked.
"""
import hashlib
import re

# ------------------------------------------------------------------ knowledge base
# label, regex, specialist, causes, care steps, eat, avoid, duration, red flags, medicine note
KB = [
 dict(id="chest", label="chest discomfort", spec="Cardiologist",
  rx=r"chest|heart (pain|attack|problem|beat)|palpitation|heartbeat",
  causes="muscle strain, acidity, anxiety, a lung problem or sometimes a heart condition",
  care=["sit down, stay calm and stop any activity", "loosen tight clothing and breathe slowly", "note when it started, how long it lasts and whether it spreads to the arm, jaw or back", "do not drive yourself if the pain is strong"],
  eat="light, low-salt meals until you have been checked", avoid="smoking, heavy exertion and large oily meals",
  dur="Short muscle-type chest pain often settles in minutes to hours, but chest pain should never be left unchecked",
  red="the pain is severe, spreads to the arm or jaw, or comes with sweating, breathlessness, nausea or dizziness (go to emergency care at once)",
  meds="Please do not self-medicate for chest pain; it needs to be examined first."),
 dict(id="fever", label="fever", spec="General Physician",
  rx=r"fever|temperature|chills|viral|shiver",
  causes="a viral or bacterial infection, and sometimes the flu, typhoid or dengue",
  care=["rest and drink plenty of fluids such as water, ORS and soups", "wear light clothes and keep the room comfortable", "check your temperature every 4 to 6 hours and keep a note", "use a damp cloth on the forehead if you feel very hot"],
  eat="warm soups, rice gruel, curd rice, fruits, coconut water and plenty of water", avoid="oily, spicy and heavy food, and cold drinks",
  dur="A viral fever usually settles in 3 to 5 days",
  red="the fever is above 39 C (102 F), lasts more than 3 days, or comes with a severe headache, stiff neck, rash, vomiting or breathing trouble",
  meds="Doctors commonly use paracetamol for fever, but the dose depends on age and weight, so please confirm it with a doctor or pharmacist."),
 dict(id="headache", label="headache", spec="Neurologist",
  rx=r"head ?ache|migraine|head pain|pain in (my )?head|light sensitiv|sensitiv\w* to light",
  causes="stress, poor sleep, dehydration, eye strain, skipped meals or migraine",
  care=["rest in a quiet, dim room and drink water", "keep regular meal and sleep times", "reduce screen time and rest your eyes", "note your triggers (certain foods, lack of sleep, bright light)"],
  eat="regular meals, plenty of water, fruits and nuts", avoid="skipping meals, too much tea or coffee, and long screen time",
  dur="A tension headache usually eases within a few hours to a day; migraines can last up to 3 days",
  red="the headache is sudden and severe, follows a head injury, or comes with vomiting, weakness, confusion, vision changes or a stiff neck",
  meds="A simple pain reliever may help, but please check the type and dose with a doctor or pharmacist, and do not overuse it."),
 dict(id="cold", label="cold and cough", spec="General Physician",
  rx=r"cough|\bcold\b|runny nose|blocked nose|sneez|congestion|phlegm|flu\b",
  causes="a viral infection, allergies or dust and cold air",
  care=["drink warm fluids and take steam inhalation 2 to 3 times a day", "gargle with warm salt water", "rest well and keep your chest and neck warm", "avoid smoke, dust and cold drinks"],
  eat="warm water, ginger or tulsi tea, soups, honey (not for babies under 1 year) and vitamin C fruits", avoid="cold drinks, ice cream, fried food and smoking",
  dur="A common cold usually clears in 7 to 10 days, and a cough can linger a little longer",
  red="the cough lasts more than 2 weeks, you cough up blood, or you have breathlessness, wheezing or a high fever",
  meds="Cough syrups and cold tablets differ by age and type of cough, so please ask a doctor or pharmacist before taking one."),
 dict(id="throat", label="sore throat", spec="ENT Specialist",
  rx=r"sore throat|throat (pain|infection|ache|irritation)|pain in (my )?throat|hoarse|swallow|tonsil",
  causes="a viral infection, a throat or tonsil infection, allergy or acid reflux",
  care=["gargle with warm salt water several times a day", "sip warm water, tea with honey or soup", "rest your voice and avoid shouting", "avoid very cold, spicy or oily food"],
  eat="warm soups, warm water, soft food and honey tea", avoid="cold drinks, ice cream, spicy and fried food",
  dur="A viral sore throat usually improves in 3 to 5 days",
  red="swallowing becomes very painful, you have a high fever, you see white patches on the tonsils, or it lasts more than 4 days",
  meds="Throat lozenges can soothe it, but antibiotics should only be taken if a doctor prescribes them."),
 dict(id="acidity", label="acidity and gas", spec="Gastroenterologist",
  rx=r"acidity|acid reflux|heartburn|\bgas\b|gastric|burning (in|sensation).{0,12}(stomach|chest)|indigestion|bloat|belching|burp",
  causes="irregular meals, spicy or oily food, stress, smoking or eating late at night",
  care=["eat smaller meals at regular times", "avoid lying down for 2 to 3 hours after eating", "raise the head of your bed slightly", "drink water between meals and walk gently after eating"],
  eat="oats, bananas, curd, coconut water, cooked vegetables and plenty of water", avoid="spicy and fried food, tea, coffee, fizzy drinks, chocolate and late-night meals",
  dur="Occasional acidity settles within hours once you correct your meals, but frequent acidity needs a check-up",
  red="you have black stools, repeated vomiting, trouble swallowing, unexplained weight loss, or the burning keeps returning for weeks",
  meds="Antacids are commonly used for occasional acidity, but if you need them often please see a doctor instead of taking them regularly."),
 dict(id="stomach", label="stomach pain", spec="Gastroenterologist",
  rx=r"stomach (pain|ache|upset|cramp|problem)|abdominal|\bbelly\b|tummy|vomit|nausea|diarrh|loose motion|constipat|food poison",
  causes="indigestion, gas, a food-related infection, constipation or acidity",
  care=["sip ORS or clean water often to avoid dehydration", "eat light food such as rice, banana, curd and toast", "avoid oily, spicy and outside food for a few days", "rest, and use a warm compress on the tummy for cramps"],
  eat="rice, banana, curd, toast, boiled potato, ORS and coconut water", avoid="oily, spicy, outside food, milk-heavy sweets and caffeine",
  dur="A simple stomach upset usually settles in 1 to 3 days",
  red="there is blood in the stool or vomit, severe or one-sided pain, signs of dehydration (very dry mouth, little urine, dizziness) or it lasts more than 2 days",
  meds="Please avoid taking painkillers or antibiotics on your own for stomach problems; ORS is the safest first step."),
 dict(id="back", label="back or neck pain", spec="Orthopedic",
  rx=r"back pain|neck pain|spine|slip disc|spondyl|posture",
  causes="poor posture, long sitting, muscle strain, lifting heavy things or a disc problem",
  care=["rest for a day or two, then start gentle stretching", "apply a warm pack for 15 to 20 minutes", "sit with your back supported and take a short walking break every hour", "avoid lifting heavy things and sleeping on a very soft bed"],
  eat="calcium-rich food (milk, curd, ragi), protein and plenty of water", avoid="long sitting, sudden heavy lifting and bending forward with a load",
  dur="Simple back strain usually eases in 1 to 2 weeks",
  red="the pain spreads down the leg, you feel numbness or weakness, you lose control of urine or stool, or it follows a fall or injury",
  meds="Pain relief gels or tablets depend on your health and other medicines, so please check with a doctor or pharmacist first."),
 dict(id="joint", label="joint or knee pain", spec="Orthopedic",
  rx=r"knee|joint|shoulder|ankle|\bhip\b|elbow|wrist|arthritis|\bstiff|heel|swollen",
  causes="overuse, an old injury, extra body weight, arthritis or joint wear and tear",
  care=["rest the joint and avoid stairs and long walks for a day or two", "use a warm pack for stiffness or a cold pack if it is swollen, 15 minutes at a time", "do gentle movements and stretches once the pain eases", "maintain a healthy weight and wear comfortable footwear"],
  eat="calcium and protein rich food, fruits, vegetables and plenty of water", avoid="sitting cross-legged for long, climbing many stairs and extra weight gain",
  dur="A mild joint strain usually eases in 1 to 2 weeks, while arthritis pain needs treatment",
  red="the joint is hot, red or very swollen, you cannot put weight on it, or there was a fall or injury",
  meds="Pain relief for joints depends on your health and other medicines, so please check with a doctor or pharmacist first."),
 dict(id="injury", label="muscle pain or injury", spec="Orthopedic",
  rx=r"muscle|body pain|sprain|fracture|injur|broken bone|leg pain|hand pain|cramp in",
  causes="overexertion, a fall or twist, a viral illness or lack of stretching",
  care=["rest the area and avoid the activity that caused it", "use a cold pack for a fresh injury in the first 2 days, then a warm pack", "wrap it lightly and keep it raised if swollen", "start gentle stretching once the pain eases"],
  eat="protein-rich food, fruits and plenty of water", avoid="heavy exercise on the injured area",
  dur="Muscle pain usually settles in a few days to 2 weeks",
  red="the area is deformed, very swollen or you cannot move it, or the pain is severe after a fall",
  meds="Please check with a doctor or pharmacist before taking pain relief tablets or applying strong gels."),
 dict(id="skin", label="skin problem", spec="Dermatologist",
  rx=r"rash|itch|acne|pimple|skin|dandruff|hair (fall|loss)|eczema|allerg|hives|fungal|ringworm|boil",
  causes="allergies, dryness, fungal infection, sweat, irritation or hormonal changes",
  care=["keep the area clean and dry and avoid scratching", "use a mild, fragrance-free soap and moisturise if the skin is dry", "avoid new creams, soaps or foods you suspect as triggers", "wear loose cotton clothes"],
  eat="plenty of water, fruits and vegetables", avoid="things you know trigger it, and picking or scratching the skin",
  dur="Mild rashes often settle in a few days, while fungal or acne problems need proper treatment",
  red="the rash spreads fast, is painful, blisters, or comes with fever or swelling of the face or lips",
  meds="Skin creams differ for allergy, fungus and acne, and some (like steroid creams) can do harm if misused, so please see a doctor first."),
 dict(id="eye", label="eye problem", spec="Ophthalmologist",
  rx=r"\beyes?\b|vision|blurred|blurry|eyesight|spectacles|\bsee\b.{0,10}(clearly|properly)",
  causes="screen strain, dryness, allergy, infection or a change in eyesight",
  care=["follow the 20-20-20 rule: every 20 minutes look 20 feet away for 20 seconds", "do not rub your eyes and wash your hands often", "avoid sharing towels or eye drops", "rinse with clean water if dust gets in"],
  eat="carrots, leafy greens, eggs, fish and plenty of water", avoid="long screen sessions without breaks and rubbing the eyes",
  dur="Eye strain eases within a day of rest, while infections need treatment",
  red="you have sudden vision loss, eye pain, strong redness, flashes or floaters",
  meds="Please avoid putting any eye drops in without a doctor's advice."),
 dict(id="ent", label="ear or nose problem", spec="ENT Specialist",
  rx=r"ear ?(ache|pain)|pain in (my )?ear|ear discharge|sinus|nose ?bleed|hearing|ringing in",
  causes="a cold, allergy, sinus infection, wax or an ear infection",
  care=["keep the ear dry and never put anything inside it", "steam inhalation can ease sinus pressure", "for a nosebleed, sit upright, lean forward and pinch the soft part of the nose for 10 minutes", "avoid blowing your nose hard"],
  eat="warm fluids and plenty of water", avoid="cold drinks and dusty places",
  dur="Cold-related ear and sinus problems settle in about a week",
  red="there is ear discharge, hearing loss, severe pain, or a nosebleed that does not stop after 15 minutes",
  meds="Ear drops should only be used after a doctor has looked at the ear."),
 dict(id="sugar", label="blood sugar", spec="Endocrinologist",
  rx=r"diabet|blood sugar|sugar level|excessive thirst|always thirsty|frequent urination|\bhba1c|thyroid",
  causes="diabetes or pre-diabetes, diet, weight, family history and, for thyroid problems, hormone imbalance",
  care=["prefer whole grains, vegetables and protein, and limit sweets and sugary drinks", "walk or exercise about 30 minutes most days", "take any prescribed medicines on time", "check your sugar as your doctor advised"],
  eat="whole grains, millets, dal, vegetables, sprouts and nuts in moderation", avoid="sweets, sugary drinks, white bread, fried snacks and skipping meals",
  dur="Blood sugar is managed long term, and food and exercise show an effect within weeks",
  red="you feel very thirsty, pass urine often, lose weight without trying, feel unusually tired, or your readings stay high",
  meds="Diabetes and thyroid medicines must be prescribed and adjusted by a doctor, so please do not start or stop them yourself."),
 dict(id="bp", label="blood pressure", spec="Cardiologist",
  rx=r"blood pressure|\bbp\b|hypertension",
  causes="too much salt, stress, obesity, lack of exercise or family history",
  care=["reduce salt, pickles and processed food", "stay active, sleep well and manage stress", "measure your BP at the same time each day and write it down", "take prescribed medicines regularly"],
  eat="fruits, vegetables, banana, oats and low-salt home food", avoid="salt, pickles, papad, packaged snacks and smoking",
  dur="Blood pressure improves over weeks with lifestyle changes and treatment",
  red="your reading is above 180/120, or you have chest pain, severe headache, vision changes or breathlessness",
  meds="BP tablets must be chosen by a doctor, and should not be stopped suddenly."),
 dict(id="urine", label="urinary problem", spec="Urologist",
  rx=r"urin|kidney|\buti\b|burning (while|during)|bladder|pee\b",
  causes="a urinary infection, not drinking enough water or kidney stones",
  care=["drink plenty of water through the day", "do not hold urine for long and keep the area clean", "wear loose cotton underwear", "avoid self-medicating with antibiotics"],
  eat="plenty of water, coconut water and buttermilk", avoid="too much tea, coffee, alcohol and very spicy food",
  dur="A simple urinary infection improves within 2 to 3 days of the right treatment",
  red="you see blood in the urine, have fever, back or side pain, or the burning does not settle in a day or two",
  meds="Urinary infections need a urine test and the right antibiotic from a doctor, so please do not take leftover antibiotics."),
 dict(id="mind", label="stress, anxiety or poor sleep", spec="Psychiatrist",
  rx=r"anxi|stress|panic|depress|sleep|insomnia|worry|low mood|feeling sad|overthink|tension|mental",
  causes="work or study pressure, worry, a lack of routine, caffeine or a lot of screen time at night",
  care=["keep a fixed sleep and wake time", "try slow breathing: inhale 4 seconds, exhale 6, for a few minutes", "talk to someone you trust and take short walks in daylight", "avoid phones and caffeine late in the evening"],
  eat="regular meals, fruits, nuts and a warm glass of milk at night", avoid="late tea or coffee, skipping meals and alcohol",
  dur="Stress-related sleep problems often improve in a few weeks once routines settle",
  red="these feelings last more than 2 weeks, affect your work or daily life, or you feel hopeless; a psychiatrist or counsellor can help a lot",
  meds="Sleep and anxiety medicines should only be taken on a doctor's prescription."),
 dict(id="women", label="period or women's health concern", spec="Gynecologist",
  rx=r"period|menstru|pregnan|pcos|cramps|\bpcod\b|white discharge|breast",
  causes="hormonal changes, stress, weight change, PCOS or thyroid problems",
  care=["track your cycle dates and symptoms in a notebook or app", "use a warm compress and light exercise for cramps", "eat iron-rich food and stay hydrated", "get enough sleep"],
  eat="iron-rich food (dates, spinach, jaggery), fruits and plenty of water", avoid="skipping meals and too much caffeine",
  dur="Period cramps usually last 1 to 3 days",
  red="bleeding is very heavy, pain is severe, periods are missing for 2 or more months, or you could be pregnant",
  meds="Please check with a doctor before taking hormonal or strong pain medicines."),
 dict(id="breath", label="breathing difficulty", spec="Pulmonologist",
  rx=r"asthma|wheez|breath|short(ness)? of breath|\bsnor",
  causes="asthma, allergy, infection, anxiety or heart and lung conditions",
  care=["sit upright, stay calm and breathe slowly", "avoid dust, smoke and strong smells", "use your prescribed inhaler as directed, if you have one", "keep the room well ventilated"],
  eat="warm fluids and light meals", avoid="smoking, dust and cold air",
  dur="Mild breathlessness from a cold settles with the cold, but breathing trouble should not be ignored",
  red="you are struggling to breathe, your lips look bluish, or you cannot speak a full sentence (seek emergency care immediately)",
  meds="Inhalers and breathing medicines must be prescribed by a doctor."),
 dict(id="tooth", label="toothache", spec="General Physician",
  rx=r"tooth|teeth|\bgum\b|dental|cavity",
  causes="a cavity, gum infection or a sensitive or broken tooth",
  care=["rinse with warm salt water", "brush gently and floss to remove food stuck between teeth", "use a cold compress on the cheek for swelling", "avoid very hot, cold or sweet food"],
  eat="soft, lukewarm food", avoid="sweets, very hot or cold drinks and chewing on the sore side",
  dur="Tooth pain does not usually go away on its own until the cause is treated",
  red="you have facial swelling, fever, or pain that keeps you awake; please see a dentist soon",
  meds="A dentist should decide on painkillers or antibiotics for tooth problems."),
 dict(id="diet", label="diet and weight", spec="General Physician",
  rx=r"\bdiet\b|weight (loss|gain)|lose weight|gain weight|overweight|obes|calorie|nutrition|healthy eating|\bfat\b",
  causes="eating habits, low activity, sleep, stress or a medical condition",
  care=["fill half your plate with vegetables and add protein at every meal", "aim for about 150 minutes of walking or exercise per week", "sleep 7 to 8 hours and drink enough water", "cut sugary drinks and fried snacks gradually"],
  eat="vegetables, dal, eggs, sprouts, fruits, curd and whole grains", avoid="sugary drinks, deep-fried snacks, junk food and skipped meals",
  dur="Healthy weight change is slow, about 0.5 to 1 kg per week",
  red="you are losing or gaining weight quickly without trying, or have a medical condition",
  meds="Please avoid weight-loss pills or supplements without a doctor's advice."),
 dict(id="tired", label="tiredness and weakness", spec="General Physician",
  rx=r"tired|fatigue|weakness|weak\b|low energy|immun|vitamin|dizz|giddy",
  causes="poor sleep, low iron or vitamin levels, stress, dehydration or an underlying illness",
  care=["sleep 7 to 8 hours at a fixed time", "eat regular, balanced meals with protein and iron", "drink 2 to 3 litres of water a day", "get some sunlight and light exercise"],
  eat="dates, leafy greens, eggs, nuts, fruits, dal and plenty of water", avoid="skipping meals and too much tea or coffee",
  dur="Tiredness from poor sleep or diet improves in a few days once you correct them",
  red="it lasts more than 2 weeks or comes with weight change, pale skin, dizziness or breathlessness; simple blood tests can find the cause",
  meds="Iron or vitamin tablets should be taken after a blood test shows you need them."),
]
FOCUS = {"Cardiologist": "heart and blood-pressure problems", "Dermatologist": "skin, hair and nail problems", "Neurologist": "headaches, nerve and brain-related problems",
  "Orthopedic": "bone, joint and muscle problems", "Gastroenterologist": "stomach and digestive problems", "Pulmonologist": "lung and breathing problems",
  "ENT Specialist": "ear, nose and throat problems", "Ophthalmologist": "eye problems", "Endocrinologist": "diabetes, thyroid and hormone problems",
  "Psychiatrist": "stress, sleep, anxiety and mood concerns", "Urologist": "urinary and kidney problems", "Gynecologist": "women's health and pregnancy care",
  "Pediatrician": "children's health", "General Physician": "general illnesses like fever, weakness and infections"}

RED_FLAGS = re.compile(r"chest pain|can.?t breathe|difficulty (in )?breathing|short(ness)? of breath|unconscious|faint|stroke|severe bleeding|heavy bleeding|seizure|vomiting blood|blood in (stool|vomit)", re.I)
CRISIS = re.compile(r"suicid|kill myself|end my life|self.?harm|want to die", re.I)
CHILD = re.compile(r"\b(child|baby|infant|toddler|kid|kids|my son|my daughter|newborn)\b", re.I)

# ------------------------------------------------------------------ understanding the message
_COMPOUND = [(r"stomach ?ache|stomach ?pain", "stomach pain"), (r"tummy ?(ache|pain)|belly ?(ache|pain)", "stomach pain"), (r"body ?ache|body ?pain", "body pain"),
             (r"back ?ache", "back pain"), (r"tooth ?ache", "toothache"), (r"ear ?ache", "ear pain"), (r"head ?ache", "headache"), (r"throat ?(ache|pain)", "sore throat"),
             (r"chest ?pain", "chest pain"), (r"eye ?(ache|pain)", "eye pain"), (r"leg ?(ache|pain)", "leg pain"), (r"joint ?(ache|pain)", "joint pain"), (r"neck ?(ache|pain)", "neck pain")]
_VOCAB = ["fever", "headache", "migraine", "cough", "sneezing", "throat", "acidity", "gastric", "vomiting", "diarrhea", "constipation", "stomach", "itching", "pimples",
          "dandruff", "shoulder", "sprain", "vision", "diabetes", "pressure", "urine", "urination", "anxiety", "stress", "insomnia", "periods", "pregnancy", "asthma",
          "breathing", "wheezing", "weight", "exercise", "tiredness", "weakness", "thyroid", "toothache", "chest", "palpitations", "allergy", "injury", "fracture",
          "swelling", "dizziness", "bleeding", "headache", "cholesterol", "infection", "nausea", "cramps", "rash", "knee", "joint", "sinus", "tonsils", "depression"]


def _dist(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


_TYPOS = {"cogh": "cough", "cof": "cough", "fver": "fever", "fevr": "fever", "hedache": "headache", "vomting": "vomiting", "loosemotion": "diarrhea"}


def _fix_word(w):
    if w in _TYPOS: return _TYPOS[w]
    if len(w) < 5 or not w.isalpha() or w in _VOCAB: return w
    limit = 1 if len(w) < 8 else 2
    best = min((v for v in _VOCAB if v[0] == w[0] and abs(len(v) - len(w)) <= limit), key=lambda v: _dist(w, v), default=None)
    return best if best and _dist(w, best) <= limit else w


def normalize(msg: str) -> str:
    t = msg.lower()
    for rx, rep in _COMPOUND:
        t = re.sub(rx, rep, t)
    out = []
    for w in re.findall(r"[a-z0-9']+|[^a-z0-9'\s]", t):
        out.append(_fix_word(w))                                          # fixes typos like "fevar", "cogh", "acidty"
    return " ".join(out)


def find_topics(msg: str):
    t = normalize(msg)
    hits = []
    for i, k in enumerate(KB):
        m = re.search(k["rx"], t, re.I)
        if m:
            hits.append((m.start(), i))
    return [KB[i] for _, i in sorted(hits)][:2]


def intent(low: str) -> str:
    if re.search(r"which (doctor|specialist)|what (doctor|specialist|kind of doctor|type of doctor)|who (should|can) i (see|consult|meet)|doctor for|specialist for|consult", low): return "doctor"
    if re.search(r"how long|how many days|how much time|when will (it|this|i)|duration|how soon", low): return "duration"
    if re.search(r"is (it|this|that) (serious|dangerous|normal|bad|harmful|risky)|should i (worry|be worried)|serious\??$|dangerous", low): return "serious"
    if re.search(r"\b(eat|food|foods|diet|drink|fruits?|vegetables?|avoid)\b", low) and re.search(r"what|which|can i|should i|avoid|good for|best|allowed", low): return "diet"
    if re.search(r"\b(medicine|medicines|medication|tablets?|pills?|drugs?|syrup|paracetamol|ointment|cream|antibiotics?|painkillers?|dose|capsules?|injection)\b", low): return "meds"
    if re.search(r"\bwhy\b|cause|reason|how (do|did) i get|how come|what is behind", low): return "cause"
    if re.search(r"what (can|should|do) i do|how (to|do i|can i|should i)|remed|home|tips?|cure|relief|relieve|treat|solution|manage|prevent|reduce|get rid|stop|help", low): return "howto"
    return "statement"


def _h(key, n, salt=""):
    return int(hashlib.md5((salt + key).encode()).hexdigest(), 16) % n


def _pick(opts, key, salt=""):
    return opts[_h(key, len(opts), salt)]


def _with_a(spec):
    if spec == "Orthopedic": spec = "Orthopedic doctor"
    return ("an " if spec[:1] in "AEIO" else "a ") + spec


def _cap(s):
    return s[:1].upper() + s[1:]


def _and(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ------------------------------------------------------------------ writing the answer
def _topic_answer(k, it, key, k2=None, child=False):
    care, lab = k["care"], k["label"]
    me = "your child's" if child else "your"
    if it == "howto":
        steps = "\n".join(f"{i + 1}. {_cap(c)}." for i, c in enumerate(care))
        body = _pick([f"Here is how to ease {me} {lab}:\n{steps}\nIf it does not improve, or if {k['red']}, please see a doctor.",
                      f"A few practical steps for {lab}:\n{steps}\nSee a doctor sooner if {k['red']}."], key, "h")
    elif it == "cause":
        body = _pick([f"{_cap(lab)} is commonly caused by {k['causes']}.\nNoting when it happens (after meals, at night, during stress) helps a doctor find the exact cause.\nSee a doctor if {k['red']}.",
                      f"The usual reasons for {lab} are {k['causes']}.\nKeep a short diary of triggers for a few days, since it makes the diagnosis easier.\nGet checked if {k['red']}."], key, "c")
    elif it == "serious":
        body = (f"Most cases of {lab} are manageable, but how serious yours is depends on the details.\n"
                f"It is usually due to {k['causes']}.\nTreat it as urgent if {k['red']}.\nOtherwise rest, follow the simple steps above for a day or two and watch how it changes.")
    elif it == "diet":
        body = _pick([f"For {lab}, food choices really help:\n• Good choices: {k['eat']}.\n• Better to avoid: {k['avoid']}.\nKeep meals small and regular and drink enough water.",
                      f"Diet tips for {lab}:\nEat: {k['eat']}.\nAvoid: {k['avoid']}.\nIf it continues despite diet changes, please get checked."], key, "d")
    elif it == "meds":
        body = (f"I can't recommend specific medicines or doses, because the right one depends on your age, health and other medicines. {k['meds']}\n"
                f"What you can safely do meanwhile:\n• {_cap(care[0])}.\n• {_cap(care[1])}.\nA pharmacist or doctor can advise you on the right medicine.")
    elif it == "duration":
        body = f"{k['dur']}.\nIf it lasts longer than that, or if {k['red']}, please see a doctor."
    elif it == "doctor":
        body = (f"For {lab}, the right specialist is {_with_a(k['spec'])}, who treats {FOCUS.get(k['spec'], 'this kind of problem')}.\n"
                "Before the visit, note when it started, what makes it better or worse, and any medicines you already take.")
    else:                                                    # plain symptom statement: three different shapes
        opener = _pick([f"I'm sorry you're dealing with {lab}." if not child else f"I'm sorry your child is unwell with {lab}.", f"Thanks for telling me about {me} {lab}.", f"That sounds uncomfortable. Let's look at {me} {lab}.",
                        f"Let's see how we can help with {me} {lab}."], key, "o")
        v = _h(key, 3, "s")
        if v == 0:
            body = f"{opener} It is usually due to {k['causes']}.\n\nWhat tends to help: {care[0]}, {care[1]}, and {care[2]}.\n\nGet it checked soon if {k['red']}."
        elif v == 1:
            body = f"{opener}\nHere is a simple plan:\n1. {_cap(care[0])}.\n2. {_cap(care[1])}.\n3. {_cap(care[2])}.\nWatch out: {k['red']}."
        else:
            body = (f"{opener}\nLikely reasons: {k['causes']}.\nYou can try:\n• {_cap(care[0])}\n• {_cap(care[1])}\n• {_cap(care[3] if len(care) > 3 else care[2])}\n"
                    f"See a doctor if: {k['red']}.")
    if k2 and it in ("statement", "howto", "cause"):
        body += f"\n\nAbout {me} {k2['label']} as well: {k2['care'][0]}. Mention it to the doctor if it continues."
    if child and it != "doctor":
        body += "\n\nSince this is about a child, please do not give any medicine without a doctor's advice on the right dose."
    return body


_DOC_LINES = ["{A} is the right specialist for this. You can book one below.", "For a proper check-up, {a} would be the best person to see. Pick a doctor below.",
              "I'd suggest consulting {a}. You can book an appointment with the doctors listed below."]


def analyze(message: str, history=None) -> dict:
    """Returns {'reply': str|None, 'spec': str|None}. reply is None only when nothing health-related was recognised."""
    m = message.strip()
    low = normalize(m)
    key = low
    if CRISIS.search(m):
        return {"reply": ("I'm really sorry you are feeling this way, and I'm glad you told me. You deserve support right now.\n"
                          "Please contact your local emergency number or a crisis helpline (in India, Tele-MANAS: 14416), or tell someone you trust so you are not alone.\n"
                          "If you like, you can book an appointment with a psychiatrist below."), "spec": "Psychiatrist"}
    topics = find_topics(m)
    it = intent(low)
    # follow-up questions ("what should I eat?") use the topic from the earlier messages
    app_help = re.search(r"\bbook\b|\bbooking|appointment|\bslot|availab|cancel|\breport|prescription|who are you|what can you do", low)
    if not topics and it != "statement" and history and not app_help:
        for h in reversed([x for x in history if x.get("role") == "user"]):
            topics = find_topics(h.get("content", ""))
            if topics: break
    words = re.findall(r"[a-z']+", low)
    if not topics:
        if len(words) <= 4 and re.match(r"(hi|hello|hey|hii+|good (morning|afternoon|evening)|vanakkam|namaste)", low):
            return {"reply": _pick(["Hello! I'm your AI Health Assistant. Tell me your symptoms or ask any health question, and I'll guide you.",
                                    "Hi there! How are you feeling today? Describe your symptoms and I'll suggest the right doctor."], key), "spec": None}
        if re.search(r"\bthank|\bthanks|thx|\bbye\b|^ok(ay)?$", low):
            return {"reply": _pick(["You're welcome! Take care, and ask me anytime.", "Happy to help. Stay healthy!"], key), "spec": None}
        if re.search(r"cancel", low) and re.search(r"appointment|booking", low):
            return {"reply": "To cancel, open Appointments in the left menu and click Cancel next to the booking. The slot becomes free for others.", "spec": None}
        if re.search(r"\bbook|appointment|slot|availab", low):
            return {"reply": "Booking is easy:\n1. Open Doctors in the left menu (or use a Book button here).\n2. Choose a doctor and pick a date.\n3. Select a free 30-minute slot and click Confirm.\nYou can see all bookings under Appointments or the Patient Dashboard.", "spec": None}
        if re.search(r"report|prescription", low):
            return {"reply": "Use Report Explainer in the left menu. Paste your diagnosis or prescription, or upload a .txt, .pdf or .docx file, and I'll explain it in simple words.", "spec": None}
        if re.search(r"who are you|what can you do|your name", low):
            return {"reply": "I'm the SmartCare AI Health Assistant. I can give general guidance for common symptoms, tell you which type of doctor to see, and help you book, view or cancel appointments. I can't diagnose or prescribe.", "spec": None}
        if re.search(r"pain|hurt|ache|sick|\bill\b|unwell|problem|feel|symptom|swell|bleed|injur|infect|health|medicine|body|burning|itch|tired|weak|cannot|can't|not able", low):
            return {"reply": ("I want to give you the right advice, so could you tell me a little more?\n• Where exactly do you feel it, or what is the main symptom?\n• Since when have you had it?\n"
                              "• Is it mild, moderate or severe?\nUntil then, rest, drink water and avoid self-medicating. A General Physician can examine you properly, and you can book one below."), "spec": "General Physician"}
        return {"reply": None, "spec": None}
    k, k2 = topics[0], (topics[1] if len(topics) > 1 else None)
    child = bool(CHILD.search(m)) or any(CHILD.search(h.get("content", "")) for h in (history or [])[-2:] if h.get("role") == "user")
    spec = "Pediatrician" if child else k["spec"]
    parts = []
    if RED_FLAGS.search(m) or k["id"] == "chest" and it == "statement":
        parts.append("Important: this can be serious. If it is severe or getting worse, please seek emergency medical care or call your local emergency number right away.")
    parts.append(_topic_answer(k, it, key, k2, child))
    if it not in ("doctor", "diet"):
        line = _pick(_DOC_LINES, key, "l").format(a=_with_a(spec), A=_cap(_with_a(spec)))
        if k2 and k2["spec"] != spec and not child:
            line += f" ({_cap(_with_a(k2['spec']))} can help with the {k2['label']}.)"
        parts.append(line)
    return {"reply": "\n\n".join(parts), "spec": spec}


def detect_spec(message: str, history=None):
    """Which specialist fits this message (used to show doctors even when a real LLM writes the answer)."""
    try:
        return analyze(message, history)["spec"]
    except Exception:
        return None
