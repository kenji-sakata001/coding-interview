from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Category, Company


class CategoryViewTests(APITestCase):
    """Category CRUD API（/api/categories/）のテスト"""

    def setUp(self):
        """各テストの前に、テスト用のCompanyとCategoryを1件ずつ作成する"""
        self.company = Company.objects.create(name="Test Company")
        self.category = Category.objects.create(
            company=self.company, name="Test Category"
        )

    def test_list(self):
        """GET /api/categories/ でCategory一覧が取得できること"""
        response = self.client.get(reverse("category-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(self.category.id))

    def test_retrieve(self):
        """GET /api/categories/{id}/ で指定したCategory1件が取得できること"""
        response = self.client.get(
            reverse("category-detail", kwargs={"pk": self.category.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Category")

    def test_create(self):
        """POST /api/categories/ でCategoryが新規作成されること"""
        payload = {"company": str(self.company.id), "name": "New Category"}
        response = self.client.post(
            reverse("category-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Category.objects.filter(
                name="New Category", company=self.company
            ).exists()
        )

    def test_update(self):
        """PUT /api/categories/{id}/ で既存Categoryの内容が更新されること"""
        payload = {"company": str(self.company.id), "name": "Updated Category"}
        response = self.client.put(
            reverse("category-detail", kwargs={"pk": self.category.id}),
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Updated Category")

    def test_partial_update(self):
        """PATCH /api/categories/{id}/ で指定したフィールドのみが更新されること"""
        response = self.client.patch(
            reverse("category-detail", kwargs={"pk": self.category.id}),
            {"name": "Partially Updated Category"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Partially Updated Category")
        # company を送らなくても、既存の値が維持されること
        self.assertEqual(self.category.company_id, self.company.id)

    def test_destroy(self):
        """DELETE /api/categories/{id}/ でCategoryが削除されること"""
        response = self.client.delete(
            reverse("category-detail", kwargs={"pk": self.category.id})
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(id=self.category.id).exists())


class CategoryViewSecurityTests(APITestCase):
    """ユーザー入力値の検証・不正な入力に対する耐性を確認するテスト"""

    def setUp(self):
        """各テストの前に、テスト用のCompanyとCategoryを1件ずつ作成する"""
        self.company = Company.objects.create(name="Test Company")
        self.category = Category.objects.create(
            company=self.company, name="Test Category"
        )

    def test_retrieve_with_malformed_uuid_returns_404(self):
        """GET /api/categories/{id}/ でURLのidがUUID形式でない場合、例外(500)ではなく404が返ること"""
        response = self.client.get("/api/categories/not-a-valid-uuid/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_without_required_company_returns_400(self):
        """POST /api/categories/ で必須項目companyを省略した場合、
        500ではなく400が返り、レコードも作成されないこと
        """
        response = self.client.post(
            reverse("category-list"), {"name": "テスト"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Category.objects.filter(name="テスト").exists())

    def test_create_with_nonexistent_company_returns_400(self):
        """POST /api/categories/ で存在しないcompany idを指定した場合、
        外部キー制約違反(500)ではなく400が返ること
        """
        payload = {
            "company": "00000000-0000-0000-0000-000000000000",
            "name": "テスト",
        }
        response = self.client.post(
            reverse("category-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Category.objects.filter(name="テスト").exists())

    def test_create_with_name_exceeding_max_length_returns_400(self):
        """POST /api/categories/ でnameが255文字を超える場合、
        DB制約エラー(500)ではなく400が返ること
        """
        payload = {"company": str(self.company.id), "name": "a" * 256}
        response = self.client.post(
            reverse("category-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Category.objects.filter(company=self.company).count(), 1
        )

    def test_create_with_duplicate_company_and_name_returns_400(self):
        """POST /api/categories/ で同一company内に同名categoryが既に存在する場合、
        DB制約違反(500)ではなく400が返り、レコードが重複作成されないこと
        """
        payload = {"company": str(self.company.id), "name": self.category.name}
        response = self.client.post(
            reverse("category-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Category.objects.filter(
                company=self.company, name=self.category.name
            ).count(),
            1,
        )

    def test_create_with_sql_injection_like_name_is_stored_as_plain_text(self):
        """POST /api/categories/ でSQLインジェクションを狙った文字列も、
        ORMのパラメータ化により単なる文字列として安全に保存されること
        """
        malicious_name = "'; DROP TABLE categories; --"
        payload = {"company": str(self.company.id), "name": malicious_name}
        response = self.client.post(
            reverse("category-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], malicious_name)
        # categoriesテーブル自体が破壊されず、既存レコードも参照できることを確認する
        self.assertTrue(Category.objects.filter(id=self.category.id).exists())

    def test_create_ignores_client_supplied_id_and_created_at(self):
        """POST /api/categories/ でクライアントがid・created_atを偽装しても、
        サーバー側で生成された値が優先されること
        """
        forged_id = "11111111-1111-1111-1111-111111111111"
        payload = {
            "id": forged_id,
            "created_at": "2000-01-01T00:00:00Z",
            "company": str(self.company.id),
            "name": "改ざん試行",
        }
        response = self.client.post(
            reverse("category-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(response.data["id"], forged_id)
        self.assertFalse(Category.objects.filter(id=forged_id).exists())
        self.assertNotEqual(
            response.data["created_at"], "2000-01-01T00:00:00Z"
        )

    def test_partial_update_with_nonexistent_company_returns_400(self):
        """PATCH /api/categories/{id}/ で存在しないcompany idを指定した場合、
        外部キー制約違反(500)ではなく400が返ること
        """
        response = self.client.patch(
            reverse("category-detail", kwargs={"pk": self.category.id}),
            {"company": "00000000-0000-0000-0000-000000000000"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_partial_update_with_duplicate_name_returns_400(self):
        """PATCH /api/categories/{id}/ で同一company内の別のcategoryと
        company+nameが重複するように更新しようとした場合、400が返ること
        """
        other = Category.objects.create(
            company=self.company, name="Other Category"
        )
        response = self.client.patch(
            reverse("category-detail", kwargs={"pk": other.id}),
            {"name": self.category.name},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_partial_update_without_changes_does_not_conflict_with_itself(self):
        """PATCH /api/categories/{id}/ で自分自身と同じcompany+nameを送っても、
        ユニーク制約違反(400)として誤って弾かれないこと
        """
        response = self.client.patch(
            reverse("category-detail", kwargs={"pk": self.category.id}),
            {"company": str(self.company.id), "name": self.category.name},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_partial_update_ignores_client_supplied_id(self):
        """PATCH /api/categories/{id}/ でクライアントがidを偽装しても、
        idが書き換わらないこと
        """
        forged_id = "22222222-2222-2222-2222-222222222222"
        response = self.client.patch(
            reverse("category-detail", kwargs={"pk": self.category.id}),
            {"id": forged_id, "name": "PATCH偽装確認"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.category.id))
        self.assertFalse(Category.objects.filter(id=forged_id).exists())

