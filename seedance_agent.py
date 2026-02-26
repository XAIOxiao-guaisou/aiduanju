# src/app/services/vision/seedance_agent.py
import asyncio
import os
import json
from pathlib import Path
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import logging

logger = logging.getLogger(__name__)

class SeedanceVisualAgent:
    def __init__(self, user_data_dir="./browser_session/default", headless=True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        
        os.makedirs(user_data_dir, exist_ok=True)
        self.session_file = Path(user_data_dir) / "volcengine_session.json"
        
    async def launch(self):
        """Adapter method for app.py to initialize browser"""
        await self.init_browser()
        
    async def init_browser(self):
        """Initializes Playwright with Stealth to evade Volcengine's anti-bot mechanisms."""
        logger.info("Initializing Volcengine (Seedance) Playwright browser...")
        self.playwright = await async_playwright().start()
        
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--window-size=1440,900'
            ]
        )
        
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    state = json.load(f)
                self.context = await self.browser.new_context(
                    storage_state=state,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.2277.112 Safari/537.36"
                )
                logger.info("Loaded previous Volcengine session.")
            except Exception as e:
                logger.warning(f"Failed to load volcengine session: {e}. Starting fresh.")
                self.context = await self.browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.2277.112 Safari/537.36"
                )
        else:
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.2277.112 Safari/537.36"
            )
            logger.info("Started new Volcengine session (Login required later).")
            
        self.page = await self.context.new_page()
        
        # 注入轻量级的本地反指纹/风控伪装代码，不依赖容易导致React崩溃的 Stealth 完整插件
        stealth_js = """
        // 1. 隐藏 webdriver 标识
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        
        // 2. 伪造 Chrome 独有属性 (headless浏览器经常缺失)
        if (!window.chrome) {
            window.chrome = { runtime: {} };
        }
        
        // 3. 伪装插件长度 (表明这不是一个空的无头浏览器)
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        
        // 4. 修改语言，使其看起来像真实的国内用户的浏览器
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US', 'en'] });
        
        // 5. 绕过通知权限检查
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = parameters => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        """
        await self.page.add_init_script(stealth_js)
        # stealth_async removed to prevent UI rendering crashes on Kuaishou/ByteDance sites
        
    async def login_only(self, timeout_minutes=3):
        """单纯打开网页并在可能的情况下自动呼出登录框"""
        if not self.page:
            await self.init_browser()
            
        try:
            print(f"🔑 [Seedance] 已为您打开火山引擎官网。请在弹出的浏览器中完成登录...")
            target_url = "https://console.volcengine.com/ark/region:ark+cn-beijing/experience/vision?modelId=doubao-seedance-2-0-260128&tab=GenVideo"
            await self.page.goto(target_url)
            
            # 尝试自动点击登录按钮
            try:
                await self.page.wait_for_timeout(3000)
                # 寻找名为“登录”的按钮或文本
                login_btn = self.page.locator('text="登录"').first
                if await login_btn.is_visible():
                    await login_btn.click()
                    print("✨ [Seedance] 已自动点击【登录】，请扫码或输入验证码！")
            except Exception as e:
                pass
            
            # 轮询检测是否登录成功 (等待能看到火山引擎控制台特有的特定元素)
            for _ in range(timeout_minutes * 60 // 2):
                if await self.page.locator('.ProseMirror, textarea').count() > 0:
                    print("✅ [Seedance] 检测到登录成功！")
                    
                    # 尝试保存当前会话
                    state = await self.context.storage_state()
                    with open(self.session_file, 'w') as f:
                        json.dump(state, f)
                    print(f"✅ [Seedance] Session 已保存到 {self.session_file}")
                    
                    overlay_js = """
                    const div = document.createElement('div');
                    div.innerHTML = '<h2>✅ 登录成功！凭证已永久保存</h2><p>本弹窗将在 3 秒后安全关闭...</p><p>🚀 您现在可以回到后台启动视频生成任务了！</p>';
                    div.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#22c55e;color:white;padding:40px;border-radius:12px;z-index:999999;box-shadow:0 20px 40px rgba(0,0,0,0.4);text-align:center;font-family:sans-serif;font-size:22px;';
                    document.body.appendChild(div);
                    """
                    await self.page.evaluate(overlay_js)
                    await asyncio.sleep(4)
                    return
                await asyncio.sleep(2)

            print("✅ [Seedance] 登录监控窗口准备按超时关闭，Session 已自动尝试保存。")
            state = await self.context.storage_state()
            with open(self.session_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            print(f"❌ [Seedance] 登录过程异常: {e}")
        finally:
            await self.close()

    async def smart_click(self, selector: str, label: str = "元素", timeout: int = 3000):
        """
        混合定位：尝试获取 DOM 元素的边界框，然后模拟真人鼠标移动到中心点并带随机偏移点击。
        这样即使 UI 存在一定程度的覆盖或重叠，只要坐标在视口内通常也能触发。
        """
        import random
        try:
            element = self.page.locator(selector).last
            if await element.is_visible(timeout=timeout):
                box = await element.bounding_box()
                if box:
                    # 模拟真人移动到中心点并带随机偏移
                    x = box['x'] + box['width'] / 2 + random.randint(-5, 5)
                    y = box['y'] + box['height'] / 2 + random.randint(-5, 5)
                    logger.info(f"SmartClick: 模拟点击 {label} 坐标 ({x:.1f}, {y:.1f})")
                    await self.page.mouse.move(x, y, steps=10)
                    await self.page.mouse.down()
                    await self.page.wait_for_timeout(random.randint(50, 150))
                    await self.page.mouse.up()
                    return True
        except Exception as e:
            logger.warning(f"SmartClick: 视觉坐标点击 [{label}] 失败: {e}")
            
        # Fallback to standard Playwright click if bounding box fails or element isn't strictly visible but might be clickable
        try:
            element = self.page.locator(selector).last
            await element.click(force=True, timeout=timeout)
            logger.info(f"SmartClick: 回退至强制 DOM 点击 [{label}] 成功")
            return True
        except Exception:
            return False
            
    async def submit_video_generation(self, prompt: str):
        """
        STAGE 1: Volcengine Submission.
        Navigates to the Doubao-Seedance-2.0 console, types the prompt, and initiates generation.
        """
        if not self.page:
            await self.init_browser()
            
        logger.info(f"Navigating to Volcengine Console... Submitting prompt: {prompt[:20]}...")
        # Direct URL to the Volcengine Doubao-Seedance video generation model
        target_url = "https://console.volcengine.com/ark/region:ark+cn-beijing/experience/vision?modelId=doubao-seedance-2-0-260128&tab=GenVideo"
        await self.page.goto(target_url, wait_until="domcontentloaded") 

        await self.page.wait_for_timeout(3000)
        
        try:
            logger.info("Configuring Video Parameters (16:9, 15s)...")
            try:
                # 1. Click parameter settings toolbar
                settings_toolbar = self.page.locator('text="5 秒"').last
                if await settings_toolbar.is_visible():
                    await settings_toolbar.click(force=True)
                else:
                    settings_toolbar = self.page.locator('div, span, button', has_text="智能比例").last
                    if await settings_toolbar.is_visible():
                        await settings_toolbar.click(force=True)
                
                await self.page.wait_for_timeout(1500)
                
                # 2. Set Aspect Ratio 16:9
                ratio_16_9 = self.page.locator('text="16:9"').last
                if await ratio_16_9.is_visible():
                    await ratio_16_9.click(force=True)
                    
                await self.page.wait_for_timeout(1000)
                
                # 3. Set Duration to 15s
                btn_15s = self.page.locator('text="15 秒"').last
                if await btn_15s.is_visible(timeout=1000):
                    await btn_15s.click(force=True)
                else:
                    btn_15s = self.page.locator('text="15s"').last
                    if await btn_15s.is_visible(timeout=1000):
                        await btn_15s.click(force=True)
                    else:
                        inputs = await self.page.get_by_role("spinbutton").all()
                        for inp in inputs:
                            val = await inp.input_value()
                            if val in ["5", "10", "15"]:
                                await inp.fill("15")
                                break
                        
                await self.page.wait_for_timeout(1000)
                
                # Close popup by clicking outside
                await self.page.mouse.click(10, 10)
                await self.page.wait_for_timeout(1000)
                
            except Exception as param_err:
                logger.warning(f"Failed to set extra parameters: {param_err}")

            # Step 1: DOM Localization for Volcengine's specific textarea
            logger.info("Attempting DOM-based localization in Volcengine...")
            
            # Look for the characteristic ProseMirror rich text editor in the Volcengine dashboard
            input_box = self.page.locator('div.ProseMirror').last
            await input_box.wait_for(state="visible", timeout=45000)
            await input_box.click()
                
            logger.info("Typing prompt into Volcengine...")
            # Clear existing text just in case
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
            
            await self.page.keyboard.type(prompt, delay=50) 
            await self.page.wait_for_timeout(1000)
            
            logger.info("Clicking the '生成' button...")
            
            # Use the new smart click fallback logic
            success = await self.smart_click('button.arco-btn-primary:has-text("生成")', "主生成按钮", timeout=3000)
            if not success:
                success = await self.smart_click('button:has-text("生成")', "备用生成按钮", timeout=3000)
                
            if not success:
                logger.warning("Failed to find or click primary button '生成' via UI")
                # Fallback to pressing Control+Enter which is common in professional dashboards
                logger.info("Fallback: Pressing Control+Enter...")
                await self.page.keyboard.press("Control+Enter")
            
            # Brief wait to ensure the request is triggered in their React state before closing
            await self.page.wait_for_timeout(5000)
            
            return {"status": "success", "message": "Volcengine Video queued. Disconnecting to prevent session timeout."}
            
        except Exception as e:
            logger.error(f"Volcengine Visual automation failed: {e}")
            raise

    async def check_and_download_video(self):
        """
        STAGE 2: Volcengine Polling & Extraction.
        Connects to the console, checks the history tab/pane. If the latest video is done, downloads it.
        """
        if not self.page:
            await self.init_browser()
            
        logger.info("Opening Volcengine to check latest video status...")
        target_url = "https://console.volcengine.com/ark/region:ark+cn-beijing/experience/vision?modelId=doubao-seedance-2-0-260128&tab=GenVideo"
        if self.page.url != target_url:
            await self.page.goto(target_url, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(5000)
        
        try:
            logger.info("Scanning for Volcengine generated videos...")
            
            # 1. Check if the generic loading video is still present on screen
            loading_vid = self.page.locator('video[src*="vision_loading.mp4"]')
            if await loading_vid.count() > 0:
                logger.info("Volcengine loading placeholder detected. Video is still generating...")
                return {"status": "generating", "message": "Video still generating."}
            
            # 2. Extract the true latest video
            video_locator = self.page.locator('video').first
            
            is_visible = await video_locator.is_visible(timeout=5000)
            if not is_visible:
                logger.info("Video not ready yet in Volcengine. Still generating...")
                return {"status": "generating", "message": "Video still generating."}
                
            blob_url = await video_locator.get_attribute("src")
            if blob_url and "vision_loading.mp4" not in blob_url:
                logger.info(f"Video is READY in Volcengine! Extracting from blob: {blob_url}")
                
                js_fetch_blob = """
                async (blobUrl) => {
                    const response = await fetch(blobUrl);
                    const blob = await response.blob();
                    return new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result.split(',')[1]);
                        reader.onerror = reject;
                        reader.readAsDataURL(blob);
                    });
                }
                """
                base64_data = await self.page.evaluate(js_fetch_blob, blob_url)
                
                import base64
                import time
                video_data = base64.b64decode(base64_data)
                
                output_dir = Path("outputs")
                output_dir.mkdir(exist_ok=True)
                
                filename = f"volcano_vid_{int(time.time())}.mp4"
                filepath = output_dir / filename
                with open(filepath, "wb") as f:
                    f.write(video_data)
                    
                logger.info(f"✅ Volcengine Video successfully saved to {filepath.absolute()}")
                return {
                    "status": "success", 
                    "message": "Volcengine Video downloaded.", 
                    "file_path": str(filepath.absolute())
                }
            else:
                return {"status": "generating", "message": "Video tag found but SRC is empty."}

        except Exception as e:
            logger.error(f"Error checking Volcengine video status: {e}")
            return {"status": "error", "message": str(e)}

    async def close(self):
        """Cleans up browser resources."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def submit_task(self, prompt: str):
        """Adapter method to match VideoEngine interface"""
        res = await self.submit_video_generation(prompt)
        return res.get("status") == "success"

    async def monitor_and_download(self, output_dir="./output"):
        """Adapter method to poll for results like VideoEngine"""
        for _ in range(360): # poll for up to 60 minutes
            res = await self.check_and_download_video()
            if res.get("status") == "success":
                return res.get("file_path")
            elif res.get("status") == "error":
                return None
            await asyncio.sleep(10)
        return None
