# ----------------------------------
# app.py (Streamlit frontend)
# ----------------------------------
import streamlit as st
import requests
import pandas as pd
import time
import uuid
from io import BytesIO
from zipfile import ZipFile

# -------------------------------
# Sentiment Analysis Imports
# -------------------------------
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import re
import emoji
from tqdm import tqdm

# -------------------------------
# GitHub Repo Details
# -------------------------------
REPO = "AP07AP/instagram-scraper-streamlit"
WORKFLOW_ID = "scraper.yml"
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
ARTIFACT_NAME = "scraped_data"  # fallback name

# -------------------------------
# Dashboard Title
# -------------------------------
st.title("📸 Instagram Analyser Dashboard")

# -------------------------------
# Scraper Inputs
# -------------------------------
profile_url = st.text_area(
    "Enter one or more Instagram Profile URLs (comma-separated or one per line)",
    height=20,
    placeholder="https://www.instagram.com/user1/"
)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date")
with col2:
    end_date = st.date_input("End Date")

username = st.text_input("Instagram Username")

# -------------------------------
# Helper: Indian number format
# -------------------------------
def format_indian_number(number):
    try:
        s = str(int(number))
    except:
        return "0"
    if len(s) <= 3:
        return s
    last3 = s[-3:]
    remaining = s[:-3]
    parts = []
    while len(remaining) > 2:
        parts.append(remaining[-2:])
        remaining = remaining[:-2]
    if remaining:
        parts.append(remaining)
    return ','.join(reversed(parts)) + ',' + last3

# -------------------------------
# Function to fetch artifact CSV
# -------------------------------
def fetch_artifact_csv(repo, token, artifact_name=ARTIFACT_NAME):
    headers = {"Authorization": f"Bearer {token}"}

    # Wait for artifact to appear (max 2 mins)
    artifact_found = False
    for _ in range(600):
        artifacts = requests.get(f"https://api.github.com/repos/{repo}/actions/artifacts", headers=headers).json().get("artifacts", [])
        if any(a["name"] == artifact_name for a in artifacts):
            artifact_found = True
            break
        time.sleep(6)

    if not artifact_found:
        st.error(f"❌ Artifact {artifact_name} not found yet. Try again in a few seconds.")
        st.stop()

    # Download artifact
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/artifacts", headers=headers)
    artifacts = r.json().get("artifacts", [])
    artifact = next((a for a in artifacts if a["name"] == artifact_name), None)
    if not artifact:
        st.error(f"❌ Artifact {artifact_name} not found.")
        return None

    download_url = artifact["archive_download_url"]
    r = requests.get(download_url, headers=headers)
    if r.status_code != 200:
        st.error("❌ Failed to download artifact.")
        return None

    zipfile = ZipFile(BytesIO(r.content))
    csv_filename = zipfile.namelist()[0]
    with zipfile.open(csv_filename) as f:
        df = pd.read_csv(f)
    return df

# -------------------------------
# SCRAPE BUTTON
# -------------------------------
if st.button("🕸️ Scrape Data"):
    if not profile_url or not username:
        st.warning("⚠️ Please fill all fields before scraping.")
        st.stop()

    unique_id = uuid.uuid4().hex[:6]
    st.session_state["artifact_name"] = f"scraped_data_{username}_{unique_id}"

    st.info(f"🚀 Triggering scraper workflow for artifact: `{st.session_state['artifact_name']}`")

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }

    payload = {
        "ref": "main",
        "inputs": {
            "profile_url": ",".join([p.strip() for p in profile_url.replace("\n", ",").split(",") if p.strip()]),
            "start_date": str(start_date),
            "end_date": str(end_date),
            "username": username,
            "artifact_name": st.session_state["artifact_name"],
        },
    }

    r = requests.post(
        f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_ID}/dispatches",
        headers=headers,
        json=payload,
    )

    if r.status_code != 204:
        st.error(f"❌ Failed to trigger workflow: {r.text}")
        st.stop()

    st.info("⏳ Waiting for workflow to complete (up to 5 mins)...")

    workflow_completed = False
    for _ in range(600):
        runs = requests.get(f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_ID}/runs", headers=headers).json()
        latest_run = runs.get("workflow_runs", [None])[0]
        if latest_run and latest_run.get("status") == "completed":
            workflow_completed = True
            break
        time.sleep(6)

    if workflow_completed:
        st.success("🔄 Scraping in progress...")
        st.session_state["scrape_done"] = True
    else:
        st.error("❌ Workflow timed out.")
        st.session_state["scrape_done"] = False

# -------------------------------
# REPORT BUTTON (enabled after scrape)
# -------------------------------
if st.session_state.get("scrape_done", False):
    if st.button("📊 Get Report"):
        artifact_name = st.session_state.get("artifact_name", ARTIFACT_NAME)
        st.info(f"📦 Fetching artifact `{artifact_name}` ...")

        df = fetch_artifact_csv(REPO, GITHUB_TOKEN, artifact_name)
        if df is None or df.empty:
            st.warning("⚠️ No data found in your artifact.")
            st.stop()

        st.session_state["scraped_df"] = df
        st.success("✅ Your report is ready!")

# -------------------------------
# SENTIMENT MODEL CLASSES
# -------------------------------
# Paste your rules_dict, EnhancedTeluguPreprocessor, MuRILSentiment classes here (from your snippet above)

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
        #with open(rules_path, "r", encoding="utf-8") as f:
            #self.rules = json.load(f)
        self.negations = self.rules.get("negations", {})
        self.boosters = self.rules.get("boosters", {})
        self.translit_variants = self.rules.get("translit_variants", {})
        self.punctuation_pattern = re.compile(r"[^\w\s]", re.UNICODE)

    def _apply_rules(self, text, mapping):
        for key, val in mapping.items():
            text = re.sub(rf"\b{key}\b", val, text, flags=re.IGNORECASE)
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
        text = text.strip().lower()
        text = self._apply_rules(text, self.translit_variants)
        text = self._apply_rules(text, self.negations)
        text = self._apply_rules(text, self.boosters)
        text = self._normalize_emoji(text)
        text = self.punctuation_pattern.sub("", text)
        return text

class MuRILSentiment:
    def __init__(self, model_name="DSL-13-SRMAP/MuRIL_WR", rules_dict=rules_dict):
        print(f"Loading model: {model_name}")
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
        print(f"\nText: {text}")
        print(f"Processed: {processed_text}")
        print(f"Logits: {logits.cpu().numpy()}")
        print(f"Probabilities: {{'negative': {probs[0]:.4f}, 'neutral': {probs[1]:.4f}, 'positive': {probs[2]:.4f}}}")
        print(f"Predicted Sentiment: {sentiment.upper()} | Confidence: {confidence:.2f}%")

        return sentiment, confidence

    def predict_excel(self, input_excel_path, output_excel_path=None):
        # Load Excel
        df = pd.read_excel(input_excel_path)

        if 'clean_text' not in df.columns:
            raise ValueError("Excel must contain a 'clean_text' column.")

        # Emoji mapping
        sentiment_emojis = {
            "negative": "😞",
            "neutral": "😐",
            "positive": "😊"
        }

        # Prepare columns
        sentiments = []
        confidence_scores = []
        sentiment_emojis_list = []

        # Process each text
        for text in tqdm(df['clean_text'], desc="Generating sentiments"):
            sentiment, confidence = self.predict(str(text))
            sentiments.append(sentiment)
            confidence_scores.append(confidence)
            sentiment_emojis_list.append(sentiment_emojis.get(sentiment, ""))

        # Append results
        df['Sentiment_label'] = sentiments
        df['Confidence_score'] = confidence_scores
        df['Sentiment_emoji'] = sentiment_emojis_list

        # Optionally, encode sentiment to numeric score
        sentiment_map = {"negative": -1, "neutral": 0, "positive": 1}
        df['Sentiment_score'] = df['Sentiment_label'].map(sentiment_map)

        # Set output path if not provided
        if output_excel_path is None:
            output_excel_path = input_excel_path.replace(".xlsx", "_sentiment.xlsx")

        # Save Excel
        df.to_excel(output_excel_path, index=False)
        print(f"Sentiment Excel saved to: {output_excel_path}")
        return output_excel_path

#  --------------------------------------------------------------------------------------------------------------------------------------------------
# Initialize sentiment model
if "sentiment_model" not in st.session_state:
    st.session_state.sentiment_model = MuRILSentiment(model_name="DSL-13-SRMAP/MuRIL_WR")

# -------------------------------
# DISPLAY REPORT + SENTIMENT
# -------------------------------
if "scraped_df" in st.session_state:
    df = st.session_state["scraped_df"]

    # -------------------------------
    # Clean data
    # -------------------------------
    df["Likes"] = df["Likes"].astype(str).str.replace(",", "").str.strip()
    df["Likes"] = pd.to_numeric(df["Likes"], errors="coerce").fillna(0)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Time"] = pd.to_datetime(df["Time"], format='%H:%M:%S', errors="coerce").dt.time
    df["Comments"] = df["Comments"].replace("", pd.NA)

    # -------------------------------
    # Sentiment Analysis
    # -------------------------------
    if "sentiment_done" not in st.session_state:
        with st.spinner("🔄 Generating sentiment analysis..."):
            if 'clean_text' not in df.columns:
                df['clean_text'] = df['Caption'].fillna("")
            sentiments = []
            confidences = []
            for text in tqdm(df['clean_text'], desc="Sentiment Analysis"):
                sentiment, confidence = st.session_state.sentiment_model.predict(str(text))
                sentiments.append(sentiment)
                confidences.append(confidence)
            df['Sentiment_Label'] = sentiments
            df['Sentiment_Score'] = [1 if s=="positive" else -1 if s=="negative" else 0 for s in sentiments]
            df['Sentiment_Confidence'] = confidences
        st.session_state["scraped_df"] = df
        st.session_state["sentiment_done"] = True

    # -------------------------------
    # Username summary
    # -------------------------------
    if "username" in df.columns:
        st.markdown("## 👥 Profile Summary")
        summary_df = (
            df.groupby("username")
            .agg(
                Total_Posts=("URL", "nunique"),
                Total_Likes=("Likes", "sum"),
                Total_Comments=("Comments", lambda x: x.notna().sum()),
            )
            .reset_index()
        )
        summary_df["Total_Likes"] = summary_df["Total_Likes"].apply(format_indian_number)
        summary_df["Total_Comments"] = summary_df["Total_Comments"].apply(format_indian_number)
        st.dataframe(summary_df, use_container_width=True)

        selected_users = st.multiselect(
            "Select profiles to explore",
            options=summary_df["username"].tolist(),
        )

        if selected_users:
            df = df[df["username"].isin(selected_users)]

    # -------------------------------
    # Overview metrics
    # -------------------------------
    st.markdown("## Overview")
    col1, col2, col3, col4 = st.columns([1,1,1,1])
    col1.metric("Total Posts", format_indian_number(df["URL"].nunique()))
    col2.metric("Total Likes", format_indian_number(df["Likes"].sum()))
    col3.metric("Total Comments", format_indian_number(df["Comments"].notna().sum()))
    # Sentiment summary
    comments_with_sentiment = df[df["Comments"].notna()]
    if not comments_with_sentiment.empty:
        sentiment_counts = comments_with_sentiment["Sentiment_Label"].value_counts(normalize=True) * 100
        pos_pct = sentiment_counts.get("positive", 0)
        neg_pct = sentiment_counts.get("negative", 0)
        neu_pct = sentiment_counts.get("neutral", 0)
        col4.metric("Positive %", f"{pos_pct:.1f}%")
        # Optional: You can add negative/neutral in other cols or as markdown

    # -------------------------------
    # Post exploration
    # -------------------------------
    st.markdown("## 📌 Explore Posts")
    post_urls = df["URL"].unique().tolist()
    selected_posts = st.multiselect("🔗 Select one or more Posts (URLs)", post_urls)

    if selected_posts:
        multi_posts = df[df["URL"].isin(selected_posts)]
        st.subheader("📝 Selected Posts Details")
        for url in selected_posts:
            post_group = multi_posts[multi_posts["URL"] == url]
            caption_row = post_group[post_group["Caption"].notna()]
            if not caption_row.empty:
                row = caption_row.iloc[0]
                st.markdown(
                    f"**Caption:** {row['Caption']}  \n"
                    f"📅 {row['Date'].date()} 🕒 {row['Time']}  \n"
                    f"❤️ Likes: {row['Likes']} 💬 Comments: {row['Comments']}"
                )

            # Show sentiment per post
            comments_only = post_group[post_group["Comments"].notna()].copy()
            if not comments_only.empty:
                st.dataframe(
                    comments_only[["Comments","Sentiment_Label","Sentiment_Score"]].reset_index(drop=True),
                    use_container_width=True
                )
