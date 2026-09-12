
import os

from flask import Flask, render_template, request
from dotenv import load_dotenv
from supabase import create_client, Client


# =========================
# Завантаження .env
# =========================

load_dotenv()


# =========================
# Flask
# =========================

app = Flask(__name__)


# =========================
# Supabase
# =========================

SUPABASE_URL = os.getenv("DB_LINK")
SUPABASE_KEY = os.getenv("DB_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "DB_LINK and DB_KEY мають бути в .env"
    )

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================
# Ціни по містах
# =========================

CITY_PRICES = {

    "kyiv": {
        "name": "Київ",
        "coefficient": 1.20
    },

    "lviv": {
        "name": "Львів",
        "coefficient": 1.15
    },

    "odesa": {
        "name": "Одеса",
        "coefficient": 1.10
    },

    "dnipro": {
        "name": "Дніпро",
        "coefficient": 1.00
    },

    "kharkiv": {
        "name": "Харків",
        "coefficient": 0.95
    },

    "vinnytsia": {
        "name": "Вінниця",
        "coefficient": 0.95
    },

    "ternopil": {
        "name": "Тернопіль",
        "coefficient": 0.90
    },

    "ivano-frankivsk": {
        "name": "Івано-Франківськ",
        "coefficient": 0.95
    },

    "uzhhorod": {
        "name": "Ужгород",
        "coefficient": 1.05
    },

    "chernivtsi": {
        "name": "Чернівці",
        "coefficient": 0.90
    }
}


# =========================
# Ціни матеріалів
# =========================

MATERIALS = {

    "walls": {

        "brick": {
            "name": "Цегла",
            "price": 7000
        },

        "gasblock": {
            "name": "Газоблок",
            "price": 5500
        },

        "wood": {
            "name": "Дерево",
            "price": 9000
        }

    },


    "floor": {

        "laminate": {
            "name": "Ламінат",
            "price": 900
        },

        "parquet": {
        "name": "Паркет",
            "price": 1800
        },

        "tile": {
            "name": "Плитка",
            "price": 1300
        }

    },


    "ceiling": {

        "paint": {
            "name": "Фарбування",
            "price": 500
        },

        "stretch": {
            "name": "Натяжна стеля",
            "price": 900
        },

        "plaster": {
            "name": "Штукатурка",
            "price": 650
        }

    },


    "roof": {

        "metal": {
            "name": "Металочерепиця",
            "price": 1200
        },

        "tile": {
            "name": "Черепиця",
            "price": 1800
        },

        "soft": {
            "name": "Бітумна черепиця",
            "price": 1500
        }

    }
}


# =========================
# Головна сторінка
# =========================

@app.route("/")
def home():

    return render_template(
        "index.html",
        cities=CITY_PRICES,
        materials=MATERIALS
    )


# =========================
# Розрахунок
# =========================

@app.route("/calculate", methods=["POST"])
def calculate():

    # -------------------------
    # Основні параметри
    # -------------------------

    building_type = request.form.get("building_type")

    city = request.form.get("city")

    rooms = int(
        request.form.get("rooms")
    )

    area = float(
        request.form.get("area")
    )


    # -------------------------
    # Перевірка міста
    # -------------------------

    if city not in CITY_PRICES:

        return "Неправильне місто", 400


    city_name = CITY_PRICES[city]["name"]

    city_coefficient = CITY_PRICES[city]["coefficient"]


    # -------------------------
    # Поверхи
    # -------------------------

    floors = None

    if building_type == "house":

        floors = int(
            request.form.get("floors")
        )

    elif building_type != "apartment":

        return "Неправильний тип житла", 400


    # -------------------------
    # Матеріали
    # -------------------------

    walls = request.form.get("walls")
    floor = request.form.get("floor")
    ceiling = request.form.get("ceiling")
    roof = request.form.get("roof")


    # -------------------------
    # Перевірка матеріалів
    # -------------------------

    if walls not in MATERIALS["walls"]:
        return "Неправильний матеріал стін", 400

    if floor not in MATERIALS["floor"]:
        return "Неправильний матеріал підлоги", 400

    if ceiling not in MATERIALS["ceiling"]:
        return "Неправильний матеріал стелі", 400

    # Дах потрібен тільки для будинку
    if building_type == "house":

        if roof not in MATERIALS["roof"]:
            return "Неправильний матеріал даху", 400


    # -------------------------
    # Ціни матеріалів
    # -------------------------

    walls_price = MATERIALS["walls"][walls]["price"]

    floor_price = MATERIALS["floor"][floor]["price"]

    ceiling_price = MATERIALS["ceiling"][ceiling]["price"]


    # -------------------------
    # Базова ціна
    # -------------------------

    if building_type == "house":

        base_price = 20000

    else:

        base_price = 15000


    # -------------------------
    # Вартість матеріалів
    # -------------------------

    materials_price = (
        walls_price
        + floor_price
        + ceiling_price
    )


    # -------------------------
    # Дах
    # -------------------------

    roof_price = 0

    if building_type == "house":

        roof_price = MATERIALS["roof"][roof]["price"]


    # -------------------------
    # Загальна ціна за м²
    # -------------------------

    price_per_m2 = (
        base_price
        + materials_price
        + roof_price
    )


    # -------------------------
    # Вплив міста
    # -------------------------

    price_per_m2 = (
        price_per_m2
        * city_coefficient
    )


    # -------------------------
    # Поверхи будинку
    # -------------------------

    if building_type == "house":

        price_per_m2 = (
            price_per_m2
            * (1 + (floors - 1) * 0.10)
        )


    # -------------------------
    # Загальна вартість
    # -------------------------

    total_price = (
        area
        * price_per_m2
    )


    # -------------------------
    # Назви матеріалів
    # -------------------------

    walls_name = MATERIALS["walls"][walls]["name"]

    floor_name = MATERIALS["floor"][floor]["name"]

    ceiling_name = MATERIALS["ceiling"][ceiling]["name"]

    roof_name = None

    if building_type == "house":

        roof_name = MATERIALS["roof"][roof]["name"]


    # -------------------------
    # Результат
    # -------------------------

    return render_template(

        "result.html",

        building_type=building_type,

        city_name=city_name,

        rooms=rooms,

        area=area,

        floors=floors,

        walls_name=walls_name,

        floor_name=floor_name,

        ceiling_name=ceiling_name,

        roof_name=roof_name,

        price_per_m2=price_per_m2,

        total_price=total_price
    )


# =========================
# Запуск
# =========================

if __name__ == "__main__":

    app.run(
        debug=True
    )

