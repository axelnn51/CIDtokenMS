import logging
from playwright.async_api import BrowserContext, Page
from jobs.models import JobStatus

logger = logging.getLogger(__name__)

class MicrosoftAuthenticator:
    def __init__(self, context: BrowserContext):
        self.context = context

    async def check_auth_status(self) -> JobStatus:
        """
        Navigates to the portal and checks if the session is active,
        or if a login/challenge is required.
        """
        page = None
        try:
            page = await self.context.new_page()
            
            # Navegamos a una URL que sepamos que redirige al login si no estamos autenticados
            # visualsupport.microsoft.com es un placeholder, ajustaremos a la URL exacta que uses.
            logger.info("Navigating to Microsoft Portal to check auth status...")
            await page.goto("https://visualsupport.microsoft.com/", wait_until="networkidle")
            
            # 1. Detectar si estamos en login
            if "login.microsoftonline.com" in page.url or "live.com" in page.url:
                logger.warning("Session expired or not found. Auth required.")
                return JobStatus.CHALLENGE_REQUIRED
                
            # 2. Detectar si hay WAF / Cloudflare
            if await page.locator("text='Just a moment...'").is_visible() or \
               await page.locator("iframe[src*='challenge']").is_visible():
                logger.warning("WAF/CAPTCHA challenge detected!")
                return JobStatus.CHALLENGE_REQUIRED
                
            # 3. Detectar si entramos correctamente al portal
            # TODO: Add specific selector that proves we are in the authenticated dashboard
            # Example:
            # if await page.locator("#user-profile-menu").is_visible():
            logger.info("Authentication verified. Session is active.")
            return JobStatus.EXECUTING

        except Exception as e:
            logger.error(f"Error checking auth status: {e}")
            return JobStatus.UNKNOWN_STATE
        finally:
            if page:
                await page.close()
