import os
import tempfile
import unittest


class StudyPlannerSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.db_file.close()
        os.environ["SQLITE_PATH"] = cls.db_file.name
        os.environ.pop("DATABASE_URL", None)
        from backend.app import app
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls.db_file.name)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "ok")

    def test_frontend_assets_are_served(self):
        with self.client.get("/css/style.css") as css:
            self.assertEqual(css.status_code, 200)
            self.assertIn("text/css", css.content_type)
            self.assertIn(b"--purple", css.data)
        with self.client.get("/js/script.js") as javascript:
            self.assertEqual(javascript.status_code, 200)
            self.assertIn("javascript", javascript.content_type)
            self.assertIn(b"const api", javascript.data)

    def test_register_and_create_subject(self):
        response = self.client.post("/api/register", json={"username": "student", "password": "password123"})
        self.assertEqual(response.status_code, 201)
        response = self.client.post("/api/subjects", json={"name": "Mathematics", "color": "#6c63ff"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["name"], "Mathematics")


if __name__ == "__main__":
    unittest.main()
