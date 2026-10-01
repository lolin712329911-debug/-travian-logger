#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【舊版】原 travian_parser.TravianClient：requests 登录框架示例（login 未实作，Actions 不使用）。
用法（在倉庫根目錄）：PYTHONPATH=. python -c "from tools.legacy.travian_client import TravianClient"
"""
from travian_parser import VillageOverview, parse_village_page


class TravianClient:
    """
    简单封装：用 requests.Session 登录并抓取 dorf2.php。
    仅作为个人账号只读查看用途的示例，请自行确认符合目标服务器的使用条款。
    """

    def __init__(self, base_url: str):
        import requests
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; PersonalVillageBot/1.0)"
        })

    def login(self, username: str, password: str):
        """
        注意：Travian 官服的登录接口可能是 POST /api/v1/auth/login 之类的 JSON 接口，
        并可能带 CSRF token / 验证码，需要你用浏览器开发者工具抓包确认真实的登录请求
        （Network 面板里找登录时发出的 POST 请求），再对应改写这里的实现。
        以下仅为占位示例。
        """
        raise NotImplementedError(
            "请根据实际登录接口（抓包获得）填写此方法，"
            "本框架仅提供页面解析部分（parse_village_page）。"
        )

    def get_village_overview(self, village_page: str = "dorf2.php") -> VillageOverview:
        resp = self.session.get(f"{self.base_url}/{village_page}")
        resp.raise_for_status()
        return parse_village_page(resp.text)
