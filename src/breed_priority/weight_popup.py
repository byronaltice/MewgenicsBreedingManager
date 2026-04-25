"""Breed Priority - scoring weights popup dialog."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .scoring import (
    GENETIC_SAFE_RISK_FLOOR, MATE_IMBALANCE_BASE_PERCENT,
    TRAIT_HIGH_THRESHOLD, TRAIT_LOW_THRESHOLD,
)
from .styles import _DIM_BTN_LG, _PRIORITY_TABLE_STYLE
from .theme import (
    CLR_BG_SCORE_AREA, CLR_TEXT_PRIMARY,
    CLR_VALUE_NEG, CLR_VALUE_POS,
)


def show_weights_popup(parent, weights: dict) -> None:
    """Open a modal dialog displaying the current scoring weight breakdown."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Scoring Weights")
    dlg.setModal(True)
    dlg.setStyleSheet(f"background:{CLR_BG_SCORE_AREA}; color:{CLR_TEXT_PRIMARY};")
    dlg.resize(460, 380)

    vb = QVBoxLayout(dlg)
    vb.setContentsMargins(16, 16, 16, 16)
    vb.setSpacing(8)

    title = QLabel("Breed Priority - Scoring Weights")
    title.setStyleSheet(f"color:{CLR_TEXT_PRIMARY}; font-size:13px; font-weight:bold;")
    vb.addWidget(title)

    table = QTableWidget()
    table.setColumnCount(2)
    table.setHorizontalHeaderLabels(["Attribute", "Weight"])
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.NoSelection)
    table.verticalHeader().setVisible(False)
    table.setShowGrid(False)
    table.setAlternatingRowColors(True)
    table.setStyleSheet(_PRIORITY_TABLE_STYLE)
    hh = table.horizontalHeader()
    hh.setSectionResizeMode(0, QHeaderView.Stretch)
    hh.setSectionResizeMode(1, QHeaderView.Fixed)
    table.setColumnWidth(1, 120)

    w = weights
    rare_threshold = int(round(w.get("stat_7_threshold", 7.0)))
    stat_count_threshold = int(round(w.get("stat_count_threshold", 7.0)))
    mate_threshold = int(round(w.get("mate_imbalance_threshold", 10.0)))
    mate_high = int(round(MATE_IMBALANCE_BASE_PERCENT + mate_threshold))
    mate_low = int(round(MATE_IMBALANCE_BASE_PERCENT - mate_threshold))
    age_threshold = int(round(w.get("age_threshold", 10.0)))
    rows_data = [
        ("-- 7-rare: bonus per stat where few scope cats share that 7 --", ""),
        (f"  7 in a stat (<={rare_threshold} cats in scope have it)", f"+{w['stat_7']:.0f}"),
        (f"  7 in a stat ({rare_threshold + 1} cats in scope)", f"+{max(0.1, round(w['stat_7'] * rare_threshold / (rare_threshold + 1), 1)):.1f}"),
        (f"  7 in a stat (sole owner, none in scope)", f"+{w['stat_7'] * 2:.0f}"),
        (f"-- Stat-count: bonus per stat at or above threshold (>={stat_count_threshold}) --", ""),
        ("  Threshold", f">={stat_count_threshold}"),
        (f"  3 stats >={stat_count_threshold}", f"+{w['stat_7_count'] * 3:.2f}"),
        (f"  7 stats >={stat_count_threshold}", f"+{w['stat_7_count'] * 7:.2f}"),
        ("Trait - top priority sole owner", f"{2 * w['trait_top_priority']:+.1f}"),
        ("Trait - desirable sole owner", f"{2 * w['trait_desirable']:+.1f}"),
        ("Trait - undesirable", f"{w['trait_undesirable']:+.1f}"),
        ("-- CHA penalty: applied when CHA is below 5 --", ""),
        ("  CHA = 4", f"{w['cha_low']:+.1f}"),
        ("  CHA = 3", f"{w['cha_low'] * 2:+.1f} (2x)"),
        (f"Low aggression (<{TRAIT_LOW_THRESHOLD * 100:.0f}%)", f"+{w['low_aggression']:.1f}"),
        ("Unknown gender (?)", f"+{w['unknown_gender']:.1f}"),
        (f"High libido (>={TRAIT_HIGH_THRESHOLD * 100:.0f}%)", f"+{w['high_libido']:.1f}"),
        (f"High aggression (>={TRAIT_HIGH_THRESHOLD * 100:.0f}%)", f"{w['high_aggression']:.1f}"),
        (f"Low libido (<{TRAIT_LOW_THRESHOLD * 100:.0f}%)", f"{w['low_libido']:.1f}"),
        ("-- Genetic safety: configurable threshold and penalty scale --", ""),
        ("  Bonus (avg risk <= threshold)", f"+{w['zero_risk_bonus']:.1f}"),
        ("  Penalty (avg risk > threshold)", f"{w['no_children']:.1f} x (risk-thr) x scale/100"),
        ("  Threshold", f"{int(round(w.get('gene_risk_threshold', GENETIC_SAFE_RISK_FLOOR)))}%"),
        ("  Penalty scale (higher = faster)", f"{int(round(w.get('gene_risk_penalty_scale', 10.0)))}"),
        ("Mate penalty", f"-{abs(w['mate_weight']):.1f} to dominant gender"),
        ("  Imbalance threshold", f"{mate_high}%/{mate_low}%"),
        ("Love interest in scope", f"+{w['love_interest']:.1f}"),
        ("Rival in scope", f"{w['rivalry']:.1f}"),
        ("-- Age penalty: multiplies per 3 years above threshold --", ""),
        (f"  Age <= {age_threshold}", "+0"),
        (f"  Age {age_threshold + 1} (+1 over, 1x)", f"{w['age_penalty']:.1f}"),
        (f"  Age {age_threshold + 4} (+4 over, 2x)", f"{2 * w['age_penalty']:.1f}"),
        (f"  Age {age_threshold + 7} (+7 over, 3x)", f"{3 * w['age_penalty']:.1f}"),
    ]

    table.setRowCount(len(rows_data))
    for row_index, (attr, weight_text) in enumerate(rows_data):
        is_header = weight_text == ""
        attr_item = QTableWidgetItem(attr)
        attr_item.setFlags(Qt.ItemIsEnabled)
        if is_header:
            attr_item.setForeground(QColor("#7070c0"))
            font = attr_item.font()
            font.setItalic(True)
            attr_item.setFont(font)
        weight_item = QTableWidgetItem(weight_text)
        weight_item.setFlags(Qt.ItemIsEnabled)
        weight_item.setTextAlignment(Qt.AlignCenter)
        if weight_text.startswith("+"):
            weight_item.setForeground(QColor(CLR_VALUE_POS))
        elif weight_text.startswith("-"):
            weight_item.setForeground(QColor(CLR_VALUE_NEG))
        table.setItem(row_index, 0, attr_item)
        table.setItem(row_index, 1, weight_item)
        table.setRowHeight(row_index, 22 if is_header else 24)

    vb.addWidget(table)

    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(_DIM_BTN_LG)
    close_btn.clicked.connect(dlg.accept)
    vb.addWidget(close_btn, alignment=Qt.AlignRight)
    dlg.exec()
