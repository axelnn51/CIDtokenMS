import logging
import os
import asyncio
from playwright.async_api import BrowserContext, Page
from jobs.models import JobStatus

logger = logging.getLogger(__name__)

class MicrosoftAuthenticator:
    def __init__(self, context: BrowserContext):
        self.context = context
        self.email = os.getenv("MS_EMAIL")
        self.password = os.getenv("MS_PASSWORD")

    async def check_auth_status(self) -> JobStatus:
        """
        Navigates to Visual Studio and performs login if necessary.
        """
        page = None
        try:
            if not self.email or not self.password:
                logger.error("MS_EMAIL or MS_PASSWORD is not set in environment!")
                return JobStatus.FAILED_PERMANENTLY

            page = await self.context.new_page()
            
            logger.info("Navigating to https://my.visualstudio.com/ to check auth status...")
            await page.goto("https://my.visualstudio.com/", wait_until="networkidle")
            
            # 1. Detect if we are already logged in
            if "my.visualstudio.com" in page.url and "login" not in page.url:
                logger.info("Already authenticated. Session is active.")
                return JobStatus.EXECUTING

            # 2. Login Flow
            logger.info("Session expired or not found. Attempting login...")
            
            # Enter Email
            email_input = page.locator("input[type='email']")
            if await email_input.is_visible(timeout=5000):
                logger.info("Entering email...")
                await email_input.fill(self.email)
                await email_input.press("Enter")
                await page.wait_for_load_state("networkidle")
            
            # Enter Password
            password_input = page.locator("input[type='password']")
            if await password_input.is_visible(timeout=10000):
                logger.info("Entering password...")
                await password_input.fill(self.password)
                await password_input.press("Enter")
                await page.wait_for_load_state("networkidle")
            
            # Handle "Stay signed in?" prompt
            stay_signed_in = page.locator("text='Stay signed in?'")
            kmsi_button = page.locator("input[id='idBtn_Back']") # Usually 'No' button
            if await stay_signed_in.is_visible(timeout=5000) or await kmsi_button.is_visible():
                logger.info("Handling 'Stay signed in' prompt...")
                await kmsi_button.click()
                await page.wait_for_load_state("networkidle")
            
            # Check final URL to verify success
            await asyncio.sleep(3) # Wait for redirects
            if "login.microsoftonline.com" not in page.url and "live.com" not in page.url:
                logger.info("Authentication successful!")
                return JobStatus.EXECUTING
            else:
                logger.warning(f"Login might have failed or needs 2FA. Current URL: {page.url}")
                return JobStatus.CHALLENGE_REQUIRED

        except Exception as e:
            logger.error(f"Error checking auth status: {e}")
            return JobStatus.UNKNOWN_STATE
        finally:
            if page:
                await page.close()
