"""E2E test for Todo App using Playwright (Python)."""

import json
import urllib.request
from playwright.sync_api import sync_playwright, expect


def clear_all_todos():
    """Delete all existing todos via API."""
    req = urllib.request.Request("http://localhost:3000/todos")
    with urllib.request.urlopen(req) as resp:
        todos = json.loads(resp.read())
    for todo in todos:
        dreq = urllib.request.Request(
            f"http://localhost:3000/todos/{todo['id']}", method="DELETE"
        )
        urllib.request.urlopen(dreq)


def main():
    clear_all_todos()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:9000/")
        page.wait_for_load_state("networkidle")

        # 1. 初期状態: 空メッセージ表示
        print("TEST 1: 初期状態 — 空メッセージが表示される")
        empty_msg = page.locator("text=Todoはまだありません")
        expect(empty_msg).to_be_visible()
        print("  PASS")

        # 2. Todo を追加
        print("TEST 2: Todo を追加")
        input_field = page.locator("input").first
        input_field.fill("E2Eテスト用Todo")
        page.locator("button:has-text('追加')").click()
        page.wait_for_timeout(2000)  # Lambda cold start
        todo_text = page.locator("text=E2Eテスト用Todo")
        expect(todo_text).to_be_visible()
        print("  PASS")

        # 3. 2つ目の Todo を追加
        print("TEST 3: 2つ目の Todo を追加")
        input_field.fill("2つ目のTodo")
        page.locator("button:has-text('追加')").click()
        page.wait_for_timeout(2000)
        expect(page.locator("text=2つ目のTodo")).to_be_visible()
        # 2件表示されている
        checkboxes = page.locator(".q-checkbox")
        expect(checkboxes).to_have_count(2)
        print("  PASS")

        # 4. Todo を完了にトグル
        print("TEST 4: Todo を完了にトグル")
        first_checkbox = checkboxes.first
        first_checkbox.click()
        page.wait_for_timeout(2000)
        # 取り消し線が適用されたか確認
        striked = page.locator(".text-strike")
        expect(striked).to_have_count(1)
        print("  PASS")

        # 5. Todo を削除
        print("TEST 5: Todo を削除")
        delete_buttons = page.locator("button[class*='text-negative'], button .q-icon:has-text('delete')").locator("xpath=ancestor::button").all()
        if not delete_buttons:
            # Quasar の delete ボタンを別の方法で取得
            delete_buttons = page.locator("button").filter(has=page.locator(".q-icon")).all()
            delete_buttons = [b for b in delete_buttons if "delete" in (b.inner_text() or "")]
        # delete アイコンのボタンを探す
        del_btns = page.locator("button.q-btn--round").all()
        if del_btns:
            del_btns[0].click()
        page.wait_for_timeout(2000)
        remaining_checkboxes = page.locator(".q-checkbox")
        expect(remaining_checkboxes).to_have_count(1)
        print("  PASS")

        # スクリーンショット保存
        page.screenshot(path="e2e/screenshot_final.png")
        print("\nスクリーンショット: e2e/screenshot_final.png")

        browser.close()

    print("\n=== 全 E2E テスト PASS ===")


if __name__ == "__main__":
    main()
