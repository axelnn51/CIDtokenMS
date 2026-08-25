from browser.chromium import ChromiumController
from playwright.async_api import BrowserContext

class BrowserLifecycle:
    """
    Context manager that guarantees browser startup and safe teardown
    even if exceptions or timeouts occur.
    """
    def __init__(self, profile_dir: str = "/opt/getcid_data/browser_profile"):
        self.controller = ChromiumController(profile_dir)
        self.context: BrowserContext = None

    async def __aenter__(self) -> BrowserContext:
        self.context = await self.controller.start()
        return self.context

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.controller.stop()
