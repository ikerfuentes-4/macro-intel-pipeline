"""Centroides de AREAS no nacionales (estrechos, mares, territorios en disputa, cordilleras
fronterizas) que aparecen con frecuencia en analisis geopolitico y que un catalogo de paises
nunca puede resolver correctamente -- un evento en "el Estrecho de Ormuz" no pertenece a un
unico pais. Se listan en ingles (clave canonica, coherente con `country_centroids.py`) con
alias en espanol resueltos por `geo/geocode.py` igual que los paises.
"""
from __future__ import annotations

REGION_CENTROIDS: dict[str, tuple[float, float]] = {
    "Strait of Hormuz": (26.57, 56.25),
    "Strait of Taiwan": (24.00, 119.30),
    "Taiwan Strait": (24.00, 119.30),
    "South China Sea": (12.00, 114.00),
    "East China Sea": (29.00, 125.00),
    "Red Sea": (20.00, 38.00),
    "Bab-el-Mandeb": (12.58, 43.32),
    "Persian Gulf": (26.70, 52.00),
    "Gulf of Aden": (12.50, 47.50),
    "Gaza Strip": (31.40, 34.35),
    "West Bank": (31.95, 35.30),
    "Golan Heights": (33.13, 35.78),
    "Kashmir": (34.08, 74.80),
    "Nagorno-Karabakh": (39.85, 46.75),
    "Donbas": (48.30, 37.80),
    "Crimea": (45.30, 34.40),
    "Sahel": (15.00, 5.00),
    "Horn of Africa": (7.00, 47.00),
    "Western Sahara": (24.22, -12.89),
    "South Caucasus": (41.70, 44.80),
    "Korean Peninsula": (38.00, 127.50),
    "Strait of Malacca": (2.80, 101.20),
    "Black Sea": (43.50, 34.50),
    "Baltic Sea": (58.00, 20.00),
    "Arctic": (78.00, 20.00),
}
