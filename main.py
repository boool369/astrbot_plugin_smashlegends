import logging
import os
import re
import time
import traceback
import json
from datetime import datetime

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# 插件元信息
@register(
    name="astrbot_plugin_smashlegends",
    author="boool369",
    desc="smashlegends最新帖子查看，最新优惠码查看与发送。",
    version="v1.0",
    repo="https://github.com/boool369/astrbot_plugin_smashlegends"
)
class SmashLegendsPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.logger = logging.getLogger(__name__)
        self.base_path = os.path.join(os.path.dirname(__file__), "plugins_data", "astrbot_plugin_smashlegends")
        self.data_path = os.path.join(self.base_path, "data")
        self.record_file = os.path.join(self.data_path, "latest_url.json")
        os.makedirs(self.data_path, exist_ok=True)

    async def initialize(self):
        self.logger.info("[SL插件] 初始化成功")

    def get_driver(self):
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=zh-CN")
        options.add_argument("--disable-blink-features=AutomationControlled")
        driver = webdriver.Chrome(options=options)
        return driver

    def get_latest_post_info(self, driver):
        driver.get("https://smashlegends.com/category/update/")
        time.sleep(3)
        post = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/main/div/section/div/div[1]/article[1]")
        link = post.find_element(By.XPATH, "./div[2]/h2/a").get_attribute("href")
        title = post.find_element(By.XPATH, "./div[2]/h2/a").text.strip()
        img = post.find_element(By.XPATH, "./div[1]/ul/li/div/a/img").get_attribute("src")
        return link, title, img

    def extract_coupon_code(self, html):
        match = re.search(r"Coupon Code:\s*</?span[^>]*>\s*<b>(\w+)</b>", html)
        if match:
            return match.group(1)
        match = re.search(r"Coupon Code:\s*([A-Za-z0-9]+)", html)
        if match:
            return match.group(1)
        return None

    def save_latest_data(self, url, title, coupon):
        data = {
            "url": url,
            "title": title,
            "coupon": coupon,
            "timestamp": datetime.now().isoformat()
        }
        with open(self.record_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.logger.info(f"[SL插件] 保存最新数据: {url}, 优惠码: {coupon}")

    def load_latest_url(self):
        if os.path.exists(self.record_file):
            with open(self.record_file, "r", encoding="utf-8") as f:
                try:
                    return json.load(f).get("url")
                except json.JSONDecodeError:
                    return None
        return None

    @filter.command("sl更新通告")
    async def sl_update(self, event: AstrMessageEvent):
        '''获取最新 SmashLegends 帖子和优惠码'''
        yield event.plain_result("🔍 正在获取最新 SmashLegends 更新...")
        try:
            driver = self.get_driver()
            try:
                link, title, img_url = self.get_latest_post_info(driver)
                last_url = self.load_latest_url()
                is_new = (link != last_url)
                self.logger.info(f"[SL插件] 最新链接: {link}, 是否新内容: {is_new}")

                yield event.image_result(img_url)
                yield event.plain_result(f"📢 最新帖子标题：{title}\n🔗 链接：{link}")
                yield event.plain_result("🎁 正在寻找优惠码...")

                driver.get(link)
                time.sleep(5)
                coupon = self.extract_coupon_code(driver.page_source)

                if coupon:
                    yield event.plain_result(f"🎉 找到优惠码：{coupon}")
                else:
                    yield event.plain_result("❌ 未找到优惠码")

                self.save_latest_data(link, title, coupon)

            finally:
                driver.quit()
        except Exception as e:
            error_msg = f"[SL插件] 处理更新出错: {str(e)}\n{traceback.format_exc()}"
            self.logger.error(error_msg)
            yield event.plain_result("⚠️ 获取更新出错，请查看日志")

    async def terminate(self):
        self.logger.info("[SL插件] 插件已卸载")
