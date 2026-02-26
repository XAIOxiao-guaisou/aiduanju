from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import os
import sys
import random
import asyncio
import uvicorn
import os
import sys

# 导入核心模块 (将父目录加入路径)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from seedance_agent import SeedanceVisualAgent as VideoEngine
from core.account_manager import AccountManager
from core.deepseek_feishu_integration import process_novel_to_feishu
import logging

# 日志配置
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
LOG_FILE = os.path.join(LOG_DIR, "app.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(app_dir, "templates")

if not os.path.exists(template_dir):
    print(f"❌ [错误] 找不到模板目录: {template_dir}")
    sys.exit(1)

app = FastAPI()
templates = Jinja2Templates(directory=template_dir)
account_mgr = AccountManager(base_dir=os.path.join(os.path.dirname(app_dir), "browser_session"))

class TaskRequest(BaseModel):
    account: str
    prompt: str

class NovelSubmission(BaseModel):
    account: str
    content: str

from fastapi.responses import Response

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")

@app.get("/")
async def read_root(request: Request):
    accounts = account_mgr.get_accounts()
    return templates.TemplateResponse("index.html", {"request": request, "accounts": accounts})

async def run_pipeline_task(account: str, prompts: list):
    session_path = account_mgr.get_session_path(account)
    # 常规任务队列现在使用无头模式静默执行
    engine = VideoEngine(user_data_dir=session_path, headless=True)
    try:
        await engine.launch()
        
        # 简单检查一下是否有可能没登录 (可选)
        # if not await engine.is_logged_in():
        #     logger.warning(f"账号 {account} 可能未登录，尝试越过但可能失败。")
            
        for idx, prompt in enumerate(prompts):
            if not prompt.strip():
                continue
            logger.info(f"=== 开始执行队列任务 {idx+1}/{len(prompts)} ===")
            # 步骤 1: 提交
            success = await engine.submit_task(prompt.strip())
            if success:
                # 步骤 2: 监控下载
                download_path = await engine.monitor_and_download()
                if download_path:
                    logger.info(f"任务 {idx+1} 成功，文件保存于: {download_path}")
                else:
                    logger.error(f"任务 {idx+1} 下载阶段失败。")
            
            # 模拟批处理人类休息时间
            if idx < len(prompts) - 1:
                wait_time = random.uniform(10, 20)
                logger.info(f"冷却休息 {wait_time:.1f} 秒，防封控...")
                await asyncio.sleep(wait_time)
                
        logger.info("🎉 当前账号该批次所有任务处理完毕！")
    except Exception as e:
        logger.error(f"Task Error: {e}")
    finally:
        await engine.close()

@app.get("/api/logs")
async def get_logs(lines: int = 50):
    """读取最后的日志内容给前端展示"""
    try:
        if not os.path.exists(LOG_FILE):
            return {"logs": ["暂无日志记录"]}
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return {"logs": [line.strip() for line in all_lines[-lines:]]}
    except Exception as e:
        return {"logs": [f"无法读取日志: {e}"]}

@app.get("/api/outputs")
async def get_outputs():
    """获取输出目录下的所有文件并按时间倒序排列"""
    # 兼容两种输出目录名配置 (Kling原本是 output, Volcengine用了 outputs)
    output_dirs = [os.path.join(app_dir, "..", "output"), os.path.join(app_dir, "..", "outputs")]
    files_info = []
    
    for d in output_dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith(".mp4"):
                    filepath = os.path.join(d, f)
                    try:
                        mtime = os.path.getmtime(filepath)
                        size = os.path.getsize(filepath)
                        # 为了给前端展示相对路径，去绝对路径
                        files_info.append({
                            "name": f,
                            "path": os.path.abspath(filepath),
                            "time": mtime,
                            "size": round(size / (1024 * 1024), 2) # MB
                        })
                    except:
                        pass
                        
    # 按照修改时间降序排列
    files_info.sort(key=lambda x: x["time"], reverse=True)
    
    # 格式化时间字符串
    import datetime
    for item in files_info:
        item["time_str"] = datetime.datetime.fromtimestamp(item["time"]).strftime('%m-%d %H:%M:%S')
        
    return {"files": files_info}

async def run_login_task(account: str):
    session_path = account_mgr.get_session_path(account)
    logger.info(f"正在为账号 {account} 启动独立登录窗口...")
    # 强制弹出有头浏览器让用户扫码
    engine = VideoEngine(user_data_dir=session_path, headless=False)
    try:
        await engine.launch()
        # 给用户 3 分钟扫码时间
        await engine.login_only(timeout_minutes=3)
        logger.info(f"账号 {account} 独立登录流程结束。")
    except Exception as e:
        logger.error(f"Login Task Error: {e}")
    finally:
        await engine.close()

@app.post("/api/login")
async def login_account(task: TaskRequest, background_tasks: BackgroundTasks):
    """独立触发登录窗口 (只用到 account 字段)"""
    background_tasks.add_task(run_login_task, task.account)
    return {"status": "ok", "message": f"已触发登录窗口，请在弹出的浏览器中扫码！"}

@app.post("/api/run")
async def run_task(task: TaskRequest, background_tasks: BackgroundTasks):
    prompt_list = [p for p in task.prompt.split('\n') if p.strip()]
    if not prompt_list:
        return {"status": "error", "message": "提示词不能为空"}
        
    background_tasks.add_task(run_pipeline_task, task.account, prompt_list)
    logger.info(f"已接收 {len(prompt_list)} 个任务，加入后台队列 (账号: {task.account})")
    return {"status": "ok", "message": f"成功接收 {len(prompt_list)} 个视频生成任务"}

@app.post("/api/upload_novel")
async def upload_novel(req: NovelSubmission, background_tasks: BackgroundTasks):
    text = req.content.strip()
    account = req.account.strip()
    if not text:
        return {"status": "error", "message": "文章内容为空！"}
    
    async def process_and_queue():
        try:
            # use asyncio.to_thread because process_novel_to_feishu has blocking requests and sleeps
            res = await asyncio.to_thread(process_novel_to_feishu, text)
            if res.get("status") == "success" and res.get("prompts"):
                prompts = res.get("prompts", [])
                logger.info(f"✨ 拆解完成，获取到 {len(prompts)} 个分镜，准备自动入列视频生成！")
                await run_pipeline_task(account, prompts)
            else:
                logger.error("❌ 拆解失败或没有获取到分镜。")
        except Exception as e:
            logger.error(f"DeepSeek 队列处理发生异常: {e}")

    background_tasks.add_task(process_and_queue)
    logger.info(f"📚 已在后台开启【闪电解文】线程，文本长度：{len(text)}")
    return {"status": "ok", "message": "文章已交由 DeepSeek AI 处理并在成功后自动触发视频生成！"}

if __name__ == "__main__":
    try:
        logger.info("--- [系统状态] ---")
        logger.info(f"工作目录: {os.getcwd()}")
        logger.info(f"账号目录: {account_mgr.base_dir}")
        logger.info(f"当前账号: {account_mgr.get_accounts()}")
        logger.info("-----------------")
        uvicorn.run(app, host="127.0.0.1", port=8000)
    except Exception as e:
        logger.critical(f"🔥 [致命错误] Web 服务启动失败: {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")
