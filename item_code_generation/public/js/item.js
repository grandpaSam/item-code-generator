/**
 * item_code_generation/public/js/item.js
 *
 * Attaches an Awesomplete autocomplete to the item_code field on the Item form.
 * When the user types "{", it fetches all Item Attributes and shows a dropdown.
 * Selecting an attribute inserts "{Attribute Name}" at the cursor position.
 */

frappe.ui.form.on("Item", {
	validate(frm) {
		if (!frm.doc.has_variants) return;
		validate_item_code_placeholders(frm);
	},

	refresh(frm) {
		// Only attach on template items (has_variants) or new items
		// We don't want this firing on every item save
		setup_item_code_autocomplete(frm);

		// If this is a new unsaved variant, show the correct SKU in the draft
		if (frm.is_new() && frm.doc.variant_of) {
			preview_sku(frm);
		}
	},

	has_variants(frm) {
		// Re-run if the user toggles the template checkbox
		setup_item_code_autocomplete(frm);
	},
});

// ---------------------------------------------------------------------------
// Calls compute_sku and updates item_code/item_name on the form
// ---------------------------------------------------------------------------
async function preview_sku(frm) {
	if (!frm.doc.variant_of) return;

	const attributes = (frm.doc.attributes || [])
		.filter((row) => row.attribute && row.attribute_value)
		.map((row) => ({
			attribute: row.attribute,
			attribute_value: row.attribute_value,
		}));

	if (!attributes.length) return;

	const r = await frappe.call({
		method: "item_code_generation.item_variant.item_code_generator.compute_sku",
		args: {
			variant_of: frm.doc.variant_of,
			attributes: JSON.stringify(attributes),
		},
	});

	if (r && r.message && r.message.sku) {
		const new_sku = r.message.sku;
		frm.set_value("item_code", new_sku);

		// Mirror item_name only if it hasn't been explicitly set to something different
		const item_name = frm.doc.item_name;
		if (!item_name || item_name === frm.doc.name || item_name === frm.doc.variant_of) {
			frm.set_value("item_name", new_sku);
		}
	}
}

// ---------------------------------------------------------------------------
// Awesomplete autocomplete for {placeholder} insertion on template items
// ---------------------------------------------------------------------------

function setup_item_code_autocomplete(frm) {
	// Only relevant for template items
	if (!frm.doc.has_variants && !frm.is_new()) return;

	// Get the underlying <input> element for the item_code field
	const $input = frm.fields_dict.item_code.$input;
	if (!$input || !$input.length) return;

	const input_el = $input[0];

	// Avoid attaching multiple instances
	if (input_el._awe_attached) return;
	input_el._awe_attached = true;

	// Initialise Awesomplete on the input
	const awe = new Awesomplete(input_el, {
		minChars: 0, // Show immediately when triggered
		maxItems: 50,
		autoFirst: true, // Pre-highlight first item so Enter works
		filter: function (text, input) {
			// Only filter against the text typed AFTER the last "{"
			const trigger_pos = input.lastIndexOf("{");
			if (trigger_pos === -1) return false;
			const partial = input.slice(trigger_pos + 1).toLowerCase();
			return text.value.toLowerCase().includes(partial);
		},
		replace: function (suggestion) {
			// Replace the partial "{..." with the full "{Attribute Name}"
			const current = input_el.value;
			const trigger_pos = current.lastIndexOf("{");
			if (trigger_pos !== -1) {
				input_el.value = current.slice(0, trigger_pos) + "{" + suggestion.value + "}";
			} else {
				input_el.value += "{" + suggestion.value + "}";
			}
			// Sync the value back to the Frappe doc
			frm.set_value("item_code", input_el.value);
			awe.close();
		},
	});

	// Cache the attribute list so we only fetch once per form load
	let attribute_list = null;

	async function get_attributes() {
		if (attribute_list) return attribute_list;
		const result = await frappe.db.get_list("Item Attribute", {
			fields: ["name"],
			limit: 100,
			order_by: "name asc",
		});
		attribute_list = result.map((r) => r.name);
		return attribute_list;
	}

	// Listen for keyup on the input
	$input.on("keyup", async function (e) {
		if (e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "Enter") {
			e.stopPropagation();
			return;
		}
		const val = input_el.value;
		const trigger_pos = val.lastIndexOf("{");

		// Only show autocomplete if there's an open "{" with no closing "}"
		const after_trigger = val.slice(trigger_pos + 1);
		const is_open = trigger_pos !== -1 && !after_trigger.includes("}");

		if (!is_open) {
			awe.close();
			return;
		}

		// Fetch attributes and update the list
		const attrs = await get_attributes();
		awe.list = attrs;

		// Open the dropdown
		awe.evaluate();
	});

	// Close the dropdown if the user clicks away
	$input.on("blur", function () {
		// Small delay so a click on a suggestion registers first
		setTimeout(() => awe.close(), 200);
	});
}


// ---------------------------------------------------------------------------
// Validates that every {placeholder} in item_code matches an attribute on the
// item's own Attributes table — catching typos and missing attribute setup
// ---------------------------------------------------------------------------

function validate_item_code_placeholders(frm) {
    const item_code = frm.doc.item_code || '';

    // Extract all {placeholder} tokens from item_code
    const placeholders = [...item_code.matchAll(/\{([^}]+)\}/g)].map(m => m[1]);

    // Build a set of attribute names from the item's own attributes table
    const defined_attrs = (frm.doc.attributes || [])
        .map(row => (row.attribute || '').trim())
        .filter(Boolean);
    const defined_attrs_lower = new Set(defined_attrs.map(a => a.toLowerCase()));
    const placeholders_lower = new Set(placeholders.map(p => p.toLowerCase()));

    // Check 1: placeholders in item_code with no matching attribute
    const unknown = placeholders.filter(ph => !defined_attrs_lower.has(ph.toLowerCase()));

    // Check 2: attributes on the item with no matching placeholder in item_code
    const unaccounted = defined_attrs.filter(attr => !placeholders_lower.has(attr.toLowerCase()));

    const errors = [];

    if (unknown.length) {
        errors.push(
            __('Item Code contains {0} placeholder{1} not found in the Item Attributes table: <b>{2}</b>',
            [
                unknown.length,
                unknown.length > 1 ? 's' : '',
                unknown.map(u => '{' + u + '}').join(', ')
            ])
        );
    }

    if (unaccounted.length) {
        errors.push(
            __('Item Attribute{0} not accounted for in the Item Code: <b>{1}</b>',
            [
                unaccounted.length > 1 ? 's are' : ' is',
                unaccounted.map(a => '{' + a + '}').join(', ')
            ])
        );
    }

    if (errors.length) {
        frappe.throw(
            errors.join('<br><br>') + '<br><br>'
            + __('Fix the Item Code placeholders or update the <b>Attributes</b> tab so they match.')
        );
    }
}
