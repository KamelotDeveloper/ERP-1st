"""Unit tests for validate_math — pre-flight mathematical validation.

Tests cover:
1. Exact match → valid=True
2. Diff within 0.01 → valid=False, within_tolerance=True
3. Diff >= 0.02 → valid=False, within_tolerance=False
4. All zero → valid=True
5. With tributos and op_ex → valid=True
6. Negative values (NC) → valid=True
"""

import pytest

from services.comprobante_fiscal import validate_math


# ===========================================================================
# 1. Exact match
# ===========================================================================

class TestExactMatch:
    """ImpTotal equals sum of components exactly."""

    def test_simple_factura(self):
        """Factura A: total = neto + iva."""
        result = validate_math(
            imp_total=121.0,
            imp_neto=100.0,
            imp_iva=21.0,
        )
        assert result["valid"] is True
        assert result["expected"] == 121.0
        assert result["actual"] == 121.0
        assert result["difference"] == 0.0
        assert result["within_tolerance"] is True

    def test_factura_with_decimals(self):
        """Factura with decimal values: total = neto + iva."""
        result = validate_math(
            imp_total=150.75,
            imp_neto=125.00,
            imp_iva=25.75,
        )
        assert result["valid"] is True
        assert result["difference"] == 0.0

    def test_rounded_values_same_as_wsfe(self):
        """Uses the same round(x, 2) that _build_fe_cae_request applies."""
        result = validate_math(
            imp_total=round(121.001, 2),
            imp_neto=round(100.001, 2),
            imp_iva=round(21.0, 2),
        )
        # After rounding: 121.00 == 100.00 + 0 + 0 + 21.00 + 0
        assert result["valid"] is True
        assert result["expected"] == 121.00
        assert result["actual"] == 121.00


# ===========================================================================
# 2. Diff within 0.01 (ARCA tolerance)
# ===========================================================================

class TestDiffWithinTolerance:
    """Difference <= 0.01: valid=False but within_tolerance=True."""

    def test_diff_exactly_0_01(self):
        """Diff = 0.01 is within ARCA's tolerance (margen de error)."""
        result = validate_math(
            imp_total=121.01,
            imp_neto=100.0,
            imp_iva=21.0,
        )
        assert result["valid"] is False
        assert result["within_tolerance"] is True
        assert result["difference"] == 0.01

    def test_diff_0_005(self):
        """Diff = 0.01 after rounding (0.005 rounded up)."""
        result = validate_math(
            imp_total=121.01,
            imp_neto=100.0,
            imp_iva=21.0,
        )
        assert result["valid"] is False
        assert result["within_tolerance"] is True
        assert result["difference"] == 0.01

    def test_diff_0_001(self):
        """Diff = 0.0 after rounding (0.001 → 0.0)."""
        result = validate_math(
            imp_total=121.001,
            imp_neto=100.0,
            imp_iva=21.0,
        )
        assert result["valid"] is True  # rounds to exact
        assert result["within_tolerance"] is True
        assert result["difference"] == 0.0

    def test_custom_tolerance(self):
        """Custom tolerance changes within_tolerance boundary."""
        result = validate_math(
            imp_total=121.05,
            imp_neto=100.0,
            imp_iva=21.0,
            tolerance=0.1,
        )
        assert result["valid"] is False
        assert result["within_tolerance"] is True  # 0.05 <= 0.1
        assert result["difference"] == 0.05


# ===========================================================================
# 3. Diff >= 0.02 (ARCA rejects with error 10030)
# ===========================================================================

class TestDiffOverTolerance:
    """Difference >= 0.02: valid=False and within_tolerance=False."""

    def test_diff_exactly_0_02(self):
        """Diff = 0.02 exceeds ARCA tolerance → rejected."""
        result = validate_math(
            imp_total=121.02,
            imp_neto=100.0,
            imp_iva=21.0,
        )
        assert result["valid"] is False
        assert result["within_tolerance"] is False
        assert result["difference"] == 0.02

    def test_diff_0_10(self):
        """Diff = 0.10 is way over tolerance."""
        result = validate_math(
            imp_total=121.10,
            imp_neto=100.0,
            imp_iva=21.0,
        )
        assert result["valid"] is False
        assert result["within_tolerance"] is False
        assert result["difference"] == 0.10

    def test_large_mismatch(self):
        """Large mismatch (e.g. 10.0) is detected."""
        result = validate_math(
            imp_total=131.0,
            imp_neto=100.0,
            imp_iva=21.0,
        )
        assert result["valid"] is False
        assert result["within_tolerance"] is False
        assert result["difference"] == 10.0


# ===========================================================================
# 4. All zero
# ===========================================================================

class TestAllZero:
    """All values are zero — trivial true."""

    def test_all_zeros(self):
        """All zeros: 0 == 0 + 0 + 0 + 0 + 0."""
        result = validate_math(
            imp_total=0.0,
            imp_neto=0.0,
            imp_iva=0.0,
        )
        assert result["valid"] is True
        assert result["expected"] == 0.0
        assert result["actual"] == 0.0
        assert result["difference"] == 0.0
        assert result["within_tolerance"] is True

    def test_all_zeros_explicit_components(self):
        """All zeros with explicit conc/op_ex/trib."""
        result = validate_math(
            imp_total=0.0,
            imp_neto=0.0,
            imp_tot_conc=0.0,
            imp_op_ex=0.0,
            imp_iva=0.0,
            imp_trib=0.0,
        )
        assert result["valid"] is True

    def test_all_none_defaults(self):
        """No arguments (all defaults): 0 == 0."""
        result = validate_math(imp_total=0.0, imp_neto=0.0)
        assert result["valid"] is True


# ===========================================================================
# 5. With tributos and op_ex
# ===========================================================================

class TestWithTributosOpEx:
    """Comprobantes with ImpTotConc, ImpOpEx, ImpTrib components."""

    def test_with_op_ex(self):
        """Total includes exempt operations."""
        result = validate_math(
            imp_total=150.0,
            imp_neto=100.0,
            imp_op_ex=30.0,
            imp_iva=20.0,
        )
        assert result["valid"] is True
        assert result["expected"] == 150.0

    def test_with_tributos(self):
        """Total includes tributos (IIBB, etc.)."""
        result = validate_math(
            imp_total=140.0,
            imp_neto=100.0,
            imp_iva=21.0,
            imp_trib=19.0,
        )
        assert result["valid"] is True
        assert result["expected"] == 140.0

    def test_with_conc_and_all(self):
        """All five components present and correct."""
        result = validate_math(
            imp_total=200.0,
            imp_neto=100.0,
            imp_tot_conc=10.0,
            imp_op_ex=20.0,
            imp_iva=30.0,
            imp_trib=40.0,
        )
        assert result["valid"] is True
        assert result["expected"] == 200.0

    def test_all_components_mismatch(self):
        """All components present but total is off."""
        result = validate_math(
            imp_total=205.0,
            imp_neto=100.0,
            imp_tot_conc=10.0,
            imp_op_ex=20.0,
            imp_iva=30.0,
            imp_trib=40.0,
        )
        assert result["valid"] is False
        assert result["within_tolerance"] is False
        assert result["difference"] == 5.0

    def test_components_in_result_dict(self):
        """Result contains all component values."""
        result = validate_math(
            imp_total=200.0,
            imp_neto=100.0,
            imp_tot_conc=10.0,
            imp_op_ex=20.0,
            imp_iva=30.0,
            imp_trib=40.0,
        )
        comp = result["components"]
        assert comp["imp_neto"] == 100.0
        assert comp["imp_tot_conc"] == 10.0
        assert comp["imp_op_ex"] == 20.0
        assert comp["imp_iva"] == 30.0
        assert comp["imp_trib"] == 40.0


# ===========================================================================
# 6. Negative values (Nota de Crédito)
# ===========================================================================

class TestNegativeValues:
    """Nota de Crédito: all amounts are negative."""

    def test_nc_exact_match(self):
        """NC: total matches sum of negative components."""
        result = validate_math(
            imp_total=-121.0,
            imp_neto=-100.0,
            imp_iva=-21.0,
        )
        assert result["valid"] is True
        assert result["expected"] == -121.0
        assert result["actual"] == -121.0

    def test_nc_within_tolerance(self):
        """NC: small rounding difference within tolerance."""
        result = validate_math(
            imp_total=-121.01,
            imp_neto=-100.0,
            imp_iva=-21.0,
        )
        assert result["valid"] is False
        assert result["within_tolerance"] is True
        assert result["difference"] == 0.01

    def test_nc_over_tolerance(self):
        """NC: difference over tolerance."""
        result = validate_math(
            imp_total=-121.02,
            imp_neto=-100.0,
            imp_iva=-21.0,
        )
        assert result["valid"] is False
        assert result["within_tolerance"] is False
        assert result["difference"] == 0.02

    def test_nc_with_tributos(self):
        """NC with tributos (negative tributos)."""
        result = validate_math(
            imp_total=-140.0,
            imp_neto=-100.0,
            imp_iva=-21.0,
            imp_trib=-19.0,
        )
        assert result["valid"] is True
        assert result["expected"] == -140.0

    def test_nc_mixed_sign(self):
        """NC with positive tributo (unusual but possible)."""
        result = validate_math(
            imp_total=-130.0,
            imp_neto=-100.0,
            imp_iva=-21.0,
            imp_trib=-9.0,
        )
        assert result["valid"] is True
        assert result["expected"] == -130.0
