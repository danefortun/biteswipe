from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import string
from functools import wraps
from datetime import datetime, timedelta, timezone
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
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from blog_db import BlogPosts
from config import Config
from db import db, migrate
from users_db import (
    GroupSwipeMember,
    GroupSwipeMessage,
    GroupSwipeSession,
    GroupSwipeVote,
    SavedRestaurant,
    UserActivity,
    UserFollow,
    UserInterest,
    UserNotification,
    UserRestaurantRating,
    Users,
)


ALLOWED_UPLOAD_EXTENSIONS = {"gif", "jpeg", "jpg", "png", "webp"}
MAX_CHAT_MESSAGE_LENGTH = 500
CHAT_PAGE_SIZE = 20
CHAT_RATE_LIMIT_COUNT = 5
CHAT_RATE_LIMIT_WINDOW_SECONDS = 60
MAX_NAME_LENGTH = 32
MAX_HANDLE_LENGTH = 32
MIN_HANDLE_LENGTH = 2
MAX_BIO_LENGTH = 256
MAX_QUICK_INTEREST_LENGTH = 16
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
QUICK_INTEREST_RE = re.compile(r"^[A-Za-z0-9 ]+$")
BLOCKED_QUICK_INTEREST_TERMS = {
    "bastard",
    "bitch",
    "bullshit",
    "chink",
    "cunt",
    "dick",
    "dyke",
    "fag",
    "fuck",
    "gook",
    "kike",
    "nazi",
    "nigga",
    "nigger",
    "paki",
    "prick",
    "retard",
    "shit",
    "slut",
    "tranny",
    "whore",
}
DEFAULT_PROFILE_STAT_VISIBILITY = {
    "saved_picks": True,
    "cravings": True,
    "allergy_signals": True,
    "interests": True,
    "join_date": False,
    "connections": False,
    "places_visited": False,
    "reviews_given": False,
}
DEFAULT_PROFILE_STAT_ENABLED = {
    "saved_picks": True,
    "cravings": True,
    "allergy_signals": True,
    "interests": True,
    "join_date": False,
    "connections": False,
    "places_visited": False,
    "reviews_given": False,
}
PROFILE_STAT_LABELS = {
    "saved_picks": "saved picks",
    "cravings": "cravings",
    "allergy_signals": "allergy signals",
    "interests": "interests",
    "join_date": "join date",
    "connections": "connections",
    "places_visited": "places visited",
    "reviews_given": "reviews given",
}
DEFAULT_PROFILE_STAT_KEYS = ("saved_picks", "cravings", "allergy_signals", "interests")
OPTIONAL_PROFILE_STAT_KEYS = ("join_date", "connections", "places_visited", "reviews_given")
OSM_AMENITIES = ("restaurant", "fast_food", "cafe", "food_court")
METERS_PER_MILE = 1609.344
WALKING_SPEED_METERS_PER_MINUTE = 83

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
    "cheapPrice": {"label": "$5 - $20", "levels": {1}},
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
    "Gym",
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

RESTAURANT_FALLBACK_IMAGE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("coffee", ("coffee", "cafe", "espresso", "tea", "bakery")),
    ("pizza", ("pizza", "pizzeria")),
    ("mexican", ("mexican", "taco", "burrito", "tex-mex")),
    ("asian", ("chinese", "japanese", "korean", "thai", "vietnamese", "sushi", "ramen", "asian")),
    ("indian", ("indian", "curry", "tandoori")),
    ("mediterranean", ("mediterranean", "greek", "middle eastern", "falafel", "halal", "kebab")),
    ("vegan", ("vegan", "vegetarian", "salad", "healthy")),
    ("dessert", ("dessert", "ice cream", "donut", "pastry", "sweet")),
    ("breakfast", ("breakfast", "brunch", "diner", "bagel")),
    ("american", ("american", "burger", "bbq", "barbecue", "sandwich", "fast food", "chicken")),
)
DEFAULT_RESTAURANT_FALLBACK_IMAGE = "general"

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
    "drexel.edu": {"image_file": "schools/backdrops/drexel.webp"},
    "temple.edu": {"image_file": "schools/backdrops/temple.webp"},
    "upenn.edu": {"image_file": "schools/backdrops/penn.webp", "card_image_file": "schools/upenn logo.webp"},
    "wcupa.edu": {"image_file": "schools/backdrops/west-chester.webp"},
}

BADGE_DESCRIPTIONS: dict[str, str] = {
    "Co-Founder": "One of the original minds behind BiteSwipe. A true OG.",
    "BiteBot": "The official BiteSwipe bot account. Beep boop.",
    "First save": "Saved their first restaurant. The journey begins!",
    "10 saves": "Saved 10 restaurants. Building quite the foodie list.",
    "25 saves": "Saved 25 restaurants. A seasoned BiteSwiper.",
    "Power user": "An absolute BiteSwipe machine. 25+ saves and counting.",
    "World traveler": "Saved restaurants across 5+ different cuisines. Globally curious.",
    "Adventurous": "Explored 3+ different cuisines. Always down to try something new.",
    "Safe eater": "Has allergen filters set. Eating smart and staying safe.",
    "Plant based": "Keeps it green. Vegan or vegetarian at heart.",
    "Critic": "Rated 5+ restaurants. Their opinion matters around here.",
    "On a streak": "Active within the last 24 hours. Truly committed to the cause.",
    "Face reveal": "Uploaded a profile picture. We see you!",
    "Camera shy": "Still rocking the default avatar. Mysterious vibes only.",
    "Storyteller": "Wrote a bio. Letting the world know who they are.",
    "People Watcher": "No bio yet. Observing from the shadows.",
    "Fully loaded": "Complete profile — photo, bio, pronouns, and food preferences all set.",
    "Social butterfly": "Following 5+ people. Spreading the foodie love.",
    "Popular": "Has 5+ followers. People want to know what they're eating.",
    "Squad goals": "Deep in the group swipe scene. Always eating with the crew.",
    "'Yo soy fiesta'": "Has hosted a group swipe session. The life of the party.",
    "Founder party": "Has shared a BiteSwipe party with one of the founders.",
    "Taste setter": "Has food preferences set. Knows exactly what they want.",
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
    "distance": 2,
    "minRating": 0,
    "openNow": False,
    "outdoorSeating": False,
    "takeoutOnly": False,
    "dineIn": False,
    "foodPreferences": [],
    "cuisineExclusions": [],
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
    if migrate is not None:
        migrate.init_app(app, db)
    app.jinja_env.globals["uploaded_file_url"] = uploaded_file_url
    app.jinja_env.globals["profile_picture_is_custom"] = profile_picture_is_custom
    app.jinja_env.globals["public_handle_for_user"] = public_handle_for_user
    app.jinja_env.globals["header_account_label"] = header_account_label
    register_routes(app)
    register_cli(app)
    register_shell_context(app)

    if app.config.get("AUTO_CREATE_DB", True):
        with app.app_context():
            db.create_all()
            ensure_user_interest_columns()
            ensure_usernames()
            ensure_user_profile_stat_defaults()
            ensure_saved_restaurant_detail_columns()
            ensure_user_interest_rows()

    return app


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create configured database tables."""
        db.create_all()
        ensure_user_interest_columns()
        ensure_usernames()
        ensure_user_profile_stat_defaults()
        ensure_saved_restaurant_detail_columns()
        ensure_user_interest_rows()
        print("Initialized the database.")


def register_shell_context(app: Flask) -> None:
    @app.shell_context_processor
    def make_shell_context() -> dict[str, Any]:
        return {
            "db": db,
            "BlogPosts": BlogPosts,
            "GroupSwipeMember": GroupSwipeMember,
            "GroupSwipeMessage": GroupSwipeMessage,
            "GroupSwipeSession": GroupSwipeSession,
            "GroupSwipeVote": GroupSwipeVote,
            "SavedRestaurant": SavedRestaurant,
            "UserActivity": UserActivity,
            "UserFollow": UserFollow,
            "UserInterest": UserInterest,
            "UserNotification": UserNotification,
            "UserRestaurantRating": UserRestaurantRating,
            "Users": Users,
        }


def ensure_user_interest_columns() -> None:
    column_names = get_table_column_names("users")
    required_columns = {
        "username": "VARCHAR(32)",
        "email_verified": "BOOLEAN DEFAULT 0 NOT NULL",
        "email_verification_token": "VARCHAR(128)",
        "email_verification_sent_at": "VARCHAR(40)",
        "joined_at": "VARCHAR(40)",
        "profile_stat_visibility_json": "TEXT DEFAULT '{}'",
        "profile_stat_enabled_json": "TEXT DEFAULT '{}'",
        "profile_stat_order_json": "TEXT DEFAULT '[]'",
        "profile_badge_visibility_json": "TEXT DEFAULT '{}'",
        "profile_badge_order_json": "TEXT DEFAULT '[]'",
        "profile_banner_file_path": "VARCHAR(255)",
        "profile_showcase_file_path": "VARCHAR(255)",
        "campus_theme_domain": "VARCHAR(255)",
        "transportation_mode": "VARCHAR(16)",
        "pronouns": "VARCHAR(64)",
        "last_active_at": "VARCHAR(40)",
        "allergen_interests_json": "TEXT DEFAULT '[]'",
        "food_preferences_json": "TEXT DEFAULT '[]'",
        "hobby_interests_json": "TEXT DEFAULT '[]'",
    }

    for column_name, column_type in required_columns.items():
        if column_name not in column_names:
            db.session.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))

    group_columns = get_table_column_names("group_swipe_sessions") if inspect(db.engine).has_table("group_swipe_sessions") else set()
    if group_columns and "expires_at" not in group_columns:
        db.session.execute(text("ALTER TABLE group_swipe_sessions ADD COLUMN expires_at VARCHAR(40)"))

    db.session.commit()


def ensure_usernames() -> None:
    if "username" not in get_table_column_names("users"):
        return

    for user in Users.query.order_by(Users.id.asc()).all():
        username = normalize_user_handle(getattr(user, "username", None))
        if username and username == getattr(user, "username", None):
            continue

        seed = username or default_username_from_email(user.email)
        user.username = unique_public_username(seed, user.id)

    db.session.commit()


def ensure_user_profile_stat_defaults() -> None:
    column_names = get_table_column_names("users")
    if (
        "joined_at" not in column_names
        and "profile_stat_visibility_json" not in column_names
        and "profile_stat_enabled_json" not in column_names
    ):
        return

    changed = False
    now = datetime.now(timezone.utc).isoformat()
    for user in Users.query.order_by(Users.id.asc()).all():
        if "joined_at" in column_names and not getattr(user, "joined_at", None):
            user.joined_at = now
            changed = True
        if "profile_stat_visibility_json" in column_names:
            visibility = profile_stat_visibility_for_user(user)
            if visibility != parse_profile_stat_visibility(getattr(user, "profile_stat_visibility_json", None)):
                user.profile_stat_visibility_json = json.dumps(visibility)
                changed = True
        if "profile_stat_enabled_json" in column_names:
            enabled = profile_stat_enabled_for_user(user)
            if enabled != parse_profile_stat_enabled(getattr(user, "profile_stat_enabled_json", None)):
                user.profile_stat_enabled_json = json.dumps(enabled)
                changed = True

    if changed:
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


def ensure_user_interest_rows() -> None:
    if not inspect(db.engine).has_table("user_interests"):
        return

    for user in Users.query.all():
        for field_name, category in {
            "allergen_interests_json": "allergen",
            "food_preferences_json": "food",
            "hobby_interests_json": "hobby",
        }.items():
            existing = UserInterest.query.filter_by(user_id=user.id, category=category).first()
            if existing is not None:
                continue

            values = parse_legacy_interest_json(getattr(user, field_name, "[]"))
            if values:
                user.set_interest_list(field_name, values)

    db.session.commit()


def parse_legacy_interest_json(value: Any) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []

    if not isinstance(parsed, list):
        return []

    return [normalize_interest_label(item) for item in parsed if normalize_interest_label(item)]


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
        if user is not None:
            touch_user_activity(user)
        return {
            "template_user": user,
            "school_theme": build_school_theme_payload(user),
            "unread_notifications": unread_notifications_for_user(user),
            "profile_completion": build_profile_completion(user) if user is not None else None,
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

        join_group_from_invite(user)
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
            elif action == "upload_banner":
                handle_profile_banner_upload(user)
            elif action == "upload_showcase":
                handle_profile_showcase_upload(user)
            elif action == "update_bio":
                update_user_bio(user)
            elif action == "update_name":
                update_user_name(user)
            elif action == "update_pronouns":
                update_user_pronouns(user)
            elif action == "add_food_preference":
                add_user_food_preference(user)
            elif action == "add_hobby_interest":
                add_user_hobby_interest(user)
            elif action == "remove_interest":
                remove_user_interest(user)
            elif action == "update_campus_theme":
                update_user_campus_theme(user)
            elif action == "update_profile_stat":
                update_user_profile_stat(user)
            elif action == "update_profile_badge":
                update_user_profile_badge(user)
            else:
                flash("Unknown profile action.")

            return redirect(url_for("profile"))

        return render_template("public.html", **build_profile_template_context(user))

    @app.post("/profile/order")
    @login_required
    def update_profile_order() -> Any:
        user = current_user()
        if user is None:
            abort(401)

        payload = request.get_json(silent=True) or {}
        kind = str(payload.get("kind", "")).strip()
        order = [str(item).strip() for item in payload.get("order", []) if str(item).strip()]

        if kind == "stats":
            valid_keys = set(DEFAULT_PROFILE_STAT_VISIBILITY)
            user.profile_stat_order_json = json.dumps([key for key in order if key in valid_keys])
        elif kind == "badges":
            valid_keys = {badge["key"] for badge in build_profile_badges(user, include_hidden=True)}
            user.profile_badge_order_json = json.dumps([key for key in order if key in valid_keys])
        else:
            return jsonify({"ok": False, "message": "Unknown profile order type."}), 400

        db.session.commit()
        return jsonify({"ok": True})

    @app.get("/settings")
    @login_required
    def settings() -> Any:
        user = current_user()
        if user is None:
            abort(404)
        return render_template(
            "settings.html",
            **build_profile_template_context(user),
            incoming_follow_requests=pending_follow_requests(user),
            outgoing_follow_requests=outgoing_follow_requests(user),
        )

    @app.get("/friends/requests")
    @login_required
    def friend_requests() -> Any:
        user = current_user()
        if user is None:
            abort(404)
        return render_template(
            "follow_requests.html",
            incoming_follow_requests=pending_follow_requests(user),
            outgoing_follow_requests=outgoing_follow_requests(user),
        )

    @app.get("/userID=<int:user_id>")
    def legacy_public_user_profile(user_id: int) -> Any:
        return redirect(url_for("public_user_profile", user_id=user_id), code=301)

    @app.get("/user/<int:user_id>")
    def public_user_profile(user_id: int) -> Any:
        user = Users.query.get_or_404(user_id)
        return render_template(
            "public_user.html",
            **build_profile_template_context(user, is_public_profile=True),
        )

    @app.get("/@<handle>")
    def public_user_handle_profile(handle: str) -> Any:
        user = find_user_by_public_handle_or_404(handle)
        return render_template(
            "public_user.html",
            **build_profile_template_context(user, is_public_profile=True),
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

        if user is None:
            flash("No BiteSwipe account exists for that email yet. Create one first.")
            return render_template("login.html"), 404

        if not verify_password(user.password, password):
            flash("Invalid email or password.")
            return render_template("login.html"), 401

        if not is_password_hash(user.password):
            user.password = generate_password_hash(password)
            db.session.commit()

        session.clear()
        session.permanent = False
        session["email"] = user.email
        session["id"] = user.id
        session["needs_campus_prompt"] = bool(get_school_theme_for_email(user.email) and not user.campus_theme_domain)

        flash("Login successful.")
        return redirect(url_for("home"))

    @app.route("/signup", methods=["POST", "GET"])
    def signup() -> Any:
        if request.method == "GET":
            if "email" in session:
                return redirect(url_for("home"))
            return render_template("signup.html")

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("pass", "")
        confirm_password = request.form.get("confirm_pass", "")

        if not email or not password or not confirm_password:
            flash("Email, password, and password confirmation are required.")
            return render_template("signup.html"), 400

        if not is_valid_email(email):
            flash("Enter a valid email address.")
            return render_template("signup.html"), 400

        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template("signup.html"), 400

        if Users.query.filter_by(email=email).first() is not None:
            flash("An account already exists for that email. Log in instead.")
            return render_template("signup.html"), 409

        user = Users(
            name=default_name_from_email(email),
            username=unique_public_username(default_username_from_email(email)),
            email=email,
            password=generate_password_hash(password),
        )
        issue_email_verification(user)
        db.session.add(user)
        db.session.commit()

        session.clear()
        session.permanent = False
        session["email"] = user.email
        session["id"] = user.id
        session["needs_campus_prompt"] = bool(get_school_theme_for_email(user.email))

        flash("Account created. Check your email verification link when delivery is configured.")
        return redirect(url_for("home"))

    @app.get("/verify-email/<token>")
    def verify_email(token: str) -> Any:
        user = Users.query.filter_by(email_verification_token=token).first_or_404()
        user.email_verified = True
        user.email_verification_token = None
        db.session.commit()
        flash("Email verified.")
        return redirect(url_for("login"))

    @app.route("/forgot-password", methods=["POST", "GET"])
    def forgot_password() -> Any:
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            if not email:
                flash("Enter your email to start password recovery.")
                return render_template("forgot_password.html"), 400

            flash("Password reset email delivery is not enabled yet. Ask the BiteSwipe team to reset this account.")
            return render_template("forgot_password.html")

        return render_template("forgot_password.html")

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

            ok, retry_seconds = check_chat_rate_limit()
            if not ok:
                flash(f"Slow down a bit before posting again. Try in {retry_seconds} seconds.")
                return redirect(url_for("blog"))

            new_msg = BlogPosts(message, session.get("id"))
            db.session.add(new_msg)
            db.session.commit()
            return redirect(url_for("blog"))

        return render_template("blog.html")

    @app.get("/get_posts")
    @login_required
    def get_posts() -> Any:
        limit = clamp_int(request.args.get("limit"), 1, CHAT_PAGE_SIZE, CHAT_PAGE_SIZE)
        before_id = clamp_int(request.args.get("before"), 1, 10**12, None)
        query = BlogPosts.query.order_by(BlogPosts.id.desc())
        if before_id:
            query = query.filter(BlogPosts.id < before_id)
        posts = query.limit(limit).all()
        user_ids = {post.user_id for post in posts if post.user_id is not None}
        users_by_id = {
            user.id: user
            for user in Users.query.filter(Users.id.in_(user_ids)).all()
        } if user_ids else {}
        ordered_posts = list(reversed(posts))

        return jsonify(
            {
                "posts": [
                    {
                        "id": post.id,
                        "message": post.message,
                        "user_id": post.user_id,
                        "user_name": users_by_id.get(post.user_id).name
                        if users_by_id.get(post.user_id)
                        else "Unknown",
                        "created_at": post.time,
                    }
                    for post in ordered_posts
                ],
                "has_more": len(posts) == limit,
                "next_before": min((post.id for post in posts), default=None),
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
            if provider == "google":
                if not api_key:
                    return jsonify({"places": [], "error": "Google Places API key is not configured."}), 503
                places = search_restaurants_with_google(user, api_key, filters, radius_meters)
                source = "google"
            elif provider == "openstreetmap":
                places = search_restaurants_with_openstreetmap(user.latitude, user.longitude, radius_meters)
                source = "openstreetmap"
            else:
                places, source = search_restaurants_hybrid(user, api_key, filters, radius_meters)
        except Exception:
            current_app.logger.exception("Restaurant search failed.")
            return jsonify({"places": [], "error": "Restaurant search failed. Please try again."}), 502

        filtered_places = apply_restaurant_filters(places, filters)
        message = None

        if places and not filtered_places:
            filtered_places = apply_distance_filter(places, filters)
            message = "No exact filter matches found, so showing nearby restaurants instead."

        annotate_travel_times(filtered_places, user.transportation_mode)
        annotate_restaurant_confidence(filtered_places, filters)
        sort_restaurants_by_availability(filtered_places)
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

    @app.post("/group_session/message")
    @login_required
    def group_session_message() -> Any:
        user = current_user()
        group_session = get_current_group_session()
        if user is None or group_session is None:
            return jsonify({"ok": False, "message": "Join or create a group first."}), 400
        payload = request.get_json(silent=True) or {}
        message = normalize_optional_string(payload.get("message"), 160)
        if not message:
            return jsonify({"ok": False, "message": "Choose a quick reaction first."}), 400
        db.session.add(GroupSwipeMessage(session_id=group_session.id, user_id=user.id, message=message))
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

    @app.get("/user_ratings")
    @login_required
    def user_ratings() -> Any:
        user_id = session.get("id")
        ratings = (
            UserRestaurantRating.query.filter_by(user_id=user_id).all()
            if user_id
            else []
        )
        return jsonify({"ratings": {row.place_id: row.rating for row in ratings}})

    @app.post("/user_rating")
    @login_required
    def user_rating() -> Any:
        user = current_user()
        if user is None:
            abort(401)

        payload = request.get_json(silent=True) or {}
        place_id = normalize_optional_string(payload.get("place") or payload.get("place_id") or payload.get("name"), 255)
        rating = normalize_optional_int(payload.get("rating"))

        if not place_id or rating is None or rating < 1 or rating > 5:
            return jsonify({"ok": False, "message": "Choose a 1-5 star rating."}), 400

        saved_rating = UserRestaurantRating.query.filter_by(user_id=user.id, place_id=place_id).first()
        if saved_rating is None:
            saved_rating = UserRestaurantRating(user_id=user.id, place_id=place_id, rating=rating)
            db.session.add(saved_rating)
        else:
            saved_rating.update_rating(rating)

        db.session.commit()
        return jsonify({"ok": True, "place": place_id, "rating": saved_rating.rating})

    @app.post("/save_transportation")
    @login_required
    def save_transportation() -> Any:
        user = current_user()
        if user is None:
            abort(401)

        payload = request.get_json(silent=True) or {}
        mode = str(payload.get("mode", "")).strip().lower()
        if mode not in {"walking", "driving", "both"}:
            return jsonify({"ok": False, "message": "Choose walking, driving, or both."}), 400

        user.transportation_mode = mode
        filters = sanitize_filters(session.get("filters") or filters_from_user_interests(user))
        filters["distance"] = 1 if mode == "walking" else 10
        session["filters"] = filters
        db.session.commit()

        return jsonify({"ok": True, "mode": mode, "filters": filters})

    @app.post("/save_campus_theme")
    @login_required
    def save_campus_theme() -> Any:
        user = current_user()
        if user is None:
            abort(401)

        payload = request.get_json(silent=True) or request.form
        domain = str(payload.get("campus_theme_domain", "")).strip().lower()
        if domain and get_school_theme_for_domain(domain) is None:
            return jsonify({"ok": False, "message": "That campus theme is not available yet."}), 400

        user.campus_theme_domain = domain or None
        session["needs_campus_prompt"] = False
        db.session.commit()
        theme = build_school_theme_payload(user)
        return jsonify({"ok": True, "theme": theme, "message": "Campus mode updated."})

    @app.post("/notifications/<int:notification_id>/read")
    @login_required
    def mark_notification_read(notification_id: int) -> Any:
        user = current_user()
        if user is None:
            abort(401)
        notification = UserNotification.query.filter_by(id=notification_id, user_id=user.id).first_or_404()
        notification.is_read = True
        db.session.commit()
        return redirect(notification.link_url or url_for("profile"))

    @app.post("/follow/<int:user_id>")
    @login_required
    def follow_user(user_id: int) -> Any:
        viewer = current_user()
        target = Users.query.get_or_404(user_id)
        if viewer is None or viewer.id == target.id:
            return redirect(url_for("public_user_profile", user_id=user_id))

        follow = UserFollow.query.filter_by(follower_id=viewer.id, following_id=target.id).first()
        if follow is None:
            reciprocal = UserFollow.query.filter_by(follower_id=target.id, following_id=viewer.id).first()
            status = "approved" if reciprocal and reciprocal.status == "approved" else "pending"
            follow = UserFollow(follower_id=viewer.id, following_id=target.id, status=status)
            db.session.add(follow)
            flash("Follow request sent." if status == "pending" else "You are now following each other.")
        db.session.commit()
        return redirect(url_for("public_user_profile", user_id=user_id))

    @app.post("/follow/<int:user_id>/approve")
    @login_required
    def approve_follow_user(user_id: int) -> Any:
        viewer = current_user()
        if viewer is None:
            abort(401)
        follow = UserFollow.query.filter_by(follower_id=user_id, following_id=viewer.id).first_or_404()
        follow.status = "approved"
        reciprocal = UserFollow.query.filter_by(follower_id=viewer.id, following_id=user_id).first()
        if reciprocal is None:
            db.session.add(UserFollow(follower_id=viewer.id, following_id=user_id, status="approved"))
        else:
            reciprocal.status = "approved"
        create_notification(
            user_id=user_id,
            actor_user_id=viewer.id,
            kind="follow_accepted",
            message=f"{viewer.name} accepted your follow request.",
            link_url=url_for("public_user_handle_profile", handle=public_handle_for_user(viewer)),
        )
        db.session.commit()
        flash("Friend approved.")
        return redirect(safe_redirect_target(request.form.get("next")) or url_for("friend_requests"))

    @app.post("/follow/<int:user_id>/decline")
    @login_required
    def decline_follow_user(user_id: int) -> Any:
        viewer = current_user()
        if viewer is None:
            abort(401)
        follow = UserFollow.query.filter_by(follower_id=user_id, following_id=viewer.id, status="pending").first_or_404()
        db.session.delete(follow)
        db.session.commit()
        flash("Follow request declined.")
        return redirect(safe_redirect_target(request.form.get("next")) or url_for("friend_requests"))

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


def get_school_theme_for_domain(domain: str | None) -> dict[str, str | None] | None:
    domain = str(domain or "").strip().lower()
    if not domain:
        return None

    if domain in SCHOOL_THEMES:
        return dict(SCHOOL_THEMES[domain], domain=domain, is_generated="false")

    if domain.endswith(".edu"):
        return build_generated_school_theme(domain)

    return None


def get_user_school_theme_domain(user: Users | None) -> str:
    if user is None:
        return ""

    selected_domain = str(getattr(user, "campus_theme_domain", "") or "").strip().lower()
    if selected_domain:
        return selected_domain

    detected_theme = get_school_theme_for_email(user.email)
    return str(detected_theme.get("domain", "")) if detected_theme else ""


def get_school_theme_options() -> list[dict[str, str | None]]:
    return [
        {
            "domain": domain,
            "name": str(theme["name"]),
            "short_name": str(theme["short_name"]),
        }
        for domain, theme in sorted(SCHOOL_THEMES.items(), key=lambda item: str(item[1]["name"]))
    ]


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

    selected_domain = str(getattr(user, "campus_theme_domain", "") or "").strip().lower()
    theme = get_school_theme_for_domain(selected_domain) if selected_domain else get_school_theme_for_email(user.email)
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


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


def issue_email_verification(user: Users) -> None:
    user.email_verified = False
    user.email_verification_token = secrets.token_urlsafe(32)
    user.email_verification_sent_at = datetime.now(timezone.utc).isoformat()


def clamp_int(value: Any, minimum: int, maximum: int, default: int | None) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def check_chat_rate_limit() -> tuple[bool, int]:
    now = datetime.now(timezone.utc)
    raw_events = session.get("chat_post_times", [])
    events: list[datetime] = []
    event_values = raw_events if isinstance(raw_events, list) else []
    for value in event_values:
        try:
            event_time = datetime.fromisoformat(str(value))
        except ValueError:
            continue
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        if now - event_time < timedelta(seconds=CHAT_RATE_LIMIT_WINDOW_SECONDS):
            events.append(event_time)

    if len(events) >= CHAT_RATE_LIMIT_COUNT:
        oldest = min(events)
        retry_seconds = CHAT_RATE_LIMIT_WINDOW_SECONDS - int((now - oldest).total_seconds())
        return False, max(retry_seconds, 1)

    events.append(now)
    session["chat_post_times"] = [event.isoformat() for event in events]
    return True, 0


def default_name_from_email(email: str) -> str:
    name = email.split("@", 1)[0].replace(".", " ").replace("_", " ").strip()
    return (name.title() or "New User")[:MAX_NAME_LENGTH]


def parse_profile_stat_visibility(value: Any) -> dict[str, bool]:
    visibility = dict(DEFAULT_PROFILE_STAT_VISIBILITY)
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        parsed = {}
    if isinstance(parsed, dict):
        for key in DEFAULT_PROFILE_STAT_VISIBILITY:
            if key in parsed:
                visibility[key] = bool(parsed[key])
    return visibility


def parse_profile_stat_enabled(value: Any) -> dict[str, bool]:
    enabled = dict(DEFAULT_PROFILE_STAT_ENABLED)
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        parsed = {}
    if isinstance(parsed, dict):
        for key in DEFAULT_PROFILE_STAT_ENABLED:
            if key in parsed:
                enabled[key] = bool(parsed[key])
    return enabled


def parse_profile_order(value: Any, valid_keys: set[str]) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        parsed = []
    if not isinstance(parsed, list):
        return []

    order: list[str] = []
    seen: set[str] = set()
    for item in parsed:
        key = str(item).strip()
        if key in valid_keys and key not in seen:
            order.append(key)
            seen.add(key)
    return order


def ordered_items(items: list[dict[str, Any]], order: list[str]) -> list[dict[str, Any]]:
    positions = {key: index for index, key in enumerate(order)}
    return sorted(
        enumerate(items),
        key=lambda pair: (positions.get(str(pair[1].get("key")), len(positions) + pair[0])),
    )


def profile_stat_visibility_for_user(user: Users) -> dict[str, bool]:
    return parse_profile_stat_visibility(getattr(user, "profile_stat_visibility_json", None))


def profile_stat_enabled_for_user(user: Users) -> dict[str, bool]:
    return parse_profile_stat_enabled(getattr(user, "profile_stat_enabled_json", None))


def save_profile_stat_visibility(user: Users, visibility: dict[str, bool]) -> None:
    cleaned = {
        key: bool(visibility.get(key, DEFAULT_PROFILE_STAT_VISIBILITY[key]))
        for key in DEFAULT_PROFILE_STAT_VISIBILITY
    }
    user.profile_stat_visibility_json = json.dumps(cleaned)


def save_profile_stat_enabled(user: Users, enabled: dict[str, bool]) -> None:
    cleaned = {
        key: bool(enabled.get(key, DEFAULT_PROFILE_STAT_ENABLED[key]))
        for key in DEFAULT_PROFILE_STAT_ENABLED
    }
    user.profile_stat_enabled_json = json.dumps(cleaned)


def format_join_date(value: str | None) -> str:
    if not value:
        return "New"
    try:
        joined_at = datetime.fromisoformat(value)
    except ValueError:
        return "New"
    return joined_at.strftime("%b %Y")


def build_profile_stats(user: Users, include_hidden: bool = False) -> list[dict[str, Any]]:
    visibility = profile_stat_visibility_for_user(user)
    enabled = profile_stat_enabled_for_user(user)
    food_preferences = user.get_interest_list("food_preferences_json")
    allergen_interests = user.get_interest_list("allergen_interests_json")
    hobby_interests = user.get_interest_list("hobby_interests_json")
    connection_rows = UserFollow.query.filter(
        ((UserFollow.follower_id == user.id) | (UserFollow.following_id == user.id)),
        UserFollow.status == "approved",
    ).all()
    connection_ids = {
        row.following_id if row.follower_id == user.id else row.follower_id
        for row in connection_rows
    }
    connections = len(connection_ids)
    reviews_given = UserRestaurantRating.query.filter_by(user_id=user.id).count()
    values: dict[str, str | int] = {
        "saved_picks": len(user.saved_restaurants),
        "cravings": len(food_preferences),
        "allergy_signals": len(allergen_interests),
        "interests": len(hobby_interests),
        "join_date": format_join_date(getattr(user, "joined_at", None)),
        "connections": connections,
        "places_visited": len(user.saved_restaurants),
        "reviews_given": reviews_given,
    }

    stats = []
    for key in (*DEFAULT_PROFILE_STAT_KEYS, *OPTIONAL_PROFILE_STAT_KEYS):
        visible = visibility.get(key, False)
        is_enabled = enabled.get(key, key in DEFAULT_PROFILE_STAT_KEYS)
        is_default = key in DEFAULT_PROFILE_STAT_KEYS
        if (include_hidden and is_enabled) or visible:
            stats.append(
                {
                    "key": key,
                    "label": PROFILE_STAT_LABELS[key],
                    "value": values[key],
                    "visible": visible,
                    "enabled": is_enabled,
                    "is_default": is_default,
                }
            )
    ordered = ordered_items(
        stats,
        parse_profile_order(getattr(user, "profile_stat_order_json", None), set(DEFAULT_PROFILE_STAT_VISIBILITY)),
    )
    return [item for _, item in ordered]


def badge_key_for_label(label: str) -> str:
    return "badge-" + re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def profile_badge_visibility_for_user(user: Users, badge_keys: set[str]) -> dict[str, bool]:
    visibility = {key: True for key in badge_keys}
    try:
        parsed = json.loads(getattr(user, "profile_badge_visibility_json", None) or "{}")
    except (TypeError, json.JSONDecodeError):
        parsed = {}
    if isinstance(parsed, dict):
        for key in badge_keys:
            if key in parsed:
                visibility[key] = bool(parsed[key])
    return visibility


def build_profile_badges(user: Users, include_hidden: bool = False) -> list[dict[str, Any]]:
    raw_badges: list[dict[str, Any]] = []
    if user.pronouns:
        raw_badges.append({"key": "pronouns", "label": user.pronouns, "description": "Profile pronouns"})

    favorite_cuisine = favorite_cuisine_for_user(user)
    if favorite_cuisine:
        raw_badges.append({
            "key": "favorite-cuisine",
            "label": f"Favorite: {favorite_cuisine}",
            "description": "Favorite cuisine from profile preferences",
        })

    for badge in build_user_badges(user):
        raw_badges.append({
            "key": badge_key_for_label(badge),
            "label": badge,
            "description": BADGE_DESCRIPTIONS.get(badge, ""),
        })

    badge_keys = {badge["key"] for badge in raw_badges}
    visibility = profile_badge_visibility_for_user(user, badge_keys)
    badges = [
        badge | {"visible": visibility.get(badge["key"], True)}
        for badge in raw_badges
        if include_hidden or visibility.get(badge["key"], True)
    ]
    ordered = ordered_items(
        badges,
        parse_profile_order(getattr(user, "profile_badge_order_json", None), badge_keys),
    )
    return [item for _, item in ordered]


def default_username_from_email(email: str) -> str:
    return normalize_user_handle(email.split("@", 1)[0]) or "user"


def normalize_user_handle(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("@"):
        text = text[1:]
    handle = re.sub(r"[^a-z0-9_]+", "-", text).strip("-_")
    return handle[:MAX_HANDLE_LENGTH]


def is_public_username_available(username: str, current_user_id: int | None = None) -> bool:
    existing = Users.query.filter_by(username=username).first()
    return existing is None or existing.id == current_user_id


def unique_public_username(seed: Any, current_user_id: int | None = None) -> str:
    base = normalize_user_handle(seed) or "user"
    if base.isdigit():
        base = f"user-{base}"
    if len(base) < MIN_HANDLE_LENGTH:
        base = f"{base}user"[:MAX_HANDLE_LENGTH]

    if is_public_username_available(base, current_user_id):
        return base

    for suffix in range(2, 10000):
        suffix_text = f"-{suffix}"
        candidate = f"{base[:MAX_HANDLE_LENGTH - len(suffix_text)]}{suffix_text}"
        if is_public_username_available(candidate, current_user_id):
            return candidate

    return f"user-{secrets.token_hex(4)}"


def public_handle_for_user(user: Users) -> str:
    handle = normalize_user_handle(getattr(user, "username", None))
    return handle or f"user-{user.id}"


def header_account_label(user: Users | None) -> str:
    if user is None:
        return "Settings"
    if user.name and user.name.strip():
        return user.name.strip()
    return f"@{public_handle_for_user(user)}"


def safe_redirect_target(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("/") and not value.startswith("//"):
        return value
    return None


def find_user_by_public_handle_or_404(handle: str) -> Users:
    normalized_handle = normalize_user_handle(handle)
    if not normalized_handle:
        abort(404)

    user = Users.query.filter_by(username=normalized_handle).first()
    if user is not None:
        return user

    abort(404)


def build_profile_template_context(user: Users, is_public_profile: bool = False) -> dict[str, Any]:
    profile_handle = public_handle_for_user(user)
    profile_completion = build_profile_completion(user)
    profile_stats = build_profile_stats(user, include_hidden=not is_public_profile)
    profile_stat_enabled = profile_stat_enabled_for_user(user)
    return {
        "u": user,
        "profile_handle": profile_handle,
        "profile_handle_label": f"(@{profile_handle})",
        "public_handle_for_user": public_handle_for_user,
        "is_public_profile": is_public_profile,
        "profile_completion": profile_completion,
        "profile_steps": profile_completion["completed_count"],
        "profile_stats": profile_stats,
        "available_profile_stats": [
            {
                "key": key,
                "label": PROFILE_STAT_LABELS[key],
            }
            for key in OPTIONAL_PROFILE_STAT_KEYS
            if not profile_stat_enabled.get(key, False)
        ],
        "saved_restaurant_count": len(user.saved_restaurants),
        "allergen_interests": user.get_interest_list("allergen_interests_json"),
        "food_preferences": user.get_interest_list("food_preferences_json"),
        "hobby_interests": user.get_interest_list("hobby_interests_json"),
        "food_preference_presets": FOOD_PREFERENCE_PRESETS,
        "hobby_interest_presets": HOBBY_INTEREST_PRESETS,
        "school_theme_options": get_school_theme_options(),
        "current_school_theme_domain": get_user_school_theme_domain(user),
        "selected_campus_theme_domain": str(user.campus_theme_domain or ""),
        "detected_school_theme": get_school_theme_for_email(user.email),
        "favorite_cuisine": favorite_cuisine_for_user(user),
        "profile_badges": build_profile_badges(user, include_hidden=not is_public_profile),
        "badge_descriptions": BADGE_DESCRIPTIONS,
        "foodies_you_might_know": suggest_school_users(user) if not is_public_profile else [],
        "profile_activity": build_profile_activity(user),
        "follow_status": follow_status_for_viewer(user) if is_public_profile else None,
        "incoming_follow_request": incoming_follow_request_from_profile(user) if is_public_profile else None,
        "pending_follow_requests": pending_follow_requests(user) if not is_public_profile else [],
    }


def profile_picture_is_custom(user: Users | None) -> bool:
    if user is None:
        return False
    value = str(getattr(user, "pfp_file_path", "") or "")
    return bool(value and value != "transparentnewdefaultpicture.png")


def build_profile_completion(user: Users) -> dict[str, Any]:
    interest_count = (
        len(user.get_interest_list("allergen_interests_json"))
        + len(user.get_interest_list("food_preferences_json"))
        + len(user.get_interest_list("hobby_interests_json"))
    )
    steps = [
        {
            "key": "bio",
            "label": "Bio",
            "href": "#about-title",
            "complete": bool(user.bio and user.bio != "this is a placeholder!" and user.bio.strip()),
        },
        {
            "key": "photo",
            "label": "Photo",
            "href": "#profile-image",
            "complete": profile_picture_is_custom(user),
        },
        {
            "key": "pronouns",
            "label": "Pronouns",
            "href": "#profile-pronouns",
            "complete": bool(getattr(user, "pronouns", None)),
        },
        {
            "key": "interests",
            "label": "Interests",
            "href": "#interests-title",
            "complete": interest_count > 0,
        },
    ]
    completed = [step for step in steps if step["complete"]]
    missing = [step for step in steps if not step["complete"]]
    return {
        "steps": steps,
        "completed_count": len(completed),
        "total_count": len(steps),
        "percent": int(round(len(completed) / len(steps) * 100)),
        "missing": missing,
    }


def unread_notifications_for_user(user: Users | None) -> list[UserNotification]:
    if user is None:
        return []
    return (
        UserNotification.query.filter_by(user_id=user.id, is_read=False)
        .order_by(UserNotification.created_at.desc())
        .limit(5)
        .all()
    )


def create_notification(
    user_id: int,
    kind: str,
    message: str,
    actor_user_id: int | None = None,
    link_url: str | None = None,
) -> None:
    db.session.add(
        UserNotification(
            user_id=user_id,
            actor_user_id=actor_user_id,
            kind=kind,
            message=message,
            link_url=link_url,
        )
    )


def touch_user_activity(user: Users) -> None:
    now = datetime.now(timezone.utc).isoformat()
    if user.last_active_at and user.last_active_at[:13] == now[:13]:
        return
    user.last_active_at = now
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()


def favorite_cuisine_for_user(user: Users) -> str | None:
    preferences = user.get_interest_list("food_preferences_json")
    return preferences[0] if preferences else None


def configured_founder_user_ids() -> set[int]:
    raw_value = current_app.config.get("BITESWIPE_FOUNDER_USER_IDS", [1])
    if isinstance(raw_value, str):
        raw_items = raw_value.split(",")
    elif isinstance(raw_value, (list, tuple, set)):
        raw_items = raw_value
    else:
        raw_items = [raw_value]

    user_ids: set[int] = set()
    for item in raw_items:
        try:
            user_id = int(str(item).strip())
        except (TypeError, ValueError):
            continue
        if user_id > 0:
            user_ids.add(user_id)
    return user_ids


def configured_founder_handles() -> set[str]:
    raw_value = current_app.config.get("BITESWIPE_FOUNDER_HANDLES", [])
    if isinstance(raw_value, str):
        raw_items = raw_value.split(",")
    elif isinstance(raw_value, (list, tuple, set)):
        raw_items = raw_value
    else:
        raw_items = [raw_value]
    return {handle for item in raw_items if (handle := normalize_user_handle(item))}


def is_biteswipe_founder(user: Users) -> bool:
    return user.id in configured_founder_user_ids() or public_handle_for_user(user) in configured_founder_handles()


def has_partied_with_biteswipe_founder(user: Users) -> bool:
    founder_ids = configured_founder_user_ids()
    founder_handles = configured_founder_handles()
    if not founder_ids and not founder_handles:
        return False

    for membership in user.group_swipe_memberships:
        for member in membership.session.members:
            if member.user_id == user.id:
                continue
            if member.user_id in founder_ids:
                return True
            member_user = member.user
            if member_user is not None and public_handle_for_user(member_user) in founder_handles:
                return True

    return False


def build_user_badges(user: Users) -> list[str]:
    badges = []
    saved_count = len(user.saved_restaurants)

    # --- Founder / special accounts ---
    if is_biteswipe_founder(user):
        badges.append("Co-Founder")
    if user.id == 2:
        badges.append("BiteBot")

    # --- Save milestones ---
    if saved_count >= 25:
        badges.append("25 saves")
    elif saved_count >= 10:
        badges.append("10 saves")
    elif saved_count >= 1:
        badges.append("First save")

    # --- Food explorer ---
    saved_cuisines = {
        r.cuisine.lower()
        for r in user.saved_restaurants
        if r.cuisine
    }
    if len(saved_cuisines) >= 5:
        badges.append("World traveler")
    elif len(saved_cuisines) >= 3:
        badges.append("Adventurous")

    # --- Allergen / dietary ---
    allergen_interests = user.get_interest_list("allergen_interests_json")
    food_preferences = user.get_interest_list("food_preferences_json")

    if allergen_interests:
        badges.append("Safe eater")

    plant_based_keywords = {"vegan", "vegetarian", "plant based"}
    if any(p.lower() in plant_based_keywords for p in food_preferences):
        badges.append("Plant based")

    # --- Activity ---
    rated_count = UserRestaurantRating.query.filter_by(user_id=user.id).count()
    if rated_count >= 5:
        badges.append("Critic")

    if saved_count >= 25:
        badges.append("Power user")

    if user.last_active_at:
        try:
            last_active = datetime.fromisoformat(user.last_active_at)
            days_since_active = (datetime.now(timezone.utc) - last_active.replace(tzinfo=timezone.utc)).days
            if days_since_active <= 1:
                badges.append("On a streak")
        except ValueError:
            pass

    # --- Profile completion ---
    if getattr(user, "pfp_file_path", None):
        badges.append("Face reveal")

    if getattr(user, "bio", None) and len(user.bio.strip()) > 0:
        badges.append("Storyteller")

    fully_loaded = all([
        getattr(user, "pfp_file_path", None),
        getattr(user, "bio", None),
        getattr(user, "pronouns", None),
        food_preferences,
    ])
    if fully_loaded:
        badges.append("Fully loaded")

    # --- Social ---
    following_count = UserFollow.query.filter_by(
        follower_id=user.id, status="approved"
    ).count()
    follower_count = UserFollow.query.filter_by(
        following_id=user.id, status="approved"
    ).count()

    if following_count >= 5:
        badges.append("Social butterfly")
    if follower_count >= 5:
        badges.append("Popular")

    hosted_count = len(user.hosted_group_sessions)
    group_member_count = GroupSwipeMember.query.filter_by(user_id=user.id).count()

    if hosted_count >= 5 or group_member_count >= 5:
        badges.append("Squad goals")

    # --- Group host ---
    if user.hosted_group_sessions:
        badges.append("'Yo soy fiesta'")

    if has_partied_with_biteswipe_founder(user):
        badges.append("Founder party")

    # --- Taste setter ---
    if favorite_cuisine_for_user(user):
        badges.append("Taste setter")

    return badges


def build_profile_activity(user: Users) -> list[str]:
    activity = [row.summary for row in sorted(user.activity_rows, key=lambda row: row.created_at, reverse=True)[:6]]
    if activity:
        return activity
    return [f"Saved {row.name}" for row in sorted(user.saved_restaurants, key=lambda row: row.created_at, reverse=True)[:4]]


def suggest_school_users(user: Users) -> list[Users]:
    domain = user.email.split("@", 1)[1].lower() if "@" in user.email else ""
    if not domain:
        return []
    my_interests = {
        value.strip().lower()
        for field_name in ("allergen_interests_json", "food_preferences_json", "hobby_interests_json")
        for value in user.get_interest_list(field_name)
        if value.strip()
    }
    candidates = (
        Users.query.filter(Users.email.ilike(f"%@{domain}"), Users.id != user.id)
        .order_by(Users.id.desc())
        .limit(40)
        .all()
    )

    def score(candidate: Users) -> tuple[int, int]:
        candidate_interests = {
            value.strip().lower()
            for field_name in ("allergen_interests_json", "food_preferences_json", "hobby_interests_json")
            for value in candidate.get_interest_list(field_name)
            if value.strip()
        }
        return (len(my_interests & candidate_interests), candidate.id)

    return sorted(candidates, key=score, reverse=True)[:6]


def follow_status_for_viewer(profile_user: Users) -> str | None:
    viewer = current_user()
    if viewer is None or viewer.id == profile_user.id:
        return None
    follow = UserFollow.query.filter_by(follower_id=viewer.id, following_id=profile_user.id).first()
    return follow.status if follow else "none"


def incoming_follow_request_from_profile(profile_user: Users) -> UserFollow | None:
    viewer = current_user()
    if viewer is None or viewer.id == profile_user.id:
        return None
    return UserFollow.query.filter_by(follower_id=profile_user.id, following_id=viewer.id, status="pending").first()


def pending_follow_requests(user: Users) -> list[UserFollow]:
    return (
        UserFollow.query.filter_by(following_id=user.id, status="pending")
        .order_by(UserFollow.created_at.desc())
        .limit(8)
        .all()
    )


def outgoing_follow_requests(user: Users) -> list[UserFollow]:
    return (
        UserFollow.query.filter_by(follower_id=user.id, status="pending")
        .order_by(UserFollow.created_at.desc())
        .limit(8)
        .all()
    )


def handle_profile_picture_upload(user: Users) -> None:
    upload_profile_image(
        user=user,
        request_field="image",
        file_prefix="user",
        user_field="pfp_file_path",
        missing_message="Choose an image before uploading.",
        invalid_message="Profile pictures must be GIF, JPEG, PNG, or WebP images.",
        success_message="Profile picture updated.",
        error_message="Unable to save profile picture. Please try again.",
    )


def handle_profile_banner_upload(user: Users) -> None:
    upload_profile_image(
        user=user,
        request_field="banner_image",
        file_prefix="user-banner",
        user_field="profile_banner_file_path",
        missing_message="Choose a banner image before uploading.",
        invalid_message="Profile banners must be GIF, JPEG, PNG, or WebP images.",
        success_message="Profile banner updated.",
        error_message="Unable to save profile banner. Please try again.",
    )


def handle_profile_showcase_upload(user: Users) -> None:
    upload_profile_image(
        user=user,
        request_field="showcase_image",
        file_prefix="user-showcase",
        user_field="profile_showcase_file_path",
        missing_message="Choose a showcase image before uploading.",
        invalid_message="Showcase images must be GIF, JPEG, PNG, or WebP images.",
        success_message="Profile showcase image updated.",
        error_message="Unable to save profile showcase image. Please try again.",
    )


def upload_profile_image(
    user: Users,
    request_field: str,
    file_prefix: str,
    user_field: str,
    missing_message: str,
    invalid_message: str,
    success_message: str,
    error_message: str,
) -> None:
    file = request.files.get("image")
    if file is None or not file.filename:
        file = request.files.get(request_field)

    if file is None or not file.filename:
        flash(missing_message)
        return

    original_name = secure_filename(file.filename)
    extension = Path(original_name).suffix.lower().lstrip(".")
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        flash(invalid_message)
        return

    file_name = f"{file_prefix}-{user.id}.{extension}"

    try:
        file_reference = save_profile_upload_file(file, file_name)
        setattr(user, user_field, file_reference)
        db.session.commit()
        flash(success_message)
    except (OSError, RuntimeError):
        db.session.rollback()
        current_app.logger.exception(error_message)
        flash(error_message)


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

    if "username" in request.form:
        new_username = normalize_user_handle(request.form.get("username", ""))
        if not MIN_HANDLE_LENGTH <= len(new_username) <= MAX_HANDLE_LENGTH:
            flash(f"Username must be between {MIN_HANDLE_LENGTH} and {MAX_HANDLE_LENGTH} characters.")
            return

        if not is_public_username_available(new_username, user.id):
            flash(f"@{new_username} is already taken.")
            return

        user.username = new_username

    user.name = new_name
    db.session.commit()
    flash("Profile name updated.")


def update_user_profile_stat(user: Users) -> None:
    stat_key = request.form.get("stat_key", "").strip()
    stat_visible = request.form.get("visible", "true").strip().lower() in {"1", "true", "yes", "on"}

    if stat_key not in DEFAULT_PROFILE_STAT_VISIBILITY:
        flash("Unknown profile stat.")
        return

    visibility = profile_stat_visibility_for_user(user)
    enabled = profile_stat_enabled_for_user(user)
    enabled[stat_key] = True
    visibility[stat_key] = stat_visible
    save_profile_stat_enabled(user, enabled)
    save_profile_stat_visibility(user, visibility)
    db.session.commit()
    flash(f"{PROFILE_STAT_LABELS[stat_key].title()} is now {'public' if stat_visible else 'private'}.")


def update_user_profile_badge(user: Users) -> None:
    badge_key = request.form.get("badge_key", "").strip()
    badge_visible = request.form.get("visible", "true").strip().lower() in {"1", "true", "yes", "on"}
    badges = build_profile_badges(user, include_hidden=True)
    badge_keys = {badge["key"] for badge in badges}

    if badge_key not in badge_keys:
        flash("Unknown profile badge.")
        return

    visibility = profile_badge_visibility_for_user(user, badge_keys)
    visibility[badge_key] = badge_visible
    user.profile_badge_visibility_json = json.dumps(visibility)
    db.session.commit()
    flash(f"Badge is now {'public' if badge_visible else 'private'}.")


def update_user_pronouns(user: Users) -> None:
    pronouns = normalize_optional_string(request.form.get("pronouns"), 64)
    user.pronouns = pronouns
    db.session.commit()
    flash("Pronouns updated.")


def add_user_food_preference(user: Users) -> None:
    preference, message = validate_quick_interest(request.form.get("food_preference", ""))
    if not preference:
        flash(message or "Enter a quick interest before adding it.")
        return

    preferences = user.get_interest_list("food_preferences_json")
    preferences.append(preference)
    user.set_interest_list("food_preferences_json", preferences)
    db.session.commit()
    sync_session_filters_from_user(user)
    flash(f"Added {preference} to your quick interests.")


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


def update_user_campus_theme(user: Users) -> None:
    domain = str(request.form.get("campus_theme_domain", "")).strip().lower()

    if domain and get_school_theme_for_domain(domain) is None:
        flash("That campus theme is not available yet.")
        return

    user.campus_theme_domain = domain or None
    session["needs_campus_prompt"] = False
    db.session.commit()
    flash("Campus mode updated.")


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
        elif key == "minRating":
            try:
                filters[key] = min(max(float(payload[key]), 0), 5)
            except (TypeError, ValueError):
                filters[key] = default
        elif key == "foodPreferences":
            filters[key] = sanitize_quick_interest_values(payload[key])
        elif isinstance(default, list):
            filters[key] = sanitize_interest_values(payload[key])

    return filters


def sanitize_interest_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []

    return [normalize_interest_label(value) for value in values if normalize_interest_label(value)][:30]


def sanitize_quick_interest_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        quick_interest, _message = validate_quick_interest(value)
        if not quick_interest:
            continue

        key = quick_interest.lower()
        if key in seen:
            continue

        cleaned.append(quick_interest)
        seen.add(key)

    return cleaned[:30]


def validate_quick_interest(value: Any) -> tuple[str | None, str | None]:
    text = normalize_interest_label(value)
    if not text:
        return None, "Enter a quick interest before adding it."

    if len(text) > MAX_QUICK_INTEREST_LENGTH:
        return None, f"Quick interests must be {MAX_QUICK_INTEREST_LENGTH} characters or fewer."

    if not QUICK_INTEREST_RE.fullmatch(text):
        return None, "Quick interests can only use letters, numbers, and spaces."

    compact = re.sub(r"[^a-z0-9]+", "", text.lower())
    if any(term in compact for term in BLOCKED_QUICK_INTEREST_TERMS):
        return None, "That quick interest is not allowed."

    return text, None


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
    food_preferences = sanitize_quick_interest_values(filters.get("foodPreferences", []))
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
    price_text = normalize_price_text(payload.get("price_text")) or format_price_text(
        normalize_price_level(payload.get("price_level"))
    )
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
        db.session.flush()
        db.session.add(UserActivity(user_id=user.id, action="save", summary=f"Saved {name}"))
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

    group_session = GroupSwipeSession.query.filter_by(code=code, is_active=True).first()
    if group_session is not None and group_session_is_expired(group_session):
        group_session.is_active = False
        db.session.commit()
        session.pop("group_swipe_code", None)
        return None
    return group_session


def group_session_is_expired(group_session: GroupSwipeSession) -> bool:
    if not group_session.expires_at:
        return False
    try:
        expires_at = datetime.fromisoformat(group_session.expires_at)
    except ValueError:
        return False
    return datetime.now(timezone.utc) >= expires_at.replace(tzinfo=timezone.utc)


def join_group_from_invite(user: Users) -> None:
    code = normalize_group_code(request.args.get("group", ""))
    if not code:
        return

    group_session = GroupSwipeSession.query.filter_by(code=code, is_active=True).first()
    if group_session is None:
        flash("That group invite is no longer active.")
        return

    add_group_member(group_session, user)
    db.session.commit()
    session["group_swipe_code"] = group_session.code
    flash(f"Joined group {group_session.code}.")


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
        "next_open_time",
    }
    return {key: payload.get(key) for key in allowed_keys if key in payload}


def serialize_group_session(group_session: GroupSwipeSession, user: Users | None = None) -> dict[str, Any]:
    members = sorted(group_session.members, key=lambda member: member.joined_at)
    member_ids = {member.user_id for member in members}
    member_count = max(len(member_ids), 1)
    votes = list(group_session.votes)
    saved_votes = [vote for vote in votes if vote.action == "save"]
    vetoed_places = {vote.place_id for vote in votes if vote.action == "veto"}
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
            "is_vetoed": place_id in vetoed_places,
        }

        if place_id in vetoed_places:
            maybe.append(entry)
        elif member_ids and voter_ids >= member_ids:
            consensus.append(entry)
        else:
            maybe.append(entry)

    consensus.sort(key=lambda item: item["name"])
    maybe.sort(key=lambda item: (-item["saved_count"], item["name"]))

    return {
        "code": group_session.code,
        "invite_path": url_for("home", group=group_session.code),
        "expires_at": group_session.expires_at,
        "expires_in_seconds": max(0, int((datetime.fromisoformat(group_session.expires_at).replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds())) if group_session.expires_at else None,
        "is_host": bool(user and user.id == group_session.host_user_id),
        "member_count": member_count,
        "members": [
            {
                "id": member.user_id,
                "name": member.user.name if member.user else "BiteSwipe user",
                "avatar": uploaded_file_url(member.user.pfp_file_path if member.user else None, "transparentnewdefaultpicture.png"),
            }
            for member in members
        ],
        "vote_count": len(votes),
        "consensus": consensus[:12],
        "almost": maybe[:12],
        "messages": [
            {
                "name": message.user.name if message.user else "BiteSwipe user",
                "message": message.message,
            }
            for message in sorted(group_session.messages, key=lambda item: item.created_at, reverse=True)[:8]
        ],
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
    food_preferences = sanitize_quick_interest_values(filters.get("foodPreferences", []))

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


def sort_restaurants_by_availability(places: list[dict[str, Any]]) -> None:
    def sort_key(place: dict[str, Any]) -> tuple[int, float, str]:
        is_open = place.get("is_open")
        distance = normalize_optional_float(place.get("distance_meters"))
        if is_open is True:
            availability_rank = 0
        elif is_open is False:
            availability_rank = 2
        else:
            availability_rank = 1

        return (
            availability_rank,
            distance if distance is not None else float("inf"),
            str(place.get("name") or ""),
        )

    places.sort(key=sort_key)


def restaurant_matches_filters(place: dict[str, Any], filters: dict[str, Any]) -> bool:
    if not restaurant_matches_distance(place, filters):
        return False

    price_level = place.get("price_level")
    if selected_price_levels(filters) and price_level is not None and price_level not in selected_price_levels(filters):
        return False

    rating = normalize_optional_float(place.get("rating"))
    if filters.get("minRating") and (rating is None or rating < float(filters["minRating"])):
        return False

    if not restaurant_matches_seating_filters(place, filters):
        return False

    if not restaurant_matches_cuisine_exclusions(place, sanitize_interest_values(filters.get("cuisineExclusions", []))):
        return False

    if not restaurant_matches_food_preferences(place, sanitize_quick_interest_values(filters.get("foodPreferences", []))):
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


def restaurant_matches_cuisine_exclusions(place: dict[str, Any], exclusions: list[str]) -> bool:
    if not exclusions:
        return True

    searchable = " ".join(
        str(place.get(key) or "")
        for key in ("name", "address", "cuisine", "photo_category")
    ).lower()

    return not any(exclusion.lower() in searchable for exclusion in exclusions)


def restaurant_matches_seating_filters(place: dict[str, Any], filters: dict[str, Any]) -> bool:
    seating = place.get("seating_tags") or {}

    if filters.get("outdoorSeating") and seating.get("outdoor") is False:
        return False

    if filters.get("takeoutOnly") and seating.get("takeout") is False:
        return False

    if filters.get("dineIn") and seating.get("dine_in") is False:
        return False

    return True


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


def annotate_restaurant_confidence(places: list[dict[str, Any]], filters: dict[str, Any]) -> None:
    for place in places:
        place["bite_confidence"] = build_bite_confidence(place, filters)
        allergy_confidence = build_allergy_confidence(place, filters)
        if allergy_confidence:
            place["allergy_confidence"] = allergy_confidence


def build_bite_confidence(place: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any]:
    score = 48
    reasons: list[str] = []

    distance = normalize_optional_float(place.get("distance_meters"))
    if distance is not None:
        miles = distance / METERS_PER_MILE
        if miles <= 0.5:
            score += 18
            reasons.append("very close")
        elif miles <= 1.5:
            score += 12
            reasons.append("nearby")
        elif miles <= filters["distance"]:
            score += 6
            reasons.append("inside your distance")

    rating = normalize_optional_float(place.get("rating"))
    if rating is not None:
        if rating >= 4.5:
            score += 16
            reasons.append("strong rating")
        elif rating >= 4.0:
            score += 10
            reasons.append("solid rating")
        elif rating >= 3.5:
            score += 4

    price_level = place.get("price_level")
    if selected_price_levels(filters) and price_level in selected_price_levels(filters):
        score += 10
        reasons.append("price match")

    food_preferences = sanitize_quick_interest_values(filters.get("foodPreferences", []))
    if food_preferences and restaurant_matches_food_preferences(place, food_preferences):
        score += 12
        reasons.append("craving match")

    allergy_confidence = build_allergy_confidence(place, filters)
    if allergy_confidence and allergy_confidence["level"] == "strong":
        score += 8
        reasons.append("clear allergy signal")

    score = min(max(score, 0), 99)
    label = "Great fit" if score >= 82 else "Good fit" if score >= 68 else "Possible fit"
    return {"score": score, "label": label, "reasons": reasons[:4]}


def build_allergy_confidence(place: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any] | None:
    active_filters = [
        (key, config)
        for key, config in ALLERGEN_FILTERS.items()
        if filters.get(key)
    ]
    if not active_filters:
        return None

    dietary_tags = place.get("dietary_tags") or {}
    matched_labels = []
    unknown_labels = []

    for _key, config in active_filters:
        tag_names = config["diet_tags"]
        known_values = [
            dietary_tags.get(tag_name)
            for tag_name in tag_names
            if dietary_tags.get(tag_name) is not None
        ]

        if any(value in {"yes", "only"} for value in known_values):
            matched_labels.append(str(config["label"]))
        else:
            unknown_labels.append(str(config["label"]))

    if matched_labels and not unknown_labels:
        return {
            "level": "strong",
            "label": "Strong allergy signal",
            "detail": f"Tagged for {', '.join(matched_labels)}. Still confirm ingredients before ordering.",
        }

    if matched_labels:
        return {
            "level": "mixed",
            "label": "Partial allergy signal",
            "detail": f"Tagged for {', '.join(matched_labels)}, but {', '.join(unknown_labels)} still needs checking.",
        }

    return {
        "level": "unknown",
        "label": "Verify allergy safety",
        "detail": "No public allergy tags were found for your selected filters. Ask the restaurant before ordering.",
    }


def extract_dietary_tags(tags: dict[str, Any]) -> dict[str, str]:
    return {
        key: str(value).strip().lower()
        for key, value in tags.items()
        if key.startswith("diet:")
    }


def extract_seating_tags(tags: dict[str, Any]) -> dict[str, bool | None]:
    return {
        "outdoor": normalize_osm_yes_no(tags.get("outdoor_seating")),
        "takeout": normalize_osm_yes_no(tags.get("takeaway") or tags.get("takeout")),
        "dine_in": normalize_osm_yes_no(tags.get("indoor_seating") or tags.get("dine_in")),
    }


def normalize_osm_yes_no(value: Any) -> bool | None:
    if value is None:
        return None

    text_value = str(value).strip().lower()
    if text_value in {"yes", "true", "1", "only"}:
        return True
    if text_value in {"no", "false", "0"}:
        return False
    return None


def normalize_price_level(value: Any) -> int | None:
    if value is None:
        return None

    text_value = str(value).strip()
    if not text_value:
        return None

    if set(text_value) <= {"$"}:
        return min(max(len(text_value), 1), 4)

    try:
        numeric_level = int(text_value)
    except ValueError:
        return None

    if numeric_level <= 0:
        return None

    return min(numeric_level, 4)


def normalize_google_price_level(value: Any) -> int | None:
    if value is None:
        return None

    price_map = {
        "PRICE_LEVEL_FREE": None,
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
        return None

    return "$" * min(price_level, 4)


def normalize_price_text(value: Any) -> str | None:
    text_value = normalize_optional_string(value, 64)

    if text_value is None:
        return None

    if text_value.strip().lower() in {"free", "0", "unknown", "price not listed"}:
        return None

    if set(text_value.strip()) <= {"$"}:
        return format_price_text(normalize_price_level(text_value))

    return text_value


def restaurant_fallback_image_category(*values: Any) -> str:
    searchable = " ".join(str(value or "") for value in values).replace("_", " ").lower()

    for category, keywords in RESTAURANT_FALLBACK_IMAGE_KEYWORDS:
        if any(keyword in searchable for keyword in keywords):
            return category

    return DEFAULT_RESTAURANT_FALLBACK_IMAGE


def restaurant_fallback_image_url(category: str) -> str:
    return url_for("static", filename=f"restaurant-fallbacks/{category}.webp")


def normalize_website_url(value: Any) -> str | None:
    website = normalize_optional_string(value, 512)
    if website is None:
        return None

    if website.startswith(("http://", "https://")):
        return website

    return f"https://{website}"


def is_external_upload_reference(value: Any) -> bool:
    return str(value or "").startswith(("http://", "https://"))


def uploaded_file_url(value: Any, fallback: str | None = None) -> str:
    file_reference = str(value or fallback or "").strip()
    if not file_reference:
        file_reference = "transparentnewdefaultpicture.png"

    if is_external_upload_reference(file_reference):
        return file_reference

    return url_for("static", filename=f"uploads/{file_reference}")


def save_profile_upload_file(file: Any, file_name: str) -> str:
    provider = str(current_app.config.get("UPLOAD_STORAGE_PROVIDER", "local")).lower()

    if provider == "s3":
        return save_profile_upload_to_s3(file, file_name)

    file_path = Path(current_app.config["UPLOAD_FOLDER"]) / file_name
    file.save(file_path)
    return file_name


def save_profile_upload_to_s3(file: Any, file_name: str) -> str:
    bucket = str(current_app.config.get("UPLOADS_S3_BUCKET", "")).strip()
    public_base_url = str(current_app.config.get("UPLOADS_PUBLIC_BASE_URL", "")).strip().rstrip("/")
    prefix = str(current_app.config.get("UPLOADS_S3_PREFIX", "profile-uploads")).strip().strip("/")

    if not bucket or not public_base_url:
        raise RuntimeError("S3 uploads require UPLOADS_S3_BUCKET and UPLOADS_PUBLIC_BASE_URL.")

    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("S3 uploads require boto3. Install requirements.txt first.") from exc

    key = f"{prefix}/{file_name}" if prefix else file_name
    file.stream.seek(0)
    boto3.client("s3").upload_fileobj(
        file.stream,
        bucket,
        key,
        ExtraArgs={"ContentType": file.mimetype or "application/octet-stream"},
    )
    return f"{public_base_url}/{key}"


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


def search_restaurants_hybrid(
    user: Users,
    api_key: str | None,
    filters: dict[str, Any] | None = None,
    radius_meters: int | None = None,
) -> tuple[list[dict[str, Any]], str]:
    osm_places = search_restaurants_with_openstreetmap(user.latitude, user.longitude, radius_meters)

    if not api_key or not google_places_enrichment_allowed():
        return osm_places, "openstreetmap"

    try:
        google_places = search_restaurants_with_google(user, api_key, filters, radius_meters)
    except Exception:
        current_app.logger.exception("Google Places enrichment failed; using OpenStreetMap results.")
        return osm_places, "openstreetmap"

    if not google_places:
        return osm_places, "openstreetmap"

    merged_places = merge_osm_places_with_google_enrichment(osm_places, google_places)
    source = "hybrid" if any(place.get("source") == "hybrid" for place in merged_places) else "openstreetmap"
    return merged_places, source


def google_places_enrichment_allowed() -> bool:
    configured_ratio = normalize_optional_float(current_app.config.get("GOOGLE_PLACES_USAGE_RATIO"))
    spend = normalize_optional_float(current_app.config.get("GOOGLE_PLACES_MONTHLY_SPEND_USD")) or 0.0
    credit = normalize_optional_float(current_app.config.get("GOOGLE_PLACES_MONTHLY_CREDIT_USD")) or 200.0
    disable_at = normalize_optional_float(current_app.config.get("GOOGLE_PLACES_DISABLE_AT_USAGE_RATIO")) or 0.6

    usage_ratio = configured_ratio if configured_ratio is not None and configured_ratio >= 0 else spend / credit
    return usage_ratio < disable_at


def merge_osm_places_with_google_enrichment(
    osm_places: list[dict[str, Any]],
    google_places: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched_places: list[dict[str, Any]] = []

    for osm_place in osm_places:
        google_place = best_google_enrichment_match(osm_place, google_places)

        if google_place is None:
            enriched_places.append(osm_place)
            continue

        merged_place = dict(osm_place)
        merged_place["source"] = "hybrid"
        merged_place["google_place_id"] = google_place.get("place")

        if google_place.get("photo"):
            merged_place["photo"] = google_place["photo"]
            merged_place["photo_source"] = google_place.get("photo_source") or "google_places"
            merged_place["photo_category"] = google_place.get("photo_category") or "google_places"

        for key in ("price_level", "price_text", "rating", "review_count", "website", "is_open", "next_open_time", "opening_hours_text"):
            if google_place.get(key) is not None:
                merged_place[key] = google_place[key]

        if not merged_place.get("cuisine") and google_place.get("cuisine"):
            merged_place["cuisine"] = google_place["cuisine"]

        if not merged_place.get("address") and google_place.get("address"):
            merged_place["address"] = google_place["address"]

        enriched_places.append(merged_place)

    return enriched_places


def best_google_enrichment_match(
    osm_place: dict[str, Any],
    google_places: list[dict[str, Any]],
) -> dict[str, Any] | None:
    best_place: dict[str, Any] | None = None
    best_score = 0

    for google_place in google_places:
        score = score_place_enrichment_match(osm_place, google_place)
        if score > best_score:
            best_score = score
            best_place = google_place

    return best_place if best_score >= 8 else None


def score_place_enrichment_match(osm_place: dict[str, Any], google_place: dict[str, Any]) -> int:
    osm_name = normalize_place_match_text(osm_place.get("name"))
    google_name = normalize_place_match_text(google_place.get("name"))

    if not osm_name or not google_name:
        return 0

    score = 0
    if osm_name == google_name:
        score += 10
    elif osm_name in google_name or google_name in osm_name:
        score += 7
    else:
        shared_tokens = set(osm_name.split()) & set(google_name.split())
        score += min(len(shared_tokens), 3) * 2

    score += min(address_token_overlap(osm_place.get("address"), google_place.get("address")), 4)
    return score


def address_token_overlap(first: Any, second: Any) -> int:
    first_tokens = set(normalize_place_match_text(first).split())
    second_tokens = set(normalize_place_match_text(second).split())
    return len(first_tokens & second_tokens)


def normalize_place_match_text(value: Any) -> str:
    text_value = str(value or "").lower()
    return " ".join(re.findall(r"[a-z0-9]+", text_value))


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
    cuisine = tags.get("cuisine")
    fallback_category = restaurant_fallback_image_category(cuisine, name, place_type)
    distance = (
        distance_meters(origin_latitude, origin_longitude, latitude, longitude)
        if latitude is not None and longitude is not None
        else None
    )

    return {
        "name": name,
        "place": f"osm:{element.get('type')}:{element.get('id')}",
        "photo": restaurant_fallback_image_url(fallback_category),
        "photo_source": "biteswipe_fallback",
        "photo_category": fallback_category,
        "source": "openstreetmap",
        "address": format_osm_address(tags),
        "cuisine": cuisine,
        "price_level": normalize_price_level(tags.get("price") or tags.get("price:range")),
        "price_text": format_price_text(normalize_price_level(tags.get("price") or tags.get("price:range"))),
        "dietary_tags": extract_dietary_tags(tags),
        "seating_tags": extract_seating_tags(tags),
        "rating": None,
        "review_count": None,
        "website": normalize_website_url(tags.get("website") or tags.get("contact:website")),
        "is_open": None,
        "opening_hours_text": tags.get("opening_hours"),
        "distance_meters": distance,
        "walking_minutes": walking_minutes_from_meters(distance),
        "driving_minutes": driving_minutes_from_meters(distance),
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


def walking_minutes_from_meters(meters: Any) -> int | None:
    distance = normalize_optional_float(meters)
    if distance is None:
        return None

    return max(1, round(distance / WALKING_SPEED_METERS_PER_MINUTE))


def driving_minutes_from_meters(meters: Any) -> int | None:
    distance = normalize_optional_float(meters)
    if distance is None:
        return None

    return max(2, round(distance / 800))


def annotate_travel_times(places: list[dict[str, Any]], transportation_mode: str | None) -> None:
    mode = transportation_mode if transportation_mode in {"walking", "driving", "both"} else "walking"

    for place in places:
        distance = place.get("distance_meters")
        place["walking_minutes"] = walking_minutes_from_meters(distance)
        place["driving_minutes"] = driving_minutes_from_meters(distance)
        place["transportation_mode"] = mode


def format_google_place(place: dict[str, Any], api_key: str) -> dict[str, Any]:
    display_name = place.get("displayName") or {}
    photos = place.get("photos") or []
    photo_name = photos[0].get("name") if photos else None
    opening_hours = place.get("currentOpeningHours") or {}
    weekday_descriptions = opening_hours.get("weekdayDescriptions") or []
    cuisine = " ".join(place.get("types") or [])
    fallback_category = restaurant_fallback_image_category(cuisine, display_name.get("text", ""))

    return {
        "name": display_name.get("text", "Unknown restaurant"),
        "place": place.get("id"),
        "photo": (
            f"https://places.googleapis.com/v1/{photo_name}/media?maxHeightPx=500&key={api_key}"
            if photo_name
            else restaurant_fallback_image_url(fallback_category)
        ),
        "photo_source": "google_places" if photo_name else "biteswipe_fallback",
        "photo_category": "google_places" if photo_name else fallback_category,
        "source": "google",
        "address": place.get("formattedAddress"),
        "cuisine": cuisine,
        "price_level": normalize_google_price_level(place.get("priceLevel")),
        "price_text": format_price_text(normalize_google_price_level(place.get("priceLevel"))),
        "dietary_tags": {},
        "seating_tags": {},
        "rating": normalize_optional_float(place.get("rating")),
        "review_count": place.get("userRatingCount"),
        "website": place.get("websiteUri") or place.get("googleMapsUri"),
        "is_open": opening_hours.get("openNow"),
        "next_open_time": opening_hours.get("nextOpenTime"),
        "opening_hours_text": "; ".join(weekday_descriptions[:2]) if weekday_descriptions else None,
        "distance_meters": None,
        "walking_minutes": None,
        "driving_minutes": None,
    }


app = create_app()


if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))
