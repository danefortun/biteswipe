from __future__ import annotations

import unittest
import shutil
from unittest.mock import patch
from uuid import uuid4
from pathlib import Path

from db import db
from main import build_overpass_query, create_app, format_osm_place, get_school_theme_for_email
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
        theme = get_school_theme_for_email("student@drexel.edu")
        self.assertIsNotNone(theme)
        self.assertEqual(theme["slug"], "drexel")
        self.assertEqual(theme["short_name"], "Drexel")
        self.assertEqual(theme["image_file"], "schools/drexel.webp")

        subdomain_theme = get_school_theme_for_email("student@mail.drexel.edu")
        self.assertIsNotNone(subdomain_theme)
        self.assertEqual(subdomain_theme["slug"], "drexel")

        self.assertEqual(get_school_theme_for_email("student@temple.edu")["image_file"], "schools/temple.webp")
        self.assertEqual(get_school_theme_for_email("student@upenn.edu")["image_file"], "schools/upenn.webp")
        self.assertEqual(get_school_theme_for_email("student@wcupa.edu")["image_file"], "schools/west-chester.webp")

        generated = get_school_theme_for_email("student@examplecollege.edu")
        self.assertIsNotNone(generated)
        self.assertEqual(generated["domain"], "examplecollege.edu")
        self.assertEqual(generated["is_generated"], "true")

        self.assertIsNone(get_school_theme_for_email("person@example.com"))

    def test_home_applies_school_theme_to_cards_page(self) -> None:
        self.login(email="student@drexel.edu")

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-school-theme="drexel"', response.data)
        self.assertIn(b"--school-primary: #07294D", response.data)
        self.assertIn(b"Drexel mode", response.data)

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
        self.assertIn("Market St", place["address"])

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
