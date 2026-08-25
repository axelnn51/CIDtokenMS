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
            
            # Extract EVERYTHING from the browser context since we don't know the specific target
            logger.info("Extracting all cookies and storage state...")
            storage_state = await self.context.storage_state()
            
            # Extract Cookies
            cookies = storage_state.get('cookies', [])
            
            # Extract Local Storage from origins
            origins = storage_state.get('origins', [])
            local_storage = {}
            for origin in origins:
                ls_items = origin.get('localStorage', [])
                if ls_items:
                    local_storage[origin['origin']] = {item['name']: item['value'] for item in ls_items}
            
            # Combine into a final result payload
            extracted_data = {
                "cookies": cookies,
                "local_storage": local_storage,
                "network_tokens": [] # If any were caught by interceptor
            }

            if extracted_token:
                extracted_data["network_tokens"].append({
                    "type": token_type,
                    "value": extracted_token
                })
                
            # Log success
            logger.info(f"Extraction successful! Found {len(cookies)} cookies and {len(local_storage)} origins with localStorage.")
            
            # Return the massive JSON object so the user can parse it on their backend
            import json
            return JobResult(token=json.dumps(extracted_data), token_type="FullDump")

        except Exception as e:
            logger.error(f"Error during token extraction: {e}")
            return JobResult(error_type="EXECUTION_ERROR", error_message=str(e))
        finally:
            if page:
                await page.close()
