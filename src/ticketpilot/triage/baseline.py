from __future__ import annotations

from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


class TfidfLogRegClassifier:
    def __init__(self, c: float = 8.0, max_features: int = 60000) -> None:
        self.word = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=max_features)
        self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True, max_features=max_features)
        self.model = LogisticRegression(C=c, max_iter=2000)
        self.classes: list[str] = []

    def _features(self, texts: Sequence[str], fit: bool = False):
        if fit:
            return hstack([self.word.fit_transform(texts), self.char.fit_transform(texts)]).tocsr()
        return hstack([self.word.transform(texts), self.char.transform(texts)]).tocsr()

    def fit(self, texts: Sequence[str], labels: Sequence[str]) -> "TfidfLogRegClassifier":
        self.model.fit(self._features(texts, fit=True), labels)
        self.classes = [str(label) for label in self.model.classes_]
        return self

    def predict_proba(self, texts: Sequence[str]) -> np.ndarray:
        return self.model.predict_proba(self._features(texts))

    def predict(self, texts: Sequence[str]) -> list[str]:
        probabilities = self.predict_proba(texts)
        return [self.classes[index] for index in probabilities.argmax(axis=1)]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: Path) -> "TfidfLogRegClassifier":
        return joblib.load(path)
