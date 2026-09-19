# -*- coding: utf-8 -*-
"""
Конструктор житла — Flask-застосунок для орієнтовного розрахунку вартості.

ЦЕ ЄДИНИЙ ФАЙЛ ПРОЄКТУ: сторінки, стилі й скрипти вже всередині.
Папка templates не потрібна. Запуск:  python main.py
"""

import socket
import subprocess
import sys
import threading
import webbrowser
from math import sqrt

try:
    import flask  # noqa: F401
except ImportError:
    print("Flask не встановлено. Встановлюю, зачекайте...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])

from flask import Flask, jsonify, redirect, render_template_string, request, url_for

app = Flask(__name__)


# ---------------------------------------------------------------------------
# ДАНІ (тут можна змінювати міста, матеріали та ціни)
# ---------------------------------------------------------------------------

# coef — регіональний коефіцієнт до всіх цін
CITIES = {
    "kyiv": {"name": "Київ", "coef": 1.25},
    "lviv": {"name": "Львів", "coef": 1.10},
    "odesa": {"name": "Одеса", "coef": 1.12},
    "dnipro": {"name": "Дніпро", "coef": 1.03},
    "kharkiv": {"name": "Харків", "coef": 1.00},
    "vinnytsia": {"name": "Вінниця", "coef": 0.96},
    "zaporizhzhia": {"name": "Запоріжжя", "coef": 0.95},
    "other": {"name": "Інше місто", "coef": 0.90},
}


def _opt(name, price, note):
    """Один матеріал: назва, ціна за м² (грн) і коротке пояснення."""
    return {"name": name, "price": price, "note": note}


# Для квартири — внутрішнє оздоблення, для будинку — конструкції та дах.
# Матеріали в кожній групі впорядковані від дешевших до дорожчих.
CATALOG = {
    "apartment": {
        "title": "Квартира",
        "summary": "Оздоблення: стіни, підлога, стеля",
        "materials_hint": "Внутрішнє оздоблення приміщень",
        "area_limits": (15, 300),
        "area_example": 60,
        "work_share": 0.35,  # вартість робіт як частка від вартості матеріалів
        "groups": {
            "walls": {
                "title": "Матеріал стін",
                "label": "Стіни",
                "options": {
                    "wallpaper": _opt("Флізелінові шпалери", 350, "Швидко й недорого"),
                    "paint": _opt("Фарбування по штукатурці", 480, "Гладка стіна в один колір"),
                    "drywall": _opt("Гіпсокартон під фарбування", 650, "Вирівнює криві стіни"),
                    "decor": _opt("Декоративна штукатурка", 900, "Фактура під камінь чи шовк"),
                    "wood": _opt("Дерев'яні панелі", 1200, "Тепле натуральне покриття"),
                },
            },
            "floor": {
                "title": "Матеріал підлоги",
                "label": "Підлога",
                "options": {
                    "linoleum": _opt("Лінолеум", 300, "Бюджетний і вологостійкий"),
                    "laminate": _opt("Ламінат", 550, "Найпоширеніший варіант"),
                    "vinyl": _opt("Вінілова плитка SPC", 850, "Не боїться води"),
                    "tile": _opt("Керамограніт", 1050, "Довговічний, підходить для теплої підлоги"),
                    "parquet": _opt("Паркетна дошка", 1700, "Натуральне дерево"),
                },
            },
            "ceiling": {
                "title": "Матеріал стелі",
                "label": "Стеля",
                "options": {
                    "paint": _opt("Фарбування", 250, "Проста рівна стеля"),
                    "stretch": _opt("Натяжна стеля", 450, "Ховає нерівності за один день"),
                    "drywall": _opt("Гіпсокартонна стеля", 650, "Під підсвітку й карнизи"),
                    "multilevel": _opt("Багаторівнева з підсвіткою", 1150, "Виразний дизайн"),
                },
            },
        },
    },
    "house": {
        "title": "Будинок",
        "summary": "Будівництво: стіни, підлога, перекриття, дах",
        "materials_hint": "Конструкції та покрівля будинку",
        "area_limits": (40, 1000),
        "area_example": 120,
        "work_share": 0.45,
        "groups": {
            "walls": {
                "title": "Матеріал стін",
                "label": "Стіни",
                "options": {
                    "aerated": _opt("Газобетон", 1400, "Тепло й швидке будівництво"),
                    "sip": _opt("SIP-панелі", 1750, "Каркасна технологія, енергоефективно"),
                    "ceramic": _opt("Керамоблок", 1950, "Теплий і «дихаючий»"),
                    "brick": _opt("Керамічна цегла", 2300, "Класика: міцно й довговічно"),
                    "timber": _opt("Клеєний брус", 2900, "Дерев'яний будинок"),
                },
            },
            "floor": {
                "title": "Матеріал підлоги",
                "label": "Підлога",
                "options": {
                    "wood_joists": _opt("Дерев'яна підлога по лагах", 1000, "Легка й тепла"),
                    "screed": _opt("Бетонна стяжка з утепленням", 1100, "Стандарт для приватних будинків"),
                    "slab": _opt("Монолітна плита", 1600, "Максимальна міцність"),
                    "warm": _opt("Водяна тепла підлога", 1900, "Комфорт і економія на опаленні"),
                },
            },
            "ceiling": {
                "title": "Матеріал перекриття",
                "label": "Перекриття",
                "options": {
                    "drywall": _opt("Підвісна стеля з гіпсокартону", 650, "Рівна поверхня під оздоблення"),
                    "beams": _opt("Дерев'яні балки перекриття", 800, "Легка конструкція"),
                    "clapboard": _opt("Дерев'яна вагонка", 950, "Тепла естетика з відкритими балками"),
                    "rc": _opt("Залізобетонні плити", 1500, "Міцне міжповерхове перекриття"),
                },
            },
            "roof": {
                "title": "Матеріал даху",
                "label": "Дах",
                "options": {
                    "profnastil": _opt("Профнастил", 600, "Найдешевше покриття"),
                    "metal": _opt("Металочерепиця", 850, "Оптимум ціни й вигляду"),
                    "bitumen": _opt("Бітумна черепиця", 1050, "Тиха, підходить для складних дахів"),
                    "seam": _opt("Фальцева покрівля", 1500, "Довговічна, сучасний вигляд"),
                    "ceramic": _opt("Керамічна черепиця", 1900, "Служить понад 50 років"),
                },
            },
        },
    },
}

CEILING_HEIGHT = 2.7  # висота поверху, м


# ---------------------------------------------------------------------------
# ДОПОМІЖНІ ФУНКЦІЇ
# ---------------------------------------------------------------------------

def plural(n, forms):
    """Правильна форма слова: plural(3, ('кімната', 'кімнати', 'кімнат'))."""
    n = abs(int(n))
    if 11 <= n % 100 <= 14:
        return forms[2]
    last = n % 10
    if last == 1:
        return forms[0]
    if 2 <= last <= 4:
        return forms[1]
    return forms[2]


def to_int(value, low, high):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def parse_params(data):
    """Перевіряє дані форми. Повертає (params, errors)."""
    errors = []
    params = {}

    city = data.get("city", "")
    if city in CITIES:
        params["city"] = city
    else:
        errors.append("Оберіть місто")

    btype = data.get("building_type", "")
    if btype not in CATALOG:
        errors.append("Оберіть тип житла")
        return None, errors
    params["building_type"] = btype
    spec = CATALOG[btype]

    low, high = spec["area_limits"]
    try:
        area = float(str(data.get("area", "")).strip().replace(",", "."))
    except ValueError:
        errors.append("Вкажіть площу")
    else:
        if low <= area <= high:
            params["area"] = area
        else:
            errors.append(f"Площа має бути від {low} до {high} м²")

    rooms = to_int(data.get("rooms"), 1, 5)
    if rooms is None:
        errors.append("Вкажіть кількість кімнат")
    else:
        params["rooms"] = rooms

    if btype == "house":
        floors = to_int(data.get("floors"), 1, 3)
        if floors is None:
            errors.append("Вкажіть кількість поверхів")
        else:
            params["floors"] = floors
    else:
        params["floors"] = 1

    for gkey, group in spec["groups"].items():
        choice = data.get(f"{btype}_{gkey}", "")
        if choice in group["options"]:
            params[gkey] = choice
        else:
            errors.append(f"Оберіть: {group['title'].lower()}")

    return (None, errors) if errors else (params, [])


def surfaces(btype, area, rooms, floors):
    """Розрахункові площі поверхонь у м²."""
    if btype == "apartment":
        # стіни разом з перегородками: чим більше кімнат, тим більше стін
        return {
            "walls": area * (2.2 + 0.15 * rooms),
            "floor": area,
            "ceiling": area,
        }

    footprint = area / floors  # площа забудови
    outer_walls = 4 * sqrt(footprint) * CEILING_HEIGHT * floors
    partitions = area * (0.3 + 0.1 * rooms)
    return {
        "walls": outer_walls + partitions,
        "floor": area,
        "ceiling": area,
        "roof": footprint * 1.35,  # з урахуванням нахилу та звісів
    }


def calculate(params):
    """Рахує вартість за перевіреними параметрами."""
    btype = params["building_type"]
    spec = CATALOG[btype]
    city = CITIES[params["city"]]
    area = params["area"]
    rooms = params["rooms"]
    floors = params["floors"]

    areas = surfaces(btype, area, rooms, floors)

    rows = []
    for gkey, group in spec["groups"].items():
        option = group["options"][params[gkey]]
        unit_price = option["price"] * city["coef"]
        rows.append(
            {
                "key": gkey,
                "label": group["label"],
                "material": option["name"],
                "area": round(areas[gkey], 1),
                "unit_price": round(unit_price),
                "cost": round(areas[gkey] * unit_price),
            }
        )

    materials_total = sum(row["cost"] for row in rows)
    work_cost = round(materials_total * spec["work_share"])
    total = materials_total + work_cost

    for row in rows:
        row["share"] = round(row["cost"] / total * 100)

    form_values = {
        "city": params["city"],
        "building_type": btype,
        "area": f"{area:g}",
        "rooms": rooms,
    }
    if btype == "house":
        form_values["floors"] = floors
    for gkey in spec["groups"]:
        form_values[f"{btype}_{gkey}"] = params[gkey]

    return {
        "form": form_values,
        "building_type": btype,
        "type_title": spec["title"],
        "city_name": city["name"],
        "city_coef": city["coef"],
        "area": area,
        "rooms_label": f"{rooms} {plural(rooms, ('кімната', 'кімнати', 'кімнат'))}",
        "floors_label": (
            f"{floors} {plural(floors, ('поверх', 'поверхи', 'поверхів'))}"
            if btype == "house"
            else None
        ),
        "rows": rows,
        "materials_total": materials_total,
        "work_pct": round(spec["work_share"] * 100),
        "work_cost": work_cost,
        "work_share": round(work_cost / total * 100),
        "total": total,
        "per_m2": round(total / area),
    }


# ---------------------------------------------------------------------------
# ФІЛЬТРИ ДЛЯ ШАБЛОНІВ
# ---------------------------------------------------------------------------

@app.template_filter("money")
def money(value):
    """1234567 -> '1 234 567' (з нерозривними пробілами)."""
    return f"{int(round(value)):,}".replace(",", "\u00a0")


@app.template_filter("dec")
def dec(value):
    """60.0 -> '60', 60.5 -> '60,5'."""
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


# ---------------------------------------------------------------------------
# МАРШРУТИ
# ---------------------------------------------------------------------------

def render_index(initial, errors):
    return render_template_string(
        INDEX_HTML,
        cities=CITIES,
        catalog=CATALOG,
        initial=initial,
        errors=errors,
    )


@app.route("/")
def index():
    return render_index({}, [])


@app.route("/estimate", methods=["POST"])
def estimate_view():
    """Швидкий розрахунок для живого підсумку на головній сторінці."""
    params, errors = parse_params(request.form)
    if errors:
        return jsonify(ok=False, errors=errors)
    return jsonify(ok=True, **calculate(params))


@app.route("/calculate", methods=["GET", "POST"])
def calculate_view():
    if request.method == "GET":
        return redirect(url_for("index"))

    params, errors = parse_params(request.form)
    if errors:
        return render_index(request.form.to_dict(), errors), 400
    return render_template_string(RESULT_HTML, calc=calculate(params))


@app.route("/edit", methods=["POST"])
def edit_view():
    """Повертає до форми зі збереженими значеннями."""
    return render_index(request.form.to_dict(), [])


# ---------------------------------------------------------------------------
# ШАБЛОНИ СТОРІНОК (HTML + CSS + JS)
# Це звичайні рядки Python: сюди можна вносити правки в HTML, CSS і JS.
# ---------------------------------------------------------------------------

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="uk">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#10263b">

    <title>Конструктор житла</title>

    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%2310263b'/%3E%3Cpath d='M6 17 16 8l10 9M9 15v10h14V15' stroke='%23f0a81e' stroke-width='2.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600;700&family=Unbounded:wght@500;600&display=swap" rel="stylesheet">

    <style>
{% raw %}
/* ==========================================================================
   Конструктор житла
   ========================================================================== */

:root {
    --paper: #edf1f4;
    --sheet: #ffffff;
    --ink: #10263b;
    --blue: #1b4f8a;
    --blue-soft: #e4eef8;
    --amber: #f0a81e;
    --line: #d3dce5;
    --muted: #5a6d80;
    --focus: #2f7fe0;
    --danger: #b3261e;

    --font-body: "Onest", system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    --font-display: "Unbounded", "Onest", system-ui, -apple-system, "Segoe UI", Arial, sans-serif;
}

*,
*::before,
*::after {
    box-sizing: border-box;
}

[hidden] {
    display: none !important;
}

html {
    -webkit-text-size-adjust: 100%;
}

body {
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: var(--font-body);
    font-size: 16px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
}

h1, h2, h3, p, ul {
    margin: 0;
}

button, input, select {
    font: inherit;
    color: inherit;
}

:focus-visible {
    outline: 3px solid var(--focus);
    outline-offset: 2px;
}

/* --- Шапка ---------------------------------------------------------------- */

.top {
    max-width: 1240px;
    margin: 0 auto;
    padding: 28px 24px 0;
}

.brand {
    display: inline-flex;
    align-items: center;
    gap: 12px;
    color: inherit;
    text-decoration: none;
}

.brand-mark {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: var(--ink);
    color: var(--amber);
}

.brand-name {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: 1.05rem;
    letter-spacing: -0.01em;
}

.intro {
    max-width: 1240px;
    margin: 0 auto;
    padding: 36px 24px 0;
}

.intro h1 {
    max-width: 22ch;
    font-family: var(--font-display);
    font-weight: 600;
    font-size: clamp(1.6rem, 3.4vw, 2.5rem);
    line-height: 1.15;
    letter-spacing: -0.02em;
}

.intro p {
    max-width: 52ch;
    margin-top: 14px;
    color: var(--muted);
    font-size: 1.05rem;
}

/* --- Основна сітка ------------------------------------------------------- */

.layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 360px;
    gap: 28px;
    align-items: start;
    max-width: 1240px;
    margin: 0 auto;
    padding: 28px 24px 80px;
}

.sheet {
    background: var(--sheet);
    border: 1px solid var(--line);
    border-radius: 20px;
}

.alert {
    margin: 24px 32px 0;
    padding: 14px 18px;
    border: 1.5px solid var(--danger);
    border-radius: 12px;
    background: #fdecea;
    color: #5f1410;
}

.alert ul {
    margin-top: 6px;
    padding-left: 20px;
}

/* --- Рядки форми: назва зліва, поля справа ------------------------------- */

.row {
    display: grid;
    grid-template-columns: 170px minmax(0, 1fr);
    gap: 28px;
    padding: 32px;
}

.row + .row {
    border-top: 1px solid var(--line);
}

.row-head h2 {
    font-size: 1.1rem;
    font-weight: 700;
    line-height: 1.3;
}

.row-head p {
    margin-top: 6px;
    color: var(--muted);
    font-size: 0.9rem;
}

.fields {
    display: grid;
    gap: 24px;
}

.field-label {
    display: block;
    margin-bottom: 10px;
    font-weight: 600;
    font-size: 0.95rem;
}

.hint {
    margin-top: 8px;
    color: var(--muted);
    font-size: 0.85rem;
}

/* --- Поля вводу ---------------------------------------------------------- */

select,
input[type="number"] {
    width: 100%;
    height: 50px;
    padding: 0 14px;
    border: 1.5px solid var(--line);
    border-radius: 10px;
    background: #fff;
    font-size: 1rem;
}

select {
    appearance: none;
    padding-right: 42px;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='9' viewBox='0 0 14 9' fill='none'%3E%3Cpath d='M1 1.5 7 7.5l6-6' stroke='%2310263b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 16px center;
    cursor: pointer;
}

select:hover,
input[type="number"]:hover {
    border-color: #9fb0c1;
}

select:focus,
input[type="number"]:focus {
    outline: none;
    border-color: var(--blue);
    box-shadow: 0 0 0 3px rgba(47, 127, 224, 0.25);
}

.input-suffix {
    position: relative;
    max-width: 260px;
}

.input-suffix input {
    padding-right: 48px;
}

.suffix {
    position: absolute;
    top: 50%;
    right: 16px;
    transform: translateY(-50%);
    color: var(--muted);
    pointer-events: none;
}

/* Приховуємо нативні радіокнопки, лишаючи їх доступними з клавіатури */
.tile input,
.pill input,
.chip input {
    position: absolute;
    top: 0;
    left: 0;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
}

.tile,
.pill,
.chip {
    position: relative;
    display: block;
    cursor: pointer;
}

/* --- Тип житла ----------------------------------------------------------- */

.tiles {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}

.tile-body {
    display: flex;
    flex-direction: column;
    gap: 14px;
    height: 100%;
    padding: 18px;
    border: 1.5px solid var(--line);
    border-radius: 16px;
    background: #fff;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s;
}

.tile-body svg {
    width: 44px;
    height: 44px;
    color: var(--blue);
}

.tile-name {
    display: block;
    font-size: 1.15rem;
    font-weight: 700;
}

.tile-desc {
    display: block;
    margin-top: 2px;
    color: var(--muted);
    font-size: 0.88rem;
    line-height: 1.35;
}

.tile:hover input:not(:checked) + .tile-body {
    border-color: var(--blue);
}

.tile input:checked + .tile-body {
    border-color: var(--ink);
    background: var(--ink);
    color: #fff;
}

.tile input:checked + .tile-body svg {
    color: var(--amber);
}

.tile input:checked + .tile-body .tile-desc {
    color: rgba(255, 255, 255, 0.78);
}

.tile input:focus-visible + .tile-body,
.pill input:focus-visible + span,
.chip input:focus-visible + .chip-body {
    outline: 3px solid var(--focus);
    outline-offset: 2px;
}

/* --- Кімнати та поверхи -------------------------------------------------- */

.pills {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.pill span {
    display: grid;
    place-items: center;
    min-width: 52px;
    height: 46px;
    padding: 0 14px;
    border: 1.5px solid var(--line);
    border-radius: 10px;
    background: #fff;
    font-weight: 600;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s;
}

.pill:hover input:not(:checked) + span {
    border-color: var(--blue);
}

.pill input:checked + span {
    border-color: var(--blue);
    background: var(--blue);
    color: #fff;
}

/* --- Матеріали ----------------------------------------------------------- */

.group {
    min-width: 0;
    margin: 0 0 28px;
    padding: 0;
    border: 0;
}

.group:last-child {
    margin-bottom: 0;
}

.group legend {
    margin-bottom: 10px;
    padding: 0;
    font-weight: 700;
    font-size: 0.95rem;
}

.chips {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 10px;
}

.chip-body {
    position: relative;
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 14px 44px 14px 14px;
    border: 1.5px solid var(--line);
    border-radius: 12px;
    background: #fff;
    transition: background-color 0.15s, border-color 0.15s;
}

.chip-body::after {
    content: "";
    position: absolute;
    top: 14px;
    right: 14px;
    width: 18px;
    height: 18px;
    border: 1.5px solid #9fb0c1;
    border-radius: 50%;
    background: #fff;
}

.chip-name {
    font-weight: 600;
    line-height: 1.3;
}

.chip-note {
    margin-top: 2px;
    color: var(--muted);
    font-size: 0.85rem;
    line-height: 1.35;
}

.chip-price {
    margin-top: auto;
    padding-top: 10px;
    color: var(--blue);
    font-size: 0.9rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}

.chip:hover input:not(:checked) + .chip-body {
    border-color: var(--blue);
}

.chip input:checked + .chip-body {
    border-color: var(--blue);
    background: var(--blue-soft);
}

.chip input:checked + .chip-body::after {
    border-color: var(--blue);
    background: radial-gradient(circle, var(--blue) 0 4.5px, #fff 5px);
}

/* --- Синя панель з підсумком (креслярська сітка) ------------------------- */

.summary,
.hero {
    background-color: var(--ink);
    background-image:
        linear-gradient(rgba(255, 255, 255, 0.055) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.055) 1px, transparent 1px);
    background-size: 24px 24px;
    background-position: -1px -1px;
    color: #fff;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}

.summary {
    position: sticky;
    top: 24px;
    padding: 28px;
    border-radius: 20px;
}

.summary-label {
    color: rgba(255, 255, 255, 0.72);
    font-size: 0.95rem;
}

.summary-total {
    margin-top: 8px;
    font-family: var(--font-display);
    font-weight: 600;
    font-size: clamp(1.7rem, 2.6vw, 2.15rem);
    line-height: 1.15;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
}

.cur {
    margin-left: 6px;
    color: var(--amber);
    font-size: 0.55em;
    letter-spacing: 0;
}

.summary-per {
    min-height: 3em;
    margin-top: 8px;
    color: rgba(255, 255, 255, 0.78);
    font-size: 0.95rem;
}

.bar {
    display: flex;
    gap: 2px;
    height: 12px;
    margin: 20px 0 14px;
    border-radius: 6px;
    overflow: hidden;
}

.seg {
    flex: 1 1 0;
    min-width: 3px;
    transition: flex-grow 0.35s ease;
}

.seg-0 { background: #4c8fe0; }
.seg-1 { background: #2fb5a0; }
.seg-2 { background: #9a8af0; }
.seg-3 { background: #ee7b6a; }
.seg-work { background: var(--amber); }

.legend {
    padding: 0;
    list-style: none;
}

.legend li {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    font-size: 0.92rem;
}

.legend-name {
    flex: 1;
}

.legend-sum {
    font-variant-numeric: tabular-nums;
}

.swatch {
    flex: none;
    width: 12px;
    height: 12px;
    border-radius: 4px;
}

.summary .btn {
    margin-top: 22px;
}

.fine {
    margin-top: 14px;
    color: rgba(255, 255, 255, 0.62);
    font-size: 0.8rem;
    line-height: 1.4;
}

/* --- Кнопки -------------------------------------------------------------- */

.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 14px 24px;
    border: 1.5px solid transparent;
    border-radius: 12px;
    font-weight: 700;
    text-decoration: none;
    cursor: pointer;
    transition: background-color 0.15s, border-color 0.15s;
}

.btn-block {
    width: 100%;
}

.btn-amber {
    background: var(--amber);
    color: var(--ink);
}

.btn-amber:hover {
    background: #f7bb46;
}

.btn-solid {
    background: var(--ink);
    color: #fff;
}

.btn-solid:hover {
    background: #1d3c58;
}

.btn-ghost {
    border-color: var(--line);
    background: #fff;
    color: var(--ink);
}

.btn-ghost:hover {
    border-color: var(--ink);
}

/* --- Сторінка результату ------------------------------------------------- */

.result {
    display: grid;
    gap: 24px;
    max-width: 1000px;
    margin: 0 auto;
    padding: 28px 24px 80px;
}

.hero {
    padding: 40px;
    border-radius: 24px;
}

.hero-total {
    margin-top: 8px;
    font-family: var(--font-display);
    font-weight: 600;
    font-size: clamp(2rem, 7vw, 3.5rem);
    line-height: 1.1;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
}

.hero .summary-per {
    min-height: 0;
    font-size: 1.05rem;
}

.meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 22px;
    padding: 0;
    list-style: none;
}

.meta li {
    padding: 6px 14px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.1);
    font-size: 0.9rem;
}

.hero .bar {
    height: 16px;
    margin-top: 32px;
    border-radius: 8px;
}

.hero .legend {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    column-gap: 32px;
}

.block {
    padding: 32px;
}

.block h2 {
    font-size: 1.25rem;
    margin-bottom: 18px;
}

.table {
    width: 100%;
    border-collapse: collapse;
}

.table th {
    padding: 0 12px 12px;
    border-bottom: 1.5px solid var(--ink);
    color: var(--muted);
    font-size: 0.85rem;
    font-weight: 600;
    text-align: left;
}

.table td {
    padding: 16px 12px;
    border-bottom: 1px solid var(--line);
    vertical-align: top;
}

.table .num {
    text-align: right;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
}

.table th:first-child,
.table td:first-child {
    padding-left: 0;
}

.table th:last-child,
.table td:last-child {
    padding-right: 0;
}

.cell-flex {
    display: flex;
    gap: 12px;
}

.cell-flex .swatch {
    margin-top: 6px;
}

.sub {
    display: block;
    color: var(--muted);
    font-size: 0.9rem;
    line-height: 1.35;
}

.sub-mobile {
    display: none;
}

.table tfoot td {
    border-bottom: 0;
    padding-top: 20px;
    font-size: 1.15rem;
    font-weight: 700;
}

.notes {
    display: grid;
    gap: 10px;
    padding: 0;
    list-style: none;
    color: #2b4157;
}

.notes li {
    position: relative;
    padding-left: 22px;
    max-width: 78ch;
}

.notes li::before {
    content: "";
    position: absolute;
    top: 0.6em;
    left: 2px;
    width: 8px;
    height: 8px;
    border-radius: 2px;
    background: var(--blue);
}

.actions {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
}

.actions form {
    margin: 0;
}

/* --- Планшети та телефони ------------------------------------------------ */

@media (max-width: 1100px) {
    .layout {
        grid-template-columns: minmax(0, 1fr);
    }

    .summary {
        position: static;
    }
}

@media (max-width: 700px) {
    .top { padding: 20px 16px 0; }
    .intro { padding: 24px 16px 0; }

    .layout {
        gap: 20px;
        padding: 20px 16px 0;
    }

    .row {
        grid-template-columns: minmax(0, 1fr);
        gap: 16px;
        padding: 24px 20px;
    }

    .alert {
        margin: 20px 20px 0;
    }

    /* Компактна панель з підсумком, що завжди видна внизу екрана */
    .summary {
        position: sticky;
        bottom: 0;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
        gap: 2px 16px;
        margin: 0 -16px;
        padding: 14px 16px calc(14px + env(safe-area-inset-bottom));
        border-radius: 20px 20px 0 0;
    }

    .summary-label,
    .bar,
    .legend,
    .fine {
        display: none;
    }

    .summary-total {
        margin-top: 0;
        font-size: 1.25rem;
        white-space: nowrap;
        overflow-wrap: normal;
    }

    .summary-per {
        min-height: 0;
        margin-top: 0;
        font-size: 0.85rem;
    }

    .summary .btn {
        grid-column: 2;
        grid-row: 1 / span 2;
        width: auto;
        max-width: 138px;
        margin-top: 0;
        padding: 10px 12px;
        font-size: 0.9rem;
        line-height: 1.25;
        text-align: center;
    }

    .result { padding: 20px 16px 60px; }
    .hero { padding: 28px 22px; }
    .block { padding: 24px 20px; }

    .table thead,
    .col-detail,
    .col-share {
        display: none;
    }

    .sub-mobile {
        display: block;
    }

    .actions .btn {
        flex: 1 1 100%;
    }
}

@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        transition: none !important;
    }
}

@media print {
    body { background: #fff; }
    .top, .actions { display: none; }
    .result { padding: 0; }
    .block { border: 0; padding: 16px 0; }
}

.set-note {
    margin: 0 0 18px;
}

{% endraw %}
    </style>
</head>

<body>

{% set cur_type = initial.building_type if initial.building_type in catalog else 'apartment' %}
{% set cur_rooms = (initial.rooms or '2')|string %}
{% set cur_floors = (initial.floors or '1')|string %}

<header class="top">
    <a class="brand" href="{{ url_for('index') }}">
        <span class="brand-mark">
            <svg width="24" height="24" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M6 17 16 8l10 9M9 15v10h14V15"/>
            </svg>
        </span>
        <span class="brand-name">Конструктор житла</span>
    </a>
</header>

<div class="intro">
    <h1>Порахуйте вартість житла за матеріалами</h1>
    <p>Оберіть місто, тип житла та матеріали — підсумок праворуч оновлюється одразу.</p>
</div>

<form class="layout" id="calc" action="{{ url_for('calculate_view') }}" method="post"
      data-estimate-url="{{ url_for('estimate_view') }}">

    <div class="sheet">

        {% if errors %}
        <div class="alert" role="alert">
            <strong>Перевірте, будь ласка, форму</strong>
            <ul>
                {% for error in errors %}
                <li>{{ error }}</li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}

        <!-- Місто -->
        <section class="row">
            <div class="row-head">
                <h2>Місто</h2>
                <p>Ціни на матеріали й роботи залежать від регіону.</p>
            </div>
            <div class="fields">
                <div>
                    <label class="field-label" for="city">Виберіть місто</label>
                    <select name="city" id="city" required>
                        <option value="">Виберіть місто</option>
                        {% for key, city in cities.items() %}
                        <option value="{{ key }}" {% if initial.city == key %}selected{% endif %}>{{ city.name }}</option>
                        {% endfor %}
                    </select>
                </div>
            </div>
        </section>

        <!-- Тип житла -->
        <section class="row">
            <div class="row-head">
                <h2>Що ви хочете створити?</h2>
                <p>Від типу залежить набір матеріалів.</p>
            </div>
            <div class="fields">
                <div class="tiles">
                    {% for btype, spec in catalog.items() %}
                    <label class="tile">
                        <input type="radio" name="building_type" value="{{ btype }}"
                               data-min="{{ spec['area_limits'][0] }}"
                               data-max="{{ spec['area_limits'][1] }}"
                               data-example="{{ spec['area_example'] }}"
                               {% if cur_type == btype %}checked{% endif %} required>
                        <span class="tile-body">
                            {% if btype == 'apartment' %}
                            <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                <rect x="10" y="6" width="28" height="36" rx="2"/>
                                <path d="M17 14h4M27 14h4M17 22h4M27 22h4M17 30h4M27 30h4"/>
                                <path d="M21 42v-6h6v6"/>
                            </svg>
                            {% else %}
                            <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                <path d="M6 22 24 7l18 15"/>
                                <path d="M10 19v23h28V19"/>
                                <path d="M20 42V30h8v12"/>
                            </svg>
                            {% endif %}
                            <span>
                                <span class="tile-name">{{ spec['title'] }}</span>
                                <span class="tile-desc">{{ spec['summary'] }}</span>
                            </span>
                        </span>
                    </label>
                    {% endfor %}
                </div>
            </div>
        </section>

        <!-- Параметри -->
        <section class="row">
            <div class="row-head">
                <h2>Параметри</h2>
                <p>Кількість кімнат і площа впливають на обсяг матеріалів.</p>
            </div>
            <div class="fields">

                <div>
                    <span class="field-label" id="rooms-label">Кількість кімнат</span>
                    <div class="pills" role="group" aria-labelledby="rooms-label">
                        {% for r in range(1, 6) %}
                        <label class="pill">
                            <input type="radio" name="rooms" value="{{ r }}" {% if cur_rooms == r|string %}checked{% endif %}>
                            <span>{{ r }}</span>
                        </label>
                        {% endfor %}
                    </div>
                </div>

                <div>
                    <label class="field-label" for="area">Загальна площа</label>
                    <div class="input-suffix">
                        <input type="number" name="area" id="area"
                               min="{{ catalog[cur_type]['area_limits'][0] }}"
                               max="{{ catalog[cur_type]['area_limits'][1] }}"
                               step="0.1" inputmode="decimal"
                               placeholder="Наприклад: {{ catalog[cur_type]['area_example'] }}"
                               value="{{ initial.area or '' }}" required>
                        <span class="suffix">м²</span>
                    </div>
                    <p class="hint" id="areaHint">Від {{ catalog[cur_type]['area_limits'][0] }} до {{ catalog[cur_type]['area_limits'][1] }} м²</p>
                </div>

                <div id="floorsRow" {% if cur_type != 'house' %}hidden{% endif %}>
                    <span class="field-label" id="floors-label">Кількість поверхів</span>
                    <div class="pills" role="group" aria-labelledby="floors-label">
                        {% for f in range(1, 4) %}
                        <label class="pill">
                            <input type="radio" name="floors" value="{{ f }}"
                                   {% if cur_floors == f|string %}checked{% endif %}
                                   {% if cur_type != 'house' %}disabled{% endif %}>
                            <span>{{ f }}</span>
                        </label>
                        {% endfor %}
                    </div>
                </div>

            </div>
        </section>

        <!-- Матеріали: окремий набір для квартири й для будинку -->
        <section class="row">
            <div class="row-head">
                <h2>Матеріали</h2>
                <p>Набір залежить від типу житла.</p>
            </div>
            <div>
                {% for btype, spec in catalog.items() %}
                <div class="mat-set" data-type="{{ btype }}" {% if cur_type != btype %}hidden{% endif %}>
                    <p class="hint set-note">{{ spec['materials_hint'] }}</p>

                    {% for gkey, group in spec['groups'].items() %}
                    {% set saved = initial.get(btype ~ '_' ~ gkey) %}
                    <fieldset class="group">
                        <legend>{{ group['title'] }}</legend>
                        <div class="chips">
                            {% for okey, opt in group['options'].items() %}
                            <label class="chip">
                                <input type="radio" name="{{ btype }}_{{ gkey }}" value="{{ okey }}" required
                                       {% if cur_type != btype %}disabled{% endif %}
                                       {% if saved == okey or (saved not in group['options'] and loop.first) %}checked{% endif %}>
                                <span class="chip-body">
                                    <span class="chip-name">{{ opt['name'] }}</span>
                                    <span class="chip-note">{{ opt['note'] }}</span>
                                    <span class="chip-price">{{ opt['price']|money }} грн/м²</span>
                                </span>
                            </label>
                            {% endfor %}
                        </div>
                    </fieldset>
                    {% endfor %}
                </div>
                {% endfor %}
            </div>
        </section>

    </div>

    <!-- Живий підсумок -->
    <aside class="summary">
        <p class="summary-label">Орієнтовна вартість</p>
        <p class="summary-total">
            <span id="total">—</span><span class="cur" id="totalCur" hidden>грн</span>
        </p>
        <p class="summary-per" id="perM2" aria-live="polite">Виберіть місто та вкажіть площу.</p>

        <div class="bar" id="bar" aria-hidden="true" hidden></div>
        <ul class="legend" id="legend"></ul>

        <button type="submit" class="btn btn-amber btn-block">Детальний розрахунок</button>
        <p class="fine">Сума орієнтовна: остаточна ціна залежить від підрядника, сезону та стану приміщення.</p>
    </aside>

</form>

<script>
{% raw %}
(function () {
    "use strict";

    var form = document.getElementById("calc");
    var areaInput = document.getElementById("area");
    var areaHint = document.getElementById("areaHint");
    var floorsRow = document.getElementById("floorsRow");

    var totalEl = document.getElementById("total");
    var curEl = document.getElementById("totalCur");
    var perEl = document.getElementById("perM2");
    var barEl = document.getElementById("bar");
    var legendEl = document.getElementById("legend");

    var estimateUrl = form.getAttribute("data-estimate-url");
    var reduceMotion = window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var numberFormat = new Intl.NumberFormat("uk-UA");

    function fmt(n) {
        return numberFormat.format(Math.round(n));
    }

    function escapeHtml(text) {
        var map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
        return String(text).replace(/[&<>"']/g, function (c) { return map[c]; });
    }

    /* ---------- Тип житла: показуємо потрібний набір матеріалів ---------- */

    function applyType() {
        var radio = form.querySelector('input[name="building_type"]:checked');
        if (!radio) return;
        var type = radio.value;

        areaInput.min = radio.getAttribute("data-min");
        areaInput.max = radio.getAttribute("data-max");
        areaInput.placeholder = "Наприклад: " + radio.getAttribute("data-example");
        areaHint.textContent = "Від " + radio.getAttribute("data-min") +
            " до " + radio.getAttribute("data-max") + " м²";

        floorsRow.hidden = type !== "house";
        Array.prototype.forEach.call(floorsRow.querySelectorAll("input"), function (input) {
            input.disabled = type !== "house";
        });

        // Вимкнені поля не потрапляють ні у форму, ні у перевірку required
        Array.prototype.forEach.call(document.querySelectorAll(".mat-set"), function (set) {
            var active = set.getAttribute("data-type") === type;
            set.hidden = !active;
            Array.prototype.forEach.call(set.querySelectorAll("input"), function (input) {
                input.disabled = !active;
            });
        });
    }

    /* ---------- Живий підсумок ---------- */

    var shownTotal = 0;
    var rafId = 0;

    function animateTotal(target) {
        cancelAnimationFrame(rafId);

        if (reduceMotion) {
            shownTotal = target;
            totalEl.textContent = fmt(target);
            return;
        }

        var from = shownTotal;
        var start = performance.now();
        var duration = 350;

        function step(now) {
            var t = Math.min(1, (now - start) / duration);
            var eased = 1 - Math.pow(1 - t, 3);
            shownTotal = Math.round(from + (target - from) * eased);
            totalEl.textContent = fmt(shownTotal);
            if (t < 1) rafId = requestAnimationFrame(step);
        }
        rafId = requestAnimationFrame(step);
    }

    function syncBar(rows) {
        var existing = {};
        Array.prototype.forEach.call(barEl.children, function (el) {
            existing[el.getAttribute("data-key")] = el;
        });

        rows.forEach(function (row) {
            var el = existing[row.key];
            if (!el) {
                el = document.createElement("span");
                el.setAttribute("data-key", row.key);
            }
            el.className = "seg " + row.cls;
            el.style.flexGrow = row.cost;
            barEl.appendChild(el); // переставляє елемент у правильний порядок
            delete existing[row.key];
        });

        Object.keys(existing).forEach(function (key) {
            barEl.removeChild(existing[key]);
        });
    }

    function showEmpty(messages) {
        cancelAnimationFrame(rafId);
        shownTotal = 0;
        totalEl.textContent = "—";
        curEl.hidden = true;
        perEl.textContent = messages.join(". ") + ".";
        barEl.hidden = true;
        legendEl.innerHTML = "";
    }

    function showEstimate(data) {
        var rows = data.rows.map(function (row, i) {
            return { key: row.key, label: row.label, cost: row.cost, cls: "seg-" + i };
        });
        rows.push({ key: "work", label: "Роботи", cost: data.work_cost, cls: "seg-work" });

        curEl.hidden = false;
        barEl.hidden = false;
        perEl.textContent = "Близько " + fmt(data.per_m2) + " грн за м²";

        syncBar(rows);
        legendEl.innerHTML = rows.map(function (row) {
            return '<li><span class="swatch ' + row.cls + '"></span>' +
                '<span class="legend-name">' + escapeHtml(row.label) + "</span>" +
                '<span class="legend-sum">' + fmt(row.cost) + " грн</span></li>";
        }).join("");

        animateTotal(data.total);
    }

    var requestId = 0;
    var timer = 0;

    function runEstimate() {
        var mine = ++requestId;
        fetch(estimateUrl, {
            method: "POST",
            body: new URLSearchParams(new FormData(form))
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (mine !== requestId) return; // прийшла застаріла відповідь
                if (data.ok) showEstimate(data);
                else showEmpty(data.errors);
            })
            .catch(function () {
                if (mine === requestId) showEmpty(["Не вдалося оновити розрахунок"]);
            });
    }

    function scheduleEstimate() {
        clearTimeout(timer);
        timer = setTimeout(runEstimate, 180);
    }

    /* ---------- Події ---------- */

    form.addEventListener("input", scheduleEstimate);
    form.addEventListener("change", function (event) {
        if (event.target.name === "building_type") applyType();
        scheduleEstimate();
    });

    applyType();
    runEstimate();
})();

{% endraw %}
</script>

</body>

</html>
"""

RESULT_HTML = r"""<!DOCTYPE html>
<html lang="uk">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#10263b">

    <title>Розрахунок вартості — Конструктор житла</title>

    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%2310263b'/%3E%3Cpath d='M6 17 16 8l10 9M9 15v10h14V15' stroke='%23f0a81e' stroke-width='2.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600;700&family=Unbounded:wght@500;600&display=swap" rel="stylesheet">

    <style>
{% raw %}
/* ==========================================================================
   Конструктор житла
   ========================================================================== */

:root {
    --paper: #edf1f4;
    --sheet: #ffffff;
    --ink: #10263b;
    --blue: #1b4f8a;
    --blue-soft: #e4eef8;
    --amber: #f0a81e;
    --line: #d3dce5;
    --muted: #5a6d80;
    --focus: #2f7fe0;
    --danger: #b3261e;

    --font-body: "Onest", system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    --font-display: "Unbounded", "Onest", system-ui, -apple-system, "Segoe UI", Arial, sans-serif;
}

*,
*::before,
*::after {
    box-sizing: border-box;
}

[hidden] {
    display: none !important;
}

html {
    -webkit-text-size-adjust: 100%;
}

body {
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: var(--font-body);
    font-size: 16px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
}

h1, h2, h3, p, ul {
    margin: 0;
}

button, input, select {
    font: inherit;
    color: inherit;
}

:focus-visible {
    outline: 3px solid var(--focus);
    outline-offset: 2px;
}

/* --- Шапка ---------------------------------------------------------------- */

.top {
    max-width: 1240px;
    margin: 0 auto;
    padding: 28px 24px 0;
}

.brand {
    display: inline-flex;
    align-items: center;
    gap: 12px;
    color: inherit;
    text-decoration: none;
}

.brand-mark {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: var(--ink);
    color: var(--amber);
}

.brand-name {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: 1.05rem;
    letter-spacing: -0.01em;
}

.intro {
    max-width: 1240px;
    margin: 0 auto;
    padding: 36px 24px 0;
}

.intro h1 {
    max-width: 22ch;
    font-family: var(--font-display);
    font-weight: 600;
    font-size: clamp(1.6rem, 3.4vw, 2.5rem);
    line-height: 1.15;
    letter-spacing: -0.02em;
}

.intro p {
    max-width: 52ch;
    margin-top: 14px;
    color: var(--muted);
    font-size: 1.05rem;
}

/* --- Основна сітка ------------------------------------------------------- */

.layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 360px;
    gap: 28px;
    align-items: start;
    max-width: 1240px;
    margin: 0 auto;
    padding: 28px 24px 80px;
}

.sheet {
    background: var(--sheet);
    border: 1px solid var(--line);
    border-radius: 20px;
}

.alert {
    margin: 24px 32px 0;
    padding: 14px 18px;
    border: 1.5px solid var(--danger);
    border-radius: 12px;
    background: #fdecea;
    color: #5f1410;
}

.alert ul {
    margin-top: 6px;
    padding-left: 20px;
}

/* --- Рядки форми: назва зліва, поля справа ------------------------------- */

.row {
    display: grid;
    grid-template-columns: 170px minmax(0, 1fr);
    gap: 28px;
    padding: 32px;
}

.row + .row {
    border-top: 1px solid var(--line);
}

.row-head h2 {
    font-size: 1.1rem;
    font-weight: 700;
    line-height: 1.3;
}

.row-head p {
    margin-top: 6px;
    color: var(--muted);
    font-size: 0.9rem;
}

.fields {
    display: grid;
    gap: 24px;
}

.field-label {
    display: block;
    margin-bottom: 10px;
    font-weight: 600;
    font-size: 0.95rem;
}

.hint {
    margin-top: 8px;
    color: var(--muted);
    font-size: 0.85rem;
}

/* --- Поля вводу ---------------------------------------------------------- */

select,
input[type="number"] {
    width: 100%;
    height: 50px;
    padding: 0 14px;
    border: 1.5px solid var(--line);
    border-radius: 10px;
    background: #fff;
    font-size: 1rem;
}

select {
    appearance: none;
    padding-right: 42px;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='9' viewBox='0 0 14 9' fill='none'%3E%3Cpath d='M1 1.5 7 7.5l6-6' stroke='%2310263b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 16px center;
    cursor: pointer;
}

select:hover,
input[type="number"]:hover {
    border-color: #9fb0c1;
}

select:focus,
input[type="number"]:focus {
    outline: none;
    border-color: var(--blue);
    box-shadow: 0 0 0 3px rgba(47, 127, 224, 0.25);
}

.input-suffix {
    position: relative;
    max-width: 260px;
}

.input-suffix input {
    padding-right: 48px;
}

.suffix {
    position: absolute;
    top: 50%;
    right: 16px;
    transform: translateY(-50%);
    color: var(--muted);
    pointer-events: none;
}

/* Приховуємо нативні радіокнопки, лишаючи їх доступними з клавіатури */
.tile input,
.pill input,
.chip input {
    position: absolute;
    top: 0;
    left: 0;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
}

.tile,
.pill,
.chip {
    position: relative;
    display: block;
    cursor: pointer;
}

/* --- Тип житла ----------------------------------------------------------- */

.tiles {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}

.tile-body {
    display: flex;
    flex-direction: column;
    gap: 14px;
    height: 100%;
    padding: 18px;
    border: 1.5px solid var(--line);
    border-radius: 16px;
    background: #fff;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s;
}

.tile-body svg {
    width: 44px;
    height: 44px;
    color: var(--blue);
}

.tile-name {
    display: block;
    font-size: 1.15rem;
    font-weight: 700;
}

.tile-desc {
    display: block;
    margin-top: 2px;
    color: var(--muted);
    font-size: 0.88rem;
    line-height: 1.35;
}

.tile:hover input:not(:checked) + .tile-body {
    border-color: var(--blue);
}

.tile input:checked + .tile-body {
    border-color: var(--ink);
    background: var(--ink);
    color: #fff;
}

.tile input:checked + .tile-body svg {
    color: var(--amber);
}

.tile input:checked + .tile-body .tile-desc {
    color: rgba(255, 255, 255, 0.78);
}

.tile input:focus-visible + .tile-body,
.pill input:focus-visible + span,
.chip input:focus-visible + .chip-body {
    outline: 3px solid var(--focus);
    outline-offset: 2px;
}

/* --- Кімнати та поверхи -------------------------------------------------- */

.pills {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.pill span {
    display: grid;
    place-items: center;
    min-width: 52px;
    height: 46px;
    padding: 0 14px;
    border: 1.5px solid var(--line);
    border-radius: 10px;
    background: #fff;
    font-weight: 600;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s;
}

.pill:hover input:not(:checked) + span {
    border-color: var(--blue);
}

.pill input:checked + span {
    border-color: var(--blue);
    background: var(--blue);
    color: #fff;
}

/* --- Матеріали ----------------------------------------------------------- */

.group {
    min-width: 0;
    margin: 0 0 28px;
    padding: 0;
    border: 0;
}

.group:last-child {
    margin-bottom: 0;
}

.group legend {
    margin-bottom: 10px;
    padding: 0;
    font-weight: 700;
    font-size: 0.95rem;
}

.chips {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 10px;
}

.chip-body {
    position: relative;
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 14px 44px 14px 14px;
    border: 1.5px solid var(--line);
    border-radius: 12px;
    background: #fff;
    transition: background-color 0.15s, border-color 0.15s;
}

.chip-body::after {
    content: "";
    position: absolute;
    top: 14px;
    right: 14px;
    width: 18px;
    height: 18px;
    border: 1.5px solid #9fb0c1;
    border-radius: 50%;
    background: #fff;
}

.chip-name {
    font-weight: 600;
    line-height: 1.3;
}

.chip-note {
    margin-top: 2px;
    color: var(--muted);
    font-size: 0.85rem;
    line-height: 1.35;
}

.chip-price {
    margin-top: auto;
    padding-top: 10px;
    color: var(--blue);
    font-size: 0.9rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}

.chip:hover input:not(:checked) + .chip-body {
    border-color: var(--blue);
}

.chip input:checked + .chip-body {
    border-color: var(--blue);
    background: var(--blue-soft);
}

.chip input:checked + .chip-body::after {
    border-color: var(--blue);
    background: radial-gradient(circle, var(--blue) 0 4.5px, #fff 5px);
}

/* --- Синя панель з підсумком (креслярська сітка) ------------------------- */

.summary,
.hero {
    background-color: var(--ink);
    background-image:
        linear-gradient(rgba(255, 255, 255, 0.055) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.055) 1px, transparent 1px);
    background-size: 24px 24px;
    background-position: -1px -1px;
    color: #fff;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}

.summary {
    position: sticky;
    top: 24px;
    padding: 28px;
    border-radius: 20px;
}

.summary-label {
    color: rgba(255, 255, 255, 0.72);
    font-size: 0.95rem;
}

.summary-total {
    margin-top: 8px;
    font-family: var(--font-display);
    font-weight: 600;
    font-size: clamp(1.7rem, 2.6vw, 2.15rem);
    line-height: 1.15;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
}

.cur {
    margin-left: 6px;
    color: var(--amber);
    font-size: 0.55em;
    letter-spacing: 0;
}

.summary-per {
    min-height: 3em;
    margin-top: 8px;
    color: rgba(255, 255, 255, 0.78);
    font-size: 0.95rem;
}

.bar {
    display: flex;
    gap: 2px;
    height: 12px;
    margin: 20px 0 14px;
    border-radius: 6px;
    overflow: hidden;
}

.seg {
    flex: 1 1 0;
    min-width: 3px;
    transition: flex-grow 0.35s ease;
}

.seg-0 { background: #4c8fe0; }
.seg-1 { background: #2fb5a0; }
.seg-2 { background: #9a8af0; }
.seg-3 { background: #ee7b6a; }
.seg-work { background: var(--amber); }

.legend {
    padding: 0;
    list-style: none;
}

.legend li {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    font-size: 0.92rem;
}

.legend-name {
    flex: 1;
}

.legend-sum {
    font-variant-numeric: tabular-nums;
}

.swatch {
    flex: none;
    width: 12px;
    height: 12px;
    border-radius: 4px;
}

.summary .btn {
    margin-top: 22px;
}

.fine {
    margin-top: 14px;
    color: rgba(255, 255, 255, 0.62);
    font-size: 0.8rem;
    line-height: 1.4;
}

/* --- Кнопки -------------------------------------------------------------- */

.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 14px 24px;
    border: 1.5px solid transparent;
    border-radius: 12px;
    font-weight: 700;
    text-decoration: none;
    cursor: pointer;
    transition: background-color 0.15s, border-color 0.15s;
}

.btn-block {
    width: 100%;
}

.btn-amber {
    background: var(--amber);
    color: var(--ink);
}

.btn-amber:hover {
    background: #f7bb46;
}

.btn-solid {
    background: var(--ink);
    color: #fff;
}

.btn-solid:hover {
    background: #1d3c58;
}

.btn-ghost {
    border-color: var(--line);
    background: #fff;
    color: var(--ink);
}

.btn-ghost:hover {
    border-color: var(--ink);
}

/* --- Сторінка результату ------------------------------------------------- */

.result {
    display: grid;
    gap: 24px;
    max-width: 1000px;
    margin: 0 auto;
    padding: 28px 24px 80px;
}

.hero {
    padding: 40px;
    border-radius: 24px;
}

.hero-total {
    margin-top: 8px;
    font-family: var(--font-display);
    font-weight: 600;
    font-size: clamp(2rem, 7vw, 3.5rem);
    line-height: 1.1;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
}

.hero .summary-per {
    min-height: 0;
    font-size: 1.05rem;
}

.meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 22px;
    padding: 0;
    list-style: none;
}

.meta li {
    padding: 6px 14px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.1);
    font-size: 0.9rem;
}

.hero .bar {
    height: 16px;
    margin-top: 32px;
    border-radius: 8px;
}

.hero .legend {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    column-gap: 32px;
}

.block {
    padding: 32px;
}

.block h2 {
    font-size: 1.25rem;
    margin-bottom: 18px;
}

.table {
    width: 100%;
    border-collapse: collapse;
}

.table th {
    padding: 0 12px 12px;
    border-bottom: 1.5px solid var(--ink);
    color: var(--muted);
    font-size: 0.85rem;
    font-weight: 600;
    text-align: left;
}

.table td {
    padding: 16px 12px;
    border-bottom: 1px solid var(--line);
    vertical-align: top;
}

.table .num {
    text-align: right;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
}

.table th:first-child,
.table td:first-child {
    padding-left: 0;
}

.table th:last-child,
.table td:last-child {
    padding-right: 0;
}

.cell-flex {
    display: flex;
    gap: 12px;
}

.cell-flex .swatch {
    margin-top: 6px;
}

.sub {
    display: block;
    color: var(--muted);
    font-size: 0.9rem;
    line-height: 1.35;
}

.sub-mobile {
    display: none;
}

.table tfoot td {
    border-bottom: 0;
    padding-top: 20px;
    font-size: 1.15rem;
    font-weight: 700;
}

.notes {
    display: grid;
    gap: 10px;
    padding: 0;
    list-style: none;
    color: #2b4157;
}

.notes li {
    position: relative;
    padding-left: 22px;
    max-width: 78ch;
}

.notes li::before {
    content: "";
    position: absolute;
    top: 0.6em;
    left: 2px;
    width: 8px;
    height: 8px;
    border-radius: 2px;
    background: var(--blue);
}

.actions {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
}

.actions form {
    margin: 0;
}

/* --- Планшети та телефони ------------------------------------------------ */

@media (max-width: 1100px) {
    .layout {
        grid-template-columns: minmax(0, 1fr);
    }

    .summary {
        position: static;
    }
}

@media (max-width: 700px) {
    .top { padding: 20px 16px 0; }
    .intro { padding: 24px 16px 0; }

    .layout {
        gap: 20px;
        padding: 20px 16px 0;
    }

    .row {
        grid-template-columns: minmax(0, 1fr);
        gap: 16px;
        padding: 24px 20px;
    }

    .alert {
        margin: 20px 20px 0;
    }

    /* Компактна панель з підсумком, що завжди видна внизу екрана */
    .summary {
        position: sticky;
        bottom: 0;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
        gap: 2px 16px;
        margin: 0 -16px;
        padding: 14px 16px calc(14px + env(safe-area-inset-bottom));
        border-radius: 20px 20px 0 0;
    }

    .summary-label,
    .bar,
    .legend,
    .fine {
        display: none;
    }

    .summary-total {
        margin-top: 0;
        font-size: 1.25rem;
        white-space: nowrap;
        overflow-wrap: normal;
    }

    .summary-per {
        min-height: 0;
        margin-top: 0;
        font-size: 0.85rem;
    }

    .summary .btn {
        grid-column: 2;
        grid-row: 1 / span 2;
        width: auto;
        max-width: 138px;
        margin-top: 0;
        padding: 10px 12px;
        font-size: 0.9rem;
        line-height: 1.25;
        text-align: center;
    }

    .result { padding: 20px 16px 60px; }
    .hero { padding: 28px 22px; }
    .block { padding: 24px 20px; }

    .table thead,
    .col-detail,
    .col-share {
        display: none;
    }

    .sub-mobile {
        display: block;
    }

    .actions .btn {
        flex: 1 1 100%;
    }
}

@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        transition: none !important;
    }
}

@media print {
    body { background: #fff; }
    .top, .actions { display: none; }
    .result { padding: 0; }
    .block { border: 0; padding: 16px 0; }
}

.set-note {
    margin: 0 0 18px;
}

{% endraw %}
    </style>
</head>

<body>

<header class="top">
    <a class="brand" href="{{ url_for('index') }}">
        <span class="brand-mark">
            <svg width="24" height="24" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M6 17 16 8l10 9M9 15v10h14V15"/>
            </svg>
        </span>
        <span class="brand-name">Конструктор житла</span>
    </a>
</header>

<main class="result">

    <!-- Підсумок -->
    <section class="hero">
        <p class="summary-label">Орієнтовна вартість</p>
        <h1 class="hero-total">{{ calc.total|money }}<span class="cur">грн</span></h1>
        <p class="summary-per">Близько {{ calc.per_m2|money }} грн за м²</p>

        <ul class="meta">
            <li>{{ calc.type_title }}</li>
            <li>{{ calc.city_name }}</li>
            <li>{{ calc.area|dec }} м²</li>
            <li>{{ calc.rooms_label }}</li>
            {% if calc.floors_label %}<li>{{ calc.floors_label }}</li>{% endif %}
        </ul>

        <div class="bar" aria-hidden="true">
            {% for row in calc.rows %}
            <span class="seg seg-{{ loop.index0 }}" style="flex-grow: {{ row.cost }}"></span>
            {% endfor %}
            <span class="seg seg-work" style="flex-grow: {{ calc.work_cost }}"></span>
        </div>

        <ul class="legend">
            {% for row in calc.rows %}
            <li>
                <span class="swatch seg-{{ loop.index0 }}"></span>
                <span class="legend-name">{{ row.label }}</span>
                <span class="legend-sum">{{ row.cost|money }} грн</span>
            </li>
            {% endfor %}
            <li>
                <span class="swatch seg-work"></span>
                <span class="legend-name">Роботи</span>
                <span class="legend-sum">{{ calc.work_cost|money }} грн</span>
            </li>
        </ul>
    </section>

    <!-- Таблиця -->
    <section class="sheet block">
        <h2>З чого складається сума</h2>

        <table class="table">
            <thead>
                <tr>
                    <th>Позиція</th>
                    <th class="num col-detail">Площа</th>
                    <th class="num col-detail">Ціна за м²</th>
                    <th class="num">Вартість</th>
                    <th class="num col-share">Частка</th>
                </tr>
            </thead>
            <tbody>
                {% for row in calc.rows %}
                <tr>
                    <td>
                        <div class="cell-flex">
                            <span class="swatch seg-{{ loop.index0 }}"></span>
                            <div>
                                <strong>{{ row.label }}</strong>
                                <span class="sub">{{ row.material }}</span>
                                <span class="sub sub-mobile">{{ row.area|dec }} м² × {{ row.unit_price|money }} грн/м²</span>
                            </div>
                        </div>
                    </td>
                    <td class="num col-detail">{{ row.area|dec }} м²</td>
                    <td class="num col-detail">{{ row.unit_price|money }} грн</td>
                    <td class="num">{{ row.cost|money }} грн</td>
                    <td class="num col-share">{{ row.share }}%</td>
                </tr>
                {% endfor %}
                <tr>
                    <td>
                        <div class="cell-flex">
                            <span class="swatch seg-work"></span>
                            <div>
                                <strong>Роботи</strong>
                                <span class="sub">{{ calc.work_pct }}% від вартості матеріалів</span>
                            </div>
                        </div>
                    </td>
                    <td class="num col-detail">—</td>
                    <td class="num col-detail">—</td>
                    <td class="num">{{ calc.work_cost|money }} грн</td>
                    <td class="num col-share">{{ calc.work_share }}%</td>
                </tr>
            </tbody>
            <tfoot>
                <tr>
                    <td>Разом</td>
                    <td class="col-detail"></td>
                    <td class="col-detail"></td>
                    <td class="num">{{ calc.total|money }} грн</td>
                    <td class="col-share"></td>
                </tr>
            </tfoot>
        </table>
    </section>

    <!-- Як рахували -->
    <section class="sheet block">
        <h2>Як ми рахували</h2>
        <ul class="notes">
            <li>Ціни враховують коефіцієнт міста {{ calc.city_name }}: ×{{ ('%.2f'|format(calc.city_coef))|replace('.', ',') }}.</li>
            {% if calc.building_type == 'apartment' %}
            <li>Площа стін розрахункова: вона зростає разом із кількістю кімнат, бо додаються перегородки.</li>
            <li>Не враховано: вікна й двері, електрику, сантехніку, кухню та меблі.</li>
            {% else %}
            <li>Стіни — це зовнішні стіни з урахуванням поверхів і внутрішні перегородки. Площа даху враховує нахил і звіси.</li>
            <li>Не враховано: фундамент, вікна й двері, інженерні системи, зовнішнє оздоблення та благоустрій.</li>
            {% endif %}
            <li>Ціни на матеріали орієнтовні й можуть відрізнятися залежно від постачальника та сезону.</li>
        </ul>
    </section>

    <div class="actions">
        <form action="{{ url_for('edit_view') }}" method="post">
            {% for name, value in calc.form.items() %}
            <input type="hidden" name="{{ name }}" value="{{ value }}">
            {% endfor %}
            <button type="submit" class="btn btn-solid">Змінити параметри</button>
        </form>
        <a class="btn btn-ghost" href="{{ url_for('index') }}">Новий розрахунок</a>
        <button type="button" class="btn btn-ghost" onclick="window.print()">Роздрукувати</button>
    </div>

</main>

</body>

</html>
"""


# ---------------------------------------------------------------------------
# ЗАПУСК
# ---------------------------------------------------------------------------

def find_free_port(start=5000, tries=30):
    """Шукає вільний порт, щоб не потрапити на старий сервер, який ще працює."""
    for port in range(start, start + tries):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.3).close()
        except OSError:
            return port  # ніхто не слухає — порт вільний
    return start


if __name__ == "__main__":
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"

    print("=" * 56)
    print("  Конструктор житла запущено")
    print("  Відкрийте в браузері:", url)
    print("  Зупинити сервер: Ctrl+C")
    print("=" * 56)

    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)