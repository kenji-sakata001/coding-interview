from django.db import IntegrityError, transaction
from django.test import TestCase

from api.models import Category, Company


class CategoryModelConstraintTests(TestCase):
    """Categoryモデルの制約（on_delete設定・ユニーク制約）を確認するテスト"""

    def setUp(self):
        """テスト用のCompanyを1件作成する"""
        self.company = Company.objects.create(name="Test Company")

    def test_deleting_company_cascades_to_categories(self):
        """companyを削除すると、on_delete=CASCADEによりそのcompanyに紐づくcategoryも削除されること"""
        category = Category.objects.create(
            company=self.company,
            name="Category",
        )
        self.company.delete()
        self.assertFalse(Category.objects.filter(id=category.id).exists())

    def test_deleting_parent_category_sets_null_on_children(self):
        """parent_categoryを削除すると、on_delete=SET_NULLにより、子categoryのparent_categoryがNULLになること
        （子category自体は削除されずに残ること）
        """
        parent = Category.objects.create(
            company=self.company,
            name="Parent Category",
        )
        child = Category.objects.create(
            company=self.company, name="Child Category", parent_category=parent
        )

        parent.delete()
        child.refresh_from_db()

        self.assertIsNone(child.parent_category)
        self.assertTrue(Category.objects.filter(id=child.id).exists())

    def test_creating_duplicate_company_and_name_raises_integrity_error(self):
        """同一company内に同名categoryを直接作成しようとすると、
        unique_company_category_combination制約によりIntegrityErrorが発生すること
        """
        Category.objects.create(
            company=self.company, name="Duplicate Category"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(
                    company=self.company, name="Duplicate Category"
                )

        self.assertEqual(
            Category.objects.filter(
                company=self.company, name="Duplicate Category"
            ).count(),
            1,
        )

