"""Environment-backed configuration for the deployable Flask application."""

import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "local-development-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///study_planner.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
