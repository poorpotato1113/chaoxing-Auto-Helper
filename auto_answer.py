import base64
import requests
import time
import re
import os
from playwright.sync_api import sync_playwright

# =====================================================================
# ⚠️ 必看：运行前请配置以下两项信息！
# =====================================================================
# 1. 请前往智谱 AI (https://open.bigmodel.cn/) 注册并申请免费的 API Key
API_KEY = "在此填入你的API_KEY" 

# 2. 请复制学习通课程页面的长链接，粘贴在下面双引号内
TARGET_URL = "在此填入你的课程链接"
# =====================================================================

API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions" 
MODEL_NAME = "glm-5.3-flash" 

# 获取当前脚本所在的绝对路径（核心优化）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def get_answer_from_vision_ai(image_path):
    base64_img = image_to_base64(image_path)
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = """你是一位知识渊博的大学军事理论教授。请仔细阅读图片中的题目。
如果是单选题或判断题，请直接告诉我正确的选项字母（如 A 或 B）。
如果是多选题，请用逗号分隔告诉我所有正确选项字母（如 A,C）。
不要输出任何解释，只输出字母。"""
    data = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]
            }
        ],
        "temperature": 0.1
    }
    try:
        response = requests.post(API_URL, headers=headers, json=data)
        answer = response.json()['choices'][0]['message']['content'].strip()
        return re.sub(r'[^A-D]', '', answer)
    except Exception as e:
        return None

def process_video(page):
    print("🎬 正在寻找视频播放按钮...")
    clicked_play = False
    
    for f in page.frames:
        try:
            play_btn = f.locator(".vjs-big-play-button")
            if play_btn.count() > 0:
                play_btn.first.click()
                print("✅ 成功点击播放按钮！开始监控进度...")
                clicked_play = True
                break
        except:
            continue
            
    if not clicked_play:
        print("⚠️ 没找到常规播放按钮，尝试点击视频区域中央...")
        page.mouse.click(640, 450)
        
    time.sleep(5) 
    
    target_frame = None
    for f in page.frames:
        try:
            if f.locator("video").count() > 0:
                target_frame = f
                break
        except:
            continue
            
    if not target_frame:
        print("⚠️ 没找到视频框架，可能这节没视频，直接跳过...")
        return True 
        
    while True:
        page.mouse.move(500, 500) 
        time.sleep(1)
        page.mouse.move(502, 502)
        
        js_get_progress = """
        () => {
            let v = document.querySelector('video');
            if (!v) return {p: -1, ended: false};
            v.muted = true; 
            if (v.paused && !v.ended) { v.play(); } 
            let p = v.duration === 0 ? 0 : (v.currentTime / v.duration) * 100;
            return {p: p, ended: v.ended};
        }
        """
        try:
            res = target_frame.evaluate(js_get_progress)
            progress = res['p']
            is_ended = res['ended']
            
            if progress == -1: break
            print(f"📺 当前视频进度: {progress:.1f}%")
            
            if progress >= 99.5 or is_ended:
                print("🎉 视频已完整播放完毕！")
                print("⏳ 正在等待 15 秒，让超星后台同步任务点数据...")
                time.sleep(15) 
                return True
        except Exception:
            break
        time.sleep(10) 
    return True

def process_quiz(page):
    print("📝 正在进入答题模式...")
    try:
        page.locator("text='章节测验'").first.click(timeout=5000)
        print("✅ 已点击章节测验标签。")
    except:
        print("⚠️ 没找到测验标签，可能已经在答题页了。")

    print("⏳ 正在等待题目框架加载（最多等 30 秒）...")
    target_frame = None
    for i in range(15):
        for f in page.frames:
            try:
                if f.locator(".TiMu").count() > 0:
                    target_frame = f
                    break
            except: continue
        if target_frame:
            print("✅ 成功找到题目框架！")
            break
        time.sleep(2) 
        
    if not target_frame:
        print("❌ 等待超时，找不到题目框架，跳过答题。")
        return

    screenshot_dir = os.path.join(SCRIPT_DIR, "temp_screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)

    processed_questions = set() 
    last_scroll_height = 0
    
    while True:
        try:
            if not target_frame:
                break
            questions = target_frame.locator(".TiMu").all()
        except Exception:
            print("⚠️ 题目框架已失效或网页刷新。")
            break
            
        print(f"📄 当前页面检测到 {len(questions)} 道题目。")
        
        for q in questions:
            try:
                q_text = q.inner_text()[:30].replace("\n", "") 
                if q_text in processed_questions:
                    continue 
                
                print(f"\n▶️ 正在做新题: {q_text}...")
                q.scroll_into_view_if_needed()
                time.sleep(1)
                
                img_path = os.path.join(screenshot_dir, "current_question.png")
                q.screenshot(path=img_path)
                
                print("📡 正在问 AI...")
                answer = get_answer_from_vision_ai(img_path) 
                print(f"🤖 AI 给出的答案: 【 {answer} 】")
                
                if answer:
                    option_elements = q.locator("label, .answerBg, .Zy_Ul li").all()
                    valid_options = []
                    for el in option_elements:
                        if el.is_visible():
                            b = el.bounding_box()
                            if b: valid_options.append((b['y'], el))
                    
                    valid_options.sort(key=lambda x: x[0])
                    sorted_els = [x[1] for x in valid_options]
                    
                    for char in answer:
                        idx = ord(char) - 65
                        if idx < len(sorted_els):
                            try:
                                sorted_els[idx].click(force=True, timeout=3000)
                                print(f"✅ 成功点击选项 {char}")
                                time.sleep(0.5)
                            except: pass
                
                processed_questions.add(q_text)
                time.sleep(1)
                
            except Exception:
                pass
        
        print("\n⬇️ 正在向下滚动，寻找更多题目...")
        try:
            page.mouse.wheel(0, 500)
            time.sleep(3)
            current_scroll_height = page.evaluate("window.scrollY")
            if current_scroll_height == last_scroll_height:
                print("\n🛑 已经滚动到底部，答题完毕！")
                break
            last_scroll_height = current_scroll_height
        except Exception:
            break

def submit_and_next(page):
    print("🚀 正在尝试交卷（物理点击版）...")
    time.sleep(2)
    
    submit_success = False
    
    for f in page.frames:
        try:
            btn = f.locator("button:has-text('提交'), input[type='button'][value*='提交']").last
            if btn.count() == 0:
                btn = f.locator("text='提交'").last
                
            if btn.count() > 0 and btn.is_visible():
                btn.scroll_into_view_if_needed()
                time.sleep(1)
                box = btn.bounding_box()
                if box:
                    x = box['x'] + box['width'] / 2
                    y = box['y'] + box['height'] / 2
                    page.mouse.click(x, y)
                    print("✅ 物理点击了底部的提交按钮。")
                    submit_success = True
                    break
        except: pass
                
    if not submit_success:
        print("❌ 找不到底部提交按钮，跳过。")
        return False 
        
    print("⏳ 等待弹窗出现...")
    time.sleep(3) 
    
    print("🔍 正在寻找二次确认弹窗的按钮...")
    confirm_success = False
    for f in page.frames:
        try:
            btns = f.locator(".layui-layer-btn0, button:has-text('提交'), a:has-text('提交')").all()
            for btn in reversed(btns): 
                if btn.is_visible():
                    box = btn.bounding_box()
                    if box:
                        cx = box['x'] + box['width'] / 2
                        cy = box['y'] + box['height'] / 2
                        page.mouse.click(cx, cy)
                        print("✅ 物理点击了弹窗里的【提交】。")
                        confirm_success = True
                        time.sleep(3)
                        break
            if confirm_success:
                break
        except: pass

    if not confirm_success:
        print("⚠️ 物理点击没找到，尝试 JS 爆破弹窗...")
        for f in page.frames:
            try:
                js_code = """
                () => {
                    let btns = Array.from(document.querySelectorAll('.layui-layer-btn0, button, a'));
                    for (let i = btns.length - 1; i >= 0; i--) {
                        let el = btns[i];
                        if (el.innerText && el.innerText.includes('提交') && el.offsetParent !== null) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }
                """
                if f.evaluate(js_code):
                    print("✅ JS 爆破成功，已处理弹窗。")
                    break
            except: pass
            
    print("⏳ 等待成绩页加载...")
    time.sleep(6) 
    
    print("🔍 正在死皮赖脸寻找【下一节】按钮...")
    
    try:
        page.mouse.wheel(0, 800) 
        time.sleep(2)
    except: pass

    for attempt in range(5):
        print(f"  -> 第 {attempt + 1} 次寻找 '下一节'...")
        
        for f in page.frames:
            try:
                js_click_next = """
                () => {
                    let els = Array.from(document.querySelectorAll('a, button, div, span'));
                    for (let el of els) {
                        if (el.innerText && el.innerText.trim() === '下一节' && el.offsetParent !== null) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }
                """
                if f.evaluate(js_click_next):
                    print("✅ JS 爆破成功，已点击【下一节】！")
                    time.sleep(5)
                    return True
            except: pass
            
            try:
                next_btn = f.locator("text='下一节'").last 
                if next_btn.count() > 0:
                    box = next_btn.bounding_box()
                    if box:
                        nx = box['x'] + box['width'] / 2
                        ny = box['y'] + box['height'] / 2
                        page.mouse.click(nx, ny)
                        print("✅ 物理坐标点击【下一节】成功！")
                        time.sleep(5) 
                        return True
            except: pass
            
        time.sleep(3) 

    print("🛑 试了5次，真没找到下一节按钮，可能这门课已经刷完了！")
    return False

def run():
    with sync_playwright() as p:
        print("正在启动 Edge 浏览器...")
        
        profile_path = os.path.join(SCRIPT_DIR, "my_edge_profile")
        
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_path, 
            headless=False,
            channel="msedge", 
            viewport={"width": 1280, "height": 900}
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        page.add_init_script("""
            window.onblur = null;
            window.onfocus = function() {};
            Object.defineProperty(document, 'hidden', {value: false, writable: false});
            Object.defineProperty(document, 'visibilityState', {value: 'visible', writable: false});
        """)

        print("正在打开网页...")
        page.goto(TARGET_URL)
        
        print("\n⏳ 请在 30 秒内完成登录，并停留在起始章节。")
        time.sleep(30)
        
        while True:
            print("\n=============================================")
            print("🔄 开始新章节循环...")
            
            try:
                video_done = process_video(page)
                if video_done:
                    time.sleep(3) 
                    process_quiz(page)
                
                success = submit_and_next(page)
                
                if not success:
                    print("🎉 运行结束或遇到无法处理的页面。程序自动停止。")
                    break
            except Exception as e:
                print(f"⚠️ 循环中出现意外错误: {e}")
                print("尝试继续下一轮...")
                time.sleep(5)

        print("\n所有任务完成！按 Ctrl+C 退出程序。")
        while True:
            time.sleep(10)

if __name__ == "__main__":
    run()