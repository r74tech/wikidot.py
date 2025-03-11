"""
Wikidotフォーラムのスレッドを扱うモジュール

このモジュールは、Wikidotサイトのフォーラムスレッドに関連するクラスや機能を提供する。
スレッドの情報取得や閲覧などの操作が可能。
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from bs4 import BeautifulSoup

from ..common.exceptions import NoElementException
from ..util.parser import odate as odate_parser
from ..util.parser import user as user_parser

if TYPE_CHECKING:
    from .forum_category import ForumCategory
    from .site import Site
    from .user import AbstractUser


class ForumThreadCollection(list["ForumThread"]):
    """
    フォーラムスレッドのコレクションを表すクラス
    
    複数のフォーラムスレッドを格納し、一括して操作するためのリスト拡張クラス。
    特定のカテゴリ内のスレッド一覧を取得する機能などを提供する。
    """
    
    def __init__(
        self,
        site: Optional["Site"] = None,
        threads: Optional[list["ForumThread"]] = None,
    ):
        """
        初期化メソッド
        
        Parameters
        ----------
        site : Site | None, default None
            スレッドが属するサイト。Noneの場合は最初のスレッドから推測する
        threads : list[ForumThread] | None, default None
            格納するスレッドのリスト
        """
        super().__init__(threads or [])

        if site is not None:
            self.site = site
        else:
            self.site = self[0].site

    def __iter__(self) -> Iterator["ForumThread"]:
        """
        コレクション内のスレッドを順に返すイテレータ
        
        Returns
        -------
        Iterator[ForumThread]
            スレッドオブジェクトのイテレータ
        """
        return super().__iter__()

    @staticmethod
    def _parse(
        site: "Site", html: BeautifulSoup, category: Optional["ForumCategory"] = None
    ) -> list["ForumThread"]:
        """
        フォーラムページのHTMLからスレッド情報を抽出する内部メソッド
        
        HTMLからスレッドのタイトル、説明、作成者、作成日時などの情報を抽出し、
        ForumThreadオブジェクトのリストを生成する。
        
        Parameters
        ----------
        site : Site
            スレッドが属するサイト
        html : BeautifulSoup
            パース対象のHTML
        category : ForumCategory | None, default None
            スレッドが属するカテゴリ（オプション）
            
        Returns
        -------
        list[ForumThread]
            抽出されたスレッドオブジェクトのリスト
            
        Raises
        ------
        NoElementException
            必要なHTML要素が見つからない場合
        """
        threads = []
        for info in html.select("table.table tr.head~tr"):
            title = info.select_one("div.title a")
            if title is None:
                raise NoElementException("Title element is not found.")

            title_href = title.get("href")
            if title_href is None:
                raise NoElementException("Title href is not found.")

            thread_id_match = re.search(r"t-(\d+)", str(title_href))
            if thread_id_match is None:
                raise NoElementException("Thread ID is not found.")

            thread_id = int(thread_id_match.group(1))

            description_elem = info.select_one("div.description")
            user_elem = info.select_one("span.printuser")
            odate_elem = info.select_one("span.odate")
            posts_count_elem = info.select_one("td.posts")

            if description_elem is None:
                raise NoElementException("Description element is not found.")
            if user_elem is None:
                raise NoElementException("User element is not found.")
            if odate_elem is None:
                raise NoElementException("Odate element is not found.")
            if posts_count_elem is None:
                raise NoElementException("Posts count element is not found.")

            thread = ForumThread(
                site=site,
                id=int(thread_id),
                title=title.text,
                description=description_elem.text,
                created_by=user_parser(site.client, user_elem),
                created_at=odate_parser(odate_elem),
                post_count=int(posts_count_elem.text),
                category=category,
            )

            threads.append(thread)

        return threads

    @staticmethod
    def acquire_all_in_category(category: "ForumCategory") -> "ForumThreadCollection":
        """
        特定のカテゴリ内のすべてのスレッドを取得する
        
        カテゴリページの各ページにアクセスし、すべてのスレッド情報を収集する。
        ページネーションが存在する場合は、すべてのページを巡回する。
        
        Parameters
        ----------
        category : ForumCategory
            スレッドを取得するカテゴリ
            
        Returns
        -------
        ForumThreadCollection
            カテゴリ内のすべてのスレッドを含むコレクション
            
        Raises
        ------
        NoElementException
            HTML要素の解析に失敗した場合
        """
        threads = []

        first_response = category.site.amc_request(
            [
                {
                    "p": 1,
                    "c": category.id,
                    "moduleName": "forum/ForumViewCategoryModule",
                }
            ]
        )[0]

        first_body = first_response.json()["body"]
        first_html = BeautifulSoup(first_body, "lxml")

        threads.extend(ForumThreadCollection._parse(category.site, first_html))

        # pager検索
        pager = first_html.select_one("div.pager")
        if pager is None:
            return ForumThreadCollection(site=category.site, threads=threads)

        last_page = int(pager.select("a")[-2].text)
        if last_page == 1:
            return ForumThreadCollection(site=category.site, threads=threads)

        responses = category.site.amc_request(
            [
                {
                    "p": page,
                    "c": category.id,
                    "moduleName": "forum/ForumViewCategoryModule",
                }
                for page in range(2, last_page + 1)
            ]
        )

        for response in responses:
            body = response.json()["body"]
            html = BeautifulSoup(body, "lxml")
            threads.extend(ForumThreadCollection._parse(category.site, html, category))

        return ForumThreadCollection(site=category.site, threads=threads)


@dataclass
class ForumThread:
    """
    Wikidotフォーラムのスレッドを表すクラス
    
    フォーラムスレッドの基本情報を保持する。スレッドのタイトル、説明、
    作成者、作成日時、投稿数などの情報を提供する。
    
    Attributes
    ----------
    site : Site
        スレッドが属するサイト
    id : int
        スレッドID
    title : str
        スレッドのタイトル
    description : str
        スレッドの説明または抜粋
    created_by : AbstractUser
        スレッドの作成者
    created_at : datetime
        スレッドの作成日時
    post_count : int
        スレッド内の投稿数
    category : ForumCategory | None, default None
        スレッドが属するフォーラムカテゴリ
    """
    
    site: "Site"
    id: int
    title: str
    description: str
    created_by: "AbstractUser"
    created_at: datetime
    post_count: int
    category: Optional["ForumCategory"] = None

    def __str__(self):
        """
        オブジェクトの文字列表現
        
        Returns
        -------
        str
            スレッドの文字列表現
        """
        return (
            f"ForumThread(id={self.id}, "
            f"title={self.title}, description={self.description}, "
            f"created_by={self.created_by}, created_at={self.created_at}, "
            f"post_count={self.post_count})"
        )
