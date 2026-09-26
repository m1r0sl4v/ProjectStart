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

from flask import Flask, Response, jsonify, redirect, render_template_string, request, url_for

app = Flask(__name__)


# ---------------------------------------------------------------------------
# ДАНІ ТА КУРСИ ВАЛЮТ
# ---------------------------------------------------------------------------

RATES = {
    "UAH": 1.0,
    "USD": 41.5,
    "EUR": 45.0
}

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
    return {"name": name, "price": price, "note": note}


CATALOG = {
    "apartment": {
        "title": "Квартира",
        "summary": "Оздоблення: стіни, підлога, стеля",
        "materials_hint": "Внутрішнє оздоблення приміщень",
        "area_limits": (15, 300),
        "area_example": 60,
        "work_share": 0.35,
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

CEILING_HEIGHT = 2.7


# ---------------------------------------------------------------------------
# ДОПОМІЖНІ ФУНКЦІЇ ТА ОБЧИСЛЕННЯ
# ---------------------------------------------------------------------------

def plural(n, forms):
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
    if btype == "apartment":
        return {
            "walls": area * (2.2 + 0.15 * rooms),
            "floor": area,
            "ceiling": area,
        }

    footprint = area / floors
    outer_walls = 4 * sqrt(footprint) * CEILING_HEIGHT * floors
    partitions = area * (0.3 + 0.1 * rooms)
    return {
        "walls": outer_walls + partitions,
        "floor": area,
        "ceiling": area,
        "roof": footprint * 1.35,
    }


def calculate_mortgage(total_price, years=20, rate=7.0, down_payment_pct=20):
    """Обчислення іпотечного платежу ("єОселя")."""
    down_payment = total_price * (down_payment_pct / 100)
    loan_amount = total_price - down_payment
    monthly_rate = (rate / 100) / 12
    n_payments = years * 12

    if monthly_rate > 0:
        monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** n_payments) / (((1 + monthly_rate) ** n_payments) - 1)
    else:
        monthly_payment = loan_amount / n_payments

    return {
        "down_payment": round(down_payment),
        "loan_amount": round(loan_amount),
        "monthly_payment": round(monthly_payment),
        "years": years,
        "rate": rate
    }


def calculate_range(params):
    btype = params["building_type"]
    spec = CATALOG[btype]
    city = CITIES[params["city"]]
    area = params["area"]
    rooms = params["rooms"]
    floors = params["floors"]
    areas = surfaces(btype, area, rooms, floors)

    min_mats = 0
    max_mats = 0

    for gkey, group in spec["groups"].items():
        prices = [opt["price"] * city["coef"] for opt in group["options"].values()]
        min_mats += areas[gkey] * min(prices)
        max_mats += areas[gkey] * max(prices)

    min_total = round(min_mats * (1 + spec["work_share"]))
    max_total = round(max_mats * (1 + spec["work_share"]))

    return {
        "min_total": min_total,
        "max_total": max_total,
        "min_per_m2": round(min_total / area),
        "max_per_m2": round(max_total / area),
    }


def estimate_timeline(params):
    btype = params["building_type"]
    area = params["area"]
    floors = params.get("floors", 1)

    if btype == "apartment":
        base_days = 20 + area * 0.4 + params["rooms"] * 3
    else:
        base_days = 60 + area * 0.8 + floors * 15

    days = round(base_days)
    months = round(days / 30, 1)
    return {"days": days, "months": months}


def calculate(params):
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
        "rooms": rooms,
        "floors": floors,
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
        "usd_total": round(total / RATES["USD"]),
        "eur_total": round(total / RATES["EUR"]),
        "range": calculate_range(params),
        "timeline": estimate_timeline(params),
        "mortgage": calculate_mortgage(total)
    }


# ---------------------------------------------------------------------------
# ФІЛЬТРИ ДЛЯ ШАБЛОНІВ
# ---------------------------------------------------------------------------

@app.template_filter("money")
def money(value):
    return f"{int(round(value)):,}".replace(",", "\u00a0")


@app.template_filter("dec")
def dec(value):
    if isinstance(value, (int, float)):
        text = f"{value:g}"
    else:
        text = str(value)
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
    return render_template_string(RESULT_HTML, calc=calculate(params), rates=RATES)


@app.route("/edit", methods=["POST"])
def edit_view():
    return render_index(request.form.to_dict(), [])


@app.route("/download_txt", methods=["POST"])
def download_txt():
    params, errors = parse_params(request.form)
    if errors:
        return redirect(url_for("index"))

    calc = calculate(params)
    lines = [
        "==================================================",
        "            КОШТОРИС БУДІВНИЦТВА / РЕМОНТУ        ",
        "==================================================",
        f"Об'єкт: {calc['type_title']}",
        f"Місто: {calc['city_name']}",
        f"Площа: {calc['area']} м² ({calc['rooms_label']})",
    ]
    if calc.get("floors_label"):
        lines.append(f"Поверхів: {calc['floors_label']}")

    lines.extend(
        [
            f"Орієнтовний термін робіт: ~{calc['timeline']['days']} днів (~{calc['timeline']['months']} міс.)",
            "--------------------------------------------------",
            "ДЕТАЛІЗАЦІЯ ВИТРАТ:",
        ]
    )

    for row in calc["rows"]:
        lines.append(
            f"• {row['label']} ({row['material']}): {row['area']} м² × {row['unit_price']} грн = {row['cost']:,} грн"
        )

    lines.extend(
        [
            f"• Роботи ({calc['work_pct']}%): {calc['work_cost']:,} грн",
            "--------------------------------------------------",
            f"ЗАГАЛЬНА ВАРТІСТЬ: {calc['total']:,} грн  (~${calc['usd_total']:,} USD / ~€{calc['eur_total']:,} EUR)",
            f"Вартість за 1 м²: {calc['per_m2']:,} грн",
            "--------------------------------------------------",
            "ОЦІНКА ІПОТЕКИ (єОселя 7% на 20 років):",
            f"• Перший внесок (20%): {calc['mortgage']['down_payment']:,} грн",
            f"• Щомісячний платіж:  {calc['mortgage']['monthly_payment']:,} грн/міс",
            "--------------------------------------------------",
            "ВИЛКА ЦІН ДЛЯ ЦЬОГО ОБ'ЄКТА:",
            f"• Бюджетний варіант: {calc['range']['min_total']:,} грн",
            f"• Обраний варіант:   {calc['total']:,} грн",
            f"• Преміум варіант:   {calc['range']['max_total']:,} грн",
            "==================================================",
        ]
    )

    content = "\n".join(lines).replace(",", " ")
    return Response(
        content,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=koshtorys.txt"},
    )


# ---------------------------------------------------------------------------
# ШАБЛОНИ СТОРІНОК
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
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">

    <style>
{% raw %}
:root {
    --paper: #f1f5f9; --panel: #ffffff; --ink: #0f172a; --navy: #0f172a; --navy-2: #1e293b;
    --amber: #f59e0b; --amber-strong: #d97706; --steel: #0284c7; --line: #e2e8f0;
    --line-navy: rgba(255, 255, 255, 0.16); --muted: #64748b; --muted-navy: rgba(255, 255, 255, 0.68);
    --focus: #0284c7; --danger: #ef4444;
    --font-body: "IBM Plex Sans", system-ui, -apple-system, sans-serif;
    --font-display: "IBM Plex Sans Condensed", var(--font-body);
    --font-mono: "IBM Plex Mono", monospace;
}

*, *::before, *::after { box-sizing: border-box; }
[hidden] { display: none !important; }
body { margin: 0; background: var(--paper); color: var(--ink); font-family: var(--font-body); font-size: 16px; line-height: 1.5; }
h1, h2, h3, p, ul { margin: 0; }
button, input, select { font: inherit; color: inherit; }

.top { max-width: 1240px; margin: 0 auto; padding: 24px 24px 0; }
.brand { display: inline-flex; align-items: center; gap: 12px; color: inherit; text-decoration: none; }
.brand-mark { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 10px; background: var(--navy); color: var(--amber); font-size: 1.2rem; }
.brand-name { font-family: var(--font-display); font-weight: 700; font-size: 1.2rem; letter-spacing: -0.01em; }

.intro { max-width: 1240px; margin: 0 auto; padding: 28px 24px 0; border-bottom: 1px solid var(--line); }
.intro-inner { padding-bottom: 24px; }
.intro h1 { font-family: var(--font-display); font-weight: 700; font-size: clamp(1.8rem, 3.5vw, 2.6rem); color: var(--navy); }
.intro p { margin-top: 8px; color: var(--muted); font-size: 1.05rem; }

.layout { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 24px; align-items: start; max-width: 1240px; margin: 0 auto; padding: 28px 24px 80px; }
.sheet { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.03); overflow: hidden; }
.alert { margin: 24px 32px 0; padding: 14px 18px; border: 1.5px solid var(--danger); border-radius: 8px; background: #fef2f2; color: #991b1b; }

.row { display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: 28px; padding: 28px 32px; }
.row + .row { border-top: 1px solid var(--line); }
.row-head h2 { position: relative; padding-left: 14px; font-size: 1.1rem; font-weight: 700; color: var(--navy); }
.row-head h2::before { content: ""; position: absolute; top: 0.15em; left: 0; width: 4px; height: 1.1em; background: var(--amber); border-radius: 2px; }
.row-head p { margin-top: 6px; padding-left: 14px; color: var(--muted); font-size: 0.88rem; }

.fields { display: grid; gap: 20px; }
.field-label { display: block; margin-bottom: 8px; font-weight: 600; font-size: 0.95rem; }
.hint { margin-top: 6px; color: var(--muted); font-size: 0.85rem; }

select, input[type="number"] { width: 100%; height: 48px; padding: 0 14px; border: 1.5px solid var(--line); border-radius: 8px; background: #fff; font-size: 1rem; transition: border-color 0.15s; }
select:focus, input[type="number"]:focus { outline: none; border-color: var(--focus); }
.input-suffix { position: relative; max-width: 260px; }
.input-suffix input { padding-right: 48px; font-family: var(--font-mono); font-weight: 500; }
.suffix { position: absolute; top: 50%; right: 16px; transform: translateY(-50%); color: var(--muted); pointer-events: none; }

.tile input, .pill input, .chip input { position: absolute; opacity: 0; pointer-events: none; }
.tile, .pill, .chip { position: relative; display: block; cursor: pointer; }

.tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.tile-body { display: flex; flex-direction: column; gap: 8px; padding: 18px; border: 1.5px solid var(--line); border-radius: 10px; background: #fff; transition: all 0.15s; }
.tile input:checked + .tile-body { border-color: var(--navy); background: var(--navy); color: #fff; }

.pills { display: flex; flex-wrap: wrap; gap: 8px; }
.pill span { display: grid; place-items: center; min-width: 50px; height: 44px; padding: 0 14px; border: 1.5px solid var(--line); border-radius: 8px; background: #fff; font-family: var(--font-mono); font-weight: 600; transition: all 0.15s; }
.pill input:checked + span { border-color: var(--navy); background: var(--navy); color: #fff; }

.group { margin: 0 0 24px; padding: 0; border: 0; }
.group legend { margin-bottom: 12px; font-weight: 700; font-size: 0.95rem; color: var(--navy); }
.chips { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; }
.chip-body { display: flex; flex-direction: column; height: 100%; padding: 14px; border: 1.5px solid var(--line); border-radius: 8px; background: #fff; transition: all 0.15s; }
.chip-name { font-weight: 600; font-size: 0.95rem; }
.chip-note { margin-top: 4px; color: var(--muted); font-size: 0.83rem; }
.chip-price { margin-top: auto; padding-top: 10px; color: var(--steel); font-family: var(--font-mono); font-size: 0.87rem; font-weight: 600; }
.chip input:checked + .chip-body { border-color: var(--steel); background: #f0f9ff; }

.summary { position: sticky; top: 24px; padding: 28px; border-radius: 14px; background: var(--navy); color: #fff; box-shadow: 0 10px 25px rgba(15, 23, 42, 0.15); }
.summary-label { color: var(--muted-navy); font-size: 0.92rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
.summary-total { margin-top: 10px; font-family: var(--font-mono); font-weight: 700; font-size: clamp(1.8rem, 2.5vw, 2.2rem); }
.cur { margin-left: 6px; color: var(--amber); }
.summary-per { margin-top: 8px; color: var(--muted-navy); font-size: 0.92rem; }

.btn { display: inline-flex; align-items: center; justify-content: center; padding: 14px 22px; border-radius: 8px; font-weight: 600; text-decoration: none; cursor: pointer; border: none; transition: all 0.15s; }
.btn-block { width: 100%; }
.btn-amber { background: var(--amber); color: #0f172a; }
.btn-amber:hover { background: var(--amber-strong); }

@media (max-width: 1100px) { .layout { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 700px) {
    .row { grid-template-columns: minmax(0, 1fr); padding: 20px; }
    .summary { position: sticky; bottom: 0; border-radius: 14px 14px 0 0; padding: 20px; z-index: 10; }
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
        <span class="brand-mark">🏠</span>
        <span class="brand-name">Конструктор житла</span>
    </a>
</header>

<div class="intro">
    <div class="intro-inner">
        <h1>Порахуйте вартість житла за матеріалами</h1>
        <p>Оберіть місто, тип житла та матеріали — підсумок праворуч оновлюється одразу.</p>
    </div>
</div>

<form class="layout" id="calc" action="{{ url_for('calculate_view') }}" method="post" data-estimate-url="{{ url_for('estimate_view') }}">
    <div class="sheet">
        {% if errors %}
        <div class="alert" role="alert">
            <strong>Перевірте форму:</strong>
            <ul>{% for error in errors %}<li>{{ error }}</li>{% endfor %}</ul>
        </div>
        {% endif %}

        <section class="row">
            <div class="row-head">
                <h2>Місто</h2>
                <p>Ціни на матеріали залежать від регіону.</p>
            </div>
            <div class="fields">
                <select name="city" id="city" required>
                    <option value="">Виберіть місто</option>
                    {% for key, city in cities.items() %}
                    <option value="{{ key }}" {% if initial.city == key %}selected{% endif %}>{{ city.name }}</option>
                    {% endfor %}
                </select>
            </div>
        </section>

        <section class="row">
            <div class="row-head">
                <h2>Тип житла</h2>
            </div>
            <div class="fields">
                <div class="tiles">
                    {% for btype, spec in catalog.items() %}
                    <label class="tile">
                        <input type="radio" name="building_type" value="{{ btype }}"
                               data-min="{{ spec['area_limits'][0] }}" data-max="{{ spec['area_limits'][1] }}"
                               data-example="{{ spec['area_example'] }}"
                               {% if cur_type == btype %}checked{% endif %} required>
                        <span class="tile-body">
                            <span class="tile-name" style="font-weight: 700;">{{ spec['title'] }}</span>
                            <span class="tile-desc" style="font-size: 0.88rem;">{{ spec['summary'] }}</span>
                        </span>
                    </label>
                    {% endfor %}
                </div>
            </div>
        </section>

        <section class="row">
            <div class="row-head">
                <h2>Параметри</h2>
            </div>
            <div class="fields">
                <div>
                    <span class="field-label">Кількість кімнат</span>
                    <div class="pills">
                        {% for r in range(1, 6) %}
                        <label class="pill">
                            <input type="radio" name="rooms" value="{{ r }}" {% if cur_rooms == r|string %}checked{% endif %}>
                            <span>{{ r }}</span>
                        </label>
                        {% endfor %}
                    </div>
                </div>

                <div>
                    <label class="field-label" for="area">Загальна площа (м²)</label>
                    <div class="input-suffix">
                        <input type="number" name="area" id="area" step="0.1"
                               value="{{ initial.area or '' }}" required>
                        <span class="suffix">м²</span>
                    </div>
                    <p class="hint" id="areaHint"></p>
                </div>

                <div id="floorsRow" {% if cur_type != 'house' %}hidden{% endif %}>
                    <span class="field-label">Кількість поверхів</span>
                    <div class="pills">
                        {% for f in range(1, 4) %}
                        <label class="pill">
                            <input type="radio" name="floors" value="{{ f }}" {% if cur_floors == f|string %}checked{% endif %}>
                            <span>{{ f }}</span>
                        </label>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </section>

        <section class="row">
            <div class="row-head">
                <h2>Матеріали</h2>
            </div>
            <div>
                {% for btype, spec in catalog.items() %}
                <div class="mat-set" data-type="{{ btype }}" {% if cur_type != btype %}hidden{% endif %}>
                    {% for gkey, group in spec['groups'].items() %}
                    <fieldset class="group">
                        <legend>{{ group['title'] }}</legend>
                        <div class="chips">
                            {% for okey, opt in group['options'].items() %}
                            <label class="chip">
                                <input type="radio" name="{{ btype }}_{{ gkey }}" value="{{ okey }}"
                                       {% if cur_type != btype %}disabled{% endif %}
                                       {% if loop.first %}checked{% endif %}>
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

    <aside class="summary">
        <p class="summary-label">Орієнтовна вартість</p>
        <p class="summary-total"><span id="total">—</span><span class="cur" id="totalCur" hidden>грн</span></p>
        <p class="summary-per" id="perM2">Заповніть форму для розрахунку.</p>
        <button type="submit" class="btn btn-amber btn-block" style="margin-top: 20px;">Детальний розрахунок</button>
    </aside>
</form>

<script>
{% raw %}
(function () {
    "use strict";
    var form = document.getElementById("calc");
    var floorsRow = document.getElementById("floorsRow");
    var totalEl = document.getElementById("total");
    var curEl = document.getElementById("totalCur");
    var perEl = document.getElementById("perM2");
    var estimateUrl = form.getAttribute("data-estimate-url");

    function applyType() {
        var radio = form.querySelector('input[name="building_type"]:checked');
        if (!radio) return;
        var type = radio.value;
        floorsRow.hidden = type !== "house";
        Array.prototype.forEach.call(document.querySelectorAll(".mat-set"), function (set) {
            var active = set.getAttribute("data-type") === type;
            set.hidden = !active;
            Array.prototype.forEach.call(set.querySelectorAll("input"), function (input) {
                input.disabled = !active;
            });
        });
    }

    function runEstimate() {
        fetch(estimateUrl, { method: "POST", body: new URLSearchParams(new FormData(form)) })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.ok) {
                    totalEl.textContent = new Intl.NumberFormat("uk-UA").format(data.total);
                    curEl.hidden = false;
                    perEl.textContent = "Близько " + new Intl.NumberFormat("uk-UA").format(data.per_m2) + " грн/м² (термін: ~" + data.timeline.days + " днів)";
                } else {
                    totalEl.textContent = "—";
                    curEl.hidden = true;
                    perEl.textContent = data.errors.join(". ");
                }
            });
    }

    form.addEventListener("input", runEstimate);
    form.addEventListener("change", function (e) {
        if (e.target.name === "building_type") applyType();
        runEstimate();
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
    <meta name="theme-color" content="#0f172a">

    <title>Розрахунок вартості — Конструктор житла</title>

    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%2310263b'/%3E%3Cpath d='M6 17 16 8l10 9M9 15v10h14V15' stroke='%23f0a81e' stroke-width='2.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">

    <style>
{% raw %}
:root {
    --paper: #f1f5f9; --panel: #ffffff; --ink: #0f172a; --navy: #0f172a; --navy-2: #1e293b;
    --amber: #f59e0b; --steel: #0284c7; --line: #cbd5e1; --muted: #64748b;
    --font-body: "IBM Plex Sans", system-ui, sans-serif; --font-mono: "IBM Plex Mono", monospace;
}
*, *::before, *::after { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink); font-family: var(--font-body); font-size: 16px; line-height: 1.5; }

.top { max-width: 1000px; margin: 0 auto; padding: 24px 24px 0; }
.brand { display: inline-flex; align-items: center; gap: 12px; color: inherit; text-decoration: none; font-weight: 700; font-size: 1.1rem; }

.result { display: grid; gap: 24px; max-width: 1000px; margin: 0 auto; padding: 28px 24px 80px; }
.hero { padding: 36px 40px; border-radius: 16px; background: var(--navy); color: #fff; position: relative; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.15); }
.hero-total { font-family: var(--font-mono); font-size: clamp(2.2rem, 5vw, 3.4rem); margin-top: 6px; font-weight: 700; }

.curr-picker { position: absolute; top: 28px; right: 28px; display: flex; gap: 6px; }
.curr-btn { background: rgba(255,255,255,0.1); color: #fff; border: 1px solid rgba(255,255,255,0.2); padding: 8px 14px; border-radius: 6px; cursor: pointer; font-family: var(--font-mono); font-weight: 600; font-size: 0.9rem; transition: all 0.15s; }
.curr-btn:hover { background: rgba(255,255,255,0.2); }
.curr-btn.active { background: var(--amber); color: #0f172a; border-color: var(--amber); }

.sheet { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 32px; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.03); }
.sheet h2 { margin-bottom: 20px; font-size: 1.25rem; font-weight: 700; color: var(--navy); }

.table { width: 100%; border-collapse: collapse; }
.table th { padding: 0 12px 12px; border-bottom: 2px solid var(--ink); color: var(--muted); text-align: left; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
.table td { padding: 16px 12px; border-bottom: 1px solid var(--line); }
.num { text-align: right; font-family: var(--font-mono); }

.sub { display: block; color: var(--muted); font-size: 0.88rem; }
.range-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
.range-card { padding: 20px; border: 1.5px solid var(--line); border-radius: 10px; background: #fff; }
.range-card.active { border-color: var(--navy); background: #f8fafc; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05); }

.mortgage-box { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; padding: 24px; background: #f0f9ff; border-radius: 10px; border: 1.5px solid #0284c7; }

.blueprint-container { overflow: hidden; border-radius: 12px; border: 1px solid #334155; }
.blueprint-svg { width: 100%; height: auto; display: block; background: #0f172a; }

.btn { display: inline-flex; align-items: center; justify-content: center; padding: 12px 22px; border-radius: 8px; font-weight: 600; text-decoration: none; cursor: pointer; border: 1px solid var(--line); background: #fff; color: var(--ink); transition: all 0.15s; }
.btn:hover { background: #f8fafc; }
.btn-solid { background: var(--navy); color: #fff; border-color: var(--navy); }
.btn-solid:hover { background: var(--navy-2); }
.actions { display: flex; flex-wrap: wrap; gap: 12px; }

@media (max-width: 640px) {
    .hero { padding: 24px; }
    .curr-picker { position: static; margin-bottom: 16px; }
    .sheet { padding: 20px; }
}
{% endraw %}
    </style>
</head>

<body>

<header class="top">
    <a class="brand" href="{{ url_for('index') }}">
        <span>🏠</span>
        <span>Конструктор житла</span>
    </a>
</header>

<main class="result">
    <section class="hero">
        <div class="curr-picker">
            <button type="button" class="curr-btn active" onclick="setCurr('UAH', 1.0, 'грн')">₴ UAH</button>
            <button type="button" class="curr-btn" onclick="setCurr('USD', {{ rates.USD }}, '$')">$ USD</button>
            <button type="button" class="curr-btn" onclick="setCurr('EUR', {{ rates.EUR }}, '€')">€ EUR</button>
        </div>

        <p style="color: rgba(255,255,255,0.7); font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">Загальна вартість</p>
        <h1 class="hero-total"><span id="valTotal">{{ calc.total|money }}</span> <span id="valSymbol" style="color:var(--amber);">грн</span></h1>
        <p style="margin-top: 8px; color: rgba(255,255,255,0.85);">Близько <span id="valPerM2">{{ calc.per_m2|money }}</span> <span class="valSym">грн</span> за м² • {{ calc.type_title }} у м. {{ calc.city_name }} ({{ calc.area|dec }} м²)</p>
    </section>

    <!-- Оновлений інтерактивний архітектурний план (SVG Blueprint) -->
    <section class="sheet">
        <h2>Архітектурне креслення планоміру ({{ calc.area|dec }} м²)</h2>
        <div class="blueprint-container">
            <svg class="blueprint-svg" viewBox="0 0 600 280" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                        <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(59, 130, 246, 0.12)" stroke-width="1"/>
                    </pattern>
                    <pattern id="grid-thick" width="100" height="100" patternUnits="userSpaceOnUse">
                        <rect width="100" height="100" fill="url(#grid)"/>
                        <path d="M 100 0 L 0 0 0 100" fill="none" stroke="rgba(59, 130, 246, 0.25)" stroke-width="1.5"/>
                    </pattern>
                    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 2 L 5 5 L 0 8 z" fill="#38bdf8"/>
                    </marker>
                </defs>

                <!-- Фон креслення -->
                <rect width="100%" height="100%" fill="#0f172a"/>
                <rect width="100%" height="100%" fill="url(#grid-thick)"/>

                <!-- Компаса (Роза вітрів) -->
                <g transform="translate(540, 42)">
                    <circle cx="0" cy="0" r="16" fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>
                    <path d="M 0 -12 L 4 0 L 0 -3 L -4 0 Z" fill="#38bdf8"/>
                    <path d="M 0 12 L 4 0 L 0 3 L -4 0 Z" fill="rgba(255,255,255,0.3)"/>
                    <text x="0" y="-18" fill="#38bdf8" font-size="9" font-family="sans-serif" font-weight="bold" text-anchor="middle">ПН</text>
                </g>

                <!-- Зовнішні розмірні лінії з стрілками -->
                <g stroke="#38bdf8" stroke-width="1" opacity="0.8">
                    <!-- Верхній розмір -->
                    <line x1="60" y1="28" x2="480" y2="28" marker-start="url(#arrow)" marker-end="url(#arrow)"/>
                    <line x1="60" y1="22" x2="60" y2="42" stroke-dasharray="2 2"/>
                    <line x1="480" y1="22" x2="480" y2="42" stroke-dasharray="2 2"/>
                    <!-- Лівий розмір -->
                    <line x1="28" y1="50" x2="28" y2="210" marker-start="url(#arrow)" marker-end="url(#arrow)"/>
                    <line x1="22" y1="50" x2="42" y2="50" stroke-dasharray="2 2"/>
                    <line x1="22" y1="210" x2="42" y2="210" stroke-dasharray="2 2"/>
                </g>
                <text x="270" y="22" fill="#38bdf8" font-size="11" font-family="monospace" text-anchor="middle" font-weight="600">{{ ((calc.area ** 0.5) * 1.3)|round(1)|dec }} м</text>
                <text x="20" y="135" fill="#38bdf8" font-size="11" font-family="monospace" text-anchor="middle" font-weight="600" transform="rotate(-90, 20, 135)">{{ ((calc.area ** 0.5) / 1.3)|round(1)|dec }} м</text>

                <!-- Контур зовнішніх капітальних стін -->
                <rect x="60" y="50" width="420" height="160" fill="rgba(30, 41, 59, 0.85)" stroke="#38bdf8" stroke-width="4" rx="2"/>

                <!-- Віконні прорізи (помаранчеві акценти) -->
                <line x1="120" y1="50" x2="180" y2="50" stroke="#f59e0b" stroke-width="5"/>
                <line x1="300" y1="50" x2="360" y2="50" stroke="#f59e0b" stroke-width="5"/>
                <line x1="120" y1="210" x2="180" y2="210" stroke="#f59e0b" stroke-width="5"/>
                <line x1="300" y1="210" x2="360" y2="210" stroke="#f59e0b" stroke-width="5"/>

                <!-- Внутрішнє планування залежно від кімнат -->
                {% if calc.rooms == 1 %}
                    <rect x="64" y="54" width="412" height="152" fill="rgba(59, 130, 246, 0.08)"/>
                    <text x="270" y="125" fill="#ffffff" font-size="14" font-family="sans-serif" font-weight="600" text-anchor="middle">Основний простір / Студія</text>
                    <text x="270" y="145" fill="#94a3b8" font-size="12" font-family="monospace" text-anchor="middle">~{{ calc.area|dec }} м²</text>

                {% elif calc.rooms == 2 %}
                    <line x1="280" y1="50" x2="280" y2="210" stroke="#38bdf8" stroke-width="3"/>
                    <path d="M 280 110 A 25 25 0 0 1 280 135" fill="none" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="3 2"/>

                    <text x="170" y="125" fill="#ffffff" font-size="13" font-family="sans-serif" font-weight="600" text-anchor="middle">Вітальня / Зала</text>
                    <text x="170" y="145" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.55)|round(1)|dec }} м²</text>

                    <text x="380" y="125" fill="#ffffff" font-size="13" font-family="sans-serif" font-weight="600" text-anchor="middle">Спальня</text>
                    <text x="380" y="145" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.45)|round(1)|dec }} м²</text>

                {% elif calc.rooms == 3 %}
                    <line x1="270" y1="50" x2="270" y2="210" stroke="#38bdf8" stroke-width="3"/>
                    <line x1="270" y1="130" x2="480" y2="130" stroke="#38bdf8" stroke-width="3"/>
                    <path d="M 270 90 A 20 20 0 0 1 270 110" fill="none" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="3 2"/>

                    <text x="165" y="125" fill="#ffffff" font-size="13" font-family="sans-serif" font-weight="600" text-anchor="middle">Вітальня</text>
                    <text x="165" y="145" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.45)|round(1)|dec }} м²</text>

                    <text x="375" y="85" fill="#ffffff" font-size="12" font-family="sans-serif" font-weight="600" text-anchor="middle">Спальня 1</text>
                    <text x="375" y="103" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.30)|round(1)|dec }} м²</text>

                    <text x="375" y="165" fill="#ffffff" font-size="12" font-family="sans-serif" font-weight="600" text-anchor="middle">Спальня 2 / Кабінет</text>
                    <text x="375" y="183" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.25)|round(1)|dec }} м²</text>

                {% elif calc.rooms == 4 %}
                    <line x1="270" y1="50" x2="270" y2="210" stroke="#38bdf8" stroke-width="3"/>
                    <line x1="60" y1="130" x2="480" y2="130" stroke="#38bdf8" stroke-width="3"/>

                    <text x="165" y="85" fill="#ffffff" font-size="12" font-family="sans-serif" font-weight="600" text-anchor="middle">Вітальня</text>
                    <text x="165" y="103" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.35)|round(1)|dec }} м²</text>

                    <text x="375" y="85" fill="#ffffff" font-size="12" font-family="sans-serif" font-weight="600" text-anchor="middle">Спальня 1</text>
                    <text x="375" y="103" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.25)|round(1)|dec }} м²</text>

                    <text x="165" y="165" fill="#ffffff" font-size="12" font-family="sans-serif" font-weight="600" text-anchor="middle">Кухня / Їдальня</text>
                    <text x="165" y="183" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.20)|round(1)|dec }} м²</text>

                    <text x="375" y="165" fill="#ffffff" font-size="12" font-family="sans-serif" font-weight="600" text-anchor="middle">Спальня 2</text>
                    <text x="375" y="183" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.20)|round(1)|dec }} м²</text>

                {% else %}
                    <line x1="200" y1="50" x2="200" y2="210" stroke="#38bdf8" stroke-width="3"/>
                    <line x1="340" y1="50" x2="340" y2="210" stroke="#38bdf8" stroke-width="3"/>
                    <line x1="200" y1="130" x2="480" y2="130" stroke="#38bdf8" stroke-width="3"/>

                    <text x="130" y="125" fill="#ffffff" font-size="12" font-family="sans-serif" font-weight="600" text-anchor="middle">Вітальня</text>
                    <text x="130" y="143" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.3)|round(1)|dec }} м²</text>

                    <text x="270" y="85" fill="#ffffff" font-size="11" font-family="sans-serif" font-weight="600" text-anchor="middle">Спальня 1</text>
                    <text x="270" y="103" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.2)|round(1)|dec }} м²</text>

                    <text x="410" y="85" fill="#ffffff" font-size="11" font-family="sans-serif" font-weight="600" text-anchor="middle">Спальня 2</text>
                    <text x="410" y="103" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.2)|round(1)|dec }} м²</text>

                    <text x="270" y="165" fill="#ffffff" font-size="11" font-family="sans-serif" font-weight="600" text-anchor="middle">Кабінет</text>
                    <text x="270" y="183" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.15)|round(1)|dec }} м²</text>

                    <text x="410" y="165" fill="#ffffff" font-size="11" font-family="sans-serif" font-weight="600" text-anchor="middle">Дитяча</text>
                    <text x="410" y="183" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="middle">~{{ (calc.area * 0.15)|round(1)|dec }} м²</text>
                {% endif %}

                <!-- Архітектурний штамп проєкту -->
                <g transform="translate(320, 222)">
                    <rect x="0" y="0" width="260" height="48" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5" rx="4"/>
                    <line x1="0" y1="24" x2="260" y2="24" stroke="#334155" stroke-width="1"/>
                    <line x1="130" y1="0" x2="130" y2="48" stroke="#334155" stroke-width="1"/>
                    <text x="10" y="16" fill="#38bdf8" font-size="10" font-family="monospace" font-weight="bold">ОБ'ЄКТ: {{ calc.type_title.upper() }}</text>
                    <text x="140" y="16" fill="#f59e0b" font-size="10" font-family="monospace" font-weight="bold">ПЛОЩА: {{ calc.area|dec }} М²</text>
                    <text x="10" y="38" fill="#94a3b8" font-size="9" font-family="sans-serif">ПОВЕРХІВ: {{ calc.floors }} | КІМНАТ: {{ calc.rooms }}</text>
                    <text x="140" y="38" fill="#94a3b8" font-size="9" font-family="sans-serif">М. {{ calc.city_name.upper() }}</text>
                </g>
            </svg>
        </div>
    </section>

    <!-- Вилка цін -->
    <section class="sheet">
        <h2>Порівняльна вилка цін</h2>
        <div class="range-grid">
            <div class="range-card">
                <span class="sub">Бюджетний варіант</span>
                <strong style="display: block; font-size: 1.25rem; font-family: var(--font-mono); margin-top: 4px;"><span class="valRangeMin">{{ calc.range.min_total|money }}</span> <span class="valSym">грн</span></strong>
            </div>
            <div class="range-card active">
                <span class="sub" style="color: var(--navy); font-weight: 700;">Ваш вибір</span>
                <strong style="display: block; font-size: 1.25rem; font-family: var(--font-mono); margin-top: 4px; color: var(--navy);"><span class="valRangeSel">{{ calc.total|money }}</span> <span class="valSym">грн</span></strong>
            </div>
            <div class="range-card">
                <span class="sub">Преміум варіант</span>
                <strong style="display: block; font-size: 1.25rem; font-family: var(--font-mono); margin-top: 4px;"><span class="valRangeMax">{{ calc.range.max_total|money }}</span> <span class="valSym">грн</span></strong>
            </div>
        </div>
    </section>

    <!-- Калькулятор Іпотеки ("єОселя") -->
    <section class="sheet">
        <h2>Розрахунок іпотеки (Програма «єОселя» під 7%)</h2>
        <div class="mortgage-box">
            <div>
                <span class="sub">Перший внесок (20%)</span>
                <strong style="font-size: 1.2rem; font-family: var(--font-mono); display: block; margin-top: 4px;"><span id="valDown">{{ calc.mortgage.down_payment|money }}</span> <span class="valSym">грн</span></strong>
            </div>
            <div>
                <span class="sub">Сума кредиту</span>
                <strong style="font-size: 1.2rem; font-family: var(--font-mono); display: block; margin-top: 4px;"><span id="valLoan">{{ calc.mortgage.loan_amount|money }}</span> <span class="valSym">грн</span></strong>
            </div>
            <div>
                <span class="sub">Щомісячний платіж (20 років)</span>
                <strong style="font-size: 1.2rem; font-family: var(--font-mono); color: var(--steel); display: block; margin-top: 4px;"><span id="valMonthly">{{ calc.mortgage.monthly_payment|money }}</span> <span class="valSym">грн</span>/міс</strong>
            </div>
        </div>
    </section>

    <!-- Деталізація кошторису -->
    <section class="sheet">
        <h2>Деталізація кошторису</h2>
        <table class="table">
            <thead>
                <tr>
                    <th>Позиція</th>
                    <th class="num">Площа</th>
                    <th class="num">Ціна / м²</th>
                    <th class="num">Вартість</th>
                </tr>
            </thead>
            <tbody>
                {% for row in calc.rows %}
                <tr>
                    <td>
                        <strong style="color: var(--navy);">{{ row.label }}</strong>
                        <span class="sub">{{ row.material }}</span>
                    </td>
                    <td class="num">{{ row.area|dec }} м²</td>
                    <td class="num"><span class="valRowPrice" data-base="{{ row.unit_price }}">{{ row.unit_price|money }}</span> <span class="valSym">грн</span></td>
                    <td class="num"><span class="valRowCost" data-base="{{ row.cost }}">{{ row.cost|money }}</span> <span class="valSym">грн</span></td>
                </tr>
                {% endfor %}
                <tr>
                    <td>
                        <strong style="color: var(--navy);">Роботи</strong>
                        <span class="sub">{{ calc.work_pct }}% від матеріалів</span>
                    </td>
                    <td class="num">—</td>
                    <td class="num">—</td>
                    <td class="num"><span class="valWorkCost" data-base="{{ calc.work_cost }}">{{ calc.work_cost|money }}</span> <span class="valSym">грн</span></td>
                </tr>
            </tbody>
        </table>
    </section>

    <div class="actions">
        <form action="{{ url_for('edit_view') }}" method="post">
            {% for name, value in calc.form.items() %}
            <input type="hidden" name="{{ name }}" value="{{ value }}">
            {% endfor %}
            <button type="submit" class="btn btn-solid">Змінити параметри</button>
        </form>

        <form action="{{ url_for('download_txt') }}" method="post">
            {% for name, value in calc.form.items() %}
            <input type="hidden" name="{{ name }}" value="{{ value }}">
            {% endfor %}
            <button type="submit" class="btn">Завантажити кошторис (.txt)</button>
        </form>

        <a class="btn" href="{{ url_for('index') }}">Новий розрахунок</a>
        <button type="button" class="btn" onclick="window.print()">Роздрукувати</button>
    </div>
</main>

<script>
    var baseTotal = {{ calc.total }};
    var basePerM2 = {{ calc.per_m2 }};
    var baseMin = {{ calc.range.min_total }};
    var baseMax = {{ calc.range.max_total }};
    var baseDown = {{ calc.mortgage.down_payment }};
    var baseLoan = {{ calc.mortgage.loan_amount }};
    var baseMonthly = {{ calc.mortgage.monthly_payment }};

    function fmt(n) {
        return new Intl.NumberFormat('uk-UA').format(Math.round(n));
    }

    function setCurr(code, rate, symbol) {
        document.querySelectorAll('.curr-btn').forEach(function(btn) { btn.classList.remove('active'); });
        event.target.classList.add('active');

        document.getElementById('valTotal').textContent = fmt(baseTotal / rate);
        document.getElementById('valSymbol').textContent = symbol;
        document.getElementById('valPerM2').textContent = fmt(basePerM2 / rate);

        document.querySelectorAll('.valSym').forEach(function(el) { el.textContent = symbol; });
        document.querySelector('.valRangeMin').textContent = fmt(baseMin / rate);
        document.querySelector('.valRangeSel').textContent = fmt(baseTotal / rate);
        document.querySelector('.valRangeMax').textContent = fmt(baseMax / rate);

        document.getElementById('valDown').textContent = fmt(baseDown / rate);
        document.getElementById('valLoan').textContent = fmt(baseLoan / rate);
        document.getElementById('valMonthly').textContent = fmt(baseMonthly / rate);

        document.querySelectorAll('.valRowPrice').forEach(function(el) {
            el.textContent = fmt(parseFloat(el.getAttribute('data-base')) / rate);
        });
        document.querySelectorAll('.valRowCost').forEach(function(el) {
            el.textContent = fmt(parseFloat(el.getAttribute('data-base')) / rate);
        });
        document.querySelector('.valWorkCost').textContent = fmt(parseFloat(document.querySelector('.valWorkCost').getAttribute('data-base')) / rate);
    }
</script>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# ЗАПУСК
# ---------------------------------------------------------------------------

def find_free_port(start=5000, tries=30):
    for port in range(start, start + tries):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.3).close()
        except OSError:
            return port
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