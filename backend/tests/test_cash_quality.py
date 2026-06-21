"""现金质量门单元测试 — v0.7.0: 8维度"""

import pytest
from app.strategies.turtle.cash_quality import CashQualityGate, CashQualityResult


def make_financial(year, revenue, net_profit, op_cf, fcf, receivables, inventory,
                    depreciation=1.0, amortization=0.5, interest=0.5,
                    # v0.7.0: 新增字段
                    dividend_paid_cf=0,
                    accounts_payable=0, notes_payable=0,
                    contract_liab=0, advance_receipts=0,
                    operate_cost=0,
                    st_borrow=0, lt_borrow=0, bonds_payable=0,
                    noncurrent_liab_due_in_1y=0,
                    total_assets=100):
    return {
        "year": year,
        "income": {
            "revenue": revenue,
            "net_profit": net_profit,
            "operate_cost": operate_cost if operate_cost > 0 else revenue * 0.6,
        },
        "balance_sheet": {
            "receivables": receivables,
            "inventory": inventory,
            "total_assets": total_assets,
            # v0.7.0: 分红质量检测字段
            "accounts_payable": accounts_payable,
            "notes_payable": notes_payable,
            "contract_liab": contract_liab,
            "advance_receipts": advance_receipts,
            "st_borrow": st_borrow,
            "lt_borrow": lt_borrow,
            "bonds_payable": bonds_payable,
            "noncurrent_liab_due_in_1y": noncurrent_liab_due_in_1y,
        },
        "cashflow": {
            "operating_cf": op_cf,
            "fcf": fcf,
            "depreciation": depreciation,
            "amortization": amortization,
            "finan_exp": interest,
            "dividend_paid_cf": dividend_paid_cf,
        },
    }


def make_raw_data(ts_code, financials):
    return {
        "meta": {"ts_code": ts_code, "name": "测试"},
        "annual_financials": financials,
    }


class TestCashQualityGate:
    def test_all_dimensions_pass(self):
        """全部8维度通过的理想情况"""
        gate = CashQualityGate()
        financials = [
            make_financial(2024, 100, 20, 18, 5, 10, 15,
                           dividend_paid_cf=3,  # FCF=5 >= 3
                           accounts_payable=5, notes_payable=1,  # 供应商=6
                           contract_liab=0,  # 净供应商欠款=6
                           operate_cost=60,  # ratio=6/60=0.1
                           st_borrow=10, total_assets=100),  # 有息负债率=10%
            make_financial(2023, 95, 19, 17, 4, 9, 14,
                           dividend_paid_cf=2,
                           accounts_payable=5, notes_payable=1,
                           operate_cost=57,  # ratio=6/57≈0.105
                           st_borrow=10, total_assets=95),
            make_financial(2022, 90, 18, 16, 3, 8, 13,
                           dividend_paid_cf=2,
                           accounts_payable=5, notes_payable=1,
                           operate_cost=54,
                           st_borrow=10, total_assets=90),
            make_financial(2021, 85, 17, 15, 2, 8, 12,
                           dividend_paid_cf=1,
                           accounts_payable=5, notes_payable=1,
                           operate_cost=51,
                           st_borrow=10, total_assets=85),
            make_financial(2020, 80, 16, 14, 1, 7, 11,
                           dividend_paid_cf=1,
                           accounts_payable=5, notes_payable=1,
                           operate_cost=48,
                           st_borrow=10, total_assets=80),
        ]
        raw = make_raw_data("000001.SZ", financials)
        result = gate.compute(raw)
        assert result.overall_passed
        assert result.dim1_passed
        assert result.dim2_passed
        assert result.dim3_passed
        assert result.dim4_passed
        assert result.dim5_passed
        assert result.dim6_passed
        assert result.dim7_passed
        assert result.dim8_passed

    def test_dim1_opcf_netprofit_fails(self):
        """经营CF/净利润不达标"""
        gate = CashQualityGate()
        financials = [
            make_financial(2024, 100, 20, 10, 5, 10, 15),  # ratio=0.5
            make_financial(2023, 95, 19, 10, 4, 9, 14),
            make_financial(2022, 90, 18, 10, 3, 8, 13),
            make_financial(2021, 85, 17, 15, 2, 8, 12),
            make_financial(2020, 80, 16, 14, 1, 7, 11),
        ]
        raw = make_raw_data("000001.SZ", financials)
        result = gate.compute(raw)
        assert not result.dim1_passed
        assert not result.overall_passed
        assert 1 in result.failed_dimensions

    def test_dim2_fcf_positive_fails(self):
        """FCF正年数不达标"""
        gate = CashQualityGate()
        financials = [
            make_financial(2024, 100, 20, 18, -1, 10, 15),
            make_financial(2023, 95, 19, 17, -1, 9, 14),
            make_financial(2022, 90, 18, 16, -1, 8, 13),
            make_financial(2021, 85, 17, 15, 1, 8, 12),
            make_financial(2020, 80, 16, 14, 1, 7, 11),
        ]
        raw = make_raw_data("000001.SZ", financials)
        result = gate.compute(raw)
        assert not result.dim2_passed
        assert 2 in result.failed_dimensions

    def test_dim3_receivables_fails(self):
        """应收/营收比过高"""
        gate = CashQualityGate()
        financials = [
            make_financial(2024, 100, 20, 18, 5, 40, 15),  # ratio=0.4
            make_financial(2023, 95, 19, 17, 4, 38, 14),
            make_financial(2022, 90, 18, 16, 3, 36, 13),
            make_financial(2021, 85, 17, 15, 2, 8, 12),
            make_financial(2020, 80, 16, 14, 1, 7, 11),
        ]
        raw = make_raw_data("000001.SZ", financials)
        result = gate.compute(raw)
        assert not result.dim3_passed
        assert 3 in result.failed_dimensions

    def test_insufficient_data(self):
        """数据不足5年"""
        gate = CashQualityGate()
        financials = [
            make_financial(2024, 100, 20, 18, 5, 10, 15),
            make_financial(2023, 95, 19, 17, 4, 9, 14),
        ]
        raw = make_raw_data("000001.SZ", financials)
        result = gate.compute(raw)
        assert not result.overall_passed

    # ── v0.7.0: dim6-8 新增测试 ──

    def test_dim6_borrowing_dividend(self):
        """dim6: FCF连续3年覆盖不了分红 → FAIL"""
        gate = CashQualityGate()
        financials = [
            make_financial(2024, 100, 20, 30, 5, 10, 15, dividend_paid_cf=10),  # FCF=5 < 10
            make_financial(2023, 95, 19, 28, 4, 9, 14, dividend_paid_cf=8),   # FCF=4 < 8
            make_financial(2022, 90, 18, 26, 3, 8, 13, dividend_paid_cf=6),   # FCF=3 < 6
            make_financial(2021, 85, 17, 24, 8, 8, 12, dividend_paid_cf=5),   # FCF=8 >= 5 ✓
            make_financial(2020, 80, 16, 22, 8, 7, 11, dividend_paid_cf=5),   # FCF=8 >= 5 ✓
        ]
        raw = make_raw_data("000001.SZ", financials)
        result = gate.compute(raw)
        assert not result.dim6_passed  # 仅2年覆盖, < 4
        assert 6 in result.failed_dimensions
        assert result.details["dim6"]["positive_years"] == 2

    def test_dim6_all_covered(self):
        """dim6: FCF 5年全 ≥ dividend_paid_cf → PASS"""
        gate = CashQualityGate()
        financials = [
            make_financial(2024, 100, 20, 30, 10, 10, 15, dividend_paid_cf=5),  # FCF=10 >= 5
            make_financial(2023, 95, 19, 28, 9, 9, 14, dividend_paid_cf=5),   # FCF=9 >= 5
            make_financial(2022, 90, 18, 26, 8, 8, 13, dividend_paid_cf=5),   # FCF=8 >= 5
            make_financial(2021, 85, 17, 24, 7, 8, 12, dividend_paid_cf=5),   # FCF=7 >= 5
            make_financial(2020, 80, 16, 22, 6, 7, 11, dividend_paid_cf=5),   # FCF=6 >= 5
        ]
        raw = make_raw_data("000001.SZ", financials)
        result = gate.compute(raw)
        assert result.dim6_passed, f"Expected dim6 pass, got details: {result.details['dim6']}"
        assert result.details["dim6"]["positive_years"] == 5

    def test_dim7_supplier_squeezed(self):
        """dim7: 供应商欠款增速远超营收 → FAIL"""
        gate = CashQualityGate()
        # 供应商欠款 CAGR 显著 > 营收 CAGR
        financials = [
            make_financial(2024, 100, 20, 30, 10, 10, 15,
                           accounts_payable=25, notes_payable=5,  # 供应商=30 → ratio=30/60=0.5
                           operate_cost=60),
            make_financial(2023, 95, 19, 28, 9, 9, 14,
                           accounts_payable=20, notes_payable=4,  # ratio=24/57≈0.421
                           operate_cost=57),
            make_financial(2022, 90, 18, 26, 8, 8, 13,
                           accounts_payable=16, notes_payable=3,  # ratio=19/54≈0.352
                           operate_cost=54),
            make_financial(2021, 85, 17, 24, 7, 8, 12,
                           accounts_payable=12, notes_payable=2,  # ratio=14/51≈0.275
                           operate_cost=51),
            make_financial(2020, 80, 16, 22, 6, 7, 11,
                           accounts_payable=8, notes_payable=1,    # ratio=9/48=0.1875
                           operate_cost=48),
        ]
        raw = make_raw_data("000001.SZ", financials)
        result = gate.compute(raw)
        # supplier_cagr: (0.5/0.1875)^(1/4)-1 ≈ (2.667)^(0.25)-1 ≈ 0.278
        # revenue_cagr: (100/80)^(1/4)-1 ≈ 1.25^0.25-1 ≈ 0.057
        # gap ≈ 0.221 > 0.10 → FAIL
        assert not result.dim7_passed, f"Expected dim7 fail, got details: {result.details['dim7']}"
        assert 7 in result.failed_dimensions

    def test_dim7_healthy_advances(self):
        """dim7: 合同负债远超应付 → 净供应商欠款=0 → PASS"""
        gate = CashQualityGate()
        financials = [
            make_financial(2024, 100, 20, 30, 10, 10, 15,
                           accounts_payable=5, notes_payable=1,    # 供应商=6
                           contract_liab=20, advance_receipts=0,   # 预收=20
                           operate_cost=60),                        # net=max(0,6-20)=0
            make_financial(2023, 95, 19, 28, 9, 9, 14,
                           accounts_payable=4, contract_liab=18,
                           operate_cost=57),
            make_financial(2022, 90, 18, 26, 8, 8, 13,
                           accounts_payable=3, contract_liab=16,
                           operate_cost=54),
            make_financial(2021, 85, 17, 24, 7, 8, 12,
                           accounts_payable=2, contract_liab=14,
                           operate_cost=51),
            make_financial(2020, 80, 16, 22, 6, 7, 11,
                           accounts_payable=1, contract_liab=12,
                           operate_cost=48),
        ]
        raw = make_raw_data("000001.SZ", financials)
        result = gate.compute(raw)
        # 所有年净供应商欠款=0 → ratios全0 → supplier_ratios[-1]=0 → 跳过CAGR → dim7_passed=True
        assert result.dim7_passed, f"Expected dim7 pass (healthy advances), got: {result.details['dim7']}"

    def test_dim8_leverage_rising(self):
        """dim8: 有息负债率3年上升15pp → FAIL"""
        gate = CashQualityGate()
        financials = [
            make_financial(2024, 100, 20, 30, 10, 10, 15,
                           st_borrow=25, lt_borrow=10,  # 有息负债=35, ratio=35/100=0.35
                           total_assets=100),
            make_financial(2023, 95, 19, 28, 9, 9, 14,
                           st_borrow=20, lt_borrow=8,   # ratio=28/95≈0.295
                           total_assets=95),
            make_financial(2022, 90, 18, 26, 8, 8, 13,
                           st_borrow=15, lt_borrow=5,   # ratio=20/90≈0.222
                           total_assets=90),
            make_financial(2021, 85, 17, 24, 7, 8, 12,
                           st_borrow=10, lt_borrow=3,   # ratio=13/85≈0.153
                           total_assets=85),
            make_financial(2020, 80, 16, 22, 6, 7, 11,
                           st_borrow=8, lt_borrow=2,     # ratio=10/80=0.125
                           total_assets=80),
        ]
        raw = make_raw_data("000001.SZ", financials)
        result = gate.compute(raw)
        # latest=0.35, three_y_ago=0.222, change=0.128 > 0.10 → FAIL
        assert not result.dim8_passed, f"Expected dim8 fail, got details: {result.details['dim8']}"
        assert 8 in result.failed_dimensions

    def test_dim8_stable_leverage(self):
        """dim8: 有息负债率3年不变 → PASS"""
        gate = CashQualityGate()
        financials = [
            make_financial(2024, 100, 20, 30, 10, 10, 15,
                           st_borrow=10, total_assets=100),
            make_financial(2023, 95, 19, 28, 9, 9, 14,
                           st_borrow=10, total_assets=95),
            make_financial(2022, 90, 18, 26, 8, 8, 13,
                           st_borrow=10, total_assets=90),
            make_financial(2021, 85, 17, 24, 7, 8, 12,
                           st_borrow=10, total_assets=85),
            make_financial(2020, 80, 16, 22, 6, 7, 11,
                           st_borrow=10, total_assets=80),
        ]
        raw = make_raw_data("000001.SZ", financials)
        result = gate.compute(raw)
        assert result.dim8_passed, f"Expected dim8 pass, got details: {result.details['dim8']}"

    def test_to_computed_format(self):
        gate = CashQualityGate()
        result = CashQualityResult(ts_code="000001.SZ", overall_passed=True)
        fmt = gate.to_computed_format(result)
        assert fmt["overall_passed"]
        assert "failed_dimensions" in fmt
        # v0.7.0: 8维度
        assert "dimension_6_fcf_dividend_coverage" in fmt
        assert "dimension_7_supplier_squeeze" in fmt
        assert "dimension_8_interest_bearing_debt_trend" in fmt
