import asyncio
import os
import random
import time
from playwright.async_api import async_playwright

class VideoEngine:
    def __init__(self, user_data_dir, headless=False):
        self.user_data_dir = os.path.abspath(user_data_dir)
        self.headless = headless
        self.target_url = "https://app.klingai.com/text-to-video"

    async def launch(self):
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.2277.112 Safari/537.36",
            args=["--disable-blink-features=AutomationControlled"]
        )
        self.page = await self.context.new_page()
        return self.page

    async def is_logged_in(self):
        """检查是否已登录 (是否存在头像或用户中心元素)"""
        try:
            # 去往首页检查
            if self.page.url != self.target_url:
                await self.page.goto(self.target_url)
            # 可灵通常如果有某某生成记录/头像就算登录成功。此处简单等待通用元素。
            # 这是个简单的 heuristic，实际可能需要观察具体 HTML 结构
            await self.page.wait_for_selector('div[class*="avatar"], img[class*="avatar"], span:has-text("我的")', timeout=5000)
            return True
        except Exception:
            return False

    async def login_only(self, timeout_minutes=3):
        """单纯打开网页并在可能的情况下自动呼出登录框"""
        try:
            print(f"🔑 [Engine] 已为您打开可灵官网。请在弹出的浏览器中手动扫码...")
            await self.page.goto(self.target_url)
            
            # 尝试自动寻找并点击页面上的“登录”按钮，帮用户把二维码弹出来
            try:
                # 匹配“登录/注册”、“登录”等常见文案按钮
                login_btn_selector = 'button:has-text("登录"), div:has-text("登录"), span:has-text("登录")'
                await self.page.wait_for_selector(login_btn_selector, timeout=5000)
                # 点击第一个匹配的
                await self.page.locator(login_btn_selector).first.click()
                print("✨ [Engine] 已自动为您展开登录二维码区，请抓紧时间扫码 (限三分钟)。")
            except Exception:
                print("👀 [Engine] 未能自动定位到登录按钮，请手动在网页右上角点击登录。")

            # 轮询检测是否登录成功
            for _ in range(timeout_minutes * 60 // 2):
                if await self.page.locator('div[class*="avatar"], img[class*="avatar"], span:has-text("我的")').count() > 0:
                    print("✅ [Engine] 检测到登录成功！")
                    overlay_js = """
                    const div = document.createElement('div');
                    div.innerHTML = '<h2>✅ 登录成功！凭证已永久保存</h2><p>本弹窗将在 3 秒后安全关闭...</p><p>🚀 您现在可以回到后台启动批量挂机了！</p>';
                    div.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#22c55e;color:white;padding:40px;border-radius:12px;z-index:999999;box-shadow:0 20px 40px rgba(0,0,0,0.4);text-align:center;font-family:sans-serif;font-size:22px;';
                    document.body.appendChild(div);
                    """
                    await self.page.evaluate(overlay_js)
                    await asyncio.sleep(4)
                    return
                await asyncio.sleep(2)

            print("✅ [Engine] 登录监控窗口准备按超时关闭，Session 已自动保存。")
        except Exception as e:
            print(f"❌ [Engine] 登录过程异常: {e}")

    async def submit_task(self, prompt):
        """提交视频生成任务"""
        try:
            print(f"🚀 [Engine] 正在处理: {prompt}")
            await self.page.goto(self.target_url)
            
            # 定位输入框 (Kling AI 已更换为 tiptap ProseMirror 富文本框)
            input_selector = '.tiptap.ProseMirror, textarea[placeholder*="描述"]'
            await self.page.wait_for_selector(input_selector, timeout=30000)
            
            # 随机延迟模拟人类
            await asyncio.sleep(random.uniform(1, 3))
            # 使用 locator 的 fill，因为可能有多个匹配（例如移动端和PC端两套UI），选可见的或第一个
            await self.page.locator(input_selector).first.fill(prompt)
            
            # 寻找生成按钮
            generate_btn = 'button:has-text("生成"), button:has-text("Generate")'
            await self.page.wait_for_selector(generate_btn)
            await asyncio.sleep(random.uniform(1, 2))
            await self.page.click(generate_btn)
            
            print("✅ [Engine] 任务已提交")
            return True
        except Exception as e:
            print(f"❌ [Engine] 提交任务失败: {e}")
            return False

    async def monitor_and_download(self, output_dir="./output"):
        """监控生成进度并下载结果"""
        import time
        # 确保输出目录存在
        output_dir = os.path.abspath(output_dir)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        try:
            download_btn_selector = 'button[class*="download"], div[class*="download"], [class*="icon-download"]'
            print("⏳ [Engine] 正在等待视频生成结束 (当前排队较慢，已将超时放宽至 60 分钟)...")
            
            # 设置极长超时 60分钟 (3600000ms)，以应对长时间排队
            await self.page.wait_for_selector(download_btn_selector, timeout=3600000)
            
            print("⏳ [Engine] 生成完毕，正在触发下载...")
            # 捕获下载事件并点击下载按钮
            async with self.page.expect_download(timeout=60000) as download_info:
                # 随机延迟，模拟真实点击
                await asyncio.sleep(random.uniform(1, 2))
                # 点击第一个匹配的下载按钮
                await self.page.click(download_btn_selector)
            
            download = await download_info.value
            
            # 生成文件名并保存
            filename = f"video_{int(time.time())}.mp4"
            filepath = os.path.join(output_dir, filename)
            await download.save_as(filepath)
            
            print(f"🎊 [Engine] 视频保存成功: {filepath}")
            return filepath
        except Exception as e:
            print(f"❌ [Engine] 监控下载失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def close(self):
        if hasattr(self, 'context'):
            await self.context.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
