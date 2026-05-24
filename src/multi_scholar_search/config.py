from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    google_scholar_base_url: str = "https://scholar.google.com/scholar"
    google_scholar_language: str = "en"
    chromium_path: str = (
        r"C:\Users\diego.melo_maplink\AppData\Local\ms-playwright"
        r"\chromium-1223\chrome-win64\chrome.exe"
    )
    user_agents_url: str = (
        "https://gist.githubusercontent.com/pzb/b4b6f57144aea7827ae4"
        "/raw/cf847b76a142955b1410c8bcef3aabe221a63db1/user-agents.txt"
    )

    chromium_proxy: str | None = None

    save_results: bool = False
    data_dir: str = "data"
    default_limit: int = 10

    # Anti-rate-limit: seconds to wait between page fetches (0 = no delay)
    page_delay: float = 3.0
    # How many times to retry a page that returns 0 results before giving up
    page_retries: int = 2
    # Extra seconds DrissionPage waits after load_start before reading HTML
    drission_settle_time: float = 2.0


settings = Settings()
