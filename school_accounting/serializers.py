from rest_framework import serializers
from .models import (
    SchoolExpenseCategory, SchoolExpense, TeacherSalary,
    SchoolIncome, SchoolDebt, SchoolAsset, SalaryReceipt
)


class SchoolExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolExpenseCategory
        fields = ['id', 'name', 'category_type', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class SchoolExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_type = serializers.CharField(source='category.category_type', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = SchoolExpense
        fields = [
            'id', 'date', 'category', 'category_name', 'category_type',
            'description', 'amount', 'payment_method', 'payee',
            'reference_number', 'term', 'academic_year', 'notes',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_name']


class TeacherSalarySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    balance_due = serializers.SerializerMethodField()

    class Meta:
        model = TeacherSalary
        fields = [
            'id', 'teacher_name', 'employee_id', 'month',
            'basic_salary', 'allowances', 'deductions', 'net_salary',
            'amount_paid', 'balance_due', 'status', 'payment_date',
            'payment_method', 'reference_number', 'notes',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'net_salary', 'created_at', 'updated_at', 'created_by_name']

    def get_balance_due(self, obj):
        return float(obj.net_salary - obj.amount_paid)


class SchoolIncomeSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    income_type_display = serializers.CharField(source='get_income_type_display', read_only=True)

    class Meta:
        model = SchoolIncome
        fields = [
            'id', 'date', 'income_type', 'income_type_display', 'description',
            'amount', 'source', 'payment_method', 'reference_number',
            'term', 'academic_year', 'notes',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_name']


class SchoolDebtSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    debt_type_display = serializers.CharField(source='get_debt_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SchoolDebt
        fields = [
            'id', 'creditor_name', 'debt_type', 'debt_type_display',
            'original_amount', 'amount_paid', 'balance', 'status', 'status_display',
            'incurred_date', 'due_date', 'description', 'notes',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at', 'created_by_name']


class SchoolAssetSerializer(serializers.ModelSerializer):
    asset_type_display = serializers.CharField(source='get_asset_type_display', read_only=True)

    class Meta:
        model = SchoolAsset
        fields = [
            'id', 'name', 'asset_type', 'asset_type_display',
            'purchase_value', 'current_value', 'purchase_date',
            'depreciation_rate', 'condition', 'location', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SalaryReceiptSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='salary.teacher_name', read_only=True)
    employee_id = serializers.CharField(source='salary.employee_id', read_only=True)
    month = serializers.DateField(source='salary.month', read_only=True)
    basic_salary = serializers.DecimalField(source='salary.basic_salary', max_digits=12, decimal_places=2, read_only=True)
    allowances = serializers.DecimalField(source='salary.allowances', max_digits=12, decimal_places=2, read_only=True)
    deductions = serializers.DecimalField(source='salary.deductions', max_digits=12, decimal_places=2, read_only=True)
    net_salary = serializers.DecimalField(source='salary.net_salary', max_digits=12, decimal_places=2, read_only=True)
    amount_paid = serializers.DecimalField(source='salary.amount_paid', max_digits=12, decimal_places=2, read_only=True)
    balance_due = serializers.SerializerMethodField()
    payment_method = serializers.CharField(source='salary.payment_method', read_only=True)
    payment_date = serializers.DateField(source='salary.payment_date', read_only=True)
    reference_number = serializers.CharField(source='salary.reference_number', read_only=True)
    status = serializers.CharField(source='salary.status', read_only=True)
    issued_by_name = serializers.CharField(source='issued_by.username', read_only=True)

    class Meta:
        model = SalaryReceipt
        fields = [
            'id', 'receipt_number', 'secure_token', 'issued_date', 'issued_by_name', 'notes',
            'salary',
            'teacher_name', 'employee_id', 'month',
            'basic_salary', 'allowances', 'deductions', 'net_salary',
            'amount_paid', 'balance_due', 'payment_method', 'payment_date',
            'reference_number', 'status',
            'created_at',
        ]
        read_only_fields = ['id', 'receipt_number', 'secure_token', 'issued_by_name', 'created_at']

    def get_balance_due(self, obj):
        return float(obj.salary.net_salary - obj.salary.amount_paid)
