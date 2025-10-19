# sentiment_model.py
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import re
import emoji
import pandas as pd
from tqdm import tqdm

# Paste your rules_dict and EnhancedTeluguPreprocessor here (same as your code)
# ...
rules_dict={
  "phonetic_mappings": {
    "ph": "f", "wh": "v", "zh": "z", "dh": "d", "bh": "b", "gh": "g",
    "kh": "k", "th": "t", "ch": "c",
    "yy": "y", "zz": "z", "nn": "n",
    "rr": "r", "tt": "t", "ll": "l", "mm": "m",
    "kk": "k", "pp": "p", "dd": "d", "gg": "g", "bb": "b", "ss": "s", "cc": "c"
  },
  "vowel_mappings": {
    "aa": "a", "aaa": "a", "aaaa": "a",
    "ee": "e", "eee": "e",
    "ii": "i", "iii": "i",
    "oo": "o", "ooo": "o",
    "uu": "u", "uuu": "u",
    "ai": "ai", "ay": "ai",
    "au": "au", "ow": "au",
    "ei": "e", "ey": "e"
  },
  "standard_spellings": {
    "nenu": "nenu", "nennu": "nenu", "nen": "nenu",
    "meeru": "meeru", "miru": "meeru", "meru": "meeru",
    "vadu": "vadu", "wadu": "vadu", "vaadu": "vadu",
    "vadi": "vadi", "wadi": "vadi",
    "idi": "idi", "idhi": "idi", "idee": "idi",
    "adi": "adi", "adhi": "adi", "adee": "adi",
    "chesanu": "chesanu", "cesanu": "chesanu", "cheshanu": "chesanu",
    "chesaru": "chesaru", "cesaru": "chesaru", "chesharu": "chesaru",
    "chestanu": "chestanu", "cestanu": "chestanu",
    "cheyali": "cheyali", "cheyyali": "cheyali", "ceyali": "cheyali",
    "unnaru": "unnaru", "unnaaru": "unnaru", "unaaru": "unnaru",
    "undi": "undi", "undhi": "undi", "vundi": "undi",
    "unnadi": "unnadi", "vunnadi": "unnadi", "unnadhi": "unnadi",
    "vacchanu": "vacchanu", "vachchanu": "vacchanu", "vachchaanu": "vacchanu",
    "vellanu": "vellanu", "wellanu": "vellanu", "vellaanu": "vellanu",
    "poyanu": "poyanu", "pooyanu": "poyanu", "poyaanu": "poyanu",
    "chusanu": "chusanu", "chushanu": "chusanu", "cuusanu": "chusanu",
    "chala": "chala", "chaala": "chala", "chaalaa": "chala", "cala": "chala",
    "bagundi": "bagundi", "baagundi": "bagundi", "bhagundi": "bagundi", "bagundhee": "bagundi",
    "manchi": "manchi", "manchee": "manchi", "maanci": "manchi",
    "manchidi": "manchidi", "maanchidi": "manchidi",
    "chetta": "chetta", "chettha": "chetta", "cheddha": "chetta",
    "chettadi": "chettadi", "chetthadi": "chettadi",
    "worst": "worst", "worstu": "worst",
    "better": "better", "bettar": "better",
    "pedda": "pedda", "peddha": "pedda", "pedhdha": "pedda",
    "chinna": "chinna", "chinnaa": "chinna", "cinna": "chinna",
    "kadu": "kadu", "kadhu": "kadu", "kaadu": "kadu", "kaadhu": "kadu",
    "ledu": "ledu", "ledhu": "ledu", "leedhu": "ledu", "leduu": "ledu",
    "leru": "leru", "leruu": "leru", "leeru": "leru",
    "enti": "enti", "yenti": "enti", "entee": "enti", "yentee": "enti",
    "ela": "ela", "elaa": "ela", "yela": "ela", "yelaa": "ela",
    "evaroo": "evaru", "evaru": "evaru", "yevaru": "evaru",
    "eppudu": "eppudu", "yeppudu": "eppudu", "eppudoo": "eppudu",
    "garu": "garu", "gaaru": "garu", "garuu": "garu",
    "kani": "kani", "kaani": "kani", "gaani": "kani",
    "kuda": "kuda", "kudaa": "kuda", "kooda": "kuda",
    "inka": "inka", "inkaa": "inka", "inko": "inka",
    "party": "party", "parti": "party", "paartee": "party",
    "leader": "leader", "leadar": "leader", "neta": "leader",
    "minister": "minister", "ministar": "minister",
    "government": "government", "governmentu": "government", "govt": "government",
    "policy": "policy", "policee": "policy", "polici": "policy",
    "decision": "decision", "decishun": "decision", "desijan": "decision"
  },
  "telugu_stop_words": ["oo","aa","ee","oh","ayya","amma","ante","anna","mari","sare","okay","ok","hmm","haa","kaadu"],
  "sentiment_words": {
    "positive": ["bagundi","manchi","manchidi","bagunna","manchiga","santosham","khushi","happy","better","best","great","excellent","super","superb","awesome","wonderful","goppa","goppaga","bhale","bavundi","bavunna"],
    "negative": ["chetta","chettadi","chettaga","worst","bad","terrible","horrible","durbaga","bada","badha","badakaram","kopam","anger","waste","useless"],
    "neutral": ["sare","okay","okayish","normal","sadarana","tatvam"]
  },
  "negation_words": ["kadu","kadhu","kaadu","ledu","ledhu","leru","not","no","never","neither","nor","nothing","kani","kaani","but","however"],
  "abbreviations": {
    "cm": "chief minister","pm": "prime minister","mla": "mla","mp": "mp",
    "tdp": "tdp","ysrcp": "ysrcp","bjp": "bjp","inc": "congress","janasena": "janasena",
    "lol": "laughing","lmao": "laughing","smh": "disappointed","wtf": "shocked","omg": "surprised",
    "fyi": "information","btw": "by the way","imo": "in my opinion","em": "enti","emiti": "enti","evd": "evadu","evr": "evaru"
  },
  "code_switch_markers": ["but","kani","kaani","and","mariyu","or","leda"],
  "emoji_positive": ["😊","😃","😄","👍","❤️","💕","🎉","✨","🙏","👏","💪"],
  "emoji_negative": ["😞","😢","😠","😡","👎","💔","😤","🤬","😭"],
  "emoji_sarcastic": ["🙄","😏","🤔","😒","🤨"],

  "booster_words": ["chaala","super","goppa","bhale","bavundi","bavunna","best","excellent","great","really"],
  "textual_sarcasm_cues": ["😂","🙄","😏","lol","lmao","kidding","just kidding","really","wow"],
  "translit_variants": {
    "nennu":"nenu",
    "miru":"meeru",
    "vunnadi":"unnadi",
    "chusanu":"chusanu",
    "chesanu":"chesanu",
    "bagundi":"bagundi",
    "chettadi":"chettadi"
  }
}

class EnhancedTeluguPreprocessor:
    def __init__(self, rules_dict=rules_dict):
        self.rules = rules_dict
        # Convert lists to dicts for _apply_rules
        self.negations = {word: "not" for word in self.rules.get("negation_words", [])}
        self.boosters = {word: word for word in self.rules.get("booster_words", [])}
        self.translit_variants = self.rules.get("translit_variants", {})
        self.punctuation_pattern = re.compile(r"[^\w\s]", re.UNICODE)

    def _apply_rules(self, text, mapping):
        for key, val in mapping.items():
            text = re.sub(rf"\b{re.escape(key)}\b", val, text, flags=re.IGNORECASE)
        return text

    def _normalize_emoji(self, text):
        for char in text:
            if char in emoji.EMOJI_DATA:
                desc = emoji.demojize(char)
                if any(pos in desc for pos in ["smile", "joy", "heart", "thumbsup", "clap", "tada", "pray"]):
                    text += " positive"
                elif any(neg in desc for neg in ["angry", "sad", "thumbsdown", "cry", "frown", "rage"]):
                    text += " negative"
        return text

    def preprocess(self, text):
        if not isinstance(text, str):
            return ""
        text = text.strip().lower()
        text = self._apply_rules(text, self.translit_variants)
        text = self._apply_rules(text, self.negations)
        text = self._apply_rules(text, self.boosters)
        text = self._normalize_emoji(text)
        text = self.punctuation_pattern.sub("", text)
        return text

# ------------------------
# Sentiment Model Wrapper
# ------------------------
class MuRILSentiment:
    def __init__(self, model_name="DSL-13-SRMAP/MuRIL_WR", rules_dict=rules_dict):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(self.device)
        self.preprocessor = EnhancedTeluguPreprocessor(rules_dict)
        self.labels = ["negative", "neutral", "positive"]

    def _contains_telugu(self, text):
        return bool(re.search(r'[\u0C00-\u0C7F]', text))

    def predict(self, text):
        if self._contains_telugu(text):
            processed_text = text.strip()
        else:
            processed_text = self.preprocessor.preprocess(text)
        inputs = self.tokenizer(processed_text, return_tensors="pt", truncation=True, padding=True).to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
        probs = F.softmax(logits, dim=-1).squeeze().cpu().numpy()
        pred_idx = probs.argmax()
        sentiment = self.labels[pred_idx]
        confidence = probs[pred_idx] * 100
        return sentiment, confidence

# ------------------------
# Emoji Removal Function
# ------------------------
def remove_emojis(text):
    if not isinstance(text, str):
        return text
    return emoji.replace_emoji(text, replace='')

# ------------------------
# Sentiment Analysis on DataFrame
# ------------------------
def analyze_comments(df: pd.DataFrame, column="Comments") -> pd.DataFrame:
    df[column] = df[column].fillna("").astype(str).apply(remove_emojis).str.strip()
    model = MuRILSentiment(model_name="DSL-13-SRMAP/MuRIL_WR", rules_dict=rules_dict)
    sentiments, confidences = [], []

    for text in tqdm(df[column], desc="Analyzing Sentiments", disable=True):
        sentiment, confidence = model.predict(text)
        sentiments.append(sentiment)
        confidences.append(confidence)

    df['Sentiment_label'] = sentiments
    df['Confidence_score'] = confidences
    sentiment_map = {"negative": -1, "neutral": 0, "positive": 1}
    df['Sentiment_score'] = df['Sentiment_label'].map(sentiment_map)
    return df
