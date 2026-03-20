import string
import json
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LinearRegression

import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.sentiment import SentimentIntensityAnalyzer

# Ensure required NLTK corpora are present in any deployment (e.g., DigitalOcean)
NLTK_RESOURCES = {
    "stopwords": "corpora/stopwords",
    "punkt": "tokenizers/punkt",
    "wordnet": "corpora/wordnet",
    "vader_lexicon": "sentiment/vader_lexicon",
    "punkt_tab": "tokenizers/punkt_tab",
}


def ensure_nltk_resources():
    for resource, path in NLTK_RESOURCES.items():
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(resource, quiet=True)


ensure_nltk_resources()

stop_words = set(stopwords.words('english'))
lemmatizer = WordNetLemmatizer()

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "train5.csv"
NEWS_DATA_PATH = BASE_DIR / "data" / "news_corpus.csv"
MODEL_DIR = BASE_DIR / "models"
VECTORIZER_PATH = MODEL_DIR / "count_vectorizer.joblib"
MODEL_PATHS = {
    "naive bayes": MODEL_DIR / "naive_bayes.joblib",
    "svm": MODEL_DIR / "svm.joblib",
}
SCORE_MODEL_PATH = MODEL_DIR / "score_regressor.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"
_VADER_ANALYZER = None
_VECTORIZER_CACHE = None
_MODEL_CACHE = {}
_SCORE_MODEL_CACHE = None
_METRICS_CACHE = None
DEFAULT_LABELS = ["negative", "neutral", "positive"]


def _normalize_model_name(model_name):
    name = str(model_name).strip().lower()
    if name in ('naive bayes', 'naivebayes', 'nb', 'multinomialnb'):
        return "naive bayes"
    if name in ('svm', 'support vector machine', 'support-vector-machine'):
        return "svm"
    raise ValueError(f"Unknown model_name: {model_name}")

def preprocess(text):
    text = str(text).translate(str.maketrans('', '', string.punctuation))
    text = text.lower()
    token = word_tokenize(text)
    filtered = []
    for i in token:
        if i not in stop_words:
            filtered.append(lemmatizer.lemmatize(i))
    
    return ' '.join(filtered)
    
def read_file(filename):
    df = pd.read_csv(filename)
    df.columns = ['Sentiment','Text','Score']
    return df 


def read_evaluation_file(filename):
    return pd.read_csv(filename)


def train_and_cache_models(data_path=None, force=False):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    data_path = Path(data_path) if data_path else DATA_PATH
    vectorizer_ready = VECTORIZER_PATH.exists()
    models_ready = all(path.exists() for path in MODEL_PATHS.values())
    score_ready = SCORE_MODEL_PATH.exists()

    if not force and vectorizer_ready and models_ready and score_ready:
        return

    if not data_path.exists():
        raise FileNotFoundError(f"Training data not found: {data_path}")

    df = read_file(data_path)
    df['Text'] = df['Text'].astype(str).apply(preprocess)

    vectorizer = CountVectorizer()
    X_vec = vectorizer.fit_transform(df['Text'].values)
    joblib.dump(vectorizer, VECTORIZER_PATH)

    y_sentiment = df['Sentiment'].values
    nb_model = MultinomialNB()
    nb_model.fit(X_vec, y_sentiment)
    joblib.dump(nb_model, MODEL_PATHS["naive bayes"])

    svm_model = LinearSVC(dual="auto", max_iter=5000, random_state=42)
    svm_model.fit(X_vec, y_sentiment)
    joblib.dump(svm_model, MODEL_PATHS["svm"])

    y_score = pd.to_numeric(df['Score'], errors='coerce').fillna(0).values
    score_model = LinearRegression()
    score_model.fit(X_vec, y_score)
    joblib.dump(score_model, SCORE_MODEL_PATH)


def load_cached_vectorizer(train_if_missing=True, data_path=None):
    global _VECTORIZER_CACHE
    if _VECTORIZER_CACHE is not None:
        return _VECTORIZER_CACHE
    if not VECTORIZER_PATH.exists():
        if train_if_missing:
            train_and_cache_models(data_path=data_path)
        else:
            raise FileNotFoundError(f"Missing cached vectorizer: {VECTORIZER_PATH}")
    _VECTORIZER_CACHE = joblib.load(VECTORIZER_PATH)
    return _VECTORIZER_CACHE


def load_cached_model(model_name, train_if_missing=True, data_path=None):
    normalized = _normalize_model_name(model_name)
    model_path = MODEL_PATHS[normalized]
    if normalized in _MODEL_CACHE:
        return load_cached_vectorizer(train_if_missing=train_if_missing, data_path=data_path), _MODEL_CACHE[normalized]
    if not model_path.exists():
        if train_if_missing:
            train_and_cache_models(data_path=data_path)
        else:
            raise FileNotFoundError(f"Missing cached model: {model_path}")
    model = joblib.load(model_path)
    _MODEL_CACHE[normalized] = model
    vectorizer = load_cached_vectorizer(train_if_missing=train_if_missing, data_path=data_path)
    return vectorizer, model


def predict_cached(X_test, model_name, train_if_missing=True, data_path=None):
    vectorizer, model = load_cached_model(model_name, train_if_missing=train_if_missing, data_path=data_path)
    X_vec = vectorizer.transform(X_test)
    return model.predict(X_vec)


def load_cached_score_model(train_if_missing=True, data_path=None):
    global _SCORE_MODEL_CACHE
    if _SCORE_MODEL_CACHE is not None:
        return load_cached_vectorizer(train_if_missing=train_if_missing, data_path=data_path), _SCORE_MODEL_CACHE
    if not SCORE_MODEL_PATH.exists():
        if train_if_missing:
            train_and_cache_models(data_path=data_path)
        else:
            raise FileNotFoundError(f"Missing cached score model: {SCORE_MODEL_PATH}")
    model = joblib.load(SCORE_MODEL_PATH)
    _SCORE_MODEL_CACHE = model
    vectorizer = load_cached_vectorizer(train_if_missing=train_if_missing, data_path=data_path)
    return vectorizer, model


def predict_score_cached(X_test, train_if_missing=True, data_path=None):
    vectorizer, model = load_cached_score_model(train_if_missing=train_if_missing, data_path=data_path)
    X_vec = vectorizer.transform(X_test)
    return model.predict(X_vec)


def evaluate_predictions(y_true, y_pred, labels=None):
    labels = list(labels or np.unique(y_true))
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    recall = recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    confusion = confusion_matrix(y_true, y_pred, labels=labels)
    f1 = f1_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    return accuracy, precision, recall, confusion, f1


def _load_evaluation_dataset(dataset_key):
    normalized = str(dataset_key).strip().lower()
    if normalized in ("train5", "train", "default"):
        path = DATA_PATH
        df = read_file(path)
    elif normalized in ("news", "news corpus", "news_corpus", "news-corpus"):
        path = NEWS_DATA_PATH
        df = read_evaluation_file(path)
    else:
        raise ValueError(f"Unknown dataset_key: {dataset_key}")

    if not path.exists():
        raise FileNotFoundError(f"Evaluation data not found: {path}")

    required_columns = {"Sentiment", "Text"}
    missing = required_columns - set(df.columns)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Missing required columns in {path.name}: {missing_list}")

    df = df.copy()
    df["Text"] = df["Text"].astype(str).apply(preprocess)
    df["Sentiment"] = df["Sentiment"].astype(str).str.strip().str.lower()
    return df


def _metrics_dict(accuracy, precision, recall, confusion, f1):
    return {
        "accuracy": float(accuracy),
        "precision": np.asarray(precision).tolist(),
        "recall": np.asarray(recall).tolist(),
        "f1": np.asarray(f1).tolist(),
        "confusion": np.asarray(confusion).tolist(),
    }


def _build_dataset_metrics(dataset_key, k=5):
    df = _load_evaluation_dataset(dataset_key)
    X = df["Text"].values
    y = df["Sentiment"].values
    labels = [label for label in DEFAULT_LABELS if label in set(y)] or list(np.unique(y))

    def _cross_validated_metrics(model_label, model_type):
        accuracy, precision, recall, confusion, f1 = evaluate_model(X, y, model_label, type=model_type, k=k, labels=labels)
        return _metrics_dict(accuracy, precision, recall, confusion, f1)

    payload = {
        "labels": labels,
        "display_name": "Train5 Corpus" if str(dataset_key).strip().lower() == "train5" else "News Corpus",
        "models": {
            "naive bayes": _cross_validated_metrics("Naive Bayes", 0),
            "svm": _cross_validated_metrics("SVM", 0),
            "vader": _cross_validated_metrics("VADER", 1),
        },
    }

    if "OpenAI_Sentiment" in df.columns:
        openai_predictions = df["OpenAI_Sentiment"].astype(str).str.strip().str.lower().values
        accuracy, precision, recall, confusion, f1 = evaluate_predictions(y, openai_predictions, labels=labels)
        payload["models"]["openai"] = _metrics_dict(accuracy, precision, recall, confusion, f1)

    return payload


def cache_metrics(data_path=None, force=False, k=5):
    global _METRICS_CACHE
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not force and METRICS_PATH.exists():
        _METRICS_CACHE = load_cached_metrics(train_if_missing=False)
        return

    payload = {
        "default_dataset": "train5",
        "datasets": {
            "train5": _build_dataset_metrics("train5", k=k),
            "news": _build_dataset_metrics("news", k=k),
        },
    }

    with open(METRICS_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    _METRICS_CACHE = payload


def load_cached_metrics(train_if_missing=True, data_path=None):
    global _METRICS_CACHE
    if _METRICS_CACHE is not None:
        return _METRICS_CACHE
    if not METRICS_PATH.exists():
        if train_if_missing:
            cache_metrics(data_path=data_path)
        else:
            raise FileNotFoundError(f"Missing cached metrics: {METRICS_PATH}")
    with open(METRICS_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    dataset_payload = payload.get("datasets", {}) if isinstance(payload, dict) else {}
    if not dataset_payload or "news" not in dataset_payload:
        if train_if_missing:
            cache_metrics(force=True)
            return _METRICS_CACHE
        train5_payload = payload if isinstance(payload, dict) else {}
        payload = {
            "default_dataset": "train5",
            "datasets": {
                "train5": train5_payload,
            },
        }

    _METRICS_CACHE = payload
    return _METRICS_CACHE

def emotion_score(X_train, y_train, X_test):
    vector = CountVectorizer()
    X_train2 = vector.fit_transform(X_train)
    X_test2 = vector.transform(X_test)

    model = LinearRegression()
    model.fit(X_train2,y_train)

    score = model.predict(X_test2)
    return score

def prebuilt_model(X_test):
    analyzer = get_vader_analyzer()
    predictions = []
    for i in X_test:
        score = analyzer.polarity_scores(i)
        score1 = score['compound']
        if score1 >= 0.2:
            predictions.append('positive')
        elif score1 <= -0.2:
            predictions.append('negative')
        else:
            predictions.append('neutral')
    return np.array(predictions)


def get_vader_analyzer():
    global _VADER_ANALYZER
    if _VADER_ANALYZER is None:
        _VADER_ANALYZER = SentimentIntensityAnalyzer()
    return _VADER_ANALYZER


def vader_score(text):
    analyzer = get_vader_analyzer()
    return analyzer.polarity_scores(text)['compound']

def evaluate_model(X, y, model, type=0, k=5, labels=None):
    labels = list(labels or np.unique(y))
    _, counts = np.unique(y, return_counts=True)
    min_class_count = int(counts.min()) if len(counts) else 0
    n_splits = min(k, min_class_count)
    if n_splits < 2:
        raise ValueError("At least two examples per sentiment class are required for cross-validation")

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    accuracies = []
    precisions = []
    recalls = []
    confusions = []
    f1_scores = []

    for train_index, test_index in skf.split(X, y):
        X_train, X_test = X[train_index], X[test_index]
        y_train, y_test = y[train_index], y[test_index]

        if type == 0:
            pred = my_model(X_train, y_train, X_test, model)
        elif type == 1:
            pred = prebuilt_model(X_test)

        accuracy, precision, recall, confusion, f1 = evaluate_predictions(y_test, pred, labels=labels)

        accuracies.append(accuracy)
        precisions.append(precision)
        recalls.append(recall)
        confusions.append(confusion)
        f1_scores.append(f1)

    avg_accuracy = np.mean(accuracies)
    avg_precision = np.mean(precisions, axis=0)
    avg_recall = np.mean(recalls, axis=0)
    sum_confusion = np.sum(confusions, axis=0)
    avg_f1 = np.mean(f1_scores, axis=0) 
    return avg_accuracy, avg_precision, avg_recall, sum_confusion, avg_f1

def my_model(X_train, y_train, X_test, model_name):
    vector = CountVectorizer()
    X_train2 = vector.fit_transform(X_train)
    X_test2 = vector.transform(X_test)

    normalized = _normalize_model_name(model_name)
    if normalized == "naive bayes":
        clf = MultinomialNB()
    elif normalized == "svm":
        clf = LinearSVC(dual="auto", max_iter=5000, random_state=42)
    else:
        raise ValueError(f"Unknown model_name: {model_name}")

    clf.fit(X_train2, y_train)
    pred = clf.predict(X_test2)
    return pred


