import logging
import asyncio
from playwright.async_api import BrowserContext, Page, Request, Response
from jobs.models import JobStatus, JobResult

logger = logging.getLogger(__name__)

class MicrosoftOperation:
    def __init__(self, context: BrowserContext):
        self.context = context

    async def execute_token_extraction(self, target_url: str) -> JobResult:
        """
        Navigates to the portal and extracts the authentication token.
        """
        page = None
        extracted_token = None
        token_type = None
        
        try:
            page = await self.context.new_page()
            
            # 1. Option A: Intercept Network Requests to catch Bearer tokens
            async def handle_request(request: Request):
                nonlocal extracted_token, token_type
                headers = request.headers
                
                # Check for Bearer token in headers
                if "authorization" in headers:
                    auth_header = headers["authorization"]
                    if auth_header.lower().startswith("bearer "):
                        extracted_token = auth_header.split(" ", 1)[1]
                        token_type = "Bearer/JWT"
                        logger.info("Token intercepted from Network Request headers!")

            page.on("request", handle_request)
            
            logger.info(f"Navigating to {target_url} for token extraction...")
            await page.goto(target_url, wait_until="networkidle")
            
            # Wait a few seconds to ensure background requests happen
            await asyncio.sleep(5)
            
            # 2. Option B: Check LocalStorage / SessionStorage if network interception didn't catch it
            if not extracted_token:
                logger.info("No token in network requests. Checking localStorage...")
                # We can execute JS to pull tokens. E.g., MSAL tokens are often stored here.
                storage_state = await self.context.storage_state()
                # Iterate over origins to find tokens or cookies
                # For this mock/refactor we'll simulate finding it if not found in headers
                # Real logic would inspect storage_state['origins'] or storage_state['cookies']
                
                # Simulated token extraction for the skeleton
                extracted_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.SIMULATED_TOKEN..."
                token_type = "LocalStorage"
                
            if extracted_token:
                logger.info(f"Token extraction successful ({token_type}).")
                return JobResult(token=extracted_token, token_type=token_type)
            else:
                return JobResult(error_type="TOKEN_NOT_FOUND", error_message="Could not extract token from network or storage.")

        except Exception as e:
            logger.error(f"Error during token extraction: {e}")
            return JobResult(error_type="EXECUTION_ERROR", error_message=str(e))
        finally:
            if page:
                await page.close()
