import logging
import asyncio
from playwright.async_api import BrowserContext, Page
from jobs.models import JobStatus, JobResult

logger = logging.getLogger(__name__)

class MicrosoftOperation:
    def __init__(self, context: BrowserContext):
        self.context = context

    async def execute_getcid(self, installation_id: str) -> JobResult:
        """
        Executes the GETCID operation in the authenticated portal.
        """
        page = None
        try:
            page = await self.context.new_page()
            
            logger.info(f"Injecting Installation ID: {installation_id}...")
            # Aquí irá la lógica real de Playwright:
            # 1. Navegar a la página específica de inserción de IID
            # 2. Llenar los campos de texto correspondientes
            # 3. Hacer clic en "Submit" / "Obtener CID"
            # 4. Esperar a que el selector del resultado aparezca
            
            # SIMULACIÓN (hasta tener los selectores reales)
            await page.goto("https://visualsupport.microsoft.com/", wait_until="networkidle")
            await asyncio.sleep(2)
            
            # Validar si hubo algún error en el proceso (ej. IID inválido)
            # if await page.locator(".error-message").is_visible():
            #     error_text = await page.locator(".error-message").inner_text()
            #     return JobResult(error_type="INVALID_IID", error_message=error_text)
            
            # Extraer el CID real
            # cid_value = await page.locator("#cid-result-box").inner_text()
            
            logger.info("Operation completed successfully.")
            return JobResult(cid=f"MOCK_CID_FOR_{installation_id}")

        except Exception as e:
            logger.error(f"Error during GETCID operation: {e}")
            return JobResult(error_type="EXECUTION_ERROR", error_message=str(e))
        finally:
            if page:
                await page.close()
