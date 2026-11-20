"""
Generate the Symptoms -> Specialization dataset (symptom_dataset.csv).

No suitable free dataset is bundled with this project, so we build one from a
medical knowledge base of typical symptoms per specialization. Each row is a
free-text patient description. To make the task realistic (not trivially
separable) we:
  * share some symptoms between specializations (e.g. "chest pain"),
  * mix in a "noise" symptom from another specialization,
  * use varied sentence templates and word orderings,
  * flip a small percentage of labels (annotation noise).
Run:  python generate_dataset.py
"""
import random
import pandas as pd

SEED = 42
N_PER_CLASS = 300
LABEL_NOISE = 0.03

KB = {
    "Cardiologist": [
        "chest pain", "chest tightness", "palpitations", "irregular heartbeat", "shortness of breath on exertion",
        "pain in left arm", "swelling in legs", "dizziness and fainting", "high blood pressure", "rapid heartbeat",
        "chest pressure while walking", "fatigue with breathlessness", "cold sweats with chest discomfort"],
    "Dermatologist": [
        "skin rash", "itching all over the body", "acne", "red patches on skin", "dry flaky skin", "hair loss",
        "skin allergy", "blisters on skin", "dark spots on face", "fungal infection between toes", "peeling skin",
        "itchy scalp with dandruff", "white patches on skin", "boils on skin"],
    "Neurologist": [
        "severe headache", "migraine", "numbness in hands", "tingling in feet", "seizures", "memory loss",
        "tremors in hands", "difficulty in balance", "dizziness and vertigo", "weakness on one side of body",
        "blurred speech", "frequent fainting spells", "pain shooting down the face", "sensitivity to light with headache"],
    "Orthopedic": [
        "knee pain", "joint pain", "back pain", "shoulder pain", "swollen joints", "stiff neck", "fracture after fall",
        "difficulty in walking due to hip pain", "ankle sprain", "muscle pain after injury", "pain in heel",
        "lower back pain radiating to leg", "stiffness in joints in the morning", "pain in elbow while lifting"],
    "Gastroenterologist": [
        "stomach pain", "acidity", "heartburn", "nausea and vomiting", "diarrhea", "constipation", "bloating",
        "blood in stool", "loss of appetite", "indigestion", "pain in upper abdomen", "yellowing of eyes and skin",
        "difficulty swallowing food", "frequent loose motions", "burning sensation in stomach"],
    "Pulmonologist": [
        "persistent cough", "wheezing", "shortness of breath", "breathing difficulty at night", "cough with phlegm",
        "chest congestion", "coughing up blood", "asthma attack", "snoring with breathing pauses",
        "tightness in chest while breathing", "cough lasting more than three weeks", "noisy breathing"],
    "ENT Specialist": [
        "sore throat", "ear pain", "blocked nose", "runny nose", "hearing loss", "ringing in the ears",
        "sinus pressure", "pain while swallowing", "hoarse voice", "nose bleeding", "ear discharge",
        "frequent sneezing", "swollen tonsils", "loss of smell", "facial pain near sinuses"],
    "Ophthalmologist": [
        "blurred vision", "eye pain", "red eyes", "watery eyes", "itchy eyes", "double vision", "difficulty seeing at night",
        "sensitivity to light", "seeing floaters", "eye swelling", "dryness in eyes", "gradual loss of vision",
        "headache after reading", "eye discharge"],
    "Endocrinologist": [
        "excessive thirst", "frequent urination", "sudden weight gain", "unexplained weight loss", "high blood sugar",
        "swelling in neck", "feeling cold all the time", "excessive sweating", "irregular periods with weight gain",
        "extreme fatigue", "hair thinning with dry skin", "increased hunger", "slow healing wounds", "mood swings with weight changes"],
    "Psychiatrist": [
        "anxiety", "depression", "panic attacks", "trouble sleeping", "constant sadness", "mood swings", "loss of interest in activities",
        "excessive worry", "hearing voices", "irritability", "lack of concentration", "feeling hopeless", "stress and insomnia",
        "social withdrawal"],
    "Urologist": [
        "burning during urination", "blood in urine", "pain in lower abdomen while urinating", "kidney stone pain",
        "frequent urination at night", "difficulty passing urine", "pain in the flank", "urinary infection", "weak urine stream",
        "pain in testicles", "feeling of incomplete bladder emptying", "cloudy urine"],
    "Gynecologist": [
        "irregular periods", "painful periods", "heavy menstrual bleeding", "missed period", "pregnancy symptoms",
        "pelvic pain", "vaginal discharge", "pain during intercourse", "pregnancy morning sickness", "breast lump",
        "difficulty conceiving", "spotting between periods", "menopause hot flashes"],
    "Pediatrician": [
        "child has fever", "baby is not feeding", "child has rash and fever", "infant crying continuously",
        "child with cough and cold", "vomiting in toddler", "child not gaining weight", "delayed milestones in child",
        "baby has diarrhea", "child with ear pulling and fever", "my son has stomach ache", "my daughter has a sore throat"],
    "General Physician": [
        "fever", "body ache", "fatigue", "weakness", "mild headache", "chills", "common cold", "loss of energy",
        "fever with body pain", "mild cough and fever", "viral fever", "generally unwell", "tiredness", "muscle aches with fever"],
}

TEMPLATES = [
    "I have {s}", "I am suffering from {s}", "experiencing {s}", "{s}", "I've been having {s} for the last few days",
    "Patient complains of {s}", "I feel {s}", "since last week I have {s}", "my main problem is {s}",
    "for two days I am having {s}", "{s}, please help", "I think I have {s}",
]


def join(symptoms, rng):
    if len(symptoms) == 1:
        return symptoms[0]
    sep = rng.choice([", ", " and ", ", also ", " with "])
    return ", ".join(symptoms[:-1]) + sep + symptoms[-1]


def main():
    rng = random.Random(SEED)
    labels = list(KB)
    rows = []
    for label in labels:
        for _ in range(N_PER_CLASS):
            k = rng.choice([1, 2, 2, 3, 3, 4])
            s = rng.sample(KB[label], min(k, len(KB[label])))
            if rng.random() < 0.25:                      # cross-specialty noise symptom
                other = rng.choice([l for l in labels if l != label])
                s.append(rng.choice(KB[other]))
            rng.shuffle(s)
            text = rng.choice(TEMPLATES).format(s=join(s, rng))
            if rng.random() < 0.3:
                text = text.lower()
            y = label
            if rng.random() < LABEL_NOISE:               # annotation noise
                y = rng.choice([l for l in labels if l != label])
            rows.append((text, y))
    df = pd.DataFrame(rows, columns=["symptoms", "specialization"]).sample(frac=1, random_state=SEED)
    df.to_csv("symptom_dataset.csv", index=False)
    print(f"Saved symptom_dataset.csv  rows={len(df)}  classes={df.specialization.nunique()}")


if __name__ == "__main__":
    main()
