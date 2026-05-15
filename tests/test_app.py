from __future__ import annotations

import unittest
import shutil
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4
from pathlib import Path

from blog_db import BlogPosts
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
    sort_restaurants_by_availability,
)
from users_db import (
    AvoidedRestaurant,
    GroupSwipeMember,
    GroupSwipeSession,
    SavedRestaurant,
    UserFollow,
    UserFilterUsage,
    UserDeckEvent,
    UserInterest,
    UserNotification,
    UserRestaurantRating,
    Users,
)


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
        self.client.post(
            "/signup",
            data={"email": email, "pass": password, "confirm_pass": password},
            follow_redirects=False,
        )
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

    def test_signup_creates_hashed_user_and_login_rejects_wrong_password(self) -> None:
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

    def test_login_unknown_email_does_not_create_account(self) -> None:
        response = self.client.post(
            "/login",
            data={"email": "typo@example.com", "pass": "password123"},
        )
        self.assertEqual(response.status_code, 404)

        with self.app.app_context():
            self.assertIsNone(Users.query.filter_by(email="typo@example.com").first())

    def test_signup_requires_matching_password_confirmation(self) -> None:
        response = self.client.post(
            "/signup",
            data={"email": "new@example.com", "pass": "password123", "confirm_pass": "different"},
        )
        self.assertEqual(response.status_code, 400)

    def test_signup_rejects_invalid_email_and_creates_verification_token(self) -> None:
        response = self.client.post(
            "/signup",
            data={"email": "not-an-email", "pass": "password123", "confirm_pass": "password123"},
        )
        self.assertEqual(response.status_code, 400)

        self.login(email="verify@example.com")
        with self.app.app_context():
            user = Users.query.filter_by(email="verify@example.com").first()
            self.assertIsNotNone(user)
            self.assertFalse(user.email_verified)
            self.assertTrue(user.email_verification_token)

    def test_forgot_password_route_exists(self) -> None:
        response = self.client.get("/forgot-password")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Forgot your password", response.data)

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

    def test_custom_quick_interests_are_limited_and_moderated(self) -> None:
        self.login()

        response = self.client.post(
            "/save_filters",
            json={
                "foodPreferences": [
                    "Tacos",
                    "Post Gym",
                    "too-many-characters-here",
                    "bad!",
                    "shit",
                ],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["filters"]["foodPreferences"], ["Tacos", "Post Gym"])

        response = self.client.post(
            "/profile",
            data={"action": "add_food_preference", "food_preference": "bad!"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"letters, numbers, and spaces", response.data)

        response = self.client.post(
            "/profile",
            data={"action": "add_food_preference", "food_preference": "Tacos"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Added Tacos to your quick interests.", response.data)

    def test_deck_streak_updates_on_home_open(self) -> None:
        self.login()
        self.client.get("/")
        with self.app.app_context():
            user = Users.query.filter_by(email="person@example.com").first()
            self.assertEqual(user.deck_streak_count, 1)

    def test_avoid_restaurant_persists_server_side(self) -> None:
        self.login()
        response = self.client.post("/avoid_restaurant", json={"place": "place-1", "name": "Nope Cafe"})
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertIsNotNone(AvoidedRestaurant.query.filter_by(place_id="place-1").first())

    def test_leaderboard_renders_unique_cuisine_counts(self) -> None:
        self.login(email="student@drexel.edu")
        with self.app.app_context():
            user = Users.query.filter_by(email="student@drexel.edu").first()
            db.session.add(SavedRestaurant(user_id=user.id, place_id="a", name="A", cuisine="Pizza"))
            db.session.add(SavedRestaurant(user_id=user.id, place_id="b", name="B", cuisine="Thai"))
            db.session.commit()
        response = self.client.get("/leaderboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"2 cuisines", response.data)

    def test_ambassador_badge_and_picks_surface_to_followers(self) -> None:
        self.login(email="ambassador@example.com")
        self.client.get("/logout")
        self.login(email="viewer@example.com")

        with self.app.app_context():
            ambassador = Users.query.filter_by(email="ambassador@example.com").first()
            viewer = Users.query.filter_by(email="viewer@example.com").first()
            for index in range(500):
                db.session.add(
                    SavedRestaurant(
                        user_id=ambassador.id,
                        place_id=f"ambassador-{index}",
                        name=f"Pick {index}",
                        cuisine="Cafe",
                        rating=5 if index == 499 else 4,
                    )
                )
            viewer.latitude = 39.9566
            viewer.longitude = -75.1899
            db.session.add(UserFollow(follower_id=viewer.id, following_id=ambassador.id, status="approved"))
            db.session.commit()

        response = self.client.get("/@ambassador")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Verified foodie", response.data)
        self.assertIn(b"Top picks", response.data)

        with patch("main.search_restaurants_hybrid", return_value=([], "hybrid")):
            response = self.client.get("/get_restaurant")
        self.assertEqual(response.status_code, 200)
        places = response.get_json()["places"]
        self.assertTrue(places)
        self.assertTrue(places[0]["ambassador_pick"])
        self.assertEqual(places[0]["recommended_by_handle"], "ambassador")

    def test_saved_exports_and_student_deal_filter(self) -> None:
        self.login(email="student@drexel.edu")
        with self.app.app_context():
            user = Users.query.filter_by(email="student@drexel.edu").first()
            saved = SavedRestaurant(
                user_id=user.id,
                place_id="deal-1",
                name="Deal Cafe",
                address="1 Campus Way",
                cuisine="Cafe",
                student_discount=True,
            )
            db.session.add(saved)
            db.session.commit()
            saved_id = saved.id
        response = self.client.get("/saved/export.kml")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Deal Cafe", response.data)
        response = self.client.get(f"/saved/{saved_id}/calendar.ics?date=2026-05-20&time=18:30")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"BEGIN:VCALENDAR", response.data)
        response = self.client.post("/save_filters", json={"studentDealsOnly": True})
        self.assertTrue(response.get_json()["filters"]["studentDealsOnly"])

    def test_google_menu_preview_is_preserved_when_provider_supplies_dishes(self) -> None:
        with self.app.test_request_context():
            place = format_google_place(
                {
                    "id": "menu-place",
                    "displayName": {"text": "Menu Cafe"},
                    "menu": ["Tacos", "Fries", "Milkshake", "Soup", "Salad", "Pie"],
                },
                "test-key",
            )
        self.assertEqual(place["menu_preview"], ["Tacos", "Fries", "Milkshake", "Soup", "Salad"])

    def test_restaurant_search_uses_cache_and_rate_limits(self) -> None:
        self.login()
        self.app.config.update(
            {
                "RESTAURANT_SEARCH_RATE_LIMIT_COUNT": 2,
                "RESTAURANT_SEARCH_RATE_LIMIT_WINDOW_SECONDS": 60,
            }
        )
        self.client.post("/save_location", json={"latitude": 39.9566, "longitude": -75.1899})
        with patch(
            "main.search_restaurants_with_openstreetmap",
            return_value=[{"name": "Cache Cafe", "place": "osm:node:9", "distance_meters": 10}],
        ) as search:
            first = self.client.get("/get_restaurant")
            second = self.client.get("/get_restaurant")
            third = self.client.get("/get_restaurant")
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.get_json()["cache_hit"])
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.get_json()["cache_hit"])
        self.assertEqual(third.status_code, 429)
        search.assert_called_once()

    def test_save_restaurant_rate_limit_blocks_bursts(self) -> None:
        self.login()
        self.app.config.update(
            {
                "RESTAURANT_SAVE_RATE_LIMIT_COUNT": 1,
                "RESTAURANT_SAVE_RATE_LIMIT_WINDOW_SECONDS": 60,
            }
        )
        payload = {"name": "Limit Cafe", "place": "osm:node:10"}
        self.assertEqual(self.client.post("/save_restaurant", json=payload).status_code, 200)
        self.assertEqual(self.client.post("/save_restaurant", json=payload).status_code, 429)

    def test_admin_dashboard_requires_admin_and_shows_metrics(self) -> None:
        self.login(email="admin@example.com")
        self.app.config.update({"ADMIN_EMAILS": ["admin@example.com"]})
        self.client.post("/save_filters", json={"openNow": True})
        self.client.post("/deck/complete")
        self.client.post("/save_location", json={"latitude": 39.9566, "longitude": -75.1899})
        with patch("main.search_restaurants_with_openstreetmap", return_value=[]):
            self.client.get("/get_restaurant")
        response = self.client.get("/admin/analytics")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Analytics dashboard", response.data)
        self.assertIn(b"Open now", response.data)
        with self.app.app_context():
            self.assertEqual(UserFilterUsage.query.count(), 1)
            self.assertEqual(UserDeckEvent.query.count(), 2)

        self.client.get("/logout")
        self.login(email="plain@example.com")
        self.assertEqual(self.client.get("/admin/analytics").status_code, 403)

    def test_pwa_manifest_is_served(self) -> None:
        response = self.client.get("/static/manifest.webmanifest")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"name": "BiteSwipe"', response.data)

    def test_default_distance_filter_is_campus_sized(self) -> None:
        self.login()

        response = self.client.get("/get_filters")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["distance"], 2)

    def test_transportation_mode_sets_radius(self) -> None:
        self.login()

        response = self.client.post("/save_transportation", json={"mode": "walking"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["filters"]["distance"], 1)

        response = self.client.post("/save_transportation", json={"mode": "driving"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["filters"]["distance"], 10)

        with self.app.app_context():
            user = Users.query.filter_by(email="person@example.com").first()
            self.assertEqual(user.transportation_mode, "driving")

    def test_user_rating_persists_server_side(self) -> None:
        self.login()

        response = self.client.post("/user_rating", json={"place": "osm:node:1", "rating": 4})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["rating"], 4)

        response = self.client.get("/user_ratings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["ratings"]["osm:node:1"], 4)

        with self.app.app_context():
            self.assertEqual(UserRestaurantRating.query.count(), 1)

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

        with self.app.app_context():
            user = Users.query.filter_by(email="person@example.com").first()
            self.assertIsNotNone(user)
            row = UserInterest.query.filter_by(user_id=user.id, category="hobby", value_key="music").first()
            self.assertIsNotNone(row)

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

    def test_profile_showcase_upload_updates_side_image(self) -> None:
        self.login()

        response = self.client.post(
            "/profile",
            data={
                "action": "upload_showcase",
                "showcase_image": (BytesIO(b"showcase-image"), "showcase.gif"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"profile-showcase-card", response.data)
        self.assertIn(b"user-showcase-", response.data)
        self.assertIn(b"profile-showcase-upload-btn", response.data)

    def test_public_user_id_profile_route_renders_public_profile(self) -> None:
        self.login()
        self.client.post(
            "/profile",
            data={"action": "add_food_preference", "food_preference": "Pizza"},
            follow_redirects=False,
        )

        with self.app.app_context():
            user = Users.query.filter_by(email="person@example.com").first()
            user_id = user.id

        response = self.client.get(f"/userID={user_id}")
        self.assertEqual(response.status_code, 301)
        self.assertIn(f"/user/{user_id}".encode(), response.headers["Location"].encode())

        response = self.client.get(f"/user/{user_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"(@person)", response.data)
        self.assertIn(b"biteswipe.lol/@person", response.data)
        self.assertIn(b"Pizza", response.data)
        self.assertNotIn(b"Edit filters", response.data)

    def test_public_profile_uses_at_handle_route(self) -> None:
        self.login(email="dane@example.com")

        response = self.client.get("/dane")
        self.assertEqual(response.status_code, 404)

        response = self.client.get("/@dane")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"(@dane)", response.data)
        self.assertIn(b"biteswipe.lol/@dane", response.data)

    def test_profile_page_shows_handle_and_copies_handle_link(self) -> None:
        self.login(email="dane@example.com")

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"(@dane)", response.data)
        self.assertIn(b"/@dane", response.data)
        self.assertIn(b"Bio, 256 characters max", response.data)
        self.assertIn(b"setup steps", response.data)
        self.assertIn(b'class="header-settings-label">Dane</span>', response.data)
        self.assertIn(b"/settings", response.data)
        self.assertIn(b"/friends/requests", response.data)

    def test_profile_stat_visibility_controls_public_stats(self) -> None:
        self.login(email="dane@example.com")

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"profile-stat-visibility-form", response.data)
        self.assertIn(b"+ join date", response.data)

        response = self.client.post(
            "/profile",
            data={"action": "update_profile_stat", "stat_key": "saved_picks", "visible": "false"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"is-hidden-stat", response.data)

        response = self.client.get("/@dane")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"saved picks", response.data)

    def test_profile_can_add_optional_public_stats(self) -> None:
        self.login(email="dane@example.com")

        response = self.client.post(
            "/profile",
            data={"action": "update_profile_stat", "stat_key": "join_date", "visible": "true"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/@dane")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"join date", response.data)

    def test_profile_badges_can_be_hidden_and_ordered_with_stats(self) -> None:
        self.login(email="dane@example.com")
        self.client.post(
            "/profile",
            data={"action": "update_pronouns", "pronouns": "they/them"},
            follow_redirects=False,
        )
        self.client.post(
            "/profile",
            data={"action": "add_food_preference", "food_preference": "Pizza"},
            follow_redirects=False,
        )

        response = self.client.post(
            "/profile",
            data={"action": "update_profile_badge", "badge_key": "pronouns", "visible": "false"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/@dane")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"they/them", response.data)

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"profile-badge-visibility-form", response.data)
        self.assertIn(b"they/them", response.data)
        self.assertIn(b"profile-sortable-item", response.data)
        self.assertNotIn(b"profile-drag-handle", response.data)

        response = self.client.post("/profile/order", json={"kind": "stats", "order": ["interests", "saved_picks"]})
        self.assertEqual(response.status_code, 200)
        response = self.client.post("/profile/order", json={"kind": "badges", "order": ["favorite-cuisine", "pronouns"]})
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/profile")
        body = response.data.decode()
        self.assertLess(body.index("interests"), body.index("saved picks"))
        self.assertLess(body.index("Favorite: Pizza"), body.index("they/them"))

    def test_public_handle_uses_selected_username_not_display_name(self) -> None:
        self.login(email="dane@example.com")

        response = self.client.post(
            "/profile",
            data={"action": "update_name", "name": "Dane Display", "username": "taste-dane"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/dane")
        self.assertEqual(response.status_code, 404)

        response = self.client.get("/@taste-dane")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dane Display", response.data)
        self.assertIn(b"(@taste-dane)", response.data)
        self.assertIn(b"biteswipe.lol/@taste-dane", response.data)

    def test_numeric_public_username_only_loads_with_at_route(self) -> None:
        self.login(email="dane@example.com")

        response = self.client.post(
            "/profile",
            data={"action": "update_name", "name": "Dane Display", "username": "1000"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/1000")
        self.assertEqual(response.status_code, 404)

        response = self.client.get("/@1000")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"(@1000)", response.data)
        self.assertIn(b"biteswipe.lol/@1000", response.data)

    def test_founder_party_badge_uses_configured_founder_ids(self) -> None:
        with self.app.app_context():
            founder = Users(
                name="Founder",
                email="founder@example.com",
                password="password",
                username="founder",
            )
            filler = Users(
                name="Filler",
                email="filler@example.com",
                password="password",
                username="filler",
            )
            party_guest = Users(
                name="Party Guest",
                email="party@example.com",
                password="password",
                username="party",
            )
            db.session.add_all([founder, filler, party_guest])
            db.session.commit()
            self.app.config["BITESWIPE_FOUNDER_USER_IDS"] = f"{founder.id},9,{filler.id + 20}"

            group_session = GroupSwipeSession(code="PARTY1", host_user_id=founder.id)
            db.session.add(group_session)
            db.session.commit()
            db.session.add(GroupSwipeMember(session_id=group_session.id, user_id=founder.id))
            db.session.add(GroupSwipeMember(session_id=group_session.id, user_id=party_guest.id))
            db.session.commit()

        response = self.client.get("/@party")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Founder party", response.data)

    def test_public_username_must_be_unique(self) -> None:
        self.login(email="dane@example.com")
        self.client.get("/logout")
        self.login(email="other@example.com")

        response = self.client.post(
            "/profile",
            data={"action": "update_name", "name": "Other Person", "username": "dane"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"@dane is already taken.", response.data)

    def test_chat_posts_return_user_names(self) -> None:
        self.login()
        response = self.client.post("/chat", data={"message": "hello"}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/get_posts")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["posts"][0]["message"], "hello")
        self.assertEqual(payload["posts"][0]["user_name"], "Person")
        self.assertIn("has_more", payload)
        self.assertIn("next_before", payload)

    def test_chat_posts_are_paginated_and_rate_limited(self) -> None:
        self.login()
        for index in range(6):
            response = self.client.post("/chat", data={"message": f"message {index}"}, follow_redirects=False)
            if index < 5:
                self.assertEqual(response.status_code, 302)
            else:
                self.assertEqual(response.status_code, 302)

        response = self.client.get("/get_posts?limit=3")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["posts"]), 3)
        self.assertTrue(payload["has_more"])

        with self.app.app_context():
            self.assertEqual(BlogPosts.query.count(), 5)

    def test_follow_approval_creates_notification(self) -> None:
        self.login(email="requester@example.com")
        self.client.get("/logout")
        self.login(email="approver@example.com")

        with self.app.app_context():
            requester = Users.query.filter_by(email="requester@example.com").first()
            approver = Users.query.filter_by(email="approver@example.com").first()
            requester_id = requester.id
            approver_id = approver.id

        self.client.get("/logout")
        self.client.post("/login", data={"email": "requester@example.com", "pass": "password123"})
        self.client.post(f"/follow/{approver_id}", follow_redirects=False)
        self.client.get("/logout")
        self.client.post("/login", data={"email": "approver@example.com", "pass": "password123"})
        response = self.client.post(f"/follow/{requester_id}/approve", follow_redirects=False)
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            notification = UserNotification.query.filter_by(user_id=requester_id, kind="follow_accepted").first()
            self.assertIsNotNone(notification)
            self.assertIn("accepted your follow request", notification.message)

    def test_friend_requests_page_and_public_profile_accept_decline(self) -> None:
        self.login(email="requester@example.com")
        self.client.get("/logout")
        self.login(email="approver@example.com")

        with self.app.app_context():
            requester = Users.query.filter_by(email="requester@example.com").first()
            approver = Users.query.filter_by(email="approver@example.com").first()
            requester_id = requester.id
            approver_id = approver.id

        self.client.get("/logout")
        self.client.post("/login", data={"email": "requester@example.com", "pass": "password123"})
        self.client.post(f"/follow/{approver_id}", follow_redirects=False)

        self.client.get("/logout")
        self.client.post("/login", data={"email": "approver@example.com", "pass": "password123"})
        response = self.client.get("/friends/requests")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Requests to you", response.data)
        self.assertIn(b"Requester", response.data)

        response = self.client.get("/@requester")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"has sent you a request", response.data)
        self.assertIn(b"Accept", response.data)
        self.assertIn(b"Decline", response.data)

        response = self.client.post(
            f"/follow/{requester_id}/decline",
            data={"next": "/friends/requests"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            self.assertIsNone(UserFollow.query.filter_by(follower_id=requester_id, following_id=approver_id).first())

        self.client.get("/logout")
        self.client.post("/login", data={"email": "requester@example.com", "pass": "password123"})
        self.client.post(f"/follow/{approver_id}", follow_redirects=False)
        self.client.get("/logout")
        self.client.post("/login", data={"email": "approver@example.com", "pass": "password123"})
        response = self.client.post(
            f"/follow/{requester_id}/approve",
            data={"next": "/requester"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/requester"))

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
                    "currentOpeningHours": {
                        "openNow": False,
                        "nextOpenTime": "2026-05-14T18:00:00Z",
                    },
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
        self.assertFalse(live_photo["is_open"])
        self.assertEqual(live_photo["next_open_time"], "2026-05-14T18:00:00Z")
        self.assertEqual(fallback_photo["photo_source"], "biteswipe_fallback")
        self.assertIn("restaurant-fallbacks/mexican.webp", fallback_photo["photo"])
        self.assertIsNone(fallback_photo["walking_minutes"])

    def test_availability_sort_de_ranks_closed_restaurants(self) -> None:
        places = [
            {"name": "Closed Cafe", "is_open": False, "distance_meters": 10},
            {"name": "Mystery Diner", "is_open": None, "distance_meters": 5},
            {"name": "Open Grill", "is_open": True, "distance_meters": 40},
        ]

        sort_restaurants_by_availability(places)

        self.assertEqual([place["name"] for place in places], ["Open Grill", "Mystery Diner", "Closed Cafe"])

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
