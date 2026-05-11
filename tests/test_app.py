from __future__ import annotations

import unittest
import shutil
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4
from pathlib import Path

from db import db
from main import (
    SCHOOL_THEMES,
    build_overpass_query,
    create_app,
    format_google_place,
    format_osm_place,
    format_price_text,
    get_school_theme_for_email,
    merge_osm_places_with_google_enrichment,
    normalize_google_price_level,
    normalize_price_level,
)
from users_db import SavedRestaurant, Users


class LifeSwipeAppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temp_root = Path(__file__).resolve().parent / ".tmp"
        temp_root.mkdir(exist_ok=True)
        self.temp_path = temp_root / uuid4().hex
        self.temp_path.mkdir()
        temp_path = self.temp_path

        self.app = create_app(
            config_overrides={
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(temp_path / 'users.db').as_posix()}",
                "SQLALCHEMY_BINDS": {
                    "posts": f"sqlite:///{(temp_path / 'posts.db').as_posix()}",
                },
                "UPLOAD_FOLDER": str(temp_path / "uploads"),
                "GOOGLE_PLACES_API_KEY": "",
                "AUTO_CREATE_DB": True,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            for engine in db.engines.values():
                engine.dispose()
        shutil.rmtree(self.temp_path, ignore_errors=True)

    def login(self, email: str = "person@example.com", password: str = "password123") -> None:
        response = self.client.post(
            "/login",
            data={"email": email, "pass": password},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_home_requires_login(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_login_creates_hashed_user_and_rejects_wrong_password(self) -> None:
        self.login()

        with self.app.app_context():
            user = Users.query.filter_by(email="person@example.com").first()
            self.assertIsNotNone(user)
            self.assertNotEqual(user.password, "password123")

        self.client.get("/logout")
        response = self.client.post(
            "/login",
            data={"email": "person@example.com", "pass": "wrong"},
        )
        self.assertEqual(response.status_code, 401)

    def test_school_theme_matches_edu_email_domains(self) -> None:
        self.assertGreaterEqual(len(SCHOOL_THEMES), 100)

        theme = get_school_theme_for_email("student@drexel.edu")
        self.assertIsNotNone(theme)
        self.assertEqual(theme["slug"], "drexel")
        self.assertEqual(theme["short_name"], "Drexel")
        self.assertEqual(theme["image_file"], "schools/backdrops/drexel.webp")
        self.assertEqual(theme["card_image_file"], "schools/badges/drexel.webp")

        subdomain_theme = get_school_theme_for_email("student@mail.drexel.edu")
        self.assertIsNotNone(subdomain_theme)
        self.assertEqual(subdomain_theme["slug"], "drexel")

        self.assertEqual(get_school_theme_for_email("student@princeton.edu")["card_image_file"], "schools/badges/princeton.webp")
        self.assertEqual(get_school_theme_for_email("student@princeton.edu")["image_file"], "schools/backdrops/princeton.webp")
        self.assertEqual(get_school_theme_for_email("student@mit.edu")["card_image_file"], "schools/badges/mit.webp")
        self.assertEqual(get_school_theme_for_email("student@temple.edu")["image_file"], "schools/backdrops/temple.webp")
        upenn_theme = get_school_theme_for_email("student@upenn.edu")
        self.assertEqual(upenn_theme["image_file"], "schools/backdrops/penn.webp")
        self.assertEqual(upenn_theme["card_image_file"], "schools/upenn logo.webp")
        self.assertEqual(get_school_theme_for_email("student@wcupa.edu")["image_file"], "schools/backdrops/west-chester.webp")
        self.assertEqual(get_school_theme_for_email("student@mail.newark.rutgers.edu")["slug"], "rutgers-newark")

        generated = get_school_theme_for_email("student@examplecollege.edu")
        self.assertIsNotNone(generated)
        self.assertEqual(generated["domain"], "examplecollege.edu")
        self.assertEqual(generated["is_generated"], "true")

        self.assertIsNone(get_school_theme_for_email("person@example.com"))

    def test_school_theme_image_assets_exist(self) -> None:
        static_root = Path(__file__).resolve().parents[1] / "static"

        for domain, theme in SCHOOL_THEMES.items():
            for key in ("image_file", "card_image_file"):
                value = theme.get(key)
                if value:
                    self.assertTrue((static_root / value).exists(), f"{domain} missing {value}")

    def test_home_applies_school_theme_to_cards_page(self) -> None:
        self.login(email="student@drexel.edu")

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-school-theme="drexel"', response.data)
        self.assertIn(b"--school-primary: #07294D", response.data)
        self.assertIn(b"Drexel mode", response.data)

    def test_home_uses_separate_upenn_backdrop_and_card_images(self) -> None:
        self.login(email="student@upenn.edu")

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"schools/backdrops/penn.webp", response.data)
        self.assertIn(b"schools/upenn%20logo.webp", response.data)

    def test_profile_campus_mode_can_override_email_theme(self) -> None:
        self.login(email="student@drexel.edu")

        response = self.client.post(
            "/profile",
            data={"action": "update_campus_theme", "campus_theme_domain": "temple.edu"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-school-theme="temple"', response.data)
        self.assertIn(b"Temple mode", response.data)

    def test_filters_are_sanitized_and_persisted_in_session(self) -> None:
        self.login()
        response = self.client.post(
            "/save_filters",
            json={
                "celiac": True,
                "distance": 999,
                "foodPreferences": ["Italian", "Seafood"],
                "hobbyInterests": ["Gaming"],
                "unknown": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["filters"]["distance"], 100)

        response = self.client.get("/get_filters")
        payload = response.get_json()
        self.assertTrue(payload["celiac"])
        self.assertEqual(payload["distance"], 100)
        self.assertEqual(payload["foodPreferences"], ["Italian", "Seafood"])
        self.assertEqual(payload["hobbyInterests"], ["Gaming"])
        self.assertNotIn("unknown", payload)

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Celiac safe", response.data)
        self.assertIn(b"Italian", response.data)
        self.assertIn(b"Gaming", response.data)

    def test_profile_quick_add_hobby_interest_updates_filters(self) -> None:
        self.login()

        response = self.client.post(
            "/profile",
            data={"action": "add_hobby_interest", "hobby_interest": "Music"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/get_filters")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["hobbyInterests"], ["Music"])

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Music", response.data)

    def test_profile_banner_upload_updates_identity_banner(self) -> None:
        self.login()

        response = self.client.post(
            "/profile",
            data={
                "action": "upload_banner",
                "banner_image": (BytesIO(b"banner-image"), "banner.webp"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"profile-identity-banner has-banner-image", response.data)
        self.assertIn(b"user-banner-", response.data)

    def test_chat_posts_return_user_names(self) -> None:
        self.login()
        response = self.client.post("/chat", data={"message": "hello"}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/get_posts")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["posts"][0]["message"], "hello")
        self.assertEqual(payload["posts"][0]["user_name"], "Person")

    def test_restaurant_route_requires_location(self) -> None:
        self.login()
        response = self.client.get("/get_restaurant")
        self.assertEqual(response.status_code, 400)
        self.assertIn("location", response.get_json()["error"].lower())

    def test_restaurant_route_uses_openstreetmap_without_google_key(self) -> None:
        self.login()
        response = self.client.post("/save_location", json={"latitude": 39.9566, "longitude": -75.1899})
        self.assertEqual(response.status_code, 200)

        with patch(
            "main.search_restaurants_with_openstreetmap",
            return_value=[
                {
                    "name": "Test Cafe",
                    "place": "osm:node:1",
                    "photo": "/static/biteswipe.png",
                    "source": "openstreetmap",
                    "address": None,
                    "distance_meters": 12.3,
                }
            ],
        ):
            response = self.client.get("/get_restaurant")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["source"], "openstreetmap")
        self.assertEqual(payload["places"][0]["name"], "Test Cafe")

    def test_restaurant_route_uses_osm_location_with_google_enrichment(self) -> None:
        self.login()
        self.app.config.update({"GOOGLE_PLACES_API_KEY": "test-key"})
        response = self.client.post("/save_location", json={"latitude": 39.9566, "longitude": -75.1899})
        self.assertEqual(response.status_code, 200)

        with (
            patch(
                "main.search_restaurants_with_openstreetmap",
                return_value=[
                    {
                        "name": "Test Cafe",
                        "place": "osm:node:1",
                        "photo": "/static/restaurant-fallbacks/general.webp",
                        "photo_source": "biteswipe_fallback",
                        "source": "openstreetmap",
                        "address": "123 Campus Walk",
                        "distance_meters": 123.4,
                        "walking_minutes": 1,
                        "price_level": None,
                        "price_text": None,
                        "dietary_tags": {},
                    }
                ],
            ),
            patch(
                "main.search_restaurants_with_google",
                return_value=[
                    {
                        "name": "Test Cafe",
                        "place": "google-place-1",
                        "photo": "https://places.googleapis.com/v1/photo/media",
                        "photo_source": "google_places",
                        "source": "google",
                        "address": "123 Campus Walk Philadelphia PA",
                        "price_level": 2,
                        "price_text": "$$",
                        "rating": 4.5,
                        "review_count": 20,
                        "website": "https://example.com",
                    }
                ],
            ) as google_search,
        ):
            response = self.client.get("/get_restaurant")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        place = payload["places"][0]
        self.assertEqual(payload["source"], "hybrid")
        self.assertEqual(place["source"], "hybrid")
        self.assertEqual(place["place"], "osm:node:1")
        self.assertEqual(place["google_place_id"], "google-place-1")
        self.assertEqual(place["distance_meters"], 123.4)
        self.assertEqual(place["walking_minutes"], 1)
        self.assertEqual(place["photo_source"], "google_places")
        self.assertEqual(place["price_text"], "$$")
        self.assertEqual(place["rating"], 4.5)
        google_search.assert_called_once()

    def test_restaurant_route_skips_google_enrichment_at_usage_limit(self) -> None:
        self.login()
        self.app.config.update(
            {
                "GOOGLE_PLACES_API_KEY": "test-key",
                "GOOGLE_PLACES_MONTHLY_SPEND_USD": 120,
                "GOOGLE_PLACES_MONTHLY_CREDIT_USD": 200,
                "GOOGLE_PLACES_DISABLE_AT_USAGE_RATIO": 0.6,
            }
        )
        response = self.client.post("/save_location", json={"latitude": 39.9566, "longitude": -75.1899})
        self.assertEqual(response.status_code, 200)

        with (
            patch(
                "main.search_restaurants_with_openstreetmap",
                return_value=[
                    {
                        "name": "Budget Cafe",
                        "place": "osm:node:2",
                        "photo": "/static/restaurant-fallbacks/general.webp",
                        "source": "openstreetmap",
                        "address": None,
                        "distance_meters": 50,
                    }
                ],
            ),
            patch("main.search_restaurants_with_google") as google_search,
        ):
            response = self.client.get("/get_restaurant")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["source"], "openstreetmap")
        google_search.assert_not_called()

    def test_restaurant_route_applies_distance_and_food_filters(self) -> None:
        self.login()
        response = self.client.post("/save_location", json={"latitude": 39.9566, "longitude": -75.1899})
        self.assertEqual(response.status_code, 200)
        self.client.post("/save_filters", json={"distance": 1, "foodPreferences": ["Italian"]})

        with patch(
            "main.search_restaurants_with_openstreetmap",
            return_value=[
                {
                    "name": "Italian Table",
                    "place": "osm:node:1",
                    "photo": "/static/biteswipe.png",
                    "source": "openstreetmap",
                    "address": None,
                    "cuisine": "italian",
                    "price_level": 2,
                    "dietary_tags": {},
                    "distance_meters": 100,
                },
                {
                    "name": "Far Italian",
                    "place": "osm:node:2",
                    "photo": "/static/biteswipe.png",
                    "source": "openstreetmap",
                    "address": None,
                    "cuisine": "italian",
                    "price_level": 2,
                    "dietary_tags": {},
                    "distance_meters": 5000,
                },
                {
                    "name": "Burger Place",
                    "place": "osm:node:3",
                    "photo": "/static/biteswipe.png",
                    "source": "openstreetmap",
                    "address": None,
                    "cuisine": "american",
                    "price_level": 1,
                    "dietary_tags": {},
                    "distance_meters": 100,
                },
            ],
        ):
            response = self.client.get("/get_restaurant")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [place["name"] for place in response.get_json()["places"]],
            ["Italian Table"],
        )

    def test_restaurant_route_applies_price_and_allergen_filters(self) -> None:
        self.login()
        response = self.client.post("/save_location", json={"latitude": 39.9566, "longitude": -75.1899})
        self.assertEqual(response.status_code, 200)
        self.client.post("/save_filters", json={"celiac": True, "mediumPrice": True})

        with patch(
            "main.search_restaurants_with_openstreetmap",
            return_value=[
                {
                    "name": "Safe Bistro",
                    "place": "osm:node:1",
                    "photo": "/static/biteswipe.png",
                    "source": "openstreetmap",
                    "address": None,
                    "cuisine": "american",
                    "price_level": 2,
                    "dietary_tags": {"diet:gluten_free": "yes"},
                    "distance_meters": 100,
                },
                {
                    "name": "Unknown Bistro",
                    "place": "osm:node:2",
                    "photo": "/static/biteswipe.png",
                    "source": "openstreetmap",
                    "address": None,
                    "cuisine": "american",
                    "price_level": 2,
                    "dietary_tags": {},
                    "distance_meters": 100,
                },
                {
                    "name": "Cheap Safe Bistro",
                    "place": "osm:node:3",
                    "photo": "/static/biteswipe.png",
                    "source": "openstreetmap",
                    "address": None,
                    "cuisine": "american",
                    "price_level": 1,
                    "dietary_tags": {"diet:gluten_free": "yes"},
                    "distance_meters": 100,
                },
            ],
        ):
            response = self.client.get("/get_restaurant")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [place["name"] for place in response.get_json()["places"]],
            ["Safe Bistro", "Unknown Bistro"],
        )
        places = response.get_json()["places"]
        self.assertEqual(places[0]["allergy_confidence"]["level"], "strong")
        self.assertEqual(places[1]["allergy_confidence"]["level"], "unknown")
        self.assertIn("bite_confidence", places[0])

    def test_restaurant_route_falls_back_when_filters_have_no_exact_matches(self) -> None:
        self.login()
        response = self.client.post("/save_location", json={"latitude": 39.9566, "longitude": -75.1899})
        self.assertEqual(response.status_code, 200)
        self.client.post("/save_filters", json={"foodPreferences": ["Seafood"]})

        with patch(
            "main.search_restaurants_with_openstreetmap",
            return_value=[
                {
                    "name": "Burger Place",
                    "place": "osm:node:1",
                    "photo": "/static/biteswipe.png",
                    "source": "openstreetmap",
                    "address": None,
                    "cuisine": "american",
                    "price_level": None,
                    "dietary_tags": {},
                    "distance_meters": 100,
                }
            ],
        ):
            response = self.client.get("/get_restaurant")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["places"][0]["name"], "Burger Place")
        self.assertIn("No exact filter matches", payload["message"])

    def test_restaurant_route_filters_closed_places_when_open_now_is_selected(self) -> None:
        self.login()
        response = self.client.post("/save_location", json={"latitude": 39.9566, "longitude": -75.1899})
        self.assertEqual(response.status_code, 200)
        self.client.post("/save_filters", json={"openNow": True})

        with patch(
            "main.search_restaurants_with_openstreetmap",
            return_value=[
                {
                    "name": "Open Cafe",
                    "place": "osm:node:1",
                    "photo": "/static/biteswipe.png",
                    "source": "openstreetmap",
                    "is_open": True,
                    "distance_meters": 100,
                },
                {
                    "name": "Closed Cafe",
                    "place": "osm:node:2",
                    "photo": "/static/biteswipe.png",
                    "source": "openstreetmap",
                    "is_open": False,
                    "distance_meters": 100,
                },
                {
                    "name": "Unknown Hours Cafe",
                    "place": "osm:node:3",
                    "photo": "/static/biteswipe.png",
                    "source": "openstreetmap",
                    "is_open": None,
                    "distance_meters": 100,
                },
            ],
        ):
            response = self.client.get("/get_restaurant")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [place["name"] for place in response.get_json()["places"]],
            ["Open Cafe", "Unknown Hours Cafe"],
        )

    def test_group_session_consensus_requires_every_member_to_save(self) -> None:
        self.login("one@example.com")
        response = self.client.post("/group_session/create")
        self.assertEqual(response.status_code, 200)
        code = response.get_json()["group"]["code"]
        self.assertEqual(response.get_json()["group"]["invite_path"], f"/?group={code}")

        self.client.get("/logout")
        self.login("two@example.com")
        response = self.client.post("/group_session/join", json={"code": code})
        self.assertEqual(response.status_code, 200)

        payload = {
            "action": "save",
            "place": "osm:node:1",
            "restaurant": {"name": "Shared Pizza", "place": "osm:node:1"},
        }
        response = self.client.post("/group_session/swipe", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["group"]["consensus"], [])

        self.client.get("/logout")
        self.login("one@example.com")
        self.client.post("/group_session/join", json={"code": code})
        response = self.client.post("/group_session/swipe", json=payload)
        self.assertEqual(response.status_code, 200)
        group = response.get_json()["group"]
        self.assertEqual(group["consensus"][0]["name"], "Shared Pizza")
        self.assertEqual(group["consensus"][0]["saved_count"], 2)

    def test_group_invite_link_joins_session_from_home(self) -> None:
        self.login("one@example.com")
        response = self.client.post("/group_session/create")
        self.assertEqual(response.status_code, 200)
        code = response.get_json()["group"]["code"]

        self.client.get("/logout")
        self.login("two@example.com")
        response = self.client.get(f"/?group={code}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/group_session/current")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["group"]["code"], code)
        self.assertEqual(response.get_json()["group"]["member_count"], 2)

    def test_openstreetmap_helpers_format_places(self) -> None:
        query = build_overpass_query(39.9566, -75.1899, 2000, 12, 25)
        self.assertIn("node[\"amenity\"~", query)
        self.assertIn("restaurant", query)

        with self.app.test_request_context():
            place = format_osm_place(
                {
                    "type": "node",
                    "id": 123,
                    "lat": 39.9567,
                    "lon": -75.1898,
                    "tags": {
                        "amenity": "restaurant",
                        "name": "Test Restaurant",
                        "addr:street": "Market St",
                    },
                },
                39.9566,
                -75.1899,
            )

        self.assertEqual(place["name"], "Test Restaurant")
        self.assertEqual(place["source"], "openstreetmap")
        self.assertEqual(place["photo_source"], "biteswipe_fallback")
        self.assertIn("restaurant-fallbacks/general.webp", place["photo"])
        self.assertEqual(place["walking_minutes"], 1)
        self.assertIn("Market St", place["address"])

        with self.app.test_request_context():
            pizza_place = format_osm_place(
                {
                    "type": "node",
                    "id": 124,
                    "lat": 39.9567,
                    "lon": -75.1898,
                    "tags": {
                        "amenity": "restaurant",
                        "name": "Slice House",
                        "cuisine": "pizza",
                    },
                },
                39.9566,
                -75.1899,
            )
        self.assertIn("restaurant-fallbacks/pizza.webp", pizza_place["photo"])

    def test_google_places_keep_live_photos_and_fallback_without_one(self) -> None:
        with self.app.test_request_context():
            live_photo = format_google_place(
                {
                    "id": "abc123",
                    "displayName": {"text": "Real Photo Cafe"},
                    "photos": [{"name": "places/photo-name"}],
                    "types": ["cafe"],
                },
                "test-key",
            )
            fallback_photo = format_google_place(
                {
                    "id": "xyz123",
                    "displayName": {"text": "No Photo Taco"},
                    "types": ["mexican_restaurant"],
                },
                "test-key",
            )

        self.assertEqual(live_photo["photo_source"], "google_places")
        self.assertIn("places.googleapis.com", live_photo["photo"])
        self.assertEqual(fallback_photo["photo_source"], "biteswipe_fallback")
        self.assertIn("restaurant-fallbacks/mexican.webp", fallback_photo["photo"])
        self.assertIsNone(fallback_photo["walking_minutes"])

    def test_hybrid_merge_keeps_osm_distance_and_google_price_photo(self) -> None:
        merged = merge_osm_places_with_google_enrichment(
            [
                {
                    "name": "Campus Pizza",
                    "place": "osm:node:3",
                    "photo": "/static/restaurant-fallbacks/pizza.webp",
                    "photo_source": "biteswipe_fallback",
                    "source": "openstreetmap",
                    "address": "10 Market Street",
                    "distance_meters": 88,
                    "walking_minutes": 1,
                    "price_text": None,
                }
            ],
            [
                {
                    "name": "Campus Pizza",
                    "place": "google-place-3",
                    "photo": "https://places.googleapis.com/photo",
                    "photo_source": "google_places",
                    "source": "google",
                    "address": "10 Market Street Philadelphia PA",
                    "price_text": "$",
                    "price_level": 1,
                }
            ],
        )

        self.assertEqual(merged[0]["source"], "hybrid")
        self.assertEqual(merged[0]["place"], "osm:node:3")
        self.assertEqual(merged[0]["google_place_id"], "google-place-3")
        self.assertEqual(merged[0]["distance_meters"], 88)
        self.assertEqual(merged[0]["photo_source"], "google_places")
        self.assertEqual(merged[0]["price_text"], "$")

    def test_restaurant_price_helpers_do_not_show_free_for_unknown_cost(self) -> None:
        self.assertEqual(normalize_price_level("$"), 1)
        self.assertEqual(format_price_text(normalize_price_level("$")), "$")
        self.assertIsNone(normalize_price_level("0"))
        self.assertIsNone(format_price_text(normalize_price_level("0")))
        self.assertIsNone(normalize_google_price_level("PRICE_LEVEL_FREE"))

        with self.app.test_request_context():
            osm_place = format_osm_place(
                {
                    "type": "node",
                    "id": 125,
                    "lat": 39.9567,
                    "lon": -75.1898,
                    "tags": {
                        "amenity": "restaurant",
                        "name": "Dollar Slice",
                        "price": "$",
                    },
                },
                39.9566,
                -75.1899,
            )
            google_place = format_google_place(
                {
                    "id": "free-level-place",
                    "displayName": {"text": "Unknown Cost Cafe"},
                    "priceLevel": "PRICE_LEVEL_FREE",
                },
                "test-key",
            )

        self.assertEqual(osm_place["price_level"], 1)
        self.assertEqual(osm_place["price_text"], "$")
        self.assertIsNone(google_place["price_level"])
        self.assertIsNone(google_place["price_text"])

    def test_save_restaurant_sends_card_to_my_stuff(self) -> None:
        self.login()
        response = self.client.post(
            "/save_restaurant",
            json={
                "name": "Savas Brick Oven Pizza",
                "place": "osm:node:123",
                "source": "openstreetmap",
                "address": "3505 Lancaster Ave",
                "photo": "/static/biteswipe.png",
                "distance_meters": 250,
                "cuisine": "pizza",
                "price_text": "$$",
                "rating": 4.5,
                "review_count": 120,
                "website": "savas.example.com",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])

        response = self.client.get("/credits")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Savas Brick Oven Pizza", response.data)
        self.assertIn(b"3505 Lancaster Ave", response.data)
        self.assertIn(b"pizza", response.data)
        self.assertIn(b"$$", response.data)
        self.assertIn(b"4.5 rated", response.data)
        self.assertIn(b"https://savas.example.com", response.data)
        self.assertIn(b"Directions", response.data)

    def test_save_restaurant_deduplicates_per_user(self) -> None:
        self.login()
        payload = {"name": "Test Cafe", "place": "osm:node:1", "source": "openstreetmap"}
        self.client.post("/save_restaurant", json=payload)
        self.client.post("/save_restaurant", json=payload | {"name": "Test Cafe Updated"})

        with self.app.app_context():
            saved = SavedRestaurant.query.all()
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].name, "Test Cafe Updated")


if __name__ == "__main__":
    unittest.main()
