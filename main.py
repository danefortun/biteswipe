from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import string
from functools import wraps
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from blog_db import BlogPosts
from config import Config
from db import db
from users_db import GroupSwipeMember, GroupSwipeSession, GroupSwipeVote, SavedRestaurant, Users


ALLOWED_UPLOAD_EXTENSIONS = {"gif", "jpeg", "jpg", "png", "webp"}
MAX_CHAT_MESSAGE_LENGTH = 500
MAX_NAME_LENGTH = 32
MAX_BIO_LENGTH = 256
OSM_AMENITIES = ("restaurant", "fast_food", "cafe", "food_court")
METERS_PER_MILE = 1609.344

ALLERGEN_FILTERS: dict[str, dict[str, str | tuple[str, ...]]] = {
    "celiac": {
        "label": "Celiac",
        "profile_label": "Celiac safe",
        "diet_tags": ("diet:gluten_free",),
    },
    "peanuts": {
        "label": "Peanuts",
        "profile_label": "Peanut safe",
        "diet_tags": ("diet:peanut_free", "diet:nut_free"),
    },
    "milk": {
        "label": "Milk",
        "profile_label": "Dairy free",
        "diet_tags": ("diet:dairy_free", "diet:vegan"),
    },
    "soy": {
        "label": "Soy",
        "profile_label": "Soy free",
        "diet_tags": ("diet:soy_free",),
    },
    "shellFish": {
        "label": "Shellfish",
        "profile_label": "Shellfish safe",
        "diet_tags": ("diet:shellfish_free",),
    },
    "sesame": {
        "label": "Sesame",
        "profile_label": "Sesame safe",
        "diet_tags": ("diet:sesame_free",),
    },
    "treenuts": {
        "label": "Tree nuts",
        "profile_label": "Tree nut safe",
        "diet_tags": ("diet:nut_free",),
    },
    "eggs": {
        "label": "Eggs",
        "profile_label": "Egg free",
        "diet_tags": ("diet:egg_free", "diet:vegan"),
    },
}

PRICE_FILTERS: dict[str, dict[str, Any]] = {
    "cheapPrice": {"label": "$5 - $20", "levels": {0, 1}},
    "mediumPrice": {"label": "$25 - $40", "levels": {2}},
    "expensivePrice": {"label": "$40+", "levels": {3, 4}},
}

FOOD_PREFERENCE_PRESETS = [
    "American",
    "Italian",
    "Seafood",
    "Mexican",
    "Chinese",
    "Japanese",
    "Indian",
    "Mediterranean",
    "Pizza",
    "Vegan",
    "Coffee",
    "Dessert",
    "Breakfast",
    "Healthy",
    "Halal",
    "Korean",
    "Thai",
]

HOBBY_INTEREST_PRESETS = [
    "Gaming",
    "Music",
    "Drawing",
    "Computers",
    "Math",
    "Science",
    "Sports",
    "Reading",
    "Movies",
    "Fitness",
    "Study Spots",
    "Coffee Runs",
]

FOOD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "american": ("american", "burger", "bbq", "barbecue", "diner", "grill"),
    "italian": ("italian", "pizza", "pasta", "trattoria"),
    "seafood": ("seafood", "fish", "sushi", "crab", "lobster", "oyster"),
    "mexican": ("mexican", "taco", "burrito", "quesadilla"),
    "chinese": ("chinese", "dim sum", "dumpling", "noodle"),
    "japanese": ("japanese", "sushi", "ramen", "teriyaki"),
    "indian": ("indian", "curry", "tandoori", "masala"),
    "mediterranean": ("mediterranean", "greek", "falafel", "kebab", "hummus"),
    "pizza": ("pizza", "pizzeria"),
    "vegan": ("vegan", "vegetarian", "plant based", "plant-based"),
    "coffee": ("coffee", "cafe", "espresso", "latte"),
    "dessert": ("dessert", "bakery", "ice cream", "donut", "pastry"),
    "breakfast": ("breakfast", "brunch", "bagel", "pancake"),
    "healthy": ("healthy", "salad", "juice", "smoothie", "vegetarian"),
    "halal": ("halal",),
    "korean": ("korean", "kimchi", "bbq"),
    "thai": ("thai", "pad thai", "curry"),
}

SCHOOL_THEME_ROWS: tuple[tuple[str, str, str, str, str, str, str], ...] = (
    ("princeton.edu", "princeton", "Princeton University", "Princeton", "#E77500", "#000000", "#FFB347"),
    ("mit.edu", "mit", "Massachusetts Institute of Technology", "MIT", "#A31F34", "#8A8B8C", "#A31F34"),
    ("harvard.edu", "harvard", "Harvard University", "Harvard", "#A51C30", "#FFFFFF", "#A51C30"),
    ("stanford.edu", "stanford", "Stanford University", "Stanford", "#8C1515", "#B83A4B", "#8C1515"),
    ("yale.edu", "yale", "Yale University", "Yale", "#00356B", "#63A8E1", "#286DC0"),
    ("uchicago.edu", "uchicago", "University of Chicago", "UChicago", "#800000", "#767676", "#800000"),
    ("duke.edu", "duke", "Duke University", "Duke", "#012169", "#00539B", "#00539B"),
    ("jhu.edu", "johns-hopkins", "Johns Hopkins University", "Johns Hopkins", "#002D72", "#68ACE5", "#0072CE"),
    ("northwestern.edu", "northwestern", "Northwestern University", "Northwestern", "#4E2A84", "#836EAA", "#4E2A84"),
    ("upenn.edu", "penn", "University of Pennsylvania", "Penn", "#011F5B", "#990000", "#2F6DB3"),
    ("caltech.edu", "caltech", "California Institute of Technology", "Caltech", "#FF6C0C", "#76777B", "#FF6C0C"),
    ("cornell.edu", "cornell", "Cornell University", "Cornell", "#B31B1B", "#222222", "#B31B1B"),
    ("brown.edu", "brown", "Brown University", "Brown", "#4E3629", "#ED1C24", "#ED1C24"),
    ("dartmouth.edu", "dartmouth", "Dartmouth College", "Dartmouth", "#00693E", "#12312B", "#00693E"),
    ("columbia.edu", "columbia", "Columbia University", "Columbia", "#B9D9EB", "#003865", "#003865"),
    ("berkeley.edu", "uc-berkeley", "University of California, Berkeley", "UC Berkeley", "#003262", "#FDB515", "#3B7EA1"),
    ("rice.edu", "rice", "Rice University", "Rice", "#00205B", "#C1C6C8", "#00205B"),
    ("ucla.edu", "ucla", "University of California, Los Angeles", "UCLA", "#2774AE", "#FFD100", "#2774AE"),
    ("vanderbilt.edu", "vanderbilt", "Vanderbilt University", "Vanderbilt", "#866D4B", "#000000", "#866D4B"),
    ("cmu.edu", "carnegie-mellon", "Carnegie Mellon University", "Carnegie Mellon", "#C41230", "#1D1D1D", "#C41230"),
    ("umich.edu", "michigan", "University of Michigan-Ann Arbor", "Michigan", "#00274C", "#FFCB05", "#00274C"),
    ("nd.edu", "notre-dame", "University of Notre Dame", "Notre Dame", "#0C2340", "#C99700", "#0C2340"),
    ("wustl.edu", "washu", "Washington University in St. Louis", "WashU", "#A51417", "#007360", "#A51417"),
    ("emory.edu", "emory", "Emory University", "Emory", "#012169", "#C5A057", "#012169"),
    ("georgetown.edu", "georgetown", "Georgetown University", "Georgetown", "#041E42", "#8D817B", "#041E42"),
    ("unc.edu", "unc", "University of North Carolina-Chapel Hill", "UNC", "#4B9CD3", "#13294B", "#4B9CD3"),
    ("virginia.edu", "virginia", "University of Virginia", "UVA", "#232D4B", "#E57200", "#E57200"),
    ("usc.edu", "usc", "University of Southern California", "USC", "#990000", "#FFCC00", "#990000"),
    ("ucsd.edu", "uc-san-diego", "University of California, San Diego", "UC San Diego", "#00629B", "#FFCD00", "#00629B"),
    ("ufl.edu", "florida", "University of Florida", "Florida", "#0021A5", "#FA4616", "#FA4616"),
    ("utexas.edu", "texas", "The University of Texas-Austin", "UT Austin", "#BF5700", "#333F48", "#BF5700"),
    ("gatech.edu", "georgia-tech", "Georgia Institute of Technology", "Georgia Tech", "#B3A369", "#003057", "#B3A369"),
    ("nyu.edu", "nyu", "New York University", "NYU", "#57068C", "#FFFFFF", "#57068C"),
    ("ucdavis.edu", "uc-davis", "University of California, Davis", "UC Davis", "#022851", "#FFBF00", "#022851"),
    ("uci.edu", "uc-irvine", "University of California, Irvine", "UC Irvine", "#0064A4", "#FFD200", "#0064A4"),
    ("bc.edu", "boston-college", "Boston College", "Boston College", "#8A100B", "#B29D6C", "#8A100B"),
    ("tufts.edu", "tufts", "Tufts University", "Tufts", "#3E8EDE", "#0E1E2F", "#3E8EDE"),
    ("illinois.edu", "illinois", "University of Illinois Urbana-Champaign", "Illinois", "#13294B", "#FF5F05", "#FF5F05"),
    ("wisc.edu", "wisconsin", "University of Wisconsin-Madison", "Wisconsin", "#C5050C", "#646569", "#C5050C"),
    ("ucsb.edu", "uc-santa-barbara", "University of California, Santa Barbara", "UC Santa Barbara", "#003660", "#FEBC11", "#003660"),
    ("osu.edu", "ohio-state", "The Ohio State University", "Ohio State", "#BB0000", "#666666", "#BB0000"),
    ("bu.edu", "boston-university", "Boston University", "Boston University", "#CC0000", "#2D2926", "#CC0000"),
    ("rutgers.edu", "rutgers-new-brunswick", "Rutgers University-New Brunswick", "Rutgers", "#CC0033", "#5F6A72", "#CC0033"),
    ("umd.edu", "maryland", "University of Maryland, College Park", "Maryland", "#E21833", "#FFD200", "#E21833"),
    ("washington.edu", "washington", "University of Washington", "Washington", "#4B2E83", "#B7A57A", "#4B2E83"),
    ("lehigh.edu", "lehigh", "Lehigh University", "Lehigh", "#653819", "#A28E6A", "#653819"),
    ("northeastern.edu", "northeastern", "Northeastern University", "Northeastern", "#C8102E", "#000000", "#C8102E"),
    ("purdue.edu", "purdue", "Purdue University", "Purdue", "#CEB888", "#000000", "#CEB888"),
    ("uga.edu", "georgia", "University of Georgia", "Georgia", "#BA0C2F", "#000000", "#BA0C2F"),
    ("rochester.edu", "rochester", "University of Rochester", "Rochester", "#003B71", "#FFD100", "#003B71"),
    ("case.edu", "case-western", "Case Western Reserve University", "Case Western", "#0A304E", "#C8D2D9", "#0A304E"),
    ("fsu.edu", "florida-state", "Florida State University", "Florida State", "#782F40", "#CEB888", "#782F40"),
    ("tamu.edu", "texas-am", "Texas A&M University", "Texas A&M", "#500000", "#D6D3C4", "#500000"),
    ("vt.edu", "virginia-tech", "Virginia Tech", "Virginia Tech", "#861F41", "#E5751F", "#E5751F"),
    ("wfu.edu", "wake-forest", "Wake Forest University", "Wake Forest", "#9E7E38", "#000000", "#9E7E38"),
    ("wm.edu", "william-and-mary", "William & Mary", "William & Mary", "#115740", "#B9975B", "#115740"),
    ("ucmerced.edu", "uc-merced", "University of California, Merced", "UC Merced", "#002856", "#DAA900", "#002856"),
    ("villanova.edu", "villanova", "Villanova University", "Villanova", "#00205B", "#13B5EA", "#0072CE"),
    ("gwu.edu", "george-washington", "George Washington University", "GW", "#033C5A", "#AA9868", "#033C5A"),
    ("psu.edu", "penn-state", "The Pennsylvania State University-University Park", "Penn State", "#1E407C", "#96BEE6", "#009CDE"),
    ("scu.edu", "santa-clara", "Santa Clara University", "Santa Clara", "#862633", "#FFFFFF", "#862633"),
    ("stonybrook.edu", "stony-brook", "Stony Brook University-SUNY", "Stony Brook", "#990000", "#5B6770", "#990000"),
    ("umn.edu", "minnesota", "University of Minnesota-Twin Cities", "Minnesota", "#7A0019", "#FFCC33", "#7A0019"),
    ("msu.edu", "michigan-state", "Michigan State University", "Michigan State", "#18453B", "#FFFFFF", "#18453B"),
    ("ncsu.edu", "nc-state", "North Carolina State University", "NC State", "#CC0000", "#000000", "#CC0000"),
    ("rpi.edu", "rpi", "Rensselaer Polytechnic Institute", "RPI", "#D6001C", "#54585A", "#D6001C"),
    ("umass.edu", "umass-amherst", "University of Massachusetts-Amherst", "UMass Amherst", "#881C1C", "#212721", "#881C1C"),
    ("miami.edu", "miami", "University of Miami", "Miami", "#F47321", "#005030", "#F47321"),
    ("brandeis.edu", "brandeis", "Brandeis University", "Brandeis", "#003478", "#FFFFFF", "#003478"),
    ("tulane.edu", "tulane", "Tulane University of Louisiana", "Tulane", "#006747", "#418FDE", "#006747"),
    ("uconn.edu", "uconn", "University of Connecticut", "UConn", "#000E2F", "#7C878E", "#000E2F"),
    ("pitt.edu", "pittsburgh", "University of Pittsburgh", "Pitt", "#003594", "#FFB81C", "#003594"),
    ("binghamton.edu", "binghamton", "Binghamton University-SUNY", "Binghamton", "#005A43", "#B2B4B2", "#005A43"),
    ("indiana.edu", "indiana", "Indiana University-Bloomington", "Indiana", "#990000", "#EEEDEB", "#990000"),
    ("clemson.edu", "clemson", "Clemson University", "Clemson", "#F56600", "#522D80", "#F56600"),
    ("newark.rutgers.edu", "rutgers-newark", "Rutgers University-Newark", "Rutgers Newark", "#CC0033", "#5F6A72", "#CC0033"),
    ("syracuse.edu", "syracuse", "Syracuse University", "Syracuse", "#D44500", "#000E54", "#D44500"),
    ("buffalo.edu", "buffalo", "University at Buffalo-SUNY", "Buffalo", "#005BBB", "#E56A54", "#005BBB"),
    ("ucr.edu", "uc-riverside", "University of California, Riverside", "UC Riverside", "#003DA5", "#FFB81C", "#003DA5"),
    ("mines.edu", "colorado-mines", "Colorado School of Mines", "Colorado Mines", "#21314D", "#B3A369", "#21314D"),
    ("drexel.edu", "drexel", "Drexel University", "Drexel", "#07294D", "#FFC600", "#007A78"),
    ("njit.edu", "njit", "New Jersey Institute of Technology", "NJIT", "#CC0000", "#58595B", "#CC0000"),
    ("stevens.edu", "stevens", "Stevens Institute of Technology", "Stevens", "#A32638", "#9EA2A2", "#A32638"),
    ("pepperdine.edu", "pepperdine", "Pepperdine University", "Pepperdine", "#00205C", "#F4C300", "#00205C"),
    ("uic.edu", "uic", "University of Illinois Chicago", "UIC", "#001E62", "#D50032", "#D50032"),
    ("wpi.edu", "wpi", "Worcester Polytechnic Institute", "WPI", "#AC2B37", "#5B6770", "#AC2B37"),
    ("yu.edu", "yeshiva", "Yeshiva University", "Yeshiva", "#0033A0", "#FFFFFF", "#0033A0"),
    ("american.edu", "american", "American University", "American", "#004FA3", "#D11242", "#D11242"),
    ("baylor.edu", "baylor", "Baylor University", "Baylor", "#154734", "#FFB81C", "#154734"),
    ("howard.edu", "howard", "Howard University", "Howard", "#003A70", "#E51937", "#003A70"),
    ("marquette.edu", "marquette", "Marquette University", "Marquette", "#003366", "#FDB933", "#003366"),
    ("rit.edu", "rit", "Rochester Institute of Technology", "RIT", "#F76902", "#000000", "#F76902"),
    ("smu.edu", "smu", "Southern Methodist University", "SMU", "#0033A0", "#CC0035", "#CC0035"),
    ("ucsc.edu", "uc-santa-cruz", "University of California, Santa Cruz", "UC Santa Cruz", "#003C6C", "#F2A900", "#003C6C"),
    ("udel.edu", "delaware", "University of Delaware", "Delaware", "#00539F", "#FFD200", "#00539F"),
    ("usf.edu", "south-florida", "University of South Florida", "USF", "#006747", "#CFC493", "#006747"),
    ("fiu.edu", "fiu", "Florida International University", "FIU", "#081E3F", "#B6862C", "#081E3F"),
    ("fordham.edu", "fordham", "Fordham University", "Fordham", "#900028", "#B9975B", "#900028"),
    ("camden.rutgers.edu", "rutgers-camden", "Rutgers University-Camden", "Rutgers Camden", "#CC0033", "#5F6A72", "#CC0033"),
    ("tcu.edu", "tcu", "Texas Christian University", "TCU", "#4D1979", "#A3A9AC", "#4D1979"),
    ("colorado.edu", "colorado-boulder", "University of Colorado Boulder", "Colorado Boulder", "#CFB87C", "#000000", "#CFB87C"),
)

SCHOOL_THEME_EXTRAS: tuple[tuple[str, str, str, str, str, str, str], ...] = (
    ("temple.edu", "temple", "Temple University", "Temple", "#9D2235", "#FFFFFF", "#222222"),
    ("wcupa.edu", "west-chester", "West Chester University", "West Chester", "#4B116F", "#F2C75C", "#6F2DA8"),
)

SCHOOL_THEME_ASSET_OVERRIDES: dict[str, dict[str, str | None]] = {
    "drexel.edu": {"image_file": "schools/drexel.webp"},
    "temple.edu": {"image_file": "schools/temple.webp"},
    "upenn.edu": {"image_file": "schools/upenn.webp", "card_image_file": "schools/upenn logo.webp"},
    "wcupa.edu": {"image_file": "schools/west-chester.webp"},
}


def build_school_theme_map() -> dict[str, dict[str, str | None]]:
    themes: dict[str, dict[str, str | None]] = {}

    for domain, slug, name, short_name, primary, secondary, accent in SCHOOL_THEME_ROWS + SCHOOL_THEME_EXTRAS:
        theme = {
            "slug": slug,
            "name": name,
            "short_name": short_name,
            "primary": primary,
            "secondary": secondary,
            "accent": accent,
            "image_file": f"schools/backdrops/{slug}.webp",
            "card_image_file": f"schools/badges/{slug}.webp",
        }
        theme.update(SCHOOL_THEME_ASSET_OVERRIDES.get(domain, {}))
        themes[domain] = theme

    return themes


SCHOOL_THEMES = build_school_theme_map()

DEFAULT_FILTERS: dict[str, Any] = {
    "celiac": False,
    "peanuts": False,
    "milk": False,
    "soy": False,
    "shellFish": False,
    "sesame": False,
    "treenuts": False,
    "eggs": False,
    "cheapPrice": False,
    "mediumPrice": False,
    "expensivePrice": False,
    "distance": 50,
    "openNow": False,
    "foodPreferences": [],
    "hobbyInterests": [],
}


def create_app(config_object: type[Config] = Config, config_overrides: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    if config_overrides:
        app.config.update(config_overrides)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    register_routes(app)
    register_cli(app)

    if app.config.get("AUTO_CREATE_DB", True):
        with app.app_context():
            db.create_all()
            ensure_user_interest_columns()
            ensure_saved_restaurant_detail_columns()

    return app


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create configured database tables."""
        db.create_all()
        ensure_user_interest_columns()
        ensure_saved_restaurant_detail_columns()
        print("Initialized the database.")


def ensure_user_interest_columns() -> None:
    column_names = get_table_column_names("users")
    required_columns = {
        "allergen_interests_json": "TEXT DEFAULT '[]'",
        "food_preferences_json": "TEXT DEFAULT '[]'",
        "hobby_interests_json": "TEXT DEFAULT '[]'",
    }

    for column_name, column_type in required_columns.items():
        if column_name not in column_names:
            db.session.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))

    db.session.commit()


def ensure_saved_restaurant_detail_columns() -> None:
    column_names = get_table_column_names("saved_restaurants")
    required_columns = {
        "cuisine": "VARCHAR(255)",
        "price_text": "VARCHAR(64)",
        "rating": "FLOAT",
        "review_count": "INTEGER",
        "website": "VARCHAR(512)",
    }

    for column_name, column_type in required_columns.items():
        if column_name not in column_names:
            db.session.execute(text(f"ALTER TABLE saved_restaurants ADD COLUMN {column_name} {column_type}"))

    db.session.commit()


def get_table_column_names(table_name: str) -> set[str]:
    if db.engine.dialect.name == "sqlite":
        return {
            row[1]
            for row in db.session.execute(text(f"PRAGMA table_info({table_name})")).all()
        }

    return {
        row[0]
        for row in db.session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = :table_name
                """
            ),
            {"table_name": table_name},
        ).all()
    }


def register_routes(app: Flask) -> None:
    @app.context_processor
    def inject_template_user() -> dict[str, Any]:
        user = current_user()
        return {
            "template_user": user,
            "school_theme": build_school_theme_payload(user),
        }

    @app.get("/health")
    def health() -> Any:
        return jsonify({"status": "ok"})

    @app.route("/index", methods=["POST", "GET"])
    @app.route("/", methods=["POST", "GET"])
    @login_required
    def home() -> Any:
        user = current_user()
        if user is None:
            session.clear()
            return redirect(url_for("login"))

        if request.method == "POST":
            raw_lat = request.form.get("latitude", "").strip()
            raw_lng = request.form.get("longitude", "").strip()

            ok, message = save_user_location(user, raw_lat, raw_lng)
            flash(message)

            return redirect(url_for("home"))

        return render_template("cards.html")

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile() -> Any:
        user = current_user()
        if user is None:
            abort(404)

        if request.method == "POST":
            action = request.form.get("action", "")

            if action == "upload_pic":
                handle_profile_picture_upload(user)
            elif action == "update_bio":
                update_user_bio(user)
            elif action == "update_name":
                update_user_name(user)
            elif action == "add_food_preference":
                add_user_food_preference(user)
            elif action == "add_hobby_interest":
                add_user_hobby_interest(user)
            elif action == "remove_interest":
                remove_user_interest(user)
            else:
                flash("Unknown profile action.")

            return redirect(url_for("profile"))

        return render_template(
            "public.html",
            u=user,
            saved_restaurant_count=len(user.saved_restaurants),
            allergen_interests=user.get_interest_list("allergen_interests_json"),
            food_preferences=user.get_interest_list("food_preferences_json"),
            hobby_interests=user.get_interest_list("hobby_interests_json"),
            food_preference_presets=FOOD_PREFERENCE_PRESETS,
            hobby_interest_presets=HOBBY_INTEREST_PRESETS,
        )

    @app.get("/credits")
    @login_required
    def credits() -> Any:
        user_id = session.get("id")
        saved_restaurants = (
            SavedRestaurant.query.filter_by(user_id=user_id)
            .order_by(SavedRestaurant.id.desc())
            .all()
            if user_id
            else []
        )
        return render_template("saved.html", saved_restaurants=saved_restaurants)

    @app.route("/login", methods=["POST", "GET"])
    def login() -> Any:
        if request.method == "GET":
            if "email" in session:
                return redirect(url_for("home"))
            return render_template("login.html")

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("pass", "")

        if not email or not password:
            flash("Email and password are required.")
            return render_template("login.html"), 400

        user = Users.query.filter_by(email=email).first()

        if user is not None:
            if not verify_password(user.password, password):
                flash("Invalid email or password.")
                return render_template("login.html"), 401

            if not is_password_hash(user.password):
                user.password = generate_password_hash(password)
                db.session.commit()
        else:
            user = Users(
                name=default_name_from_email(email),
                email=email,
                password=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.commit()

        session.clear()
        session.permanent = False
        session["email"] = user.email
        session["id"] = user.id

        flash("Login successful.")
        return redirect(url_for("home"))

    @app.route("/chat", methods=["POST", "GET"])
    @login_required
    def blog() -> Any:
        if request.method == "POST":
            message = request.form.get("message", "").strip()

            if not message:
                flash("Message cannot be empty.")
                return redirect(url_for("blog"))

            if len(message) > MAX_CHAT_MESSAGE_LENGTH:
                flash(f"Message must be {MAX_CHAT_MESSAGE_LENGTH} characters or fewer.")
                return redirect(url_for("blog"))

            new_msg = BlogPosts(message, session.get("id"))
            db.session.add(new_msg)
            db.session.commit()
            return redirect(url_for("blog"))

        return render_template("blog.html")

    @app.get("/get_posts")
    @login_required
    def get_posts() -> Any:
        posts = BlogPosts.query.order_by(BlogPosts.id.desc()).limit(20).all()
        user_ids = {post.user_id for post in posts if post.user_id is not None}
        users_by_id = {
            user.id: user
            for user in Users.query.filter(Users.id.in_(user_ids)).all()
        } if user_ids else {}

        return jsonify(
            {
                "posts": [
                    {
                        "message": post.message,
                        "user_id": post.user_id,
                        "user_name": users_by_id.get(post.user_id).name
                        if users_by_id.get(post.user_id)
                        else "Unknown",
                        "created_at": post.time,
                    }
                    for post in reversed(posts)
                ]
            }
        )

    @app.get("/logout")
    def logout() -> Any:
        session.clear()
        return redirect(url_for("login"))

    @app.post("/save_location")
    @login_required
    def save_location() -> Any:
        user = current_user()
        if user is None:
            abort(404)

        payload = request.get_json(silent=True) or request.form
        ok, message = save_user_location(
            user,
            payload.get("latitude", ""),
            payload.get("longitude", ""),
        )

        return jsonify({"ok": ok, "message": message}), 200 if ok else 400

    @app.get("/get_restaurant")
    @login_required
    def get_info() -> Any:
        user = current_user()
        if user is None:
            abort(404)

        if user.latitude is None or user.longitude is None:
            return jsonify({"places": [], "error": "Save your location before loading restaurants."}), 400

        filters = get_active_filters(user)
        radius_meters = int(filters["distance"] * METERS_PER_MILE)
        provider = str(current_app.config.get("RESTAURANT_PROVIDER", "auto")).lower()
        api_key = current_app.config.get("GOOGLE_PLACES_API_KEY")

        try:
            if provider == "google" or (provider == "auto" and api_key):
                if not api_key:
                    return jsonify({"places": [], "error": "Google Places API key is not configured."}), 503
                places = search_restaurants_with_google(user, api_key, filters, radius_meters)
                source = "google"
            else:
                places = search_restaurants_with_openstreetmap(user.latitude, user.longitude, radius_meters)
                source = "openstreetmap"
        except Exception:
            current_app.logger.exception("Restaurant search failed.")
            return jsonify({"places": [], "error": "Restaurant search failed. Please try again."}), 502

        filtered_places = apply_restaurant_filters(places, filters)
        message = None

        if places and not filtered_places:
            filtered_places = apply_distance_filter(places, filters)
            message = "No exact filter matches found, so showing nearby restaurants instead."

        return jsonify({"places": filtered_places, "source": source, "message": message})

    @app.post("/save_restaurant")
    @login_required
    def save_restaurant() -> Any:
        user = current_user()
        if user is None:
            abort(404)

        payload = request.get_json(silent=True) or {}
        ok, message, saved = save_selected_restaurant(user, payload)
        return jsonify({"ok": ok, "message": message, "saved": saved}), 200 if ok else 400

    @app.post("/group_session/create")
    @login_required
    def create_group_session() -> Any:
        user = current_user()
        if user is None:
            abort(404)

        group_session = GroupSwipeSession(code=generate_group_code(), host_user_id=user.id)
        db.session.add(group_session)
        db.session.flush()
        add_group_member(group_session, user)
        db.session.commit()
        session["group_swipe_code"] = group_session.code
        return jsonify({"ok": True, "group": serialize_group_session(group_session, user)})

    @app.post("/group_session/join")
    @login_required
    def join_group_session() -> Any:
        user = current_user()
        if user is None:
            abort(404)

        payload = request.get_json(silent=True) or request.form
        code = normalize_group_code(payload.get("code", ""))
        group_session = GroupSwipeSession.query.filter_by(code=code, is_active=True).first()

        if group_session is None:
            return jsonify({"ok": False, "message": "No active group session found for that code."}), 404

        add_group_member(group_session, user)
        db.session.commit()
        session["group_swipe_code"] = group_session.code
        return jsonify({"ok": True, "group": serialize_group_session(group_session, user)})

    @app.post("/group_session/leave")
    @login_required
    def leave_group_session() -> Any:
        session.pop("group_swipe_code", None)
        return jsonify({"ok": True, "message": "Left group mode."})

    @app.get("/group_session/current")
    @login_required
    def current_group_session() -> Any:
        user = current_user()
        if user is None:
            abort(404)

        group_session = get_current_group_session()
        if group_session is None:
            return jsonify({"ok": True, "group": None})

        return jsonify({"ok": True, "group": serialize_group_session(group_session, user)})

    @app.post("/group_session/swipe")
    @login_required
    def group_session_swipe() -> Any:
        user = current_user()
        if user is None:
            abort(404)

        group_session = get_current_group_session()
        if group_session is None:
            return jsonify({"ok": False, "message": "Join or create a group session first."}), 400

        payload = request.get_json(silent=True) or {}
        restaurant = payload.get("restaurant") if isinstance(payload.get("restaurant"), dict) else {}
        place_id = str(payload.get("place") or restaurant.get("place") or "").strip()
        action = str(payload.get("action") or "").strip().lower()

        if not place_id or action not in {"save", "pass"}:
            return jsonify({"ok": False, "message": "Unable to record that group swipe."}), 400

        vote = GroupSwipeVote.query.filter_by(
            session_id=group_session.id,
            user_id=user.id,
            place_id=place_id,
        ).first()

        if vote is None:
            vote = GroupSwipeVote(
                session_id=group_session.id,
                user_id=user.id,
                place_id=place_id,
                action=action,
                restaurant=sanitize_group_restaurant_payload(restaurant),
            )
            db.session.add(vote)
        else:
            vote.set_vote(action, sanitize_group_restaurant_payload(restaurant))

        db.session.commit()
        return jsonify({"ok": True, "group": serialize_group_session(group_session, user)})

    @app.post("/remove_restaurant/<int:restaurant_id>")
    @login_required
    def remove_restaurant(restaurant_id: int) -> Any:
        user_id = session.get("id")
        saved = SavedRestaurant.query.filter_by(id=restaurant_id, user_id=user_id).first_or_404()
        db.session.delete(saved)
        db.session.commit()
        flash(f"Removed {saved.name} from My Stuff.")
        return redirect(url_for("credits"))

    @app.post("/save_filters")
    def save_filters() -> Any:
        payload = request.get_json(silent=True) or {}
        filters = sanitize_filters(payload)
        session["filters"] = filters

        user = current_user()
        if user is not None:
            sync_user_interests_from_filters(user, filters)

        return jsonify({"ok": True, "filters": filters})

    @app.get("/get_filters")
    def get_filters() -> Any:
        user = current_user()
        saved = session.get("filters")

        if saved is None and user is not None:
            saved = filters_from_user_interests(user)

        filters = sanitize_filters(saved or DEFAULT_FILTERS)
        session["filters"] = filters
        return jsonify(filters)


def login_required(view: Any) -> Any:
    @wraps(view)
    def wrapped_view(*args: Any, **kwargs: Any) -> Any:
        if "email" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def current_user() -> Users | None:
    email = session.get("email")
    if not email:
        return None
    return Users.query.filter_by(email=email).first()


def get_email_domain(email: str | None) -> str:
    if not email or "@" not in email:
        return ""

    return email.rsplit("@", 1)[1].strip().lower()


def get_school_theme_for_email(email: str | None) -> dict[str, str | None] | None:
    domain = get_email_domain(email)
    if not domain.endswith(".edu"):
        return None

    if domain in SCHOOL_THEMES:
        return dict(SCHOOL_THEMES[domain], domain=domain, is_generated="false")

    for school_domain in sorted(SCHOOL_THEMES, key=len, reverse=True):
        theme = SCHOOL_THEMES[school_domain]
        if domain.endswith(f".{school_domain}"):
            return dict(theme, domain=school_domain, is_generated="false")

    return build_generated_school_theme(domain)


def build_generated_school_theme(domain: str) -> dict[str, str | None]:
    digest = hashlib.sha256(domain.encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") % 360
    secondary_hue = (hue + 38) % 360
    short_name = domain.split(".", 1)[0].replace("-", " ").title() or "Campus"

    return {
        "slug": slugify_school_theme(domain),
        "name": f"{short_name} Campus",
        "short_name": short_name,
        "primary": f"hsl({hue} 62% 24%)",
        "secondary": f"hsl({secondary_hue} 72% 52%)",
        "accent": f"hsl({hue} 74% 42%)",
        "image_file": None,
        "card_image_file": None,
        "domain": domain,
        "is_generated": "true",
    }


def slugify_school_theme(value: str) -> str:
    slug = []
    previous_dash = False

    for char in value.lower():
        if char.isalnum():
            slug.append(char)
            previous_dash = False
        elif not previous_dash:
            slug.append("-")
            previous_dash = True

    return "".join(slug).strip("-") or "campus"


def build_school_theme_payload(user: Users | None) -> dict[str, str | None] | None:
    if user is None:
        return None

    theme = get_school_theme_for_email(user.email)
    if theme is None:
        return None

    backdrop_file = theme.get("backdrop_file") or theme.get("image_file")
    card_image_file = theme.get("card_image_file") or theme.get("image_file")
    theme["backdrop_url"] = url_for("static", filename=str(backdrop_file)) if backdrop_file else None
    theme["card_image_url"] = url_for("static", filename=str(card_image_file)) if card_image_file else None
    theme["image_url"] = theme["card_image_url"]
    return theme


def save_user_location(user: Users, raw_latitude: Any, raw_longitude: Any) -> tuple[bool, str]:
    try:
        latitude = float(str(raw_latitude).strip())
        longitude = float(str(raw_longitude).strip())
    except ValueError:
        return False, "Unable to save location. Please try again."

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return False, "Location coordinates were outside the valid range."

    user.latitude = latitude
    user.longitude = longitude

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Unable to save user location.")
        return False, "Unable to save location. Please try again."

    return True, "Location saved successfully."


def verify_password(stored_password: str | None, candidate: str) -> bool:
    if not stored_password:
        return False

    if is_password_hash(stored_password):
        return check_password_hash(stored_password, candidate)

    # Supports legacy plaintext records and upgrades them after login.
    return hmac.compare_digest(stored_password, candidate)


def is_password_hash(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith(("pbkdf2:", "scrypt:"))


def default_name_from_email(email: str) -> str:
    name = email.split("@", 1)[0].replace(".", " ").replace("_", " ").strip()
    return (name.title() or "New User")[:MAX_NAME_LENGTH]


def handle_profile_picture_upload(user: Users) -> None:
    file = request.files.get("image")
    if file is None or not file.filename:
        flash("Choose an image before uploading.")
        return

    original_name = secure_filename(file.filename)
    extension = Path(original_name).suffix.lower().lstrip(".")
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        flash("Profile pictures must be GIF, JPEG, PNG, or WebP images.")
        return

    file_name = f"user-{user.id}.{extension}"
    file_path = Path(current_app.config["UPLOAD_FOLDER"]) / file_name

    try:
        file.save(file_path)
        user.pfp_file_path = file_name
        db.session.commit()
        flash("Profile picture updated.")
    except OSError:
        db.session.rollback()
        current_app.logger.exception("Unable to save uploaded profile picture.")
        flash("Unable to save profile picture. Please try again.")


def update_user_bio(user: Users) -> None:
    new_bio = request.form.get("bio", "").strip()
    if len(new_bio) > MAX_BIO_LENGTH:
        flash(f"Bio must be {MAX_BIO_LENGTH} characters or fewer.")
        return

    user.bio = new_bio
    db.session.commit()
    flash("Bio updated.")


def update_user_name(user: Users) -> None:
    new_name = request.form.get("name", "").strip()
    if not 2 <= len(new_name) <= MAX_NAME_LENGTH:
        flash(f"Name must be between 2 and {MAX_NAME_LENGTH} characters.")
        return

    user.name = new_name
    db.session.commit()
    flash("Name updated.")


def add_user_food_preference(user: Users) -> None:
    preference = normalize_interest_label(request.form.get("food_preference", ""))
    if not preference:
        flash("Enter a food preference before adding it.")
        return

    preferences = user.get_interest_list("food_preferences_json")
    preferences.append(preference)
    user.set_interest_list("food_preferences_json", preferences)
    db.session.commit()
    sync_session_filters_from_user(user)
    flash(f"Added {preference} to your food preferences.")


def add_user_hobby_interest(user: Users) -> None:
    interest = normalize_interest_label(request.form.get("hobby_interest", ""))
    if not interest:
        flash("Choose an interest before adding it.")
        return

    interests = user.get_interest_list("hobby_interests_json")
    interests.append(interest)
    user.set_interest_list("hobby_interests_json", interests)
    db.session.commit()
    sync_session_filters_from_user(user)
    flash(f"Added {interest} to your profile interests.")


def remove_user_interest(user: Users) -> None:
    category = request.form.get("category", "")
    value = request.form.get("value", "").strip().lower()
    field_map = {
        "allergen": "allergen_interests_json",
        "food": "food_preferences_json",
        "hobby": "hobby_interests_json",
    }
    field_name = field_map.get(category)

    if not field_name or not value:
        flash("Unable to remove that interest.")
        return

    interests = [
        item
        for item in user.get_interest_list(field_name)
        if item.lower() != value
    ]
    user.set_interest_list(field_name, interests)
    db.session.commit()
    sync_session_filters_from_user(user)
    flash("Interest removed.")


def sanitize_filters(payload: dict[str, Any]) -> dict[str, Any]:
    filters = DEFAULT_FILTERS.copy()

    for key, default in DEFAULT_FILTERS.items():
        if key not in payload:
            continue

        if isinstance(default, bool):
            filters[key] = bool(payload[key])
        elif key == "distance":
            try:
                filters[key] = min(max(int(payload[key]), 1), 100)
            except (TypeError, ValueError):
                filters[key] = default
        elif isinstance(default, list):
            filters[key] = sanitize_interest_values(payload[key])

    return filters


def sanitize_interest_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []

    return [normalize_interest_label(value) for value in values if normalize_interest_label(value)][:30]


def normalize_interest_label(value: Any) -> str:
    text = " ".join(str(value).replace("_", " ").replace("-", " ").split())
    return text[:64]


def filters_from_user_interests(user: Users) -> dict[str, Any]:
    filters = DEFAULT_FILTERS.copy()
    allergen_labels = {
        str(config["profile_label"]).lower(): key
        for key, config in ALLERGEN_FILTERS.items()
    }

    for interest in user.get_interest_list("allergen_interests_json"):
        key = allergen_labels.get(interest.lower())
        if key:
            filters[key] = True

    filters["foodPreferences"] = user.get_interest_list("food_preferences_json")
    filters["hobbyInterests"] = user.get_interest_list("hobby_interests_json")
    return filters


def sync_user_interests_from_filters(user: Users, filters: dict[str, Any]) -> None:
    allergen_interests = [
        str(config["profile_label"])
        for key, config in ALLERGEN_FILTERS.items()
        if filters.get(key)
    ]
    food_preferences = sanitize_interest_values(filters.get("foodPreferences", []))
    hobby_interests = sanitize_interest_values(filters.get("hobbyInterests", []))

    user.set_interest_list("allergen_interests_json", allergen_interests)
    user.set_interest_list("food_preferences_json", food_preferences)
    user.set_interest_list("hobby_interests_json", hobby_interests)
    db.session.commit()


def sync_session_filters_from_user(user: Users) -> None:
    session["filters"] = sanitize_filters(filters_from_user_interests(user))


def get_active_filters(user: Users) -> dict[str, Any]:
    saved = session.get("filters")
    if saved is None:
        saved = filters_from_user_interests(user)

    filters = sanitize_filters(saved)
    session["filters"] = filters
    return filters


def save_selected_restaurant(user: Users, payload: dict[str, Any]) -> tuple[bool, str, dict[str, Any] | None]:
    name = str(payload.get("name", "")).strip()
    place_id = str(payload.get("place", "")).strip()

    if not name or not place_id:
        return False, "Unable to save that restaurant.", None

    source = str(payload.get("source", "openstreetmap")).strip()[:64] or "openstreetmap"
    address = normalize_optional_string(payload.get("address"), 512)
    photo = normalize_optional_string(payload.get("photo"), 512)
    distance_meters = normalize_optional_float(payload.get("distance_meters"))
    cuisine = normalize_optional_string(payload.get("cuisine"), 255)
    price_text = normalize_optional_string(payload.get("price_text"), 64) or format_price_text(normalize_price_level(payload.get("price_level")))
    rating = normalize_optional_float(payload.get("rating"))
    review_count = normalize_optional_int(payload.get("review_count"))
    website = normalize_website_url(payload.get("website"))

    saved = SavedRestaurant.query.filter_by(user_id=user.id, place_id=place_id).first()
    created = saved is None

    if saved is None:
        saved = SavedRestaurant(
            user_id=user.id,
            place_id=place_id,
            name=name[:255],
            source=source,
            address=address,
            photo=photo,
            distance_meters=distance_meters,
            cuisine=cuisine,
            price_text=price_text,
            rating=rating,
            review_count=review_count,
            website=website,
        )
        db.session.add(saved)
    else:
        saved.name = name[:255]
        saved.source = source
        saved.address = address
        saved.photo = photo
        saved.distance_meters = distance_meters
        saved.cuisine = cuisine
        saved.price_text = price_text
        saved.rating = rating
        saved.review_count = review_count
        saved.website = website

    db.session.commit()

    message = f"Saved {saved.name} to My Stuff." if created else f"{saved.name} is already in My Stuff."
    return True, message, serialize_saved_restaurant(saved)


def generate_group_code() -> str:
    alphabet = string.ascii_uppercase + string.digits

    for _ in range(12):
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        if GroupSwipeSession.query.filter_by(code=code).first() is None:
            return code

    return "".join(secrets.choice(alphabet) for _ in range(8))


def normalize_group_code(value: Any) -> str:
    return "".join(char for char in str(value).upper() if char.isalnum())[:12]


def add_group_member(group_session: GroupSwipeSession, user: Users) -> None:
    existing = GroupSwipeMember.query.filter_by(
        session_id=group_session.id,
        user_id=user.id,
    ).first()

    if existing is None:
        db.session.add(GroupSwipeMember(session_id=group_session.id, user_id=user.id))


def get_current_group_session() -> GroupSwipeSession | None:
    code = normalize_group_code(session.get("group_swipe_code", ""))
    if not code:
        return None

    return GroupSwipeSession.query.filter_by(code=code, is_active=True).first()


def sanitize_group_restaurant_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "name",
        "place",
        "source",
        "address",
        "photo",
        "distance_meters",
        "cuisine",
        "price_text",
        "price_level",
        "rating",
        "review_count",
        "website",
        "is_open",
    }
    return {key: payload.get(key) for key in allowed_keys if key in payload}


def serialize_group_session(group_session: GroupSwipeSession, user: Users | None = None) -> dict[str, Any]:
    members = sorted(group_session.members, key=lambda member: member.joined_at)
    member_ids = {member.user_id for member in members}
    member_count = max(len(member_ids), 1)
    votes = list(group_session.votes)
    saved_votes = [vote for vote in votes if vote.action == "save"]
    saved_by_place: dict[str, list[GroupSwipeVote]] = {}

    for vote in saved_votes:
        saved_by_place.setdefault(vote.place_id, []).append(vote)

    consensus = []
    maybe = []
    for place_id, place_votes in saved_by_place.items():
        voter_ids = {vote.user_id for vote in place_votes}
        payload = place_votes[-1].restaurant_payload()
        entry = {
            "place": place_id,
            "name": payload.get("name") or "Restaurant",
            "address": payload.get("address"),
            "photo": payload.get("photo"),
            "source": payload.get("source"),
            "saved_count": len(voter_ids),
            "needed_count": member_count,
        }

        if member_ids and voter_ids >= member_ids:
            consensus.append(entry)
        else:
            maybe.append(entry)

    consensus.sort(key=lambda item: item["name"])
    maybe.sort(key=lambda item: (-item["saved_count"], item["name"]))

    return {
        "code": group_session.code,
        "is_host": bool(user and user.id == group_session.host_user_id),
        "member_count": member_count,
        "members": [
            {
                "id": member.user_id,
                "name": member.user.name if member.user else "BiteSwipe user",
            }
            for member in members
        ],
        "vote_count": len(votes),
        "consensus": consensus[:12],
        "almost": maybe[:12],
    }


def normalize_optional_string(value: Any, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:max_length] if text else None


def normalize_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def serialize_saved_restaurant(saved: SavedRestaurant) -> dict[str, Any]:
    return {
        "id": saved.id,
        "name": saved.name,
        "place": saved.place_id,
        "source": saved.source,
        "address": saved.address,
        "photo": saved.photo,
        "distance_meters": saved.distance_meters,
        "cuisine": saved.cuisine,
        "price_text": saved.price_text,
        "rating": saved.rating,
        "review_count": saved.review_count,
        "website": saved.website,
        "created_at": saved.created_at,
    }


def post_json(
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    form_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
) -> dict[str, Any]:
    request_headers = dict(headers or {})

    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    elif form_data is not None:
        body = urllib_parse.urlencode(form_data).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    else:
        body = None

    http_request = urllib_request.Request(url, data=body, headers=request_headers, method="POST")

    with urllib_request.urlopen(http_request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset))


def build_google_restaurant_query(filters: dict[str, Any]) -> str:
    terms = ["restaurant"]
    food_preferences = sanitize_interest_values(filters.get("foodPreferences", []))

    if food_preferences:
        terms.insert(0, food_preferences[0])

    if filters.get("celiac"):
        terms.append("gluten free")
    if filters.get("milk"):
        terms.append("dairy free")
    if filters.get("eggs"):
        terms.append("egg free")

    return " ".join(terms)


def apply_restaurant_filters(places: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    return [place for place in places if restaurant_matches_filters(place, filters)]


def apply_distance_filter(places: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    return [place for place in places if restaurant_matches_distance(place, filters)]


def restaurant_matches_filters(place: dict[str, Any], filters: dict[str, Any]) -> bool:
    if not restaurant_matches_distance(place, filters):
        return False

    price_level = place.get("price_level")
    if selected_price_levels(filters) and price_level is not None and price_level not in selected_price_levels(filters):
        return False

    if not restaurant_matches_food_preferences(place, sanitize_interest_values(filters.get("foodPreferences", []))):
        return False

    if filters.get("openNow") and place.get("is_open") is False:
        return False

    if not restaurant_matches_allergens(place, filters):
        return False

    return True


def restaurant_matches_distance(place: dict[str, Any], filters: dict[str, Any]) -> bool:
    distance = normalize_optional_float(place.get("distance_meters"))
    return distance is None or distance <= filters["distance"] * METERS_PER_MILE


def selected_price_levels(filters: dict[str, Any]) -> set[int]:
    levels: set[int] = set()

    for key, config in PRICE_FILTERS.items():
        if filters.get(key):
            levels.update(config["levels"])

    return levels


def restaurant_matches_food_preferences(place: dict[str, Any], food_preferences: list[str]) -> bool:
    if not food_preferences:
        return True

    searchable = " ".join(
        str(place.get(key) or "")
        for key in ("name", "address", "cuisine")
    ).lower()

    for preference in food_preferences:
        preference_key = preference.lower()
        keywords = FOOD_KEYWORDS.get(preference_key, (preference_key,))

        if any(keyword in searchable for keyword in keywords):
            return True

    return False


def restaurant_matches_allergens(place: dict[str, Any], filters: dict[str, Any]) -> bool:
    dietary_tags = place.get("dietary_tags") or {}

    for key, config in ALLERGEN_FILTERS.items():
        if not filters.get(key):
            continue

        tag_names = config["diet_tags"]
        known_values = [
            dietary_tags.get(tag_name)
            for tag_name in tag_names
            if dietary_tags.get(tag_name) is not None
        ]

        if known_values and not any(value in {"yes", "only"} for value in known_values):
            return False

    return True


def extract_dietary_tags(tags: dict[str, Any]) -> dict[str, str]:
    return {
        key: str(value).strip().lower()
        for key, value in tags.items()
        if key.startswith("diet:")
    }


def normalize_price_level(value: Any) -> int | None:
    if value is None:
        return None

    text_value = str(value).strip()
    if not text_value:
        return None

    if set(text_value) <= {"$"}:
        return min(max(len(text_value) - 1, 0), 4)

    try:
        return min(max(int(text_value), 0), 4)
    except ValueError:
        return None


def normalize_google_price_level(value: Any) -> int | None:
    if value is None:
        return None

    price_map = {
        "PRICE_LEVEL_FREE": 0,
        "PRICE_LEVEL_INEXPENSIVE": 1,
        "PRICE_LEVEL_MODERATE": 2,
        "PRICE_LEVEL_EXPENSIVE": 3,
        "PRICE_LEVEL_VERY_EXPENSIVE": 4,
    }

    return price_map.get(str(value), normalize_price_level(value))


def format_price_text(price_level: int | None) -> str | None:
    if price_level is None:
        return None

    if price_level <= 0:
        return "Free"

    return "$" * min(price_level, 4)


def normalize_website_url(value: Any) -> str | None:
    website = normalize_optional_string(value, 512)
    if website is None:
        return None

    if website.startswith(("http://", "https://")):
        return website

    return f"https://{website}"


def search_restaurants_with_google(
    user: Users,
    api_key: str,
    filters: dict[str, Any] | None = None,
    radius_meters: int | None = None,
) -> list[dict[str, Any]]:
    url = "https://places.googleapis.com/v1/places:searchText"
    search_headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.photos,places.formattedAddress,"
            "places.priceLevel,places.types,places.rating,places.userRatingCount,"
            "places.websiteUri,places.googleMapsUri,places.currentOpeningHours"
        ),
    }
    filters = filters or DEFAULT_FILTERS
    payload = {
        "textQuery": build_google_restaurant_query(filters),
        "locationBias": {
            "circle": {
                "center": {
                    "latitude": user.latitude,
                    "longitude": user.longitude,
                },
                "radius": float(radius_meters or current_app.config.get("RESTAURANT_SEARCH_RADIUS_METERS", 2000)),
            }
        },
    }

    results = post_json(url, json_body=payload, headers=search_headers, timeout=10).get("places", [])
    return [format_google_place(result, api_key) for result in results]


def search_restaurants_with_openstreetmap(
    latitude: float,
    longitude: float,
    radius_meters: int | None = None,
) -> list[dict[str, Any]]:
    radius = int(radius_meters or current_app.config.get("RESTAURANT_SEARCH_RADIUS_METERS", 2000))
    max_results = int(current_app.config.get("OSM_MAX_RESULTS", 25))
    timeout_seconds = int(current_app.config.get("OSM_OVERPASS_TIMEOUT", 12))
    query = build_overpass_query(latitude, longitude, radius, timeout_seconds, max_results)

    results = post_json(
        current_app.config.get("OSM_OVERPASS_URL", "https://overpass-api.de/api/interpreter"),
        form_data={"data": query},
        headers={"User-Agent": "LifeSwipe/1.0 restaurant search"},
        timeout=timeout_seconds + 3,
    ).get("elements", [])

    places = [
        format_osm_place(element, latitude, longitude)
        for element in results
    ]
    places = [place for place in places if place["name"]]
    places.sort(key=lambda place: place.get("distance_meters") or float("inf"))
    return places[:max_results]


def build_overpass_query(
    latitude: float,
    longitude: float,
    radius: int,
    timeout_seconds: int,
    max_results: int,
) -> str:
    amenity_regex = "|".join(OSM_AMENITIES)

    return f"""
[out:json][timeout:{timeout_seconds}];
(
  node["amenity"~"^({amenity_regex})$"](around:{radius},{latitude},{longitude});
  way["amenity"~"^({amenity_regex})$"](around:{radius},{latitude},{longitude});
  relation["amenity"~"^({amenity_regex})$"](around:{radius},{latitude},{longitude});
);
out center {max_results};
""".strip()


def format_osm_place(
    element: dict[str, Any],
    origin_latitude: float,
    origin_longitude: float,
) -> dict[str, Any]:
    tags = element.get("tags") or {}
    latitude = element.get("lat") or (element.get("center") or {}).get("lat")
    longitude = element.get("lon") or (element.get("center") or {}).get("lon")
    place_type = tags.get("amenity", "restaurant").replace("_", " ")
    name = tags.get("name") or tags.get("brand") or tags.get("operator") or place_type.title()

    return {
        "name": name,
        "place": f"osm:{element.get('type')}:{element.get('id')}",
        "photo": url_for("static", filename="biteswipe.png"),
        "source": "openstreetmap",
        "address": format_osm_address(tags),
        "cuisine": tags.get("cuisine"),
        "price_level": normalize_price_level(tags.get("price") or tags.get("price:range")),
        "price_text": format_price_text(normalize_price_level(tags.get("price") or tags.get("price:range"))),
        "dietary_tags": extract_dietary_tags(tags),
        "rating": None,
        "review_count": None,
        "website": normalize_website_url(tags.get("website") or tags.get("contact:website")),
        "is_open": None,
        "opening_hours_text": tags.get("opening_hours"),
        "distance_meters": distance_meters(origin_latitude, origin_longitude, latitude, longitude)
        if latitude is not None and longitude is not None
        else None,
    }


def format_osm_address(tags: dict[str, Any]) -> str | None:
    parts = [
        tags.get("addr:housenumber"),
        tags.get("addr:street"),
        tags.get("addr:city"),
        tags.get("addr:state"),
    ]
    address = " ".join(str(part) for part in parts if part)
    return address or None


def distance_meters(
    origin_latitude: float,
    origin_longitude: float,
    latitude: float,
    longitude: float,
) -> float:
    earth_radius_meters = 6371000
    lat1 = radians(origin_latitude)
    lat2 = radians(float(latitude))
    delta_lat = radians(float(latitude) - origin_latitude)
    delta_lon = radians(float(longitude) - origin_longitude)

    a = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return round(earth_radius_meters * c, 1)


def format_google_place(place: dict[str, Any], api_key: str) -> dict[str, Any]:
    display_name = place.get("displayName") or {}
    photos = place.get("photos") or []
    photo_name = photos[0].get("name") if photos else None
    opening_hours = place.get("currentOpeningHours") or {}
    weekday_descriptions = opening_hours.get("weekdayDescriptions") or []

    return {
        "name": display_name.get("text", "Unknown restaurant"),
        "place": place.get("id"),
        "photo": (
            f"https://places.googleapis.com/v1/{photo_name}/media?maxHeightPx=500&key={api_key}"
            if photo_name
            else url_for("static", filename="biteswipe.png")
        ),
        "source": "google",
        "address": place.get("formattedAddress"),
        "cuisine": " ".join(place.get("types") or []),
        "price_level": normalize_google_price_level(place.get("priceLevel")),
        "price_text": format_price_text(normalize_google_price_level(place.get("priceLevel"))),
        "dietary_tags": {},
        "rating": normalize_optional_float(place.get("rating")),
        "review_count": place.get("userRatingCount"),
        "website": place.get("websiteUri") or place.get("googleMapsUri"),
        "is_open": opening_hours.get("openNow"),
        "opening_hours_text": "; ".join(weekday_descriptions[:2]) if weekday_descriptions else None,
        "distance_meters": None,
    }


app = create_app()


if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))
