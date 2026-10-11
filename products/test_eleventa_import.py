import io
import unittest

from .eleventa_import import (
    NO_DEPARTMENT_LABEL,
    SUCCESS_STATUS,
    apply_wholesale_options,
    parse_wholesale_options,
    parse_eleventa_file,
    parse_excluded_codes,
    parse_money,
    validate_eleventa_rows,
)

HEADER = "Codigo\tDescripcion\tPrecio Costo\tPrecio Venta\tPrecio Mayoreo\tInventario\tInv. Minimo\tDepartamento"


def make_file(*lines, encoding="cp1252"):
    return io.BytesIO("\r\n".join([HEADER, *lines]).encode(encoding))


def statuses(*lines, min_quantity=2):
    rows = apply_wholesale_options(parse_eleventa_file(make_file(*lines)), min_quantity)
    return [row["status"] for row in validate_eleventa_rows(rows)]


class ParseEleventaFileTests(unittest.TestCase):
    def test_parses_latin1_text_and_trims_values(self):
        rows = parse_eleventa_file(make_file(" A1 \t Niño $1,000 \t$10.50\t$20.00\t$0.00\t3.00\t0.000\tJUGUETES"))
        self.assertEqual(rows[0]["code"], "A1")
        self.assertEqual(rows[0]["name"], "Niño $1,000")
        self.assertEqual(rows[0]["cost"], 10.5)
        self.assertEqual(rows[0]["quantity"], 3.0)
        self.assertEqual(rows[0]["excel_row"], 2)

    def test_no_department_label_is_none(self):
        rows = parse_eleventa_file(make_file(f"A\tB\t$1.00\t$2.00\t$0.00\t1\t0\t{NO_DEPARTMENT_LABEL}"))
        self.assertIsNone(rows[0]["department"])

    def test_replacement_character_becomes_enie(self):
        raw = (HEADER + "\nA\tNi�o\t$1.00\t$2.00\t\t1\t0\tX").encode("utf-8")
        self.assertEqual(parse_eleventa_file(io.BytesIO(raw))[0]["name"], "Niño")

    def test_quotes_in_description_are_kept(self):
        rows = parse_eleventa_file(make_file('A\tTubo 12" azul\t$1.00\t$2.00\t\t1\t0\tX'))
        self.assertEqual(rows[0]["name"], 'Tubo 12" azul')

    def test_parses_comma_separated_file_with_quotes(self):
        raw = io.BytesIO(
            'Codigo,Descripcion,Precio Costo,Precio Venta,Precio Mayoreo,Inventario,Inv. Minimo,Departamento,\n'
            'A1,"Tubo 12"" azul","$1,000.00","$2,000.00",$0.00,6,0,X,\n'.encode("utf-8")
        )
        rows = parse_eleventa_file(raw)
        self.assertEqual(rows[0]["name"], 'Tubo 12" azul')
        self.assertEqual(rows[0]["cost"], 1000.0)
        self.assertEqual(rows[0]["department"], "X")

    def test_missing_required_columns(self):
        raw = io.BytesIO(b"Codigo\tDescripcion\tPrecio Costo\nA\tB\t1")
        with self.assertRaisesRegex(ValueError, "Precio Venta"):
            parse_eleventa_file(raw)

    def test_empty_file(self):
        with self.assertRaisesRegex(ValueError, "vacío"):
            parse_eleventa_file(make_file())

    def test_parse_money(self):
        self.assertEqual(parse_money("$1,234.50"), 1234.5)
        self.assertIsNone(parse_money(""))
        self.assertNotEqual(parse_money("abc"), parse_money("abc"))


class ValidateEleventaRowsTests(unittest.TestCase):
    def test_valid_row(self):
        self.assertEqual(statuses("A\tB\t$1.00\t$2.00\t$0.00\t0\t0\tX"), [SUCCESS_STATUS])

    def test_cost_zero(self):
        self.assertEqual(statuses("A\tB\t$0.00\t$2.00\t\t1\t0\tX"), ["Costo debe ser mayor a 0"])

    def test_cost_not_lower_than_price(self):
        self.assertEqual(statuses("A\tB\t$5.00\t$2.00\t\t1\t0\tX"), ["Costo debe ser menor que precio de venta"])

    def test_wholesale_price_between_cost_and_price_is_valid(self):
        self.assertEqual(statuses("A\tB\t$1.00\t$2.00\t$1.50\t1\t0\tX"), [SUCCESS_STATUS])

    def test_wholesale_price_above_price_or_below_cost(self):
        self.assertEqual(statuses("A\tB\t$1.00\t$2.00\t$3.00\t1\t0\tX"), ["Mayoreo mayor al precio de venta"])
        self.assertEqual(statuses("A\tB\t$2.00\t$4.00\t$1.00\t1\t0\tX"), ["Mayoreo menor que el costo"])

    def test_wholesale_ignored_without_min_quantity(self):
        self.assertEqual(statuses("A\tB\t$1.00\t$2.00\t$3.00\t1\t0\tX", min_quantity=None), [SUCCESS_STATUS])

    def test_duplicated_code_points_to_first_row(self):
        result = statuses("A\tB\t$1.00\t$2.00\t\t1\t0\tX", "A\tC\t$1.00\t$2.00\t\t1\t0\tX")
        self.assertEqual(result, [SUCCESS_STATUS, "Código existente en la fila 2"])

    def test_missing_code_and_name(self):
        self.assertEqual(statuses("\tB\t$1.00\t$2.00\t\t1\t0\tX"), ["Sin código"])
        self.assertEqual(statuses("A\t\t$1.00\t$2.00\t\t1\t0\tX"), ["Sin nombre"])

    def test_negative_inventory(self):
        self.assertIn("Inventario", statuses("A\tB\t$1.00\t$2.00\t\t-1\t0\tX")[0])


class ParseExcludedCodesTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(parse_excluded_codes(""), set())
        self.assertEqual(parse_excluded_codes(None), set())

    def test_list(self):
        self.assertEqual(parse_excluded_codes('["A", " B "]'), {"A", "B"})

    def test_invalid(self):
        for value in ("{", '{"a": 1}'):
            with self.assertRaises(ValueError):
                parse_excluded_codes(value)


class WholesaleOptionsTests(unittest.TestCase):
    def test_apply_with_quantity(self):
        rows = apply_wholesale_options(parse_eleventa_file(make_file(
            "A\tB\t$1.00\t$2.00\t$1.50\t1\t0\tX", "C\tD\t$1.00\t$2.00\t$0.00\t1\t0\tX")), 3)
        self.assertEqual([(r["wholesale_price"], r["min_wholesale_quantity"]) for r in rows], [(1.5, 3), (None, None)])

    def test_apply_ignoring_wholesale(self):
        rows = apply_wholesale_options(parse_eleventa_file(make_file("A\tB\t$1.00\t$2.00\t$1.50\t1\t0\tX")), None)
        self.assertEqual((rows[0]["wholesale_price"], rows[0]["min_wholesale_quantity"]), (None, None))

    def test_parse_options(self):
        self.assertEqual(parse_wholesale_options("quantity", "3"), ("quantity", 3))
        self.assertEqual(parse_wholesale_options("ignore", ""), ("ignore", None))
        for mode, quantity in (("", "3"), ("quantity", "1"), ("quantity", "abc"), ("quantity", None)):
            with self.assertRaises(ValueError):
                parse_wholesale_options(mode, quantity)
