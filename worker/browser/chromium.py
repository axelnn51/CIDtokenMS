import logging
from playwright.async_api import async_playwright, BrowserContext

logger = logging.getLogger(__name__)

class ChromiumController:
    def __init__(self, profile_dir: str = "/opt/getcid_data/browser_profile"):
        self.profile_dir = profile_dir
        self.playwright = None
        self.browser_context: BrowserContext = None
        
    async def start(self) -> BrowserContext:
        """Starts Playwright with a persistent context and stealthy arguments."""
        logger.info("Initializing Playwright and Chromium...")
        self.playwright = await async_playwright().start()
        
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
            '--no-sandbox',
            '--disable-setuid-sandbox'
        ]
        
        self.browser_context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=True,
            args=args,
            viewport={'width': 1920, 'height': 1080},
            ignore_https_errors=True
        )
        
        return self.browser_context

    async def stop(self):
        """Stops Playwright and ensures no zombie processes."""
        if self.browser_context:
            logger.info("Closing Browser Context...")
            await self.browser_context.close()
            self.browser_context = None
            
        if self.playwright:
            logger.info("Stopping Playwright...")
            await self.playwright.stop()
            self.playwright = None
