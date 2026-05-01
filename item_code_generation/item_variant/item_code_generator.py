"""
item_code_generator.item_variant.sku_generator
==============================================

Generates a variant Item's item_code by substituting {placeholder} tokens
in the template's item_code with the sku_code defined on each Item Attribute Value.

Example
-------
Template item_code : RU{size}{color}
Variant attributes : size = "XL"  (sku_code = "00XL")
                     color   = "RED" (sku_code = "00RD")
Generated SKU      : RU00XL00RD
"""

import re
import frappe
from frappe import _
import json

# Matches any {word} token in the pattern, e.g. {caliber}, {color}
_PLACEHOLDER_RE = re.compile(r"\{([^}]+)\}")

# ---------------------------------------------------------------------------
# Whitelisted API method — called from JS before save to preview the SKU
# ---------------------------------------------------------------------------

@frappe.whitelist()
def compute_sku(variant_of, attributes):
    """
    Called from the client to compute the SKU without saving anything.

    Args:
        variant_of (str): The template item_code (which is the pattern)
        attributes (list|str): JSON list of {attribute, attribute_value} dicts

    Returns:
        dict: {sku: <generated sku>} or raises on validation error
    """
    if not frappe.has_permission("Item", ptype="write"):
        frappe.throw(
            _("You do not have permission to generate Item SKUs."),
            frappe.PermissionError,
        )

    if isinstance(attributes, str):
        attributes = json.loads(attributes)

    # Build a lightweight doc-like object so we can reuse _build_attr_code_map
    mock_doc = frappe._dict({
        "attributes": [frappe._dict(row) for row in attributes]
    })

    pattern = variant_of
    placeholders = _PLACEHOLDER_RE.findall(pattern)

    if not placeholders:
        # No tokens — return the pattern as-is
        return {"sku": pattern}

    attr_code_map = _build_attr_code_map(mock_doc)
    _validate_placeholders(placeholders, attr_code_map, item_label="(preview)")

    new_sku = _PLACEHOLDER_RE.sub(lambda m: attr_code_map[m.group(1).lower()], pattern)
    return {"sku": new_sku}

def generate_variant_sku(doc, method=None):
    """
    Hook: Item.before_save

    Only runs when:
      - The Item is a variant (variant_of is set)
      - The template's item_code contains at least one {placeholder}
    """
    if doc.has_variants:
        _validate_template_placeholders(doc)

    if not doc.variant_of or not doc.is_new():
        return  # Not a variant — nothing to do

    pattern = doc.variant_of  # e.g. "RU{caliber}{color}"

    placeholders = _PLACEHOLDER_RE.findall(pattern)
    if not placeholders:
        return  # Template SKU has no {tokens} — leave item_code alone

    # Build a map of attribute_name (lowercased) → sku_code
    # from the variant's Item Attribute table
    attr_code_map = _build_attr_code_map(doc)
    _validate_placeholders(placeholders, attr_code_map, item_label=doc.item_code or "(new)")

    # Substitute each {placeholder} with its sku_code
    def replacer(match):
        return attr_code_map[match.group(1).lower()]

    new_sku = _PLACEHOLDER_RE.sub(replacer, pattern)

    # Guard: if the generated SKU already exists on a *different* item, warn loudly
    sku = frappe.db.get_value("Item", new_sku, "name")
    if sku and sku != doc.name:
        frappe.throw(
            _(
                "Generated SKU <b>{0}</b> already exists for another Item. "
                "Check the sku_code values on your attribute values."
            ).format(new_sku)
        )

    if doc.item_code != new_sku:
        frappe.msgprint(
            _("SKU generated: <b>{0}</b>").format(new_sku),
            indicator="green",
            alert=True,
        )
    # item_name mirrors item_code by default in ERPNext; keep them in sync
    # unless the user has explicitly set a different item_name
    if not doc.item_name or doc.item_name == doc.name or doc.item_name == doc.variant_of:
        doc.item_name = new_sku
    doc.item_code = new_sku

def generate_doc_name_before_insert(doc, method=None):
	if not doc.variant_of:
		return
	generate_variant_sku(doc)
    # Only rename if before_save couldn't set the name correctly
    # (i.e. bulk creation path where child tables need cascade)
	if doc.name != doc.item_code:
		doc.name = doc.item_code

def _validate_placeholders(placeholders, attr_code_map, item_label):
    """Throws a ValidationError if any placeholder has no sku_code."""
    missing = []
    for ph in placeholders:
        key = ph.lower()
        if key not in attr_code_map:
            missing.append(ph)
        elif not attr_code_map[key]:
            missing.append(f"{ph} (sku_code is blank)")

    if missing:
        frappe.throw(
            _(
                "Cannot generate SKU for variant <b>{0}</b>.<br>"
                "The following attribute placeholders have no sku_code: <b>{1}</b><br><br>"
                "Go to <i>Stock → Item Attribute</i>, open the attribute, "
                "and fill in the <b>SKU Code</b> for each value."
            ).format(item_label, ", ".join(missing))
        )


def _validate_template_placeholders(doc):
    """
    Server-side mirror of the JS validate_item_code_placeholders function.

    Throws a ValidationError if:
      - Any {placeholder} in item_code has no matching row in the Attributes table
      - Any attribute row has no matching {placeholder} in item_code
    """
    item_code = doc.item_code or ""
    placeholders = _PLACEHOLDER_RE.findall(item_code)

    defined_attrs = [
        (row.attribute or "").strip()
        for row in (doc.get("attributes") or [])
        if (row.attribute or "").strip()
    ]

    defined_attrs_lower = {a.lower() for a in defined_attrs}
    placeholders_lower = {p.lower() for p in placeholders}

    unknown = [ph for ph in placeholders if ph.lower() not in defined_attrs_lower]
    unaccounted = [attr for attr in defined_attrs if attr.lower() not in placeholders_lower]

    errors = []

    if unknown:
        errors.append(
            _(
                "Item Code contains {0} placeholder{1} not found in the Item Attributes table: <b>{2}</b>"
            ).format(
                len(unknown),
                "s" if len(unknown) > 1 else "",
                ", ".join("{" + u + "}" for u in unknown),
            )
        )

    if unaccounted:
        errors.append(
            _("Item Attribute{0} not accounted for in the Item Code: <b>{1}</b>").format(
                "s are" if len(unaccounted) > 1 else " is",
                ", ".join("{" + a + "}" for a in unaccounted),
            )
        )

    if errors:
        frappe.throw(
            "<br><br>".join(errors)
            + "<br><br>"
            + _("Fix the Item Code placeholders or update the <b>Attributes</b> tab so they match.")
        )


def _build_attr_code_map(variant_doc):
    """
    Returns {attribute_name_lower: sku_code} for every attribute on the variant.

    Looks up sku_code from the Item Attribute Value child table:
        frappe.get_value("Item Attribute Value",
                         {"parent": attribute, "attribute_value": value},
                         "sku_code")
    """
    code_map = {}

    for row in variant_doc.get("attributes") or []:
        attr_name = (row.attribute or "").strip()
        attr_value = (row.attribute_value or "").strip()
        if not attr_name or not attr_value:
            continue

        sku_code = frappe.db.get_value(
            "Item Attribute Value",
            {"parent": attr_name, "attribute_value": attr_value},
            "sku_code",
        )

        code_map[attr_name.lower()] = sku_code or ""

    return code_map

