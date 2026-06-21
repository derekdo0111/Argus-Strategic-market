"""现金质量门 — Step 3-4

8子维度确定性计算与软门判定。
v0.7.0: 新增 dim6 FCF分红覆盖率 / dim7 供应商挤压 / dim8 有息负债趋势
"""

import logging
import math
from dataclasses import dataclass, field
from statistics import mean, stdev

logger = logging.getLogger(__name__)


@dataclass
class CashQualityResult:
    """现金质量判定结果"""
    ts_code: str
    dim1_passed: bool = False   # 经营CF/净利润 > 0.8
    dim2_passed: bool = False   # FCF正年数 ≥ 4/5
    dim3_passed: bool = False   # 应收/营收 < 0.3
    dim4_passed: bool = False   # 存货/营收 CV < 0.5
    dim5_passed: bool = False   # 经营CF CV < 0.5
    dim6_passed: bool = False   # FCF分红覆盖率 ≥ 4/5
    dim7_passed: bool = False   # 供应商挤压 < 10pp
    dim8_passed: bool = False   # 有息负债率变化 < 10pp
    overall_passed: bool = False
    details: dict = field(default_factory=dict)

    @property
    def failed_dimensions(self) -> list[int]:
        dims = []
        if not self.dim1_passed: dims.append(1)
        if not self.dim2_passed: dims.append(2)
        if not self.dim3_passed: dims.append(3)
        if not self.dim4_passed: dims.append(4)
        if not self.dim5_passed: dims.append(5)
        if not self.dim6_passed: dims.append(6)
        if not self.dim7_passed: dims.append(7)
        if not self.dim8_passed: dims.append(8)
        return dims


class CashQualityGate:
    """现金质量软门 — v0.7.0: 8子维度"""

    # === 阈值 ===
    OP_CF_NETPROFIT_THRESHOLD = 0.8      # 维度1
    FCF_POSITIVE_MIN_YEARS = 4           # 维度2 (out of 5)
    RECEIVABLES_REVENUE_MAX = 0.3        # 维度3
    INVENTORY_REVENUE_CV_MAX = 0.5       # 维度4
    OP_CF_CV_MAX = 0.5                   # 维度5
    # v0.7.0: 新增
    FCF_DIVIDEND_COVERAGE_MIN = 4        # 维度6 (FCF覆盖分红年数, out of 5)
    SUPPLIER_SQUEEZE_MAX = 0.10          # 维度7 (供应商欠款/成本CAGR - 营收CAGR < 10pp)
    INTEREST_BEARING_DEBT_CHANGE_MAX = 0.10  # 维度8 (有息负债率3年变化 < 10pp)
    LOOKBACK_YEARS = 5

    def __init__(self, rule_version: str = "v2"):
        self.rule_version = rule_version

    def compute(self, raw_data: dict) -> CashQualityResult:
        """从 raw_data 计算现金质量8维度 (v0.7.0)

        Args:
            raw_data: raw_data.yaml 格式的字典

        Returns:
            CashQualityResult
        """
        ts_code = raw_data["meta"]["ts_code"]
        financials = raw_data.get("annual_financials", [])

        if len(financials) < self.LOOKBACK_YEARS:
            logger.warning(f"{ts_code}: 财务数据不足{self.LOOKBACK_YEARS}年")
            return CashQualityResult(ts_code=ts_code)

        # 取最近N年
        recent = financials[:self.LOOKBACK_YEARS]

        result = CashQualityResult(ts_code=ts_code)

        # === 维度1: 经营CF/净利润 > 0.8（近3年均值） ===
        recent_3y = recent[:3]
        ratios = []
        for f in recent_3y:
            np_val = f["income"]["net_profit"]
            cf_val = f["cashflow"]["operating_cf"]
            if np_val and np_val != 0 and not math.isnan(cf_val):
                ratio = cf_val / np_val
                if not math.isnan(ratio) and not math.isinf(ratio):
                    ratios.append(ratio)
        if ratios:
            avg_ratio = mean(ratios)
            result.dim1_passed = avg_ratio > self.OP_CF_NETPROFIT_THRESHOLD
            result.details["dim1"] = {
                "ratios": ratios,
                "avg_3y": avg_ratio,
                "threshold": self.OP_CF_NETPROFIT_THRESHOLD,
            }

        # === 维度2: FCF正年数 ≥ 4/5 ===
        fcf_positive = 0
        fcf_valid_years = 0
        for f in recent:
            fcf_val = f["cashflow"].get("fcf", float("nan"))
            if math.isnan(fcf_val):
                continue  # NaN 跳过，不扣分
            fcf_valid_years += 1
            if fcf_val > 0:
                fcf_positive += 1
        # 判定: 至少需有不少于阈值年的有效数据，且正年数达标
        # 如果有效年数不足，按比例放宽（但至少需要3年有效数据）
        if fcf_valid_years >= 3:
            result.dim2_passed = fcf_positive >= min(
                self.FCF_POSITIVE_MIN_YEARS, fcf_valid_years
            )
        result.details["dim2"] = {
            "positive_count": fcf_positive,
            "valid_years": fcf_valid_years,
            "total_years": self.LOOKBACK_YEARS,
            "threshold": self.FCF_POSITIVE_MIN_YEARS,
        }

        # === 维度3: 应收/营收 < 0.3（近3年均值） ===
        rec_ratios = []
        for f in recent_3y:
            rev = f["income"]["revenue"]
            rec = f["balance_sheet"]["receivables"]
            if rev and rev != 0 and not math.isnan(rec):
                ratio = rec / rev
                if not math.isnan(ratio):
                    rec_ratios.append(ratio)
        if rec_ratios:
            avg_rec = mean(rec_ratios)
            result.dim3_passed = avg_rec < self.RECEIVABLES_REVENUE_MAX
            result.details["dim3"] = {
                "ratios": rec_ratios,
                "avg_3y": avg_rec,
                "threshold": self.RECEIVABLES_REVENUE_MAX,
            }

        # === 维度4: 存货/营收 CV < 0.5 ===
        # 先判断是否无存货行业（金融/软件/服务等）
        all_inv_nan_or_zero = all(
            math.isnan(f["balance_sheet"].get("inventory", float("nan")))
            or f["balance_sheet"].get("inventory", 0) == 0
            for f in recent
        )
        if all_inv_nan_or_zero:
            result.dim4_passed = True
            result.details["dim4"] = {
                "ratios": [],
                "cv": None,
                "threshold": self.INVENTORY_REVENUE_CV_MAX,
                "reason": "industry_no_inventory",
            }
        else:
            inv_ratios = []
            for f in recent:
                rev = f["income"]["revenue"]
                inv = f["balance_sheet"]["inventory"]
                if rev and rev != 0 and not math.isnan(inv):
                    ratio = inv / rev
                    if not math.isnan(ratio):
                        inv_ratios.append(ratio)
            if len(inv_ratios) >= 3:
                try:
                    avg_inv = mean(inv_ratios)
                    std_inv = stdev(inv_ratios)
                    cv = std_inv / avg_inv if avg_inv != 0 else float("inf")
                except Exception:
                    cv = float("inf")
                result.dim4_passed = cv < self.INVENTORY_REVENUE_CV_MAX
                result.details["dim4"] = {
                    "ratios": inv_ratios,
                    "cv": cv,
                    "threshold": self.INVENTORY_REVENUE_CV_MAX,
                }

        # === 维度5: 经营CF CV < 0.5 ===
        op_cfs = [
            f["cashflow"]["operating_cf"] for f in recent
            if not math.isnan(f["cashflow"].get("operating_cf", float("nan")))
        ]
        try:
            avg_cf = mean(op_cfs)
            std_cf = stdev(op_cfs)
            cv_cf = std_cf / abs(avg_cf) if avg_cf != 0 else float("inf")
        except Exception:
            cv_cf = float("inf")
        result.dim5_passed = cv_cf < self.OP_CF_CV_MAX
        result.details["dim5"] = {
            "values": op_cfs,
            "cv": cv_cf,
            "threshold": self.OP_CF_CV_MAX,
        }

        # === 维度6: FCF分红覆盖率 (近5年, FCF >= dividend_paid_cf 的年数) ===
        fcf_div_count = 0
        fcf_div_valid = 0
        for f in recent:
            fcf_val = f["cashflow"].get("fcf", float("nan"))
            div_paid = f["cashflow"].get("dividend_paid_cf", float("nan"))
            if math.isnan(fcf_val) or math.isnan(div_paid):
                continue
            fcf_div_valid += 1
            if fcf_val >= div_paid:
                fcf_div_count += 1
        if fcf_div_valid >= 3:
            result.dim6_passed = fcf_div_count >= min(
                self.FCF_DIVIDEND_COVERAGE_MIN, fcf_div_valid
            )
        result.details["dim6"] = {
            "positive_years": fcf_div_count,
            "valid_years": fcf_div_valid,
            "total_years": self.LOOKBACK_YEARS,
            "threshold": self.FCF_DIVIDEND_COVERAGE_MIN,
        }

        # === 维度7: 供应商挤压 (净供应商欠款/营业成本 CAGR - 营收 CAGR < 10pp) ===
        supplier_ratios = []
        revenue_values = []
        for f in recent:
            bs = f.get("balance_sheet", {})
            income = f.get("income", {})
            # 供应商欠款 = 应付账款 + 应付票据
            ap = bs.get("accounts_payable", 0)
            np_val = bs.get("notes_payable", 0)
            if math.isnan(ap): ap = 0
            if math.isnan(np_val): np_val = 0
            supplier_debt = ap + np_val
            # 客户预收 = max(合同负债, 预收款项) — 新老准则取大值
            cl = bs.get("contract_liab", 0)
            ar = bs.get("advance_receipts", 0)
            if math.isnan(cl): cl = 0
            if math.isnan(ar): ar = 0
            customer_advance = max(cl, ar)
            # 净供应商欠款 (负值=预收为主, 不处罚)
            net_supplier = max(0.0, supplier_debt - customer_advance)
            # 营业成本
            operate_cost = income.get("operate_cost", income.get("revenue", 0))
            if math.isnan(operate_cost): operate_cost = 0
            rev = income.get("revenue", 0)
            if math.isnan(rev): rev = 0
            if operate_cost > 0:
                supplier_ratios.append(net_supplier / operate_cost)
            if rev > 0:
                revenue_values.append(rev)
        # 计算5年CAGR (oldest→newest: [0]是newest, [-1]是oldest)
        if len(supplier_ratios) >= 3 and len(revenue_values) >= 3 \
           and supplier_ratios[0] > 0 and revenue_values[-1] > 0:
            try:
                n = len(supplier_ratios) - 1
                # CAGR = (newest / oldest)^(1/n) - 1
                supplier_cagr = (supplier_ratios[0] / supplier_ratios[-1]) ** (1.0 / n) - 1 if n > 0 and supplier_ratios[-1] > 0 else float("inf")
                revenue_cagr = (revenue_values[0] / revenue_values[-1]) ** (1.0 / n) - 1
                squeeze_gap = supplier_cagr - revenue_cagr
                result.dim7_passed = squeeze_gap < self.SUPPLIER_SQUEEZE_MAX
                result.details["dim7"] = {
                    "supplier_ratio_cagr": round(supplier_cagr, 4),
                    "revenue_cagr": round(revenue_cagr, 4),
                    "squeeze_gap": round(squeeze_gap, 4),
                    "threshold": self.SUPPLIER_SQUEEZE_MAX,
                    "ratios": [round(r, 4) for r in supplier_ratios],
                }
            except (ZeroDivisionError, ValueError):
                result.dim7_passed = True  # 无法计算则不处罚
                result.details["dim7"] = {"reason": "insufficient_data_for_cagr"}
        else:
            # 数据不足或净供应商欠款=0 → 视为通过
            result.dim7_passed = True
            if len(supplier_ratios) >= 3 and all(r == 0.0 for r in supplier_ratios):
                # 净欠款连续为0 → 业务模式不适用(无实物供应商,如广告/软件/轻资产)
                result.details["dim7"] = {"reason": "not_applicable_no_supplier_credit",
                                           "valid_ratios": len(supplier_ratios)}
            else:
                result.details["dim7"] = {"reason": "insufficient_data_for_cagr",
                                           "valid_ratios": len(supplier_ratios)}

        # === 维度8: 有息负债率趋势 (3年变化 < 10pp) ===
        interest_bearing_ratios = []
        for f in recent:
            bs = f.get("balance_sheet", {})
            st_b = bs.get("st_borrow", 0)
            lt_b = bs.get("lt_borrow", 0)
            bp = bs.get("bonds_payable", 0)
            ncd = bs.get("noncurrent_liab_due_in_1y", 0)
            if math.isnan(st_b): st_b = 0
            if math.isnan(lt_b): lt_b = 0
            if math.isnan(bp): bp = 0
            if math.isnan(ncd): ncd = 0
            interest_bearing = st_b + lt_b + bp + ncd
            ta = bs.get("total_assets", 0)
            if math.isnan(ta): ta = 0
            if ta > 0:
                interest_bearing_ratios.append(interest_bearing / ta)
        if len(interest_bearing_ratios) >= 3:
            latest = interest_bearing_ratios[0]
            three_y_ago = interest_bearing_ratios[min(2, len(interest_bearing_ratios) - 1)]
            change = latest - three_y_ago
            result.dim8_passed = change < self.INTEREST_BEARING_DEBT_CHANGE_MAX
            result.details["dim8"] = {
                "latest_ratio": round(latest, 4),
                "three_y_ago_ratio": round(three_y_ago, 4),
                "change": round(change, 4),
                "threshold": self.INTEREST_BEARING_DEBT_CHANGE_MAX,
                "ratios": [round(r, 4) for r in interest_bearing_ratios],
            }
        else:
            result.dim8_passed = True  # 数据不足不处罚
            result.details["dim8"] = {"reason": "insufficient_data",
                                       "valid_ratios": len(interest_bearing_ratios)}

        # === 综合判定 (v0.7.0: 8维度) ===
        result.overall_passed = all([
            result.dim1_passed,
            result.dim2_passed,
            result.dim3_passed,
            result.dim4_passed,
            result.dim5_passed,
            result.dim6_passed,
            result.dim7_passed,
            result.dim8_passed,
        ])

        return result

    def to_computed_format(self, result: CashQualityResult) -> dict:
        """转为 computed.yaml 中 cash_quality 的格式 (v0.7.0: 8维度)"""
        return {
            "dimension_1_opcf_to_netprofit": {
                "passed": result.dim1_passed,
                **(result.details.get("dim1", {})),
            },
            "dimension_2_fcf_positive_years": {
                "passed": result.dim2_passed,
                **(result.details.get("dim2", {})),
            },
            "dimension_3_receivables_ratio": {
                "passed": result.dim3_passed,
                **(result.details.get("dim3", {})),
            },
            "dimension_4_inventory_stability": {
                "passed": result.dim4_passed,
                **(result.details.get("dim4", {})),
            },
            "dimension_5_ocf_stability": {
                "passed": result.dim5_passed,
                **(result.details.get("dim5", {})),
            },
            "dimension_6_fcf_dividend_coverage": {
                "passed": result.dim6_passed,
                **(result.details.get("dim6", {})),
            },
            "dimension_7_supplier_squeeze": {
                "passed": result.dim7_passed,
                **(result.details.get("dim7", {})),
            },
            "dimension_8_interest_bearing_debt_trend": {
                "passed": result.dim8_passed,
                **(result.details.get("dim8", {})),
            },
            "overall_passed": result.overall_passed,
            "failed_dimensions": result.failed_dimensions,
        }
